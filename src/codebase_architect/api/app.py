"""FastAPI application factory (composition root for the REST driver).

FastAPI/Uvicorn are optional (the ``api`` extra). The scan state is held in
memory by :class:`ScanService`; moving to Redis/Arq workers and a database
repository later is a swap behind the same service interface.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from codebase_architect.api.routes import router
from codebase_architect.application.pipeline.scan_pipeline import ScanPipeline
from codebase_architect.application.registries.source_resolver import SourceProviderResolver
from codebase_architect.application.services.scan_service import ScanService
from codebase_architect.application.services.spec_service import SpecService
from codebase_architect.application.use_cases.build_code_model import BuildCodeModelUseCase
from codebase_architect.application.use_cases.import_source import ImportSourceUseCase
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.infrastructure.cache.file_narrative_cache import FileNarrativeCache
from codebase_architect.infrastructure.detection.language_detector import ExtensionLanguageDetector
from codebase_architect.infrastructure.detection.manifest_detector import CompositeManifestDetector
from codebase_architect.infrastructure.export.folder_exporter import FolderExporter
from codebase_architect.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from codebase_architect.infrastructure.persistence.file_scan_store import FileScanStore
from codebase_architect.infrastructure.persistence.file_spec_store import FileSpecStore
from codebase_architect.infrastructure.rendering.markdown_renderer import MarkdownMermaidRenderer
from codebase_architect.infrastructure.security.secret_scanner import RegexSecretScanner
from codebase_architect.infrastructure.source_providers import default_source_providers
from codebase_architect.shared.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    workspaces_dir = Path(settings.workspaces_dir)
    artifacts_dir = Path(settings.data_dir) / "scans"
    narrative_cache = (
        FileNarrativeCache(Path(settings.data_dir) / "cache" / "narrative")
        if settings.ai.cache_enabled
        else None
    )

    def build_pipeline(ai_provider: AIProvider) -> ScanPipeline:
        return ScanPipeline(
            importer=ImportSourceUseCase(
                resolver=SourceProviderResolver(default_source_providers()),
                workspaces_dir=workspaces_dir,
            ),
            model_builder=BuildCodeModelUseCase(
                language_detector=ExtensionLanguageDetector(),
                parser=TreeSitterParser(),
                manifest_detector=CompositeManifestDetector(),
            ),
            renderer=MarkdownMermaidRenderer(),
            exporter=FolderExporter(),
            ai_provider=ai_provider,
            secret_scanner=RegexSecretScanner(),
            narrative_cache=narrative_cache,
            ai_max_tokens=settings.ai.max_tokens,
        )

    app = FastAPI(
        title="Codebase Architect",
        version="0.0.0",
        summary="Scan any codebase and generate clean architecture documentation.",
    )
    store = FileScanStore(Path(settings.data_dir) / "scan-records")
    app.state.scan_service = ScanService(build_pipeline, artifacts_dir, store=store)
    app.state.spec_service = SpecService(FileSpecStore(Path(settings.data_dir) / "specs"))
    app.include_router(router)
    return app
