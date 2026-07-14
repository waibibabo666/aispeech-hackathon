"""Plain text file parser — passes content through unchanged."""

from pathlib import Path

from .base import BaseParser


class TextParser(BaseParser):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in {".txt", ".md", ".csv"}

    def parse(self, file_path: Path) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
