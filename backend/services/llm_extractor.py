"""LLM-based task extractor — the core AI component.

Architecture:
  ┌─────────────────────────────────────────────┐
  │  Shared Pipeline (model-agnostic)           │
  │  - System prompt (auto-synced from resolver)│
  │  - _parse_llm_json() — robust JSON decode   │
  │  - _map_fields() — flexible field mapping   │
  ├─────────────────────────────────────────────┤
  │  Model Profile (model-specific)             │
  │  - max_tokens, temperature                  │
  │  - response_format support                  │
  │  - Auto-detected from model name            │
  ├─────────────────────────────────────────────┤
  │  time_resolver.py (shared with LLM)         │
  │  - Fuzzy time → concrete hour/minute        │
  │  - Recurring pattern detection + expansion  │
  │  - Duration extraction                      │
  │  - Single source of truth for all time rules│
  └─────────────────────────────────────────────┘

New time rules are added in time_resolver.py — system prompt and Python
fallback pick them up automatically.
"""

import json
import logging
import re
import uuid
import asyncio as _asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from openai import AsyncOpenAI

from ..models.task import Task, TaskStatus, TaskKind
from .runtime_config import runtime_config
from .time_resolver import (
    resolve_fuzzy_time,
    resolve_fuzzy_time_or_default,
    resolve_duration,
    is_recurring,
    parse_chinese_datetime,
    infer_default_datetime,
    expand_recurring_items,
    build_time_rules_prompt,
    build_recurring_prompt,
    build_unparseable_items_rules,
)
from .context_hints import (
    lookup_task_type,
    resolve_fuzzy_range,
    extract_attendees_from_text,
    build_context_prompt,
)
from .lang import normalize as normalize_slang, build_prompt as build_slang_prompt
from .conversation_memory import memory as conversation_memory

logger = logging.getLogger("llm_extractor")


async def _retry_api_call(fn, description: str, max_retries: int = 3) -> Any:
    """Execute an async callable with retries on connection errors.

    Usage:
        raw = await _retry_api_call(
            lambda: _do_api_call(client, kwargs),
            "任务提取"
        )

    Retries up to max_retries times with exponential backoff.
    After max_retries exhausted, the last error is raised as RuntimeError.
    """
    import traceback
    import socket
    import sys as _sys

    def _unwrap_chain(e: BaseException) -> str:
        """Walk __cause__ chain to find the root error."""
        parts = []
        current: BaseException | None = e
        while current is not None:
            parts.append(f"{type(current).__name__}: {current}")
            current = current.__cause__
        return " ← ".join(parts)

    # ── One-time connection diagnostic on first failure ──
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            chain = _unwrap_chain(e)

            # On first failure, dump connection diagnostics to server log
            if attempt == 1:
                try:
                    loop = _asyncio.get_running_loop()
                    logger.warning("DIAGNOSTIC: event_loop=%s platform=%s",
                                   type(loop).__name__, _sys.platform)
                    addrs = socket.getaddrinfo("apifusion.aispeech.com.cn", 443,
                                               socket.AF_INET, socket.SOCK_STREAM)
                    logger.warning("DIAGNOSTIC: DNS resolved to %s", addrs[0][4] if addrs else "NONE")
                except Exception as diag_e:
                    logger.warning("DIAGNOSTIC: DNS/loop check failed: %s", diag_e)

            if attempt < max_retries:
                delay = 1.5 * attempt
                logger.warning(
                    "%s retry %d/%d after %.1fs | chain: %s",
                    description, attempt, max_retries, delay, chain,
                )
                await _asyncio.sleep(delay)
            else:
                logger.error(
                    "%s FAILED after %d attempts | chain: %s",
                    description, max_retries, chain,
                )
    raise RuntimeError(
        f"{description}失败（已重试{max_retries}次）。请检查网络连接和API配置: {_unwrap_chain(last_error)}"
    ) from last_error

# ──────────────────────────────────────────────────────────────
#  Model Profiles — the ONLY place model differences live
# ──────────────────────────────────────────────────────────────


@dataclass
class ModelProfile:
    """Tunable params that differ across LLM providers / model families."""

    max_tokens: int = 4096        # total completion tokens (includes reasoning)
    temperature: float | None = 0.1  # None = omit (reasoning models reject it)
    use_response_format: bool = True  # Structured Outputs / JSON mode


