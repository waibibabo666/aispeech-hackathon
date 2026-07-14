"""Abstract base class for all file parsers."""

from abc import ABC, abstractmethod
from pathlib import Path


class BaseParser(ABC):
    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """Return True if this parser can handle the given file."""
        ...

    @abstractmethod
    def parse(self, file_path: Path) -> str:
        """Extract text content from the file."""
        ...
