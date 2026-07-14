"""PDF file parser using PyMuPDF (fitz)."""

from pathlib import Path

from .base import BaseParser


class PdfParser(BaseParser):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def parse(self, file_path: Path) -> str:
        import pymupdf

        doc = pymupdf.open(str(file_path))
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text.strip())
        doc.close()
        return "\n\n".join(pages)
