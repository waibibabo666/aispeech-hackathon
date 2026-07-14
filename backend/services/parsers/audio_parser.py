"""Audio transcription parser using OpenAI Whisper API."""

from pathlib import Path

from openai import OpenAI

from ...config import settings
from .base import BaseParser

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mpga"}


class AudioParser(BaseParser):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in SUPPORTED_EXTENSIONS

    def parse(self, file_path: Path) -> str:
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )

        file_size = file_path.stat().st_size
        max_size = 25 * 1024 * 1024  # Whisper API limit is 25MB

        if file_size > max_size:
            raise ValueError(
                f"Audio file {file_path.name} is {file_size / 1024 / 1024:.1f}MB, "
                f"exceeds the Whisper API limit of 25MB. Please split the file."
            )

        with open(file_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model=settings.WHISPER_MODEL,
                file=f,
                language="zh",
                response_format="text",
            )

        return transcript
