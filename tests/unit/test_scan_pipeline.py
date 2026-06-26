"""End-to-end test of the ScanPipeline over a real folder."""

from __future__ import annotations

from pathlib import Path

from codebase_architect.application.pipeline.scan_pipeline import ScanPipeline
from codebase_architect.application.registries.source_resolver import SourceProviderResolver
from codebase_architect.application.use_cases.build_code_model import BuildCodeModelUseCase
from codebase_architect.application.use_cases.import_source import ImportSourceUseCase
from codebase_architect.domain.model.entrypoint import EntrypointKind
from codebase_architect.infrastructure.detection.language_detector import ExtensionLanguageDetector
from codebase_architect.infrastructure.detection.manifest_detector import CompositeManifestDetector
from codebase_architect.infrastructure.export.folder_exporter import FolderExporter
from codebase_architect.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from codebase_architect.infrastructure.rendering.markdown_renderer import MarkdownMermaidRenderer
from codebase_architect.infrastructure.source_providers import default_source_providers


def _pipeline(workspaces: Path) -> ScanPipeline:
    return ScanPipeline(
        importer=ImportSourceUseCase(
            resolver=SourceProviderResolver(default_source_providers()),
            workspaces_dir=workspaces,
        ),
        model_builder=BuildCodeModelUseCase(
            language_detector=ExtensionLanguageDetector(),
            parser=TreeSitterParser(),
            manifest_detector=CompositeManifestDetector(),
        ),
        renderer=MarkdownMermaidRenderer(),
        exporter=FolderExporter(),
    )


def _spring_project(root: Path) -> None:
    web = root / "src/main/java/com/demo/web"
    svc = root / "src/main/java/com/demo/service"
    web.mkdir(parents=True)
    svc.mkdir(parents=True)
    (web / "GreetController.java").write_text(
        "package com.demo.web;\n"
        "import org.springframework.web.bind.annotation.RestController;\n"
        "import com.demo.service.GreeterService;\n"
        "public class GreetController { }\n",
        encoding="utf-8",
    )
    (svc / "GreeterService.java").write_text(
        "package com.demo.service;\npublic class GreeterService { }\n",
        encoding="utf-8",
    )


def test_pipeline_generates_documentation(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _spring_project(project)

    result = _pipeline(tmp_path / "ws").run(
        str(project),
        project_title="Demo",
        generated_at="2026-01-01T00:00:00+00:00",
        out_dir=tmp_path / "docs",
    )

    # Module graph captured the internal web -> service dependency.
    edges = {(e.source, e.target) for e in result.module_graph.edges}
    assert ("com.demo.web", "com.demo.service") in edges

    # Spring controller detected as an HTTP entrypoint.
    assert any(e.kind is EntrypointKind.HTTP_ENDPOINT for e in result.entrypoints)

    # Documentation bundle written to disk with the expected pages.
    assert result.bundle is not None
    written = {f.path for f in result.bundle.files}
    assert {"README.md", "architecture.md", "modules.md"} <= written
    architecture_md = (tmp_path / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "```mermaid" in architecture_md


def test_pipeline_without_out_dir_skips_writing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _spring_project(project)
    result = _pipeline(tmp_path / "ws").run(
        str(project),
        project_title="Demo",
        generated_at="t",
        out_dir=None,
    )
    assert result.bundle is None
    assert result.documentation.pages  # IR still built
