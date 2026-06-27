"""Tests for the example HtmlSiteRenderer plugin.

Skipped when the plugin is not installed (``pip install -e plugins/html_site``).
CI installs it so the entry-point discovery path is exercised end to end.
"""

from __future__ import annotations

import pytest

pytest.importorskip("ca_plugin_html")

from ca_plugin_html.markdown import markdown_to_html  # noqa: E402
from ca_plugin_html.renderer import HtmlSiteRenderer  # noqa: E402

from codebase_architect.application.registries.renderer_registry import build_renderer  # noqa: E402
from codebase_architect.domain.model.documentation import (  # noqa: E402
    DocPage,
    DocSection,
    Documentation,
    MermaidDiagram,
)


def test_markdown_subset_conversion() -> None:
    md = (
        "## Heading\n\n- one\n- two\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n"
        "See **bold** and `code`."
    )
    html = markdown_to_html(md)
    assert "<h3>Heading</h3>" in html
    assert "<ul><li>one</li><li>two</li></ul>" in html
    assert "<table>" in html and "<td>1</td>" in html
    assert "<strong>bold</strong>" in html and "<code>code</code>" in html


def test_md_links_become_in_page_anchors() -> None:
    html = markdown_to_html("[Architecture](architecture.md)")
    assert '<a href="#architecture">Architecture</a>' in html


def test_renderer_emits_single_html_with_mermaid() -> None:
    docs = Documentation(
        title="Demo",
        generated_at="t",
        base_ref=None,
        pages=(
            DocPage(
                slug="architecture",
                title="Architecture",
                sections=(
                    DocSection(
                        heading="Graph",
                        diagram=MermaidDiagram("g", "flowchart LR\n a-->b"),
                    ),
                ),
            ),
        ),
    )
    files = HtmlSiteRenderer().render(docs)
    assert len(files) == 1
    assert files[0].path == "index.html"
    content = files[0].content
    assert "<title>Demo</title>" in content
    assert 'class="mermaid"' in content
    assert 'href="#architecture"' in content


def test_plugin_is_resolved_by_the_registry() -> None:
    assert isinstance(build_renderer("html"), HtmlSiteRenderer)