# Auto-detection: match model name (case-insensitive) → profile
MODEL_PRESETS: dict[str, ModelProfile] = {
    # ── Reasoning models (burn tokens on internal thinking) ──
    "deepseek-v4-pro-max": ModelProfile(max_tokens=16384, temperature=None, use_response_format=False),
    "deepseek-reasoner":   ModelProfile(max_tokens=16384, temperature=None, use_response_format=False),
    "o1":                  ModelProfile(max_tokens=16384, temperature=None, use_response_format=False),
    "o3":                  ModelProfile(max_tokens=16384, temperature=None, use_response_format=False),

    # ── Standard chat models (Structured Outputs + low temperature works well) ──
    "deepseek-chat":       ModelProfile(max_tokens=8192, temperature=0.1, use_response_format=False),
    "gpt-4o":              ModelProfile(max_tokens=4096, temperature=0.1, use_response_format=True),
    "gpt-4":               ModelProfile(max_tokens=4096, temperature=0.1, use_response_format=True),
    "gpt-3.5":             ModelProfile(max_tokens=4096, temperature=0.1, use_response_format=True),
    "qwen":                ModelProfile(max_tokens=4096, temperature=0.1, use_response_format=False),
    "glm":                 ModelProfile(max_tokens=4096, temperature=0.1, use_response_format=False),
    "claude":              ModelProfile(max_tokens=8192, temperature=0.1, use_response_format=False),
}

# Default for unknown models — conservative, works everywhere
DEFAULT_PROFILE = ModelProfile(max_tokens=8192, temperature=None, use_response_format=False)


def _detect_profile(model_name: str) -> ModelProfile:
    """Match model name against presets, fall back to default."""
    name_lower = model_name.lower()
    for key, profile in MODEL_PRESETS.items():
        if key in name_lower:
            return profile
    return DEFAULT_PROFILE


# ──────────────────────────────────────────────────────────────
#  Shared pipeline — JSON parsing + field mapping only
#  (time logic lives in time_resolver.py)
# ──────────────────────────────────────────────────────────────


