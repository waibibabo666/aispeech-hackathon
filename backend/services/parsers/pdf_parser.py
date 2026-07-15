"""PDF parser — extracts text via PyMuPDF, falls back to OCR for scanned pages."""

import logging
from pathlib import Path

import pymupdf

from .base import BaseParser

logger = logging.getLogger("pdf_parser")


def _ocr_page(page: pymupdf.Page) -> str:
    """Render page to image and OCR with RapidOCR. Used for scanned/image PDFs."""
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    # Render page at 200 DPI for good OCR quality
    pix = page.get_pixmap(dpi=200)
    img_bytes = pix.tobytes("png")

    result = engine(img_bytes)
    detections = result[0] if result else None
    if not detections:
        return ""

    items = []
    for detection in detections:
        box, text, _ = detection
        if text.strip():
            y = box[0][1] if box else 0
            items.append((y, text.strip()))

    items.sort(key=lambda x: x[0])
    return "\n".join(text for _, text in items)


class PdfParser(BaseParser):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def parse(self, file_path: Path) -> str:
        doc = pymupdf.open(str(file_path))
        pages_text: list[str] = []
        ocr_used = False

        for page in doc:
            text = page.get_text().strip()
            if text:
                pages_text.append(text)
            else:
                # Scanned/image page — try OCR
                try:
                    ocr_text = _ocr_page(page)
                    if ocr_text:
                        pages_text.append(ocr_text)
                        ocr_used = True
                except Exception as e:
                    logger.warning("OCR failed for page: %s", e)

        doc.close()

        if not pages_text:
            return "[此PDF中未检测到文字，可能是扫描件且OCR失败]"

        if ocr_used:
            logger.info("OCR was used for one or more pages in %s", file_path.name)

        return "\n\n".join(pages_text)
