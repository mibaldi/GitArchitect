"""ScanPipeline: import → static analysis → architecture → documentation.

This is the single entrypoint both the CLI and (later) the API drive. The AI
narrative pass plugs in between analysis and documentation in a later phase; the
pipeline already produces a complete static documentation bundle without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codebase_architect.application.use_cases.build_code_model import BuildCodeModelUseCase
from codebase_architect.application.use_cases.import_source import ImportSourceUseCase
from codebase_architect.domain.model.architecture import Architecture
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.documentation import Documentation, DocumentationBundle
from codebase_architect.domain.model.entrypoint import Entrypoint
from codebase_architect.domain.model.module import ModuleGraph
from codebase_architect.domain.model.workspace import Workspace
from codebase_architect.domain.ports.documentation import DocExporter, DocRenderer
from codebase_architect.domain.services.architecture_inference import infer_architecture
from codebase_architect.domain.services.documentation_builder import build_documentation
from codebase_architect.domain.services.entrypoints import detect_entrypoints
from codebase_architect.domain.services.module_graph import build_module_graph


@dataclass
class ScanResult:
    """Everything a scan produced."""

    workspace: Workspace
    code_model: CodeModel
    module_graph: ModuleGraph
    architecture: Architecture
    entrypoints: list[Entrypoint]
    documentation: Documentation
    bundle: DocumentationBundle | None = None


class ScanPipeline:
    """Coordinates the use cases and domain services into one scan."""

    def __init__(
        self,
        importer: ImportSourceUseCase,
        model_builder: BuildCodeModelUseCase,
        renderer: DocRenderer,
        exporter: DocExporter,
    ) -> None:
        self._importer = importer
        self._model_builder = model_builder
        self._renderer = renderer
        self._exporter = exporter

    def run(
        self,
        location: str,
        *,
        project_title: str,
        generated_at: str,
        out_dir: Path | None,
    ) -> ScanResult:
        workspace = self._importer.execute(location)
        model = self._model_builder.execute(workspace)
        graph = build_module_graph(model)
        architecture = infer_architecture(graph)
        entrypoints = detect_entrypoints(model)
        documentation = build_documentation(
            title=project_title,
            generated_at=generated_at,
            base_ref=workspace.base_ref,
            model=model,
            graph=graph,
            architecture=architecture,
            entrypoints=entrypoints,
        )

        bundle: DocumentationBundle | None = None
        if out_dir is not None:
            files = self._renderer.render(documentation)
            bundle = self._exporter.export(files, out_dir)

        return ScanResult(
            workspace=workspace,
            code_model=model,
            module_graph=graph,
            architecture=architecture,
            entrypoints=entrypoints,
            documentation=documentation,
            bundle=bundle,
        )
