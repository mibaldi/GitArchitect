"""Documentation intermediate representation (format-agnostic).

A :class:`Documentation` is a set of pages, each composed of sections that hold
Markdown text and/or a Mermaid diagram. Renderers (Markdown today, HTML later)
turn this IR into concrete files, so the structure stays independent of the
output format.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MermaidDiagram:
    """A Mermaid diagram (source only, no code fences)."""

    title: str
    code: str


@dataclass(frozen=True)
class DocSection:
    """A heading with optional Markdown body and/or a diagram."""

    heading: str | None = None
    body: str = ""
    diagram: MermaidDiagram | None = None


@dataclass(frozen=True)
class DocPage:
    """A single documentation page."""

    slug: str  # file name without extension, e.g. "architecture"
    title: str
    sections: tuple[DocSection, ...] = ()


@dataclass(frozen=True)
class Documentation:
    """The full set of generated documentation pages."""

    title: str
    generated_at: str
    base_ref: str | None
    pages: tuple[DocPage, ...] = ()


@dataclass(frozen=True)
class RenderedFile:
    """A concrete output file produced by a renderer."""

    path: str  # relative path, e.g. "architecture.md"
    content: str


@dataclass
class DocumentationBundle:
    """A rendered documentation bundle and where it was written."""

    root: str
    files: list[RenderedFile] = field(default_factory=list)
