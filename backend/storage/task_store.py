"""Task repository with JSON file persistence — tasks survive server restarts."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from ..models.task import Task, TaskStatus, TaskKind

TASKS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "tasks.json"


def _task_to_dict(task: Task) -> dict:
    d = {
        "id": task.id,
        "title": task.title,
        "datetime": task.datetime.isoformat(),
        "end_datetime": task.end_datetime.isoformat() if task.end_datetime else None,
        "kind": task.kind.value,
        "category": task.category,
        "location": task.location,
        "attendees": task.attendees,
        "notes": task.notes,
        "confidence": task.confidence,
        "source": task.source,
        "status": task.status.value,
        "created_at": task.created_at.isoformat(),
    }
    return d


def _dict_to_task(d: dict) -> Task:
    return Task(
        id=d["id"],
        title=d["title"],
        datetime=datetime.fromisoformat(d["datetime"]),
        end_datetime=datetime.fromisoformat(d["end_datetime"]) if d.get("end_datetime") else None,
        kind=TaskKind(d.get("kind", "event")),
        category=d.get("category"),
        location=d.get("location"),
        attendees=d.get("attendees", []),
        notes=d.get("notes"),
        confidence=d.get("confidence", 1.0),
        source=d.get("source", ""),
        status=TaskStatus(d.get("status", "pending")),
        created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else datetime.now(),
    )


class TaskStore:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._trash_batches: list[list[Task]] = []  # undo: each batch = one delete action
        self._load()
        self._load_trash()

    def _load(self):
        if TASKS_FILE.exists():
            try:
                data = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
                for item in data:
                    task = _dict_to_task(item)
                    self._tasks[task.id] = task
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_trash(self):
        TRASH_FILE = TASKS_FILE.parent / "trash.json"
        if TRASH_FILE.exists():
            try:
                data = json.loads(TRASH_FILE.read_text(encoding="utf-8"))
                if data and isinstance(data[0], list):
                    # New format: list of batches
                    for batch in data:
                        self._trash_batches.append([_dict_to_task(t) for t in batch])
                elif data and isinstance(data[0], dict):
                    # Old format: flat list of tasks
                    self._trash_batches = [[_dict_to_task(t) for t in data]]
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_trash(self):
        TRASH_FILE = TASKS_FILE.parent / "trash.json"
        data = [[_task_to_dict(t) for t in batch] for batch in self._trash_batches[-20:]]
        TRASH_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRASH_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save(self):
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = [_task_to_dict(t) for t in self._tasks.values()]
        TASKS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, task: Task) -> Task:
        if not task.id:
            task.id = str(uuid.uuid4())
        self._tasks[task.id] = task
        self._save()
        return task

    def add_all(self, tasks: list[Task]) -> list[Task]:
        """Add tasks, skipping duplicates (same title + date + hour)."""
        added = []
        existing = {(t.title, t.datetime.date(), t.datetime.hour) for t in self._tasks.values()}
        for task in tasks:
            key = (task.title, task.datetime.date(), task.datetime.hour)
            if key in existing:
                continue
            self.add(task)
            existing.add(key)
            added.append(task)
        if added:
            self._save()
        return added

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

    def save(self):
        """Persist current state to disk."""
        self._save()

    def confirm(self, task_id: str) -> Task | None:
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CONFIRMED
            self._save()
            return task
        return None

    def reject(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.REJECTED
            self._save()
            return True
        return False

    def delete(self, task_id: str) -> bool:
        if task_id in self._tasks:
            task = self._tasks[task_id]
            del self._tasks[task_id]
            self._trash_batches.append([task])
            self._save()
            self._save_trash()
            return True
        return False

    def delete_by_ids(self, task_ids: list[str]) -> int:
        """Delete multiple tasks as one batch. Returns count. One undo restores all."""
        count = 0
        batch = []
        for tid in task_ids:
            if tid in self._tasks:
                batch.append(self._tasks[tid])
                del self._tasks[tid]
                count += 1
        if count:
            self._trash_batches.append(batch)
            if len(self._trash_batches) > 20:
                self._trash_batches = self._trash_batches[-20:]
            self._save()
            self._save_trash()
        return count

    def undo_last_delete(self) -> list[Task]:
        """Restore tasks from the most recent batch deletion. Returns restored tasks."""
        if not self._trash_batches:
            return []

        batch = self._trash_batches.pop()
        restored = []
        for t in batch:
            if t.id not in self._tasks:
                self._tasks[t.id] = t
                restored.append(t)

        if restored:
            self._save()
            self._save_trash()

        return restored

    def clear_trash(self):
        """Permanently delete all trash."""
        self._trash_batches.clear()
        self._save_trash()

    def clear(self):
        self._tasks.clear()
        self._save()

    @property
    def count(self) -> int:
        return len(self._tasks)

    @property
    def pending_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)


task_store = TaskStore()