def _parse_llm_json(raw: str) -> Any | None:
    """Extract JSON from LLM output — handles markdown, stray text, arrays."""
    if raw is None:
        return None
    # Fast path
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # ```json ... ``` blocks
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # First { } or [ ] pair
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\[[\s\S]*\]", raw)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def map_item_to_task(item: dict, source: str, context_text: str = "") -> Task | None:
    """Convert a single JSON item (dict) into a Task, handling varied field names.

    Uses context_hints for domain-specific defaults (约会→18:00, 跑步→07:00, etc.)
    and attendee extraction.
    """
    if not isinstance(item, dict):
        return None

    # ── title ──
    title = (
        item.get("title") or item.get("event") or item.get("name") or
        item.get("事项") or item.get("事件") or ""
    )
    if not title:
        return None

    # Skip pure schedule-marker words that aren't actual tasks.
    # Only match EXACT title, not partial (e.g. "合影&休息" is valid, "休息" alone is not).
    _MARKER_WORDS = {"结束", "开始", "开幕式", "闭幕式", "时刻表", "日程表",
                     "赛程表", "安排", "流程", "休息", "备注", "注意"}
    if title.strip() in _MARKER_WORDS:
        return None

    # Build combined context text for hint lookups
    notes = item.get("notes") or item.get("备注") or item.get("description")
    full_context = f"{title} {notes or ''} {context_text}"

    # ── datetime ──
    dt_str = item.get("datetime") or item.get("date")
    time_str = item.get("time") or ""
    if dt_str and time_str and "T" not in dt_str:
        dt_str = f"{dt_str} {time_str}"
    if not dt_str:
        return None
    try:
        dt = parse_chinese_datetime(dt_str)
    except (ValueError, KeyError):
        # LLM may return a literal phrase like "每天下午" — infer from time_resolver
        dt = infer_default_datetime(full_context)
        logger.warning("Unparseable datetime '%s', inferred %s", dt_str, dt.isoformat())

    # If the time component is midnight (00:00:00), the LLM had no time-of-day info.
    # Use context_hints to pick a sensible default for this task type.
    if dt.hour == 0 and dt.minute == 0:
        hints = lookup_task_type(full_context)
        default_hour = hints.get("default_hour", 14)
        default_minute = hints.get("default_minute", 0)
        hour, minute, _cat = resolve_fuzzy_time_or_default(full_context, default_hour=default_hour)
        dt = dt.replace(hour=hour, minute=minute)

    # ── end_datetime ──
    # Resolve kind-aware: only events get a duration; deadlines/milestones are point-in-time.
    hints = lookup_task_type(full_context)
    task_kind_str = hints.get("kind", "event")
    task_kind = TaskKind(task_kind_str) if task_kind_str in ("event", "deadline", "milestone") else TaskKind.EVENT

    end_dt = None
    end_dt_str = item.get("end_datetime")
    if end_dt_str:
        try:
            end_dt = datetime.fromisoformat(end_dt_str)
        except ValueError:
            try:
                end_dt = parse_chinese_datetime(end_dt_str)
            except (ValueError, KeyError):
                pass

    if task_kind == TaskKind.EVENT:
        typical = hints.get("typical_duration")
        if end_dt is not None and typical is not None:
            actual_duration = end_dt - dt
            # Multi-hour activities (开发/比赛/培训/旅行) can legitimately span
            # many hours — only clamp short task-types that got stretched by LLM.
            marathon_keywords = ["设计", "开发", "比赛", "旅行", "旅游", "出差",
                               "培训", "讲座", "搬家", "考试", "笔试", "上课"]
            is_marathon = any(kw in title for kw in marathon_keywords)
            max_reasonable = typical * 24 if is_marathon else typical * 4
            if actual_duration > max_reasonable:
                logger.warning(
                    "Clamping end time for '%s': LLM returned %s but typical is %s",
                    title, actual_duration, typical,
                )
                end_dt = dt + typical
        elif end_dt is None and typical is not None:
            end_dt = dt + typical
    else:
        # Deadline / milestone: force no end time (point-in-time)
        end_dt = None

    # ── attendees ──
    attendees = item.get("attendees") or []
    person = item.get("person") or item.get("负责人") or item.get("person_name")
    if person and isinstance(person, str):
        attendees = [p.strip() for p in re.split(r"[、，,]", person) if p.strip()]
    if not isinstance(attendees, list):
        attendees = []

    # Extract implied attendees from text (e.g. "和产品团队碰一下" → ["产品团队"])
    extracted = extract_attendees_from_text(full_context)
    for name in extracted:
        # Strip connector prefix that may have been captured
        name = re.sub(r'^(?:和|跟|与|叫上?|约)\s*', '', name)
        if name and name not in attendees:
            attendees.append(name)

    # ── location ──
    location = (
        item.get("location") or item.get("地点") or
        item.get("place") or item.get("venue")
    )

    # ── confidence ──
    confidence = item.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5
    # Boost confidence when we have strong contextual hints
    if hints.get("category") and hints.get("default_hour") is not None:
        confidence = min(confidence + 0.05, 1.0)

    return Task(
        id=str(uuid.uuid4()),
        title=title,
        datetime=dt,
        end_datetime=end_dt,
        kind=task_kind,
        category=hints.get("category"),
        location=location,
        attendees=attendees,
        notes=notes,
        confidence=confidence,
        source=source,
        status=TaskStatus.PENDING,
    )


def _extract_items(data: Any) -> list[dict]:
    """Normalize parsed JSON into a list of item dicts."""
    if isinstance(data, list):
        return [it for it in data if isinstance(it, dict)]
    if isinstance(data, dict):
        for key in ("tasks", "events", "schedule", "items"):
            val = data.get(key)
            if isinstance(val, list):
                return [it for it in val if isinstance(it, dict)]
        # Single task object → wrap in list
        if "title" in data or "event" in data:
            return [data]
    return []


# ──────────────────────────────────────────────────────────────
#  System prompt — time rules auto-generated from time_resolver.py
# ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_BASE = """\
You are a personal schedule extraction assistant. Extract all tasks, events, and \
schedule information from the provided text. Output structured JSON.

The input text may come from:
- Chat records / messaging conversations
- Meeting notes or agendas
- Voice transcripts
- Poster or flyer text
- Documents and notifications

