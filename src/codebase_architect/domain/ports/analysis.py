"""Ports for static analysis: language detection, parsing and manifest scanning."""

from __future__ import annotations

from abc import ABC, abstractmethod

from codebase_architect.domain.model.code import Language, ParsedFile
from codebase_architect.domain.model.stack import Dependency, DetectedStack
from codebase_architect.domain.model.workspace import Workspace


class LanguageDetector(ABC):
    """Maps a file (by name/extension) to a :class:`Language`."""

    @abstractmethod
    def detect(self, relative_path: str) -> Language:
        """Return the language for ``relative_path`` (``Language.UNKNOWN`` if none)."""


class CodeParser(ABC):
    """Parses a source file into a :class:`ParsedFile`."""

    @abstractmethod
    def supports(self, language: Language) -> bool:
        """Whether this parser can extract symbols for ``language``."""

    @abstractmethod
    def parse(self, relative_path: str, language: Language, content: bytes) -> ParsedFile:
        """Parse ``content`` and return its symbols, imports and metadata."""


class ManifestDetector(ABC):
    """Detects technology stacks and dependencies from project manifests."""

    @abstractmethod
    def detect(self, workspace: Workspace) -> tuple[list[DetectedStack], list[Dependency]]:
        """Scan ``workspace`` manifests and return detected stacks and deps."""
