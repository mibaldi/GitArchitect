"""Render the Documentation IR to Markdown files with embedded Mermaid."""

from __future__ import annotations

from codebase_architect.domain.model.documentation import (
    DocPage,
    DocSection,
    Documentation,
    RenderedFile,
)
from codebase_architect.domain.ports.documentation import DocRenderer
from codebase_architect.domain.services.doc_strings import doc_strings

_INDEX_SLUG = "README"


class MarkdownMermaidRenderer(DocRenderer):
    """Produces one Markdown file per page; Mermaid is embedded as fenced code."""

    def render(self, documentation: Documentation) -> list[RenderedFile]:
        nav = [(page.slug, page.title) for page in documentation.pages]
        strings = doc_strings(documentation.language)
        return [
            RenderedFile(path=f"{page.slug}.md", content=self._render_page(page, nav, strings))
            for page in documentation.pages
        ]

    def _render_page(
        self, page: DocPage, nav: list[tuple[str, str]], strings: dict[str, str]
    ) -> str:
        parts = [f"# {page.title}", ""]
        for section in page.sections:
            parts.append(self._render_section(section))
        if page.slug == _INDEX_SLUG:
            parts.append(self._render_nav(page.slug, nav, strings))
        return "\n".join(p for p in parts if p is not None).rstrip() + "\n"

    def _render_section(self, section: DocSection) -> str:
        block: list[str] = []
        if section.heading:
            block.append(f"## {section.heading}")
            block.append("")
        if section.body:
            block.append(section.body)
            block.append("")
        if section.diagram is not None:
            block.append("```mermaid")
            block.append(section.diagram.code)
            block.append("```")
            block.append("")
        return "\n".join(block)

    def _render_nav(
        self, current: str, nav: list[tuple[str, str]], strings: dict[str, str]
    ) -> str:
        links = [
            f"- [{title}]({slug}.md)" for slug, title in nav if slug != current
        ]
        if not links:
            return ""
        return f"## {strings['heading_pages']}\n\n" + "\n".join(links) + "\n"
