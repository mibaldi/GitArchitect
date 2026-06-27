"""Tests for documentation building, rendering and exporting."""

from __future__ import annotations

from pathlib import Path

from codebase_architect.domain.model.architecture import Architecture, Component, Layer
from codebase_architect.domain.model.code import (
    ImportRef,
    Language,
    ParsedFile,
    Symbol,
    SymbolKind,
)
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.entrypoint import Entrypoint, EntrypointKind
from codebase_architect.domain.services.documentation_builder import build_documentation
from codebase_architect.domain.services.module_graph import build_module_graph
from codebase_architect.infrastructure.export.folder_exporter import FolderExporter
from codebase_architect.infrastructure.rendering.markdown_renderer import MarkdownMermaidRenderer


def _docs():
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "web/C.java",
                Language.JAVA,
                10,
                imports=(ImportRef("com.demo.service.S"),),
                package="com.demo.web",
            ),
            ParsedFile("svc/S.java", Language.JAVA, 8, package="com.demo.service"),
        ]
    )
    graph = build_module_graph(model)
    architecture = Architecture(
        components=[
            Component("com.demo.web", Layer.PRESENTATION, "keyword 'web'"),
            Component("com.demo.service", Layer.APPLICATION, "keyword 'service'"),
        ]
    )
    entrypoints = [
        Entrypoint("C", EntrypointKind.HTTP_ENDPOINT, "web/C.java", "com.demo.web", "Spring")
    ]
    return build_documentation(
        title="Demo",
        generated_at="2026-01-01T00:00:00+00:00",
        base_ref="abc123",
        model=model,
        graph=graph,
        architecture=architecture,
        entrypoints=entrypoints,
    )


def test_build_documentation_has_expected_pages() -> None:
    docs = build_documentation(
        title="Demo",
        generated_at="t",
        base_ref=None,
        model=CodeModel(),
        graph=build_module_graph(CodeModel()),
        architecture=Architecture(),
        entrypoints=[],
    )
    slugs = {p.slug for p in docs.pages}
    assert {
        "README",
        "architecture",
        "modules",
        "features",
        "entrypoints",
        "flows",
        "api",
        "dependencies",
        "security",
    } == slugs


def test_render_produces_markdown_with_mermaid() -> None:
    files = MarkdownMermaidRenderer().render(_docs())
    by_name = {f.path: f.content for f in files}
    assert "architecture.md" in by_name
    assert "```mermaid" in by_name["architecture.md"]
    assert "n0 -->" in by_name["architecture.md"] or "-->" in by_name["architecture.md"]
    # README carries the navigation to the other pages.
    assert "[Architecture](architecture.md)" in by_name["README.md"]
    assert "Demo" in by_name["README.md"]


def test_export_writes_files(tmp_path: Path) -> None:
    files = MarkdownMermaidRenderer().render(_docs())
    bundle = FolderExporter().export(files, tmp_path / "docs")
    written = {p.name for p in (tmp_path / "docs").iterdir()}
    assert "README.md" in written
    assert len(bundle.files) == len(files)
    assert (tmp_path / "docs" / "README.md").read_text(encoding="utf-8").startswith("# Demo")


def test_determinism_same_inputs_same_output() -> None:
    a = MarkdownMermaidRenderer().render(_docs())
    b = MarkdownMermaidRenderer().render(_docs())
    assert [f.content for f in a] == [f.content for f in b]


def test_narrative_is_woven_into_documentation() -> None:
    from codebase_architect.domain.model.feature import Feature
    from codebase_architect.domain.model.narrative import NarrativeReport

    model = CodeModel(parsed_files=[ParsedFile("svc/S.java", Language.JAVA, 8, package="com.demo")])
    graph = build_module_graph(model)
    narrative = NarrativeReport(
        overview="This service greets people.",
        features=[Feature("Greeting", "Returns a greeting.", ("com.demo",))],
        flows={"C": "Request flows to the service."},
    )
    docs = build_documentation(
        title="Demo",
        generated_at="t",
        base_ref=None,
        model=model,
        graph=graph,
        architecture=Architecture(),
        entrypoints=[],
        narrative=narrative,
    )
    by_slug = {p.slug: p for p in docs.pages}
    assert "features" in by_slug
    files = {f.path: f.content for f in MarkdownMermaidRenderer().render(docs)}
    assert "This service greets people." in files["README.md"]
    assert "Greeting" in files["features.md"]
    assert "Returns a greeting." in files["features.md"]


def test_features_page_derives_static_catalog_without_narrative() -> None:
    docs = build_documentation(
        title="Demo",
        generated_at="t",
        base_ref=None,
        model=CodeModel(),
        graph=build_module_graph(CodeModel()),
        architecture=Architecture(),
        entrypoints=[
            Entrypoint("GreetController", EntrypointKind.HTTP_ENDPOINT, "web/G.java", "web"),
        ],
        narrative=None,
    )
    files = {f.path: f.content for f in MarkdownMermaidRenderer().render(docs)}
    body = files["features.md"]
    # Static catalog is present and clearly labelled as derived without AI.
    assert "HTTP API" in body
    assert "_(static)_" in body
    assert "Derived statically" in body


def test_flows_are_transitive_across_modules() -> None:
    # web -> service (import) and service -> repo (call) should both appear in
    # the flow traced from the web entrypoint.
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "web/C.java",
                Language.JAVA,
                5,
                symbols=(Symbol("C", SymbolKind.CLASS, 1, 4),),
                imports=(ImportRef("com.demo.service.S"),),
                package="com.demo.web",
            ),
            ParsedFile(
                "service/S.java",
                Language.JAVA,
                5,
                symbols=(Symbol("S", SymbolKind.CLASS, 1, 4),),
                calls=("Repo",),
                package="com.demo.service",
            ),
            ParsedFile(
                "repo/Repo.java",
                Language.JAVA,
                5,
                symbols=(Symbol("Repo", SymbolKind.CLASS, 1, 4),),
                package="com.demo.repo",
            ),
        ]
    )
    docs = build_documentation(
        title="Demo",
        generated_at="t",
        base_ref=None,
        model=model,
        graph=build_module_graph(model),
        architecture=Architecture(),
        entrypoints=[Entrypoint("C", EntrypointKind.HTTP_ENDPOINT, "web/C.java", "com.demo.web")],
        narrative=None,
    )
    flows = {f.path: f.content for f in MarkdownMermaidRenderer().render(docs)}["flows.md"]
    assert "com.demo.service" in flows
    assert "com.demo.repo" in flows  # reached transitively via the call edge
