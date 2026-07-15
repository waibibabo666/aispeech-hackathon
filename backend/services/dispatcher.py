"""File dispatch service — routes files to appropriate parsers by extension."""

from pathlib import Path

from .parsers.base import BaseParser
from .parsers.text_parser import TextParser
from .parsers.docx_parser import DocxParser
from .parsers.pdf_parser import PdfParser
from .parsers.image_parser import ImageParser
from .parsers.audio_parser import AudioParser
from .parsers.pptx_parser import PptxParser


class Dispatcher:
    def __init__(self):
        self._parsers: list[BaseParser] = []
        self._register_defaults()

    def _register_defaults(self):
        self.register(TextParser())
        self.register(DocxParser())
        self.register(PdfParser())
        self.register(ImageParser())
        self.register(AudioParser())
        self.register(PptxParser())

    def register(self, parser: BaseParser):
        self._parsers.append(parser)

    def parse(self, file_path: Path) -> str:
        for parser in self._parsers:
            if parser.supports(file_path):
                return parser.parse(file_path)
        supported = self._supported_extensions()
        raise ValueError(
            f"Unsupported file type: {file_path.suffix}. "
            f"Supported: {', '.join(sorted(supported)) if supported else 'none'}"
        )

    def parse_all(self, file_paths: list[Path]) -> list[tuple[str, str]]:
        """Parse multiple files, returning list of (filename, text)."""
        results = []
        for fp in file_paths:
            text = self.parse(fp)
            results.append((fp.name, text))
        return results

    def _supported_extensions(self) -> set[str]:
        exts: set[str] = set()
        for p in self._parsers:
            # Collect extensions by checking common patterns
            # Each parser's supports() checks suffix; we enumerate known sets here
            from .parsers.text_parser import TextParser
            from .parsers.docx_parser import DocxParser
            from .parsers.pdf_parser import PdfParser
            from .parsers.image_parser import ImageParser
            from .parsers.audio_parser import AudioParser
            from .parsers.pptx_parser import PptxParser
            if isinstance(p, TextParser):
                exts.update({".txt", ".md", ".csv"})
            elif isinstance(p, DocxParser):
                exts.add(".docx")
            elif isinstance(p, PdfParser):
                exts.add(".pdf")
            elif isinstance(p, ImageParser):
                exts.update({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"})
            elif isinstance(p, AudioParser):
                exts.update({".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mpga"})
            elif isinstance(p, PptxParser):
                exts.add(".pptx")
        return exts

    @property
    def parser_count(self) -> int:
        return len(self._parsers)


# Singleton
dispatcher = Dispatcher()
