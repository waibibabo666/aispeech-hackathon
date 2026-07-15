"""Fuzzy time expression resolver — single source of truth for all Chinese time rules.

Architecture:
  ┌─────────────────────────────────────────────────┐
  │              time_resolver.py                    │
  │                                                  │
  │  FUZZY_TIME_RULES   → resolve_fuzzy_time()      │
  │  RECURRING_PATTERNS → is_recurring()             │
  │  DURATION_PATTERNS  → resolve_duration()         │
  │                                                  │
  │  parse_chinese_datetime()  — date format parsing│
  │  infer_default_datetime()  — time-of-day fallback│
  │  expand_recurring_items()  — repeat → N tasks   │
  │                                                  │
  │  build_time_rules_prompt() → str  (for LLM)     │
  │  build_recurring_prompt()   → str  (for LLM)    │
  └─────────────────────────────────────────────────┘

To add a new fuzzy time rule, just append to FUZZY_TIME_RULES below —
the system prompt and all Python fallback logic pick it up automatically.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("time_resolver")

# ──────────────────────────────────────────────────────────────
#  Rule data — ONE place to define all patterns
# ──────────────────────────────────────────────────────────────

# (regex, hour, minute, category, description)
# Order matters: more-specific patterns MUST come first (e.g. "午饭后" before "下午")
FUZZY_TIME_RULES: list[tuple[str, int, int, str, str]] = [
    # ── Pre/post meal (most specific) ──
    (r"早饭前",      7, 30, "pre-meal",   "早饭前"),
    (r"早饭后",      9,  0, "post-meal",  "早饭后"),
    (r"午饭前",     11, 30, "pre-meal",   "午饭前"),
    (r"午饭后",     13,  0, "post-meal",  "午饭后"),
    (r"晚饭前",     17,  0, "pre-meal",   "晚饭前"),
    (r"晚饭后",     20,  0, "post-meal",  "晚饭后"),
    # ── After work/school ──
    (r"下班后",     18,  0, "after-work", "下班后"),
    (r"放学后",     17,  0, "after-work", "放学后"),
    # ── Dawn ──
    (r"凌晨",        2,  0, "dawn",       "凌晨"),
    (r"半夜",        2,  0, "dawn",       "半夜"),
    (r"深夜",        2,  0, "dawn",       "深夜"),
    # ── Early morning ──
    (r"一大早",      7,  0, "early-am",   "一大早"),
    (r"清晨",        7,  0, "early-am",   "清晨"),
    # ── Morning ──
    (r"早上",        9,  0, "morning",    "早上"),
    (r"上午",        9,  0, "morning",    "上午"),
    (r"早晨",        9,  0, "morning",    "早晨"),
    # ── Noon ──
    (r"正午",       12,  0, "noon",       "正午"),
    (r"中午",       12,  0, "noon",       "中午"),
    # ── Afternoon ──
    (r"下午",       14,  0, "afternoon",  "下午"),
    # ── Evening ──
    (r"傍晚",       18,  0, "evening",    "傍晚"),
    (r"黄昏",       18,  0, "evening",    "黄昏"),
    # ── Night (must be AFTER all more specific patterns) ──
    (r"晚上",       19,  0, "night",      "晚上"),
    (r"夜晚",       19,  0, "night",      "夜晚"),
]

# Recurring event patterns — each must NOT match single-occurrence phrases
RECURRING_PATTERNS: list[str] = [
    r"每天", r"天天",
    r"每天早上", r"每天下午", r"每天晚上",
    r"工作日每天", r"周末每天",
    r"本周每天", r"本周的每天", r"这周每天",
    r"下周每天", r"下下周每天",
    r"每隔\d+\s*天", r"每\d+\s*天",
    r"每周[一二三四五六日天]",
]

# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────

_CN_NUM: dict[str, int] = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

_CN_DIGIT = r"[一二两三四五六七八九十]"


def _parse_number(s: str) -> int:
    """Parse both Arabic and Chinese numerals: '1'→1, '一'→1, '十'→10."""
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in _CN_NUM:
        return _CN_NUM[s]
    raise ValueError(f"Cannot parse number: {s}")


# Duration patterns: (regex_with_groups, builder)
# Supports both "1小时" and "一小时", "一个半小时" and "1个半小时"
DURATION_PATTERNS: list[tuple[str, Any]] = [
    # Chinese numerals + 半小时 (e.g. "一个半小时")
    (rf"({_CN_DIGIT})\s*个?\s*半小时",
     lambda m: timedelta(hours=_parse_number(m.group(1)), minutes=30)),
    # Chinese numerals + 小时
    (rf"({_CN_DIGIT})\s*个?\s*(?:半)?\s*小时",
     lambda m: timedelta(hours=_parse_number(m.group(1)))),
    # Standalone 半小时
    (r"半小时",
     lambda _: timedelta(minutes=30)),
    # Arabic numerals + 半小时
    (r"(\d+)\s*个?\s*半小时",
     lambda m: timedelta(hours=int(m.group(1)), minutes=30)),
    # Arabic numerals + 小时
    (r"(\d+)\s*个?\s*(?:半)?\s*小时",
     lambda m: timedelta(hours=int(m.group(1)))),
    (r"(\d+)\s*分钟",
     lambda m: timedelta(minutes=int(m.group(1)))),
]


# ──────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────


def resolve_fuzzy_time(text: str) -> tuple[int, int, str] | None:
    """Try to resolve a fuzzy time-of-day phrase to (hour, minute, category).

    Returns None if no fuzzy time expression is found in the text.
    When both a specific time (e.g. "7点") and a fuzzy phrase ("下午") exist,
    the specific time takes precedence — this only fires as a fallback.
    """
    if not text:
        return None
    for pattern, hour, minute, category, _desc in FUZZY_TIME_RULES:
        if re.search(pattern, text):
            return (hour, minute, category)
    return None


def resolve_fuzzy_time_or_default(text: str, default_hour: int = 14) -> tuple[int, int, str]:
    """Like resolve_fuzzy_time but always returns a value — falls back to default_hour."""
    result = resolve_fuzzy_time(text)
    if result is not None:
        return result
    return (default_hour, 0, "default")


def resolve_duration(text: str) -> timedelta | None:
    """Extract a duration from text like '一小时', '30分钟', '一个半小时'.

    Returns None if no duration expression is found.
    """
    if not text:
        return None
    for pattern, builder in DURATION_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return builder(m)
    return None


def is_recurring(text: str) -> bool:
    """Check if text describes a recurring event (daily, weekly, etc.)."""
    if not text:
        return False
    return any(re.search(p, text) for p in RECURRING_PATTERNS)


def parse_chinese_datetime(s: str) -> datetime:
    """Parse Chinese date strings into ISO datetime.

    Handles:
    - '2026-07-14T16:00:00' (ISO)
    - '7月14日 16:00'
    - '7月14日16：00' (fullwidth colon)
    - '7月14日' (date only, defaults to 09:00)
    """
    s = s.strip()
    if "T" in s or s.count("-") >= 2:
        return datetime.fromisoformat(s)

    s = s.replace("：", ":").replace("　", " ")
    s = re.sub(r"\s+", " ", s)
    year = datetime.now().year

    m = re.match(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(\d{1,2}):(\d{2})", s)
    if m:
        month, day, hour, minute = map(int, m.groups())
        return datetime(year, month, day, hour, minute)

    m = re.match(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日", s)
    if m:
        month, day = map(int, m.groups())
        return datetime(year, month, day, 9, 0)

    raise ValueError(f"Cannot parse Chinese datetime: {s}")


def infer_default_datetime(text: str | None, default_hour: int = 14) -> datetime:
    """Create a datetime for TODAY using the fuzzy time-of-day hint in `text`.

    If text contains "下午" → 14:00, "早上" → 09:00, etc.
    If text is None or has no time hint, uses default_hour.

    This is the "last resort" for when the LLM returns a literal phrase
    like "每天下午" as the datetime field.
    """
    text = text or ""
    hour, minute, _cat = resolve_fuzzy_time_or_default(text, default_hour)
    return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)


def expand_recurring_items(items: list[dict]) -> list[dict]:
    """If items contains a single recurring task, expand it into N daily tasks.

    Only triggers when:
    - Exactly 1 item in the list
    - That item's title/notes/datetime match a recurring pattern

    Returns: original items (if 0, or >1, or not recurring), or expanded list.
    """
    if len(items) != 1:
        return items

    item = items[0]
    title = item.get("title") or item.get("event") or ""
    notes = item.get("notes") or ""
    dt_field = item.get("datetime") or item.get("date") or ""
    combined = f"{title} {notes} {dt_field}"

    if not is_recurring(combined):
        return items

    # ── Resolve base datetime ──
    dt_str = item.get("datetime") or item.get("date") or ""
    time_str = item.get("time") or ""

    base_dt = None
    if dt_str:
        try:
            base_dt = parse_chinese_datetime(f"{dt_str} {time_str}")
        except (ValueError, KeyError):
            pass

    if base_dt is None:
        base_dt = infer_default_datetime(combined)
        logger.info("Inferred base datetime %s for recurring '%s'", base_dt.isoformat(), title)

    # ── Determine date range ──
    is_this_week = bool(re.search(r"本周|这周", combined))
    is_next_week = bool(re.search(r"下周(?!每)|下下周", combined))

    if is_next_week:
        days_since_monday = base_dt.weekday()
        start = base_dt + timedelta(days=7 - days_since_monday)
    elif is_this_week and not is_recurring_annual_like(combined):
        days_since_monday = base_dt.weekday()
        start = base_dt - timedelta(days=days_since_monday)
    else:
        start = base_dt

    # Check for weekday-only constraint
    weekday_only = bool(re.search(r"工作日", combined))

    # Generate 7 days from start, skipping weekends if weekday_only
    expanded = []
    for i in range(7):
        day = start + timedelta(days=i)
        if weekday_only and day.weekday() >= 5:  # Sat=5, Sun=6
            continue
        new_item = dict(item)
        new_dt = day.replace(hour=base_dt.hour, minute=base_dt.minute)
        new_item["datetime"] = new_dt.isoformat()

        # Handle end_datetime
        if item.get("end_datetime"):
            try:
                end_dt = parse_chinese_datetime(f"{item['end_datetime']} {item.get('time', '')}")
                duration = (end_dt - base_dt) if end_dt > base_dt else timedelta(hours=1)
            except (ValueError, KeyError):
                duration = resolve_duration(combined) or timedelta(hours=1)
            new_item["end_datetime"] = (new_dt + duration).isoformat()
        expanded.append(new_item)

    logger.info(
        "Expanded recurring event '%s': 1→%d tasks", title, len(expanded),
    )
    return expanded


def is_recurring_annual_like(text: str) -> bool:
    """Check if text is just '每天/天天' without '本周/下周' qualifier.

    This avoids treating a bare '每天' as 'this week only' — instead it
    starts from today for a 7-day range.
    """
    return bool(re.search(r"每天|天天", text)) and not bool(re.search(r"本周|这周|下周", text))


# ──────────────────────────────────────────────────────────────
#  Prompt generation — auto-sync with rule data
# ──────────────────────────────────────────────────────────────


def build_time_rules_prompt() -> str:
    """Generate the 'Chinese Time Expression Rules' section for the system prompt.

    Derived automatically from FUZZY_TIME_RULES — add a rule there,
    and it appears here (and in the Python fallback) with zero extra work.
    """
    lines = [
        "## Fuzzy Time-of-Day Resolution",
        "When the text mentions a time-of-day phrase without a specific hour, resolve it as follows:",
        "",
    ]

    # Group identical (category, hour, minute) entries; emit one line per unique (h, m)
    seen = set()
    for _pattern, hour, minute, category, desc in FUZZY_TIME_RULES:
        key = (category, hour, minute)
        if key in seen:
            continue
        seen.add(key)
        time_str = f"{hour:02d}:{minute:02d}"
        # Collect all expressions for this (category, hour, minute) combo
        exprs = [d for p, h, m, c, d in FUZZY_TIME_RULES if c == category and (h, m) == (hour, minute)]
        joined = "、".join(f'"{e}"' for e in exprs)
        lines.append(f"- {joined} → {time_str}")

    lines.extend([
        "",
        "## Relative Date Rules",
        'Today\'s reference date will be provided in the user message. Use it to resolve:',
        '- "下周五": next Friday from reference date',
        '- "明天下午三点": tomorrow at 15:00',
        '- "后天上午": day after tomorrow, 09:00',
        '- "月底": last day of current month, 18:00',
        '- "下周": next week — ambiguous, use Monday of next week and confidence ≤0.65',
    ])
    return "\n".join(lines)


def build_recurring_prompt() -> str:
    """Generate the 'Recurring Events' section for the system prompt."""
    return """\
