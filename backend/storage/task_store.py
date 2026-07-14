"""In-memory task repository — simple CRUD with UUID keys."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from ..models.task import Task, TaskStatus


class TaskStore:
    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def add(self, task: Task) -> Task:
        if not task.id:
            task.id = str(uuid.uuid4())
        self._tasks[task.id] = task
        return task

    def add_all(self, tasks: list[Task]) -> list[Task]:
        return [self.add(t) for t in tasks]

    def get_all(self) -> list[Task]:
        return sorted(
            [t for t in self._tasks.values() if t.status != TaskStatus.REJECTED],
            key=lambda t: t.datetime,
        )

    def get_pending(self) -> list[Task]:
        return sorted(
            [t for t in self._tasks.values() if t.status == TaskStatus.PENDING],
            key=lambda t: t.datetime,
        )

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def confirm(self, task_id: str) -> Task | None:
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CONFIRMED
        return task

    def reject(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.REJECTED
            return True
        return False

    def delete(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def clear(self):
        self._tasks.clear()

    def load_demo(self, demo_path: Path) -> list[Task]:
        """Load pre-baked demo tasks from a JSON file."""
        with open(demo_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tasks = []
        for item in data:
            task = Task(
                id=str(uuid.uuid4()),
                title=item["title"],
                datetime=datetime.fromisoformat(item["datetime"]),
                end_datetime=(
                    datetime.fromisoformat(item["end_datetime"])
                    if item.get("end_datetime")
                    else None
                ),
                location=item.get("location"),
                attendees=item.get("attendees", []),
                notes=item.get("notes"),
                confidence=item.get("confidence", 1.0),
                source=item.get("source", "demo"),
                status=TaskStatus.AUTO_CONFIRMED,
            )
            tasks.append(task)

        self.clear()
        self.add_all(tasks)
        return tasks

    @property
    def count(self) -> int:
        return len(self._tasks)

    @property
    def pending_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)


# Singleton
task_store = TaskStore()
