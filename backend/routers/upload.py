"""Upload and extraction endpoints."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from ..models.task import ExtractionResult, TextExtractRequest, UploadResponse
from ..services.dispatcher import dispatcher
from ..services.llm_extractor import extract_tasks
from ..services.confidence_router import confidence_router
from ..storage.task_store import task_store
from ..services.parsers.audio_parser import _transcribe, SUPPORTED_EXTENSIONS as AUDIO_EXTS
from ..config import settings

router = APIRouter()
logger = logging.getLogger("upload")


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
async def upload_and_extract(
    files: list[UploadFile] = File(default=[]),
    text: str = Form(default=""),
):
    """Upload files and/or raw text, extract text, then extract tasks.

    Supports three modes:
    - Text only: set `text`, omit `files`
    - Files only: set `files`, omit `text`
    - Combined: set both — text + file contents are merged before LLM extraction
    """
    if not files and not text.strip():
        raise HTTPException(status_code=400, detail="No text or files provided")

    all_text_parts: list[str] = []
    filenames: list[str] = []

    # Add manual text if provided
    if text.strip():
        all_text_parts.append(text.strip())
        filenames.append("手动输入")

    # Parse uploaded files
    temp_dir = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)

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
            # Run sync parser in thread pool to avoid blocking the event loop
            file_text = await asyncio.to_thread(dispatcher.parse, temp_path)
            logger.info("Parsed %s: %d chars", file.filename, len(file_text))
            all_text_parts.append(file_text)
            filenames.append(file.filename)
        except ValueError as e:
            logger.error("Parser failed for %s: %s", file.filename, e)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.exception("Unexpected parser error for %s", file.filename)
            raise HTTPException(status_code=500, detail=f"Parser error: {str(e)}")
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()

    if not all_text_parts:
        raise HTTPException(status_code=400, detail="No text could be extracted")

    combined_text = "\n\n---\n\n".join(
        f"[Source: {name}]\n{t}" for name, t in zip(filenames, all_text_parts)
    )
    source = ", ".join(filenames)

    try:
        tasks = await extract_tasks(combined_text, source)
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.exception("LLM extraction failed for %s", source)
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {str(e)}")

    auto, pending, discarded = confidence_router.route(tasks)

    logger.info(
        "Extraction result for %s: %d auto, %d pending, %d discarded, %d chars input",
        source, len(auto), len(pending), len(discarded), len(combined_text),
    )

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


@router.post("/transcribe-voice")
async def transcribe_voice(audio: UploadFile = File(...)):
    """Transcribe voice audio using local SenseVoice model — no cloud APIs.

    Accepts WAV or webm audio from browser MediaRecorder, returns transcribed text.
    """
    ext = Path(audio.filename or "voice.webm").suffix.lower()
    if ext not in AUDIO_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported audio format: {ext}")

    temp_dir = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"voice_{id(audio)}{ext}"

    try:
        content = await audio.read()
        temp_path.write_bytes(content)
        text = await asyncio.to_thread(_transcribe, temp_path)
        return {"text": text.strip(), "source": "voice"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Voice transcription failed")
        raise HTTPException(status_code=500, detail=f"转录失败: {e}")
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
