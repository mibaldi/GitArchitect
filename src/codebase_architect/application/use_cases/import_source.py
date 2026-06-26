"""Use case: import a codebase into an isolated, read-only workspace."""

from __future__ import annotations

from pathlib import Path

from codebase_architect.application.registries.source_resolver import SourceProviderResolver
from codebase_architect.domain.model.source import SourceLocation
from codebase_architect.domain.model.workspace import Workspace
from codebase_architect.shared.ids import new_id
from codebase_architect.shared.logging import get_logger

logger = get_logger(__name__)


class ImportSourceUseCase:
    """Resolves a location, materializes it and returns the Workspace.

    The workspace is created under ``workspaces_dir`` in a fresh, unique
    subdirectory so concurrent imports never collide.
    """

    def __init__(self, resolver: SourceProviderResolver, workspaces_dir: Path) -> None:
        self._resolver = resolver
        self._workspaces_dir = workspaces_dir

    def execute(self, raw_location: str) -> Workspace:
        location = SourceLocation(raw=raw_location)
        provider = self._resolver.resolve(location)
        dest = self._workspaces_dir / new_id()
        dest.mkdir(parents=True, exist_ok=True)

        logger.info(
            "importing_source",
            location=location.raw,
            provider=type(provider).__name__,
            source_type=provider.source_type.value,
            dest=str(dest),
        )
        workspace = provider.fetch(location, dest)
        logger.info(
            "source_imported",
            workspace_id=workspace.id,
            has_git=workspace.has_git,
            base_ref=workspace.base_ref,
        )
        return workspace
