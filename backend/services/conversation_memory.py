"""Conversation memory — lightweight context retention for LLM dispatch.

Stores the last N user messages and their outcomes in a ring buffer.
Injected into dispatch_intent so the LLM can resolve pronouns like
"把这个改到明天" or "刚才那个删了" based on prior conversation.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

MAX_TURNS = 3  # keep last 3 exchanges


@dataclass
class Turn:
    user_text: str
    action: str
    summary: str   # human-readable result, e.g. "新增 跑步 @ 明天08:00"
    at: str        # ISO timestamp


@dataclass
class ConversationMemory:
    _turns: deque[Turn] = field(default_factory=lambda: deque(maxlen=MAX_TURNS))

    def record(self, user_text: str, action: str, summary: str):
        self._turns.append(Turn(
            user_text=user_text,
            action=action,
            summary=summary,
            at=datetime.now().isoformat(),
        ))

    def to_prompt(self) -> str:
        """Format recent conversation as a compact LLM context block."""
        if not self._turns:
            return ""

        lines = ["## Recent Conversation (for pronoun resolution)"]
        for i, t in enumerate(self._turns, 1):
            lines.append(f"{i}. 用户: \"{t.user_text}\" → {t.summary}")
        lines.append(
            "当用户说\"这个/那个/它/刚才/上次\"而没有指明具体任务名时，"
            "请参考以上最近的对话来推断指的是哪个任务。"
            "优先匹配对话中刚提到的任务，而非当前任务列表。"
        )
        lines.append("")

    @property
    def is_empty(self) -> bool:
        return len(self._turns) == 0


# Singleton
memory = ConversationMemory()
