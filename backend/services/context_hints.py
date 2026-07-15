"""Context hints — lightweight domain knowledge for task enrichment.

Supplements LLM output with sensible defaults based on Chinese keyword patterns.
Not RAG, not vector search — ~35 keyword rules in a single file.
The LLM prompt auto-generates from the same rule data (like time_resolver.py).

Pipeline:
  User input → LLM (with context hints in prompt) → JSON
  → map_item_to_task() → context hints post-processing
  → Task objects
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

# ──────────────────────────────────────────────────────────────
#  Task type → default properties
#  (keyword, (default_hour, default_minute), category, typical_duration, kind)
#  kind ∈ {"event", "deadline", "milestone"}
#  None for hour = don't override (depends on external context, e.g. flight time)
# ──────────────────────────────────────────────────────────────

TASK_TYPE_HINTS: list[tuple[str, tuple[int | None, int | None], str, timedelta | None, str]] = [
    # ── Social / dating ──
    ("约会",  (18, 0),  "social",   timedelta(hours=2),       "event"),
    ("聚餐",  (18, 30), "social",   timedelta(hours=2),       "event"),
    ("派对",  (19, 0),  "social",   timedelta(hours=3),       "event"),
    ("庆祝",  (19, 0),  "social",   timedelta(hours=2),       "event"),
    ("聚会",  (18, 0),  "social",   timedelta(hours=2),       "event"),
    ("见面",  (14, 0),  "social",   timedelta(hours=1),       "event"),
    ("约饭",  (18, 0),  "social",   timedelta(hours=1.5),     "event"),
    ("约人",  (14, 0),  "social",   timedelta(hours=1),       "event"),

    # ── Meals ──
    ("晚餐",  (18, 30), "meal",     timedelta(hours=1.5),     "event"),
    ("午饭",  (12, 0),  "meal",     timedelta(hours=1),       "event"),
    ("午餐",  (12, 0),  "meal",     timedelta(hours=1),       "event"),
    ("早饭",  (8, 0),   "meal",     timedelta(minutes=45),    "event"),
    ("早餐",  (8, 0),   "meal",     timedelta(minutes=45),    "event"),
    ("吃饭",  (18, 0),  "meal",     timedelta(hours=1),       "event"),
    ("火锅",  (18, 0),  "meal",     timedelta(hours=1.5),     "event"),
    ("烧烤",  (19, 0),  "meal",     timedelta(hours=1.5),     "event"),
    ("喝一杯", (20, 0),  "social",  timedelta(hours=1.5),     "event"),
    ("喝茶",  (14, 0),  "social",   timedelta(hours=1),       "event"),

    # ── Work / meetings ──
    ("开会",   (10, 0), "work",     timedelta(hours=1),       "event"),
    ("会议",   (10, 0), "work",     timedelta(hours=1),       "event"),
    ("周会",   (9, 0),  "work",     timedelta(hours=1),       "event"),
    ("站会",   (9, 0),  "work",     timedelta(minutes=15),    "event"),
    ("汇报",   (10, 0), "work",     timedelta(hours=1),       "event"),
    ("评审",   (10, 0), "work",     timedelta(hours=1),       "event"),
    ("面试",   (9, 0),  "work",     timedelta(hours=1),       "event"),
    ("笔试",   (9, 0),  "work",     timedelta(hours=2),       "event"),
    ("出差",   (9, 0),  "work",     None,                     "event"),  # multi-day
    ("加班",   (19, 0), "work",     timedelta(hours=2),       "event"),

    # ── Work deadlines ──
    ("DDL",    (None, None), "work",    None,   "deadline"),
    ("截止",   (None, None), "work",    None,   "deadline"),
    ("提交",   (None, None), "work",    None,   "deadline"),
    ("项目截止", (None, None), "work",  None,   "deadline"),

    # ── Health / exercise ──
    ("跑步",   (7, 0),  "health",   timedelta(minutes=40),    "event"),
    ("健身",   (7, 0),  "health",   timedelta(hours=1),       "event"),
    ("锻炼",   (7, 0),  "health",   timedelta(hours=1),       "event"),
    ("游泳",   (14, 0), "health",   timedelta(hours=1),       "event"),
    ("打球",   (15, 0), "health",   timedelta(hours=1.5),     "event"),
    ("瑜伽",   (7, 0),  "health",   timedelta(hours=1),       "event"),
    ("体检",   (8, 0),  "medical",  timedelta(hours=1),       "event"),
    ("看病",   (8, 0),  "medical",  timedelta(hours=1),       "event"),
    ("挂号",   (8, 0),  "medical",  timedelta(minutes=30),    "event"),
    ("洗牙",   (9, 0),  "medical",  timedelta(minutes=45),    "event"),
    ("复查",   (9, 0),  "medical",  timedelta(minutes=45),    "event"),

    # ── Education ──
    ("上课",   (9, 0),  "education", timedelta(hours=1.5),    "event"),
    ("培训",   (9, 0),  "education", timedelta(hours=3),      "event"),
    ("讲座",   (14, 0), "education", timedelta(hours=2),      "event"),
    ("考试",   (9, 0),  "education", timedelta(hours=2),      "event"),
    ("课程",   (9, 0),  "education", timedelta(hours=1.5),    "event"),
    ("学习",   (14, 0), "education", timedelta(hours=1),      "event"),
    ("自习",   (14, 0), "education", timedelta(hours=2),      "event"),
    ("网课",   (14, 0), "education", timedelta(hours=1),      "event"),

    # ── Entertainment ──
    ("电影",   (19, 0), "entertainment", timedelta(hours=2.5), "event"),
    ("看电影",  (19, 0), "entertainment", timedelta(hours=2.5), "event"),
    ("看剧",   (19, 0), "entertainment", timedelta(hours=2),   "event"),
    ("唱歌",   (19, 0), "entertainment", timedelta(hours=3),   "event"),
    ("KTV",    (19, 0), "entertainment", timedelta(hours=3),   "event"),
    ("逛街",   (14, 0), "entertainment", timedelta(hours=2),   "event"),
    ("旅游",   (8, 0),  "travel",        None,                 "event"),  # multi-day
    ("旅行",   (8, 0),  "travel",        None,                 "event"),
    ("看展",   (14, 0), "entertainment", timedelta(hours=1.5), "event"),
    ("博物馆",  (14, 0), "entertainment", timedelta(hours=2),   "event"),

    # ── Transport / errands ──
    ("送机",   (None, None), "transport", timedelta(hours=1),       "event"),
    ("接机",   (None, None), "transport", timedelta(hours=1),       "event"),
    ("送站",   (None, None), "transport", timedelta(hours=1),       "event"),
    ("接站",   (None, None), "transport", timedelta(hours=1),       "event"),
    ("接人",   (None, None), "transport", timedelta(minutes=30),    "event"),
    ("送人",   (None, None), "transport", timedelta(minutes=30),    "event"),
    ("出门",   (None, None), "transport", timedelta(minutes=30),    "event"),
    ("出发",   (None, None), "transport", timedelta(minutes=30),    "event"),
    ("回家",   (None, None), "chore",    timedelta(minutes=30),    "event"),
    ("取快递",  (None, None), "chore",    timedelta(minutes=15),    "event"),

    # ── Chores ──
    ("搬家",   (9, 0),  "chore",   timedelta(hours=4),       "event"),
    ("大扫除",  (10, 0), "chore",   timedelta(hours=2),       "event"),
    ("打扫",   (10, 0), "chore",   timedelta(hours=1),       "event"),
    ("整理",   (10, 0), "chore",   timedelta(hours=1),       "event"),
    ("购物",   (14, 0), "chore",   timedelta(hours=1.5),     "event"),
    ("买菜",   (9, 0),  "chore",   timedelta(minutes=45),    "event"),
    ("修车",   (9, 0),  "chore",   timedelta(hours=1),       "event"),
    ("理发",   (14, 0), "chore",   timedelta(minutes=45),    "event"),
    ("剪发",   (14, 0), "chore",   timedelta(minutes=45),    "event"),
    ("化妆",   (None, None), "chore", timedelta(minutes=40), "event"),
    ("洗漱",   (None, None), "chore", timedelta(minutes=20), "event"),

    # ── Sports / games ──
    ("比赛",   (None, None), "entertainment", timedelta(hours=2), "event"),

    # ── Finance deadlines ──
    ("还款",   (None, None), "finance",   None,   "deadline"),
    ("还花呗",  (None, None), "finance",   None,   "deadline"),
    ("还信用卡", (None, None), "finance",  None,   "deadline"),
    ("交费",   (None, None), "finance",   None,   "deadline"),
    ("缴费",   (None, None), "finance",   None,   "deadline"),
    ("交房租",  (None, None), "finance",   None,   "deadline"),
    ("续费",   (None, None), "finance",   None,   "deadline"),
    ("报税",   (None, None), "finance",   None,   "deadline"),

    # ── Milestones (annual, just remember) ──
    ("生日",   (None, None), "personal",  None,   "milestone"),
    ("纪念日", (None, None), "personal",  None,   "milestone"),
    ("忌日",   (None, None), "personal",  None,   "milestone"),
    ("情人节", (None, None), "personal",  None,   "milestone"),
    ("母亲节", (None, None), "personal",  None,   "milestone"),
    ("父亲节", (None, None), "personal",  None,   "milestone"),
    ("春节",   (None, None), "holiday",   None,   "milestone"),
    ("中秋节", (None, None), "holiday",   None,   "milestone"),
    ("圣诞",   (None, None), "holiday",   None,   "milestone"),
    ("元旦",   (None, None), "holiday",   None,   "milestone"),
    ("端午",   (None, None), "holiday",   None,   "milestone"),
    ("中秋",   (None, None), "holiday",   None,   "milestone"),
    ("周年",   (None, None), "personal",  None,   "milestone"),
    ("入职周年", (None, None), "personal", None,   "milestone"),
    ("毕业周年", (None, None), "personal", None,   "milestone"),
]

# ──────────────────────────────────────────────────────────────
#  Fuzzy range → concrete date span (for delete / cancel intent)
# ──────────────────────────────────────────────────────────────

FUZZY_RANGE_HINTS: list[tuple[str, int, str]] = [
    ("这几天",   3,  "today ± 3 days"),
    ("这两天",   2,  "today ± 2 days"),
    ("这阵子",   7,  "today + 7 days"),
    ("最近",     7,  "today + 7 days"),
    ("最近几天", 7,  "today + 7 days"),
    ("这两天的事", 2, "today ± 2 days"),
    ("这几天的事", 3, "today ± 3 days"),
]

# Colloquial normalization has moved to backend/services/lang/ — the modular
# language pack. Import normalize() from there.
# context_hints.py focuses on task-type defaults, fuzzy ranges, and attendees.

# ──────────────────────────────────────────────────────────────
#  Attendee extraction patterns
#  (regex, replacement) — applied to the combined title+notes text
# ──────────────────────────────────────────────────────────────

ATTENDEE_PATTERNS: list[tuple[str, str]] = [
    # "和/跟/与/叫上 XXX 一起/碰头/碰一下/约个" → XXX
    (r"(?:和|跟|与|叫上?|约)\s*(.{1,8}?)\s*(?:一起|一块|一块儿|约个|见面|碰一下|碰个头|碰头)",
     r"\1"),
    # "XXX团队/组/部门" → XXX团队
    (r"(.{1,6}?)(?:团队|组|部门|他们|她们)\s*(?:一起|开会|讨论|碰|聊)",
     r"\1团队"),
    # "找XXX聊/讨论" → XXX
    (r"找\s*(.{1,4}?)\s*(?:聊|讨论|问|谈|说)",
     r"\1"),
]


# ──────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────


def lookup_task_type(text: str) -> dict[str, Any]:
    """Look up context hints based on keyword matching in text.

    Returns a dict with any of: default_hour, default_minute, category,
    typical_duration, matched_keyword.
    Returns empty dict if no keyword matches.

    >>> lookup_task_type("明天约会")
    {'default_hour': 18, 'default_minute': 0, 'category': 'social', 'typical_duration': ..., 'matched_keyword': '约会'}
    """
    if not text:
        return {}

    for keyword, (hour, minute), category, duration, kind in TASK_TYPE_HINTS:
        if keyword in text:
            result: dict[str, Any] = {
                "category": category,
                "kind": kind,
                "matched_keyword": keyword,
            }
            if hour is not None:
                result["default_hour"] = hour
                result["default_minute"] = minute
            if duration is not None:
                result["typical_duration"] = duration
            return result

    return {}


def resolve_fuzzy_range(text: str) -> int | None:
    """Resolve a Chinese fuzzy range phrase to a concrete day count.

    Returns None if no range phrase found.
    Positive integer = number of days from today the range covers.

    >>> resolve_fuzzy_range("把这几天的事推了")
    3
    """
    if not text:
        return None
    for phrase, days, _desc in FUZZY_RANGE_HINTS:
        if phrase in text:
            return days
    return None


def extract_attendees_from_text(text: str) -> list[str]:
    """Extract implied attendees from Chinese text using regex patterns.

    >>> extract_attendees_from_text("明天和产品团队碰一下Q3规划")
    ['产品团队']
    """
    if not text:
        return []
    results: list[str] = []
    for pattern, replacement in ATTENDEE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            name = m.expand(replacement).strip()
            if name and name not in results:
                results.append(name)
    return results


def build_context_prompt() -> str:
    """Generate the 'Task Context Hints' section for the LLM system prompt.

    Auto-generated from TASK_TYPE_HINTS — add a rule there, and it appears
    here (and in Python fallback) with zero extra work.
    """
    lines = [
        "## Task Type Defaults",
        "When NO specific time is mentioned for these task types, use these defaults:",
        "",
    ]

    # Sort by category for readability
    category_order = [
        "social", "meal", "work", "health", "medical",
        "education", "entertainment", "travel", "transport",
        "chore", "personal", "finance", "holiday",
    ]
    category_labels: dict[str, str] = {
        "social":     "社交/约会",
        "meal":       "用餐",
        "work":       "工作/会议",
        "health":     "运动/健康",
        "medical":    "医疗",
        "education":  "学习/培训",
        "entertainment": "娱乐",
        "travel":     "旅行",
        "transport":  "接送/交通",
        "chore":      "家务/杂事",
        "personal":   "个人提醒",
        "finance":    "财务",
        "holiday":    "节日",
    }
    kind_labels: dict[str, str] = {
        "event":     "📅 时间段",
        "deadline":  "🔴 截止日",
        "milestone": "⭐ 纪念日",
    }

    seen = set()
    for cat in category_order:
        cat_hints = [(kw, (h, m), d, k) for kw, (h, m), c, d, k in TASK_TYPE_HINTS
                     if c == cat and kw not in seen]
        if not cat_hints:
            continue
        lines.append(f"### {category_labels.get(cat, cat)}")
        for kw, (h, m), duration, kind in cat_hints:
            seen.add(kw)
            time_str = f"{h:02d}:{m:02d}" if h is not None else "视情况而定"
            dur_str = ""
            if duration is not None:
                dur_str = f"，约{duration}"
            kind_tag = kind_labels.get(kind, kind)
            lines.append(f'- "{kw}"类 → 默认 {time_str}{dur_str} | {kind_tag}')
        lines.append("")

    lines.extend([
        "## Fuzzy Range Resolution for Deletion",
        'When the user says things like "推掉这几天的事", resolve:',
    ])
    for phrase, days, desc in FUZZY_RANGE_HINTS:
        lines.append(f'- "{phrase}" → {desc} ({days} days)')

    return "\n".join(lines)
