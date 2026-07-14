"""Image OCR parser using GPT-4o Vision API."""

import base64
from pathlib import Path

from openai import OpenAI

from ...config import settings
from .base import BaseParser

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


class ImageParser(BaseParser):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in SUPPORTED_EXTENSIONS

    def parse(self, file_path: Path) -> str:
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )

        suffix = file_path.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }

        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        response = client.chat.completions.create(
            model=settings.MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "提取这张图片中的所有文字，保持原有格式。这可能是一张海报、截图、聊天记录、或通知。只输出提取到的文字内容，不要添加额外说明。",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_map.get(suffix, 'image/jpeg')};base64,{b64}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=4096,
        )

        content = response.choices[0].message.content
        return content or ""
