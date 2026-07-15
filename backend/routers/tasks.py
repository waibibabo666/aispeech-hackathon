"""Task management CRUD endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

from ..models.task import Task, TaskStatus
from ..storage.task_store import task_store

router = APIRouter()


class DeleteIntentRequest(BaseModel):
    text: str


class DeleteIntentResponse(BaseModel):
    deleted_count: int
    summary: str
    deleted_ids: list[str]


class IntentResponse(BaseModel):
    action: str
    # extract action
    tasks: list[Task] | None = None
    auto_added: int = 0
    pending_review: int = 0
    discarded: int = 0
    extracted_text: str | None = None
    # delete action
    deleted_count: int = 0
    summary: str | None = None
    deleted_ids: list[str] | None = None
    # chat action
    reply: str | None = None


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


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    datetime: str | None = None       # ISO datetime
    end_datetime: str | None = None   # ISO datetime or "" to clear
    location: str | None = None
    notes: str | None = None
    kind: str | None = None           # "event" | "deadline" | "milestone"


@router.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: str, req: TaskUpdateRequest):
    """Update editable fields of any task. Confirm pending tasks on edit."""
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if req.title is not None:
        task.title = req.title
    if req.datetime is not None:
        task.datetime = datetime.fromisoformat(req.datetime)
    if req.end_datetime is not None:
        task.end_datetime = datetime.fromisoformat(req.end_datetime) if req.end_datetime else None
    if req.location is not None:
        task.location = req.location or None
    if req.notes is not None:
        task.notes = req.notes or None
    if req.kind is not None:
        from ..models.task import Task, TaskStatusKind
        if req.kind in ("event", "deadline", "milestone"):
            task.kind = TaskKind(req.kind)

    # Auto-confirm if it was pending (user edited = confirmed)
    if task.status == TaskStatus.PENDING:
        task.status = TaskStatus.CONFIRMED

    task_store.save()
    return task


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    """Delete a task permanently."""
    if not task_store.delete(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


@router.post("/tasks/undo", response_model=IntentResponse)
async def undo_last_deletion():
    """Restore the most recently deleted batch of tasks. Returns restored tasks."""
    restored = task_store.undo_last_delete()
    if not restored:
        return IntentResponse(action="chat", reply="没有可恢复的任务")
    return IntentResponse(
        action="extract",
        tasks=restored,
        auto_added=len(restored),
        pending_review=0,
        discarded=0,
        summary=f"已恢复 {len(restored)} 个任务",
    )


@router.post("/tasks/delete-by-intent", response_model=DeleteIntentResponse)
async def delete_by_intent(req: DeleteIntentRequest):
    """Use LLM to match a natural-language deletion intent against current tasks."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Intent text cannot be empty")

    from ..services.llm_extractor import match_tasks_to_delete

    # Build compact task list for LLM
    all_tasks = task_store.get_all()
    task_dicts = [
        {
            "id": t.id,
            "title": t.title,
            "datetime": t.datetime.isoformat(),
            "location": t.location,
            "notes": t.notes,
        }
        for t in all_tasks
    ]

    if not task_dicts:
        return DeleteIntentResponse(deleted_count=0, summary="当前没有任务可删除", deleted_ids=[])

    try:
        ids, summary = await match_tasks_to_delete(req.text, task_dicts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM matching failed: {str(e)}")

    count = task_store.delete_by_ids(ids)

    return DeleteIntentResponse(deleted_count=count, summary=summary, deleted_ids=ids)


@router.post("/tasks/intent", response_model=IntentResponse)
async def unified_intent(req: DeleteIntentRequest):
    """One endpoint for all user intents — extract, delete, chat.

    The LLM classifies the intent and returns structured data.
    No frontend keyword matching needed.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    from ..services.llm_extractor import dispatch_intent
    from ..services.confidence_router import confidence_router
    from ..services.lang import normalize as normalize_slang
    from ..services.conversation_memory import memory as conv_mem

    # Build task context for LLM
    all_tasks = task_store.get_all()
    task_dicts = [
        {
            "id": t.id,
            "title": t.title,
            "datetime": t.datetime.isoformat(),
            "location": t.location,
            "notes": t.notes,
        }
        for t in all_tasks
    ]

    try:
        result = await dispatch_intent(req.text, task_dicts)
    except Exception as e:
        import logging
        logger = logging.getLogger("tasks")
        logger.exception("Intent dispatch failed for text: %s", req.text[:200])
        detail = str(e)
        # Include cause chain for connection errors
        if e.__cause__:
            detail = f"{detail} (cause: {e.__cause__})"
        raise HTTPException(status_code=500, detail=f"Intent dispatch failed: {detail}")

    action = result.get("action", "chat")

    if action == "extract":
        tasks_data = result.get("tasks", [])

        # Also process any delete intent embedded in extract (mixed intent)
        mix_deleted_ids = result.get("deleted_ids", []) or []
        mix_deleted_count = 0
        if mix_deleted_ids:
            mix_deleted_count = task_store.delete_by_ids(mix_deleted_ids)

        if not tasks_data:
            # Fallback: LLM returned extract with 0 tasks but text looks like pure delete.
            # E.g. "这几天的晚餐不吃了" → should be delete, not extract.
            normalized = normalize_slang(req.text)
            delete_keywords = ["全部取消", "全部删除", "删除", "取消", "不吃了", "不去了"]
            is_delete_like = any(kw in normalized for kw in delete_keywords)
            is_create_like = any(kw in req.text for kw in ["安排", "加上", "加一个", "记一下", "我要", "想", "准备", "打算"])

            if is_delete_like and not is_create_like and task_dicts:
                # Re-run as pure delete
                from ..services.llm_extractor import match_tasks_to_delete
                ids, summary = await match_tasks_to_delete(req.text, task_dicts)
                count = task_store.delete_by_ids(ids)
                conv_mem.record(req.text, "delete", summary)
                return IntentResponse(
                    action="delete",
                    deleted_count=count,
                    deleted_ids=ids,
                    summary=summary if count else "未找到匹配的任务",
                )

            if mix_deleted_count:
                return IntentResponse(
                    action="extract", tasks=[], auto_added=0,
                    pending_review=0, discarded=0,
                    extracted_text=req.text,
                    deleted_count=mix_deleted_count,
                    deleted_ids=mix_deleted_ids,
                    summary=f"已删除 {mix_deleted_count} 个任务，未识别到新的日程信息",
                )
            return IntentResponse(
                action="extract", tasks=[], auto_added=0,
                pending_review=0, discarded=0,
                extracted_text=req.text,
                summary="未识别到日程信息",
            )

        # Run tasks through the normal extraction pipeline
        tasks = []
        for item in tasks_data:
            from ..services.llm_extractor import map_item_to_task
            t = map_item_to_task(item, "manual-input", req.text)
            if t:
                tasks.append(t)

        auto, pending, discarded = confidence_router.route(tasks)
        task_store.add_all(auto)
        task_store.add_all(pending)

        summary = f"新增 {len(auto)} 个任务" + (f"，{len(pending)} 个待确认" if pending else "")
        if mix_deleted_count:
            summary += f"，已删除 {mix_deleted_count} 个任务"

        conv_mem.record(req.text, "extract", summary)

        return IntentResponse(
            action="extract",
            tasks=auto + pending,
            auto_added=len(auto),
            pending_review=len(pending),
            discarded=len(discarded),
            extracted_text=req.text,
            deleted_count=mix_deleted_count,
            deleted_ids=mix_deleted_ids,
            summary=summary,
        )

    elif action == "delete":
        ids = result.get("deleted_ids", [])
        summary = result.get("summary", f"已删除 {len(ids)} 个任务")
        count = task_store.delete_by_ids(ids)
        conv_mem.record(req.text, "delete", summary)
        return IntentResponse(
            action="delete",
            deleted_count=count,
            deleted_ids=ids,
            summary=summary,
        )

    elif action == "undo":
        restored = task_store.undo_last_delete()
        if restored:
            summary = f"已恢复 {len(restored)} 个任务"
            conv_mem.record(req.text, "undo", summary)
            return IntentResponse(
                action="extract",
                tasks=restored,
                auto_added=len(restored),
                pending_review=0,
                discarded=0,
                summary=f"已恢复 {len(restored)} 个任务",
            )
        return IntentResponse(
            action="chat",
            reply="没有可恢复的任务，垃圾箱已清空",
        )

    else:  # chat
        return IntentResponse(
            action="chat",
            reply=result.get("reply", "你好！有什么可以帮你的？"),
            summary=result.get("reply", ""),
        )