## Recurring Events — CRITICAL
When the text describes an event that repeats, you MUST expand it into ONE task per occurrence.
Each occurrence gets its own entry in the "tasks" array with a specific datetime.

Recurring patterns and how to expand them:
- "本周每天X" / "本周每天下午2点": create one task for EVERY day Mon-Sun this week
- "下周每天": create one task for each day next week (Mon-Sun)
- "每个月X号": create one task on that day this month
- "每隔X天": create tasks at X-day intervals for the next 2 weeks
- "每天" / "天天": create one task per day for the next 7 days
- "工作日每天早上": create one task per weekday (Mon-Fri) for the current week

Example:
Input: "本周每天下午2点锻炼一小时"
Output:
{"tasks": [
  {"title": "锻炼一小时", "datetime": "2026-07-13T14:00:00", "end_datetime": "2026-07-13T15:00:00", "location": null, "attendees": [], "notes": null, "confidence": 0.9},
  {"title": "锻炼一小时", "datetime": "2026-07-14T14:00:00", "end_datetime": "2026-07-14T15:00:00", "location": null, "attendees": [], "notes": null, "confidence": 0.9},
  ... one entry per day Mon-Sun
]}

Example:
Input: "下周一三五早上8点开会"
Output:
{"tasks": [
  {"title": "开会", "datetime": "<next Monday 08:00>", "end_datetime": null, "location": null, "attendees": [], "notes": null, "confidence": 0.9},
  {"title": "开会", "datetime": "<next Wednesday 08:00>", "end_datetime": null, "location": null, "attendees": [], "notes": null, "confidence": 0.9},
  {"title": "开会", "datetime": "<next Friday 08:00>", "end_datetime": null, "location": null, "attendees": [], "notes": null, "confidence": 0.9}
]}"""


def build_unparseable_items_rules() -> str:
    """Warn about phrases that should NOT produce tasks."""
    return '\n'.join([
        '## Non-Actionable Phrases',
        'The following phrases should NOT produce tasks:',
        '- "到时候再说" / "再说吧"',
        '- "改天" / "下次" / "有空"',
        '- "再说" / "看情况" / "不确定"',
        '- "结束" / "开始" / "休息" / "合影" — only skip when they appear as PURE standalone labels (no time-slot context). When they appear as a row in a schedule table with a specific time (e.g. "20:00 合影&休息"), DO extract them as tasks.',
    ])
