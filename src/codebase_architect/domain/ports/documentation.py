"""Ports for rendering and exporting documentation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from codebase_architect.domain.model.documentation import (
    Documentation,
    DocumentationBundle,
    RenderedFile,
)


class DocRenderer(ABC):
    """Turns the format-agnostic Documentation IR into concrete files."""

    @abstractmethod
    def render(self, documentation: Documentation) -> list[RenderedFile]:
        """Render every page to one or more output files."""


class DocExporter(ABC):
    """Writes rendered files to a destination."""

    @abstractmethod
    def export(self, files: list[RenderedFile], dest: Path) -> DocumentationBundle:
        """Persist ``files`` under ``dest`` and return the resulting bundle."""
