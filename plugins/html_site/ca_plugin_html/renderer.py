"""HtmlSiteRenderer: render the Documentation IR to a single static HTML page."""

from __future__ import annotations

import html

from ca_plugin_html.markdown import markdown_to_html
from codebase_architect.domain.model.documentation import (
    DocPage,
    DocSection,
    Documentation,
    RenderedFile,
)
from codebase_architect.domain.ports.documentation import DocRenderer

_MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs"

_STYLE = """
:root { color-scheme: light dark; }
body { font: 16px/1.6 system-ui, sans-serif; max-width: 960px; margin: 2rem auto;
       padding: 0 1rem; }
nav { position: sticky; top: 0; background: Canvas; padding: .5rem 0;
      border-bottom: 1px solid #8884; margin-bottom: 1rem; }
nav a { margin-right: 1rem; }
section { margin-bottom: 2.5rem; }
table { border-collapse: collapse; }
th, td { border: 1px solid #8884; padding: .3rem .6rem; text-align: left; }
code { background: #8882; padding: .1rem .3rem; border-radius: 3px; }
.mermaid { background: #8881; padding: 1rem; border-radius: 6px; }
"""


class HtmlSiteRenderer(DocRenderer):
    """Renders all documentation pages into one browsable ``index.html``."""

    def render(self, documentation: Documentation) -> list[RenderedFile]:
        nav = " ".join(
            f'<a href="#{page.slug}">{html.escape(page.title)}</a>'
            for page in documentation.pages
        )
        body = "\n".join(self._page(page) for page in documentation.pages)
        page = (
            "<!doctype html>\n<html lang=\"en\">\n<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{html.escape(documentation.title)}</title>\n"
            f"<style>{_STYLE}</style>\n"
            f'<script type="module">import mermaid from "{_MERMAID_CDN}";'
            "mermaid.initialize({startOnLoad:true});</script>\n"
            "</head>\n<body>\n"
            f"<h1>{html.escape(documentation.title)}</h1>\n"
            f"<nav>{nav}</nav>\n{body}\n</body>\n</html>\n"
        )
        return [RenderedFile(path="index.html", content=page)]

    def _page(self, page: DocPage) -> str:
        parts = [f'<section id="{page.slug}">', f"<h2>{html.escape(page.title)}</h2>"]
        for section in page.sections:
            parts.append(self._section(section))
        parts.append("</section>")
        return "\n".join(parts)

    def _section(self, section: DocSection) -> str:
        parts: list[str] = []
        if section.heading:
            parts.append(f"<h3>{html.escape(section.heading)}</h3>")
        if section.body:
            parts.append(markdown_to_html(section.body))
        if section.diagram is not None:
            parts.append(f'<pre class="mermaid">{html.escape(section.diagram.code)}</pre>')
        return "\n".join(parts)
