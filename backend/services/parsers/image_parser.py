"""Image OCR parser using RapidOCR — a lightweight ONNX-based OCR engine.

Replaces the previous GPT-4o Vision API approach. RapidOCR runs fully
locally (~30MB model), zero PyTorch dependency, optimized for Chinese text.
"""

from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

from .base import BaseParser

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# Singleton OCR engine — loaded once on first use
_ocr_engine: RapidOCR | None = None


def _get_engine() -> RapidOCR:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine


class ImageParser(BaseParser):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in SUPPORTED_EXTENSIONS

    def parse(self, file_path: Path) -> str:
        """Extract text from an image using RapidOCR.

        Detects text regions and returns them sorted top-to-bottom.
        If no text is found, returns a note indicating the image may
        not contain readable text.
        """
        engine = _get_engine()
        result = engine(str(file_path))

        # result is (detections, timing) — detections is list of [box, text, confidence]
        detections = result[0] if result else None
        if detections is None or len(detections) == 0:
            return "[此图片中未检测到文字]"

        # Sort by vertical position so reading order is preserved
        items = []
        for detection in detections:
            box, text, confidence = detection
            stripped = text.strip()
            if stripped:
                y = box[0][1] if box else 0
                items.append((y, stripped))

        items.sort(key=lambda x: x[0])
        return "\n".join(text for _, text in items)
