"""Pydantic data schemas for tasks and extraction results."""

from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    AUTO_CONFIRMED = "auto_confirmed"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class TaskKind(str, Enum):
    """Task time-structure type.

    - event:     has duration (start-end time block), e.g. 开会, 吃饭, 跑步
    - deadline:  single point-in-time, "must finish by", e.g. 还款, DL, 交房租
    - milestone: annual recurring date, "just remember", e.g. 生日, 纪念日, 春节
    """
    EVENT = "event"
    DEADLINE = "deadline"
    MILESTONE = "milestone"


class Task(BaseModel):
    id: str
    title: str
    datetime: datetime
    end_datetime: Optional[datetime] = None
    kind: TaskKind = TaskKind.EVENT
    category: Optional[str] = None  # "social" | "meal" | "work" | "health" | ...
    location: Optional[str] = None
    attendees: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    confidence: float  # 0.0 - 1.0
    source: str  # filename or "manual-input"
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)


class ExtractionResult(BaseModel):
    tasks: list[Task]
    auto_added: int
    pending_review: int
    discarded: int


class TextExtractRequest(BaseModel):
    text: str
    source: str = "manual-input"


class ConfirmRequest(BaseModel):
    task_id: str


class UploadResponse(BaseModel):
    result: ExtractionResult
    extracted_text: str