## Output Format
Return a JSON object with a "tasks" array. Each task has these fields:
- title (string): Short, descriptive task name
- datetime (ISO 8601 string): Start date/time. Always infer a specific datetime.
- end_datetime (ISO 8601 string or null): End time if mentioned or inferable (ONLY for "event" kind)
- kind (string): REQUIRED — "event", "deadline", or "milestone"
  * "event": tasks that TAKE TIME (meetings, meals, movies, sports, travel, chores)
  * "deadline": tasks that must be FINISHED BY a point (payments, submissions, project DDL)
  * "milestone": annual recurring dates you just REMEMBER (birthdays, holidays, anniversaries)
- location (string or null): Meeting place or venue
- attendees (string array): People involved
- notes (string or null): Additional context
- confidence (number 0-1): How certain the extraction is
"""

# Assemble full system prompt from time_resolver-generated sections
SYSTEM_PROMPT = (
    _SYSTEM_PROMPT_BASE
    + "\n\n"
    + build_time_rules_prompt()
    + "\n\n"
    + build_recurring_prompt()
    + "\n\n"
    + build_context_prompt()
    + "\n\n"
    + build_unparseable_items_rules()
    + "\n\n"
    + """\
## Confidence Scoring
- 0.90-1.00: Time, location, and event are all explicitly stated
- 0.70-0.89: Event is clear but time or location has some ambiguity (e.g., "下周")
- 0.50-0.69: Can only infer a vague intent, significant ambiguity
- Below 0.50: Not actionable enough — do NOT include in output

## Few-Shot Examples

### Example 1 (High confidence):
Input: "周五下午三点在3楼会议室和产品团队开Q3规划会"
Output:
{"tasks": [{"title": "Q3规划会", "datetime": "<next Friday 15:00>", "end_datetime": null, \
"location": "3楼会议室", "attendees": ["产品团队"], "notes": null, "confidence": 0.95}]}

### Example 2 (Medium confidence):
Input: "下周找个时间大家一起吃个饭"
Output:
{"tasks": [{"title": "团队聚餐", "datetime": "<next Monday 18:00>", "end_datetime": null, \
"location": null, "attendees": [], "notes": "具体时间待定", "confidence": 0.60}]}

### Example 3 (Low confidence / no output):
Input: "到时候再说吧"
Output:
{"tasks": []}

## Chat Record Handling
When the input is a chat conversation, look for:
- One person proposing a time and another agreeing
- "好的", "OK", "没问题" after a time proposal = confirmed
- Extract the AGREED time, not every mention of a possible time

