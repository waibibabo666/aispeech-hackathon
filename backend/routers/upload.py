"""Upload and extraction endpoints."""

from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from ..models.task import ExtractionResult, TextExtractRequest, UploadResponse
from ..services.dispatcher import dispatcher
from ..services.llm_extractor import extract_tasks
from ..services.confidence_router import confidence_router
from ..storage.task_store import task_store
from ..config import settings

router = APIRouter()


@router.post("/extract", response_model=UploadResponse)
async def extract_from_text(req: TextExtractRequest):
    """Extract tasks from raw text input."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        tasks = await extract_tasks(req.text, req.source)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {str(e)}")

    auto, pending, discarded = confidence_router.route(tasks)

    task_store.add_all(auto)
    task_store.add_all(pending)

    return UploadResponse(
        result=ExtractionResult(
            tasks=auto + pending,
            auto_added=len(auto),
            pending_review=len(pending),
            discarded=len(discarded),
        ),
        extracted_text=req.text,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_and_extract(files: list[UploadFile] = File(...)):
    """Upload files, extract text, then extract tasks."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Save files to temp location and parse
    temp_dir = Path("data/uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)

    all_text_parts: list[str] = []
    filenames: list[str] = []

    for file in files:
        if file.filename is None:
            continue

        # Check file size
        content = await file.read()
        if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit",
            )

        # Save temp file for parsers that need a path
        temp_path = temp_dir / file.filename
        temp_path.write_bytes(content)

        try:
            text = dispatcher.parse(temp_path)
            all_text_parts.append(text)
            filenames.append(file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()

    if not all_text_parts:
        raise HTTPException(status_code=400, detail="No text could be extracted from files")

    combined_text = "\n\n---\n\n".join(
        f"[Source: {name}]\n{text}" for name, text in zip(filenames, all_text_parts)
    )
    source = ", ".join(filenames)

    try:
        tasks = await extract_tasks(combined_text, source)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {str(e)}")

    auto, pending, discarded = confidence_router.route(tasks)

    task_store.add_all(auto)
    task_store.add_all(pending)

    return UploadResponse(
        result=ExtractionResult(
            tasks=auto + pending,
            auto_added=len(auto),
            pending_review=len(pending),
            discarded=len(discarded),
        ),
        extracted_text=combined_text,
    )
