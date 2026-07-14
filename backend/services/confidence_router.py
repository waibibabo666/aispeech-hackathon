"""Confidence router — classifies extracted tasks into three buckets."""

from ..config import settings
from ..models.task import Task, TaskStatus


class ConfidenceRouter:
    def __init__(
        self,
        auto_threshold: float | None = None,
        review_lower: float | None = None,
    ):
        self.auto_threshold = auto_threshold or settings.CONFIDENCE_AUTO_THRESHOLD
        self.review_lower = review_lower or settings.CONFIDENCE_REVIEW_LOWER

    def route(self, tasks: list[Task]) -> tuple[list[Task], list[Task], list[Task]]:
        """Classify tasks into three buckets.

        Returns:
            (auto_confirmed, pending_review, discarded)
        """
        auto: list[Task] = []
        pending: list[Task] = []
        discarded: list[Task] = []

        for task in tasks:
            if task.confidence >= self.auto_threshold:
                task.status = TaskStatus.AUTO_CONFIRMED
                auto.append(task)
            elif task.confidence >= self.review_lower:
                task.status = TaskStatus.PENDING
                pending.append(task)
            else:
                discarded.append(task)

        return auto, pending, discarded


# Singleton
confidence_router = ConfidenceRouter()