## Important
- Always output valid JSON matching the schema exactly
- If no actionable events are found, return {"tasks": []}
- Do not hallucinate details not present in the text
- If a time is a range (e.g., "3点到5点"), set datetime=start, end_datetime=end
- **Implicit end time from next event**: When text lists a sequence like "晚餐6点，6:30比赛", \
the first event's end_datetime should be the second event's start time. \
ONLY chain when the two events are clearly adjacent in the schedule (within 2 hours). \
Do NOT apply this to meals (早餐/午餐/晚饭/晚餐/吃饭) — use their typical duration instead. \
If the next event is many hours away or on a different day, use a reasonable default duration. \
An explicit duration or range in the text always takes priority.
"""
)

# JSON Schema for Structured Outputs (only used when profile.use_response_format=True)
TASK_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "task_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "datetime": {"type": "string", "description": "ISO 8601 datetime"},
                            "end_datetime": {"type": ["string", "null"], "description": "ISO 8601 datetime or null"},
                            "location": {"type": ["string", "null"]},
                            "attendees": {"type": "array", "items": {"type": "string"}},
                            "notes": {"type": ["string", "null"]},
                            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        },
                        "required": ["title", "datetime", "end_datetime", "location", "attendees", "notes", "confidence"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["tasks"],
            "additionalProperties": False,
        },
    },
}


def _build_user_prompt(text: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d (%A)")
    return (
        f"Reference date (today): {today}\n\n"
        f"Extract all schedule/task information from the following text:\n\n"
        f"---\n{text}\n---"
    )


# ──────────────────────────────────────────────────────────────
#  Shared OpenAI client factory
# ──────────────────────────────────────────────────────────────


def _build_client() -> AsyncOpenAI:
    """Create an AsyncOpenAI client with explicit no-proxy and verify settings.

    Uses an explicit httpx client to avoid Windows system proxy auto-detection
    and SSL issues that can occur inside pywebview threads.
    """
    import certifi
    http_client = httpx.AsyncClient(
        proxy=None,           # explicitly bypass any system proxy
        verify=certifi.where(),  # explicit CA bundle — more reliable on Windows
        trust_env=False,       # ignore HTTP_PROXY/HTTPS_PROXY/NO_PROXY env vars
        timeout=httpx.Timeout(60.0, connect=15.0),
    )
    logger.debug("Built OpenAI client: base_url=%s model=%s", runtime_config.llm_base_url, runtime_config.llm_model_name)
    return AsyncOpenAI(
        api_key=runtime_config.llm_api_key,
        base_url=runtime_config.llm_base_url,
        http_client=http_client,
    )


# ──────────────────────────────────────────────────────────────
#  Main entry point
# ──────────────────────────────────────────────────────────────


async def extract_tasks(
    text: str,
    source: str,
    client: AsyncOpenAI | None = None,
) -> list[Task]:
    """Extract structured tasks from raw text using the configured LLM.

    Profile is auto-detected from the model name — no manual config needed.
    """
    if client is None:
        client = _build_client()

    model = runtime_config.llm_model_name
    profile = _detect_profile(model)

    logger.info(
        "Extracting tasks with model=%s profile: max_tokens=%d temp=%s structured=%s",
        model, profile.max_tokens, profile.temperature, profile.use_response_format,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(text)},
    ]

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": profile.max_tokens,
    }
    if profile.temperature is not None:
        kwargs["temperature"] = profile.temperature

    raw: str | None = None

    # ── Attempt 1: Structured Outputs (if model supports it) ──
    if profile.use_response_format:
        try:
            resp = await client.chat.completions.create(**kwargs, response_format=TASK_SCHEMA)
            raw = resp.choices[0].message.content
        except Exception:
            raw = None

    # ── Attempt 2: Plain chat with retries ──
    if not raw:
        async def _extract_call():
            resp = await client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content

        raw = await _retry_api_call(_extract_call, "任务提取")

    if not raw:
        logger.warning("LLM returned empty response for model=%s", model)
        return []

    # ── Parse ──
    data = _parse_llm_json(raw)
    if data is None:
        logger.warning("Failed to parse LLM response as JSON: %s", raw[:500])
        return []

    items = _extract_items(data)

    # ── Post-process: expand recurring patterns ──
    items = expand_recurring_items(items)

    tasks = []
    for item in items:
        task = map_item_to_task(item, source, text)
        if task:
            tasks.append(task)

    logger.info("Extracted %d tasks from %d chars (model=%s)", len(tasks), len(text), model)
    return tasks


# ──────────────────────────────────────────────────────────────
#  Task deletion by natural language intent
# ──────────────────────────────────────────────────────────────

DELETE_INTENT_SYSTEM_PROMPT = """\
You are a precise task matching assistant. Given a list of existing tasks, TODAY's date, \
and a user's deletion intent, determine which tasks the user wants to delete.

## Date Range Resolution
TODAY's date is provided in the user message. Use it to resolve relative expressions:
- "今天": TODAY's date
- "明天": tomorrow = TODAY + 1 day
- "后天": day after tomorrow = TODAY + 2 days
- "本周": Monday through Sunday of the week containing TODAY
- "下周": Monday through Sunday of the week after TODAY
- "本月": all days in the same month as TODAY
- Specific dates like "7月16号": July 16 of the current year

## Matching Rules
- Match by title (fuzzy), date, time, or any combination.
- If the user says "删除所有晚餐", match ALL tasks whose title contains "晚餐" regardless of date.
- If the user says "删除本周所有任务", match ALL tasks whose date falls within the current week.
- If the user says "删除明天的早餐", match tasks with title "早餐" on tomorrow's date.
- If the user says "删除7月16号的", match ALL tasks on that date.
- If the user says "取消Q3规划会", match by title (fuzzy).
- If the intent is ambiguous or no tasks match, return an empty deleted_ids array.
- Be conservative: when uncertain, do NOT delete.

