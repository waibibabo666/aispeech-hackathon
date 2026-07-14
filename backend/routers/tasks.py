"""Task management CRUD endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..models.task import Task
from ..storage.task_store import task_store

router = APIRouter()

DEMO_PATH = Path("data/demo_tasks.json")


@router.get("/tasks", response_model=list[Task])
def list_tasks():
    """Get all non-rejected tasks sorted by datetime."""
    return task_store.get_all()


@router.get("/tasks/pending", response_model=list[Task])
def list_pending():
    """Get tasks awaiting user confirmation."""
    return task_store.get_pending()


@router.post("/tasks/{task_id}/confirm", response_model=Task)
def confirm_task(task_id: str):
    """Confirm a pending task."""
    task = task_store.confirm(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found or not pending")
    return task


@router.post("/tasks/{task_id}/reject")
def reject_task(task_id: str):
    """Reject a pending task."""
    if not task_store.reject(task_id):
        raise HTTPException(status_code=404, detail="Task not found or not pending")
    return {"status": "ok"}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    """Delete a task permanently."""
    if not task_store.delete(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


@router.post("/tasks/demo", response_model=list[Task])
def load_demo():
    """Load pre-baked demo tasks."""
    if not DEMO_PATH.exists():
        raise HTTPException(status_code=500, detail="Demo data file not found")
    return task_store.load_demo(DEMO_PATH)
