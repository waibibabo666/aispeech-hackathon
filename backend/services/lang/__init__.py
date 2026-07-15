"""Chinese Colloquial Language Pack — modular, data-driven normalization.

Usage:
    from backend.services.lang import normalize, build_prompt, get_stats

    cleaned = normalize("把事儿都推了")   # → "把事情全部取消"
    prompt  = build_prompt()              # → LLM prompt section

Architecture:
    All rules live in data.py — organized by category.
    This module just pipes them through the normalization pipeline.
"""

from __future__ import annotations

import re
from collections import OrderedDict

from .data import ALL_CATEGORIES

# ──────────────────────────────────────────────────────────────
#  Build sorted rule list (longest-first to avoid partial matches)
# ──────────────────────────────────────────────────────────────

# Deduplicate and sort: (colloquial → standard), longest key first
_RULES: OrderedDict[str, str] = OrderedDict()
_category_counts: dict[str, int] = {}

for cat_name, rules in ALL_CATEGORIES:
    count = 0
    for colloquial, standard in rules:
        if colloquial not in _RULES:
            _RULES[colloquial] = standard
            count += 1
    _category_counts[cat_name] = count

# Sort so longer patterns match first (prevents "取消" matching inside "全部取消")
_SORTED_RULES = sorted(_RULES.items(), key=lambda x: -len(x[0]))


def normalize(text: str) -> str:
    """Normalize colloquial Chinese to standard Mandarin.

    Applies all categories: erhua, slang, dialect, internet language, etc.

    >>> normalize("把事儿都推了，不干了")
    '把事情全部取消，全部取消'
    """
    if not text:
        return text
    for colloquial, standard in _SORTED_RULES:
        text = text.replace(colloquial, standard)
    # Collapse consecutive duplicates (e.g. "全部取消 全部取消" → "全部取消")
    text = re.sub(r'(全部取消\s*)+', '全部取消', text)
    text = re.sub(r'(全部删除\s*)+', '全部删除', text)
    return text


def build_prompt() -> str:
    """Generate the 'Colloquial Chinese Dictionary' section for LLM system prompts.

    Auto-generated from data.py — add a rule there, appears here automatically.
    """
    lines = [
        "## Colloquial Chinese Dictionary",
        "The following are spoken/informal Chinese expressions and their standard meanings. "
        "Treat the colloquial form EXACTLY as you would the standard form.",
        "",
    ]

    category_labels: dict[str, str] = {
        "erhua":           "儿化音 (Erhua → Standard)",
        "delete_signals":  "删除/取消信号 (Delete/Cancel Signals)",
        "time_phrases":    "时间口语 (Time Colloquialisms)",
        "social_phrases":  "社交/会议口语 (Social & Meeting Slang)",
        "reminder_signals":"任务/提醒信号 (Task & Reminder Signals)",
        "internet_slang":  "网络用语 (Internet Slang)",
        "regional":        "地域变体 (Regional/Dialect Variants)",
        "negation":        "否定/拒绝 (Negation & Refusal)",
        "confirm":         "确认/同意 (Confirmation & Agreement)",
    }

    for cat_name, rules in ALL_CATEGORIES:
        if not rules:
            continue
        label = category_labels.get(cat_name, cat_name)
        lines.append(f"### {label}")
        # Show top 20 most important per category
        shown = 0
        for colloquial, standard in rules:
            if colloquial == standard:
                continue
            lines.append(f"- `{colloquial}` = `{standard}`")
            shown += 1
            if shown >= 20:
                remaining = len(rules) - shown
                if remaining > 0:
                    lines.append(f"- ... (+{remaining} more)")
                break
        lines.append("")

    lines.extend([
        "## Important Colloquial Intent Rules",
        '- Any phrase in the "Delete/Cancel Signals" category = the user wants to DELETE tasks.',
        '- When delete signals appear WITH new schedule info, use action="extract" with deleted_ids.',
        '- Phrases from "Task & Reminder Signals" = the user wants to CREATE a reminder/task.',
        '- Internet slang in chat context should be interpreted normally (not literally).',
        '- Regional variants are just dialect — treat them as their standard equivalents.',
    ])

    return "\n".join(lines)


def get_stats() -> dict:
    """Return rule counts per category."""
    total = sum(_category_counts.values())
    return {
        "total_rules": total,
        "categories": dict(_category_counts),
    }