## Output Format
Return ONLY a JSON object:
{"deleted_ids": ["id1", "id2", ...], "summary": "brief Chinese description"},
If no tasks match, return {"deleted_ids": [], "summary": "未找到匹配的任务"}.
"""


async def match_tasks_to_delete(
    user_intent: str,
    all_tasks: list[dict],
    client: AsyncOpenAI | None = None,
) -> tuple[list[str], str]:
    """Use LLM to match a deletion intent against the current task list.

    Args:
        user_intent: User's natural language deletion request (e.g. "删除所有晚餐").
        all_tasks: List of dicts with {id, title, datetime, location, notes}.
        client: Optional OpenAI client.

    Returns:
        (deleted_ids, summary) — list of task IDs to delete, and a human-readable summary.
    """
    if client is None:
        client = _build_client()

    model = runtime_config.llm_model_name

    # Build a compact task listing for the LLM
    task_lines = []
    for t in all_tasks:
        dt = t.get("datetime", "")
        loc = f" @{t['location']}" if t.get("location") else ""
        notes = f" ({t['notes']})" if t.get("notes") else ""
        task_lines.append(
            f'  [{t["id"]}] {dt} | {t["title"]}{loc}{notes}'
        )

    tasks_text = "\n".join(task_lines)
    today = datetime.now().strftime("%Y-%m-%d (%A)")

    user_prompt = (
        f"TODAY is {today}.\n\n"
        f"Existing tasks ({len(task_lines)} total):\n{tasks_text}\n\n"
        f"User wants to: {user_intent}\n\n"
        f"Return JSON with deleted_ids and a Chinese summary."
    )

    async def _delete_call():
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": DELETE_INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2048,
        )
        return response.choices[0].message.content

    raw = await _retry_api_call(_delete_call, "任务删除匹配")

    if not raw:
        return [], "LLM returned empty response"

    import json as _json
    data = _parse_llm_json(raw)
    if data is None:
        logger.warning("Failed to parse delete intent response: %s", raw[:300])
        return [], "无法解析删除指令"

    if isinstance(data, list):
        # LLM might return a raw list of IDs
        return data, f"已删除 {len(data)} 个任务"

    ids = data.get("deleted_ids", [])
    summary = data.get("summary", f"已删除 {len(ids)} 个任务")
    return ids, summary


# ──────────────────────────────────────────────────────────────
#  Unified intent router — ONE LLM call, any action
# ──────────────────────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """\
You are a task management assistant. Given user input and the current task list, \
determine what the user wants and return structured JSON.

## Available Actions
Choose EXACTLY ONE action per user message:

1. **extract** — The user wants to ADD/CREATE new items, OR MODIFY existing ones.
   - For pure CREATE: "安排", "加上", "记一下", "我要", "准备"
   - For MODIFY: "改到/改成/改一下/调整" — find the old task ID, put it in deleted_ids
   - MODIFY PATTERN: "跑步改到明天8点" → deleted_ids=["<old-跑步-id>"] + tasks=[{"title":"跑步","datetime":"2026-07-17T08:00",...}]
   - MODIFY PATTERN: "把开会改到下午3点" → delete old 开会 + create new 开会 at 15:00
   - MODIFY PATTERN: "晚餐改成7点" → delete old 晚餐 + create new 晚餐 at 19:00
   - MODIFY PATTERN: "把开会地点改到5楼" → delete old + create new with location="5楼"
   - KEY RULE for modify: return BOTH deleted_ids AND tasks — we delete the old, create the new.
   - DO NOT use extract just because the text mentions event nouns if the only verb is cancel.
   - COUNTER-EXAMPLE: "不吃了" → action: "delete" (pure cancel, nothing new)

2. **delete** — The user wants to DELETE/CANCEL/REMOVE tasks with NO new plan.

3. **chat** — Conversation, question, or other actions listed below.
   - "你好" / "今天有哪些任务" → chat (reply helpfully)
   - "恢复/撤销/还原/undo/找回来 刚才删的" → action: "undo"
   - "刚删错了" / "不小心删了" / "误删了" → action: "undo"

4. **undo** — User wants to RECOVER recently deleted tasks.
   - Return action="undo" with an empty reply — the system will restore automatically.
   - Example: "恢复刚才删的" → action: "undo"
   - Example: "撤销删除" → action: "undo"
   - Example: "刚删错了" → action: "undo"
   - Example: "把那几个找回来" → action: "undo"

## Date Context
TODAY's date and the current WEEK range are provided in the user message.
Use them to resolve "本周", "今天", "明天", "后天", "这几天" etc.

## Time Default
If no specific time is mentioned (e.g. "明天约会" without "下午三点"), \
use 14:00 (2pm) as the default start time. NEVER use midnight (00:00) unless \
the text explicitly mentions early morning / midnight terms.

