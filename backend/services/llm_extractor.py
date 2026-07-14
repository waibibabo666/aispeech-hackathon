"""LLM-based task extractor — the core AI component.

Takes raw text and returns structured Task objects via GPT-4o with
Structured Outputs (JSON schema). Handles Chinese time expressions,
confidence scoring, and few-shot prompting.
"""

import json
import uuid
from datetime import datetime

from openai import AsyncOpenAI

from ..config import settings
from ..models.task import Task, TaskStatus

SYSTEM_PROMPT = """\
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
- end_datetime (ISO 8601 string or null): End time if mentioned or inferable
- location (string or null): Meeting place or venue
- attendees (string array): People involved
- notes (string or null): Additional context
- confidence (number 0-1): How certain the extraction is

## Chinese Time Expression Rules
Today's reference date will be provided in the user message. Use it to resolve:
- "下周五": next Friday from reference date
- "明天下午三点": tomorrow at 15:00
- "后天上午": day after tomorrow, 09:00
- "月底": last day of current month, 18:00
- "下周": next week — ambiguous, use Monday of next week and confidence ≤0.65
- "晚上": 19:00 (if no specific time)
- "下午": 14:00 (if no specific time)
- "上午": 09:00 (if no specific time)
- "中午": 12:00
- "到时候再说" / "再说吧": not actionable → do NOT extract as a task

## Confidence Scoring
- 0.90-1.00: Time, location, and event are all explicitly stated
- 0.70-0.89: Event is clear but time or location has some ambiguity (e.g., "下周", "到时候")
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
- Time mentions that multiple people acknowledge
- "好的", "OK", "没问题" after a time proposal = confirmed
- Extract the AGREED time, not every mention of a possible time

## Important
- Always output valid JSON matching the schema exactly
- If no actionable events are found, return {"tasks": []}
- Do not hallucinate details not present in the text
- If a time is a range (e.g., "3点到5点"), set datetime=start, end_datetime=end
"""


def _build_user_prompt(text: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d (%A)")
    return (
        f"Reference date (today): {today}\n\n"
        f"Extract all schedule/task information from the following text:\n\n"
        f"---\n{text}\n---"
    )


# JSON Schema for Structured Outputs
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
                            "end_datetime": {
                                "type": ["string", "null"],
                                "description": "ISO 8601 datetime or null",
                            },
                            "location": {"type": ["string", "null"]},
                            "attendees": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "notes": {"type": ["string", "null"]},
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                        },
                        "required": [
                            "title",
                            "datetime",
                            "end_datetime",
                            "location",
                            "attendees",
                            "notes",
                            "confidence",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["tasks"],
            "additionalProperties": False,
        },
    },
}


async def extract_tasks(
    text: str,
    source: str,
    client: AsyncOpenAI | None = None,
) -> list[Task]:
    """Extract structured tasks from raw text using GPT-4o.

    Args:
        text: Raw text to extract tasks from.
        source: Identifier for the source (filename or "manual-input").
        client: Optional OpenAI client. If None, creates one from settings.

    Returns:
        List of Task objects with confidence scores.
    """
    if client is None:
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )

    response = await client.chat.completions.create(
        model=settings.MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(text)},
        ],
        response_format=TASK_SCHEMA,
        temperature=0.1,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content
    if raw is None:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    tasks = []
    for item in data.get("tasks", []):
        try:
            dt = datetime.fromisoformat(item["datetime"])
        except (ValueError, KeyError):
            continue

        end_dt = None
        if item.get("end_datetime"):
            try:
                end_dt = datetime.fromisoformat(item["end_datetime"])
            except ValueError:
                pass

        task = Task(
            id=str(uuid.uuid4()),
            title=item["title"],
            datetime=dt,
            end_datetime=end_dt,
            location=item.get("location"),
            attendees=item.get("attendees", []),
            notes=item.get("notes"),
            confidence=item.get("confidence", 0.5),
            source=source,
            status=TaskStatus.PENDING,  # router sets final status
        )
        tasks.append(task)

    return tasks