## Delete Matching Rules
When user says "推掉这几天的事" / "取消这几天的" / "这几天的不做了":
- "这几天" = today ± a few days ≈ tasks whose date is within 3 days of today
- Match ALL existing tasks in that window, regardless of title
- Include ALL matched task IDs in deleted_ids

## Output Format — MUST be valid JSON
For **extract**:
{"action": "extract", "tasks": [{"title":"...", "datetime":"ISO", "end_datetime":null, \
"location":null, "attendees":[], "notes":null, "confidence":0.9, "kind":"event"}], \
"deleted_ids": ["id1", "id2"]}

- "tasks": extracted schedule items (may be empty if no new plans found)
- "kind": REQUIRED for each task — "event" (has duration), "deadline" (must finish by), or "milestone" (annual date, just remember)
  * "event": meetings, meals, movies, sports, travel, chores — anything that takes TIME
  * "deadline": payments (还款/交费/续费), project DDL, submissions (提交/截止) — single point, must finish BEFORE
  * "milestone": birthdays, anniversaries, holidays (春节/中秋/圣诞), 纪念日 — annual recurring point
- "deleted_ids": ALWAYS include this field — list task IDs the user wants to remove. \
Empty array [] if no delete intent.

For **delete**:
{"action": "delete", "deleted_ids": ["id1","id2"], "summary": "Chinese description"}

For **chat**:
{"action": "chat", "reply": "helpful response in Chinese"}

For **undo**:
{"action": "undo", "reply": ""}
"""

INTENT_SYSTEM_PROMPT += "\n\n" + build_context_prompt() + "\n\n" + build_slang_prompt()
async def dispatch_intent(
    user_text: str,
    current_tasks: list[dict] | None = None,
    client: AsyncOpenAI | None = None,
) -> dict:
    """Unified intent router — classify AND execute in one LLM call.

    Args:
        user_text: Raw user input (could be extract, delete, or chat).
        current_tasks: Current task list [{id, title, datetime, location, notes}].
                       Needed for delete intent matching.

    Returns:
        dict with "action" key, plus action-specific fields.
    """
    if client is None:
        client = _build_client()

    # Normalize colloquial Chinese BEFORE LLM sees it
    # "把事儿推了" → "把事取消" etc.
    normalized_text = normalize_slang(user_text)
    if normalized_text != user_text:
        logger.info("Normalized: '%s' → '%s'", user_text, normalized_text)

    model = runtime_config.llm_model_name
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d (%A)")
    # Calculate this week's range
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_str = f"{monday.strftime('%Y-%m-%d')} ~ {sunday.strftime('%Y-%m-%d')}"

    # Build task context
    task_context = ""
    if current_tasks:
        lines = []
        for t in current_tasks:
            dt = t.get("datetime", "")[:16]
            loc = f" @{t['location']}" if t.get("location") else ""
            notes = f" ({t['notes']})" if t.get("notes") else ""
            lines.append(f'  [{t["id"]}] {dt} | {t["title"]}{loc}{notes}')
        task_context = f"Current tasks ({len(lines)} total):\n" + "\n".join(lines) + "\n\n"
    else:
        task_context = "No existing tasks.\n\n"

    # Resolve fuzzy range hints for delete matching (use normalized text)
    range_days = resolve_fuzzy_range(normalized_text)
    range_hint = ""
    if range_days:
        range_hint = f"FUZZY RANGE HINT: \"这几天\"/\"最近\" etc → within {range_days} days of TODAY.\n"

    # Conversation memory for pronoun resolution
    context_block = conversation_memory.to_prompt()

    user_prompt = (
        f"TODAY: {today_str}\n"
        f"THIS WEEK: {week_str}\n\n"
        f"{context_block}\n"
        f"{range_hint}"
        f"{task_context}"
        f"User said: {normalized_text}\n\n"
        f"Determine the action and return the appropriate JSON."
    )

    async def _dispatch_call():
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content

    raw = await _retry_api_call(_dispatch_call, "意图识别")

    if not raw:
        return {"action": "chat", "reply": "抱歉，无法处理你的请求"}

    data = _parse_llm_json(raw)
    if data is None:
        logger.warning("Failed to parse intent response: %s", raw[:300])
        return {"action": "chat", "reply": "抱歉，我没理解你的意思"}

    return data
