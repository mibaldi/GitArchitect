"""Import a local Git repository.

The working tree is copied (excluding ``.git``); the commit sha is read directly
from the original ``.git`` metadata, so no ``git`` binary is required.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from codebase_architect.domain.model.source import SourceLocation, SourceType
from codebase_architect.domain.model.workspace import DEFAULT_IGNORED_DIRS, Workspace
from codebase_architect.domain.ports.source_provider import SourceProvider
from codebase_architect.domain.services.tree_checksum import compute_tree_checksum
from codebase_architect.infrastructure.source_providers._common import (
    copy_tree,
    read_git_head_sha,
)
from codebase_architect.shared.ids import new_id


class LocalGitSourceProvider(SourceProvider):
    """Materializes a local directory that contains a ``.git`` repository."""

    source_type: ClassVar[SourceType] = SourceType.LOCAL_GIT

    def supports(self, location: SourceLocation) -> bool:
        path = Path(location.raw)
        return path.is_dir() and (path / ".git").exists()

    def fetch(self, location: SourceLocation, dest: Path) -> Workspace:
        src = Path(location.raw)
        sha = read_git_head_sha(src)
        copy_tree(src, dest, ignore=DEFAULT_IGNORED_DIRS)
        base_ref = sha or compute_tree_checksum(dest, DEFAULT_IGNORED_DIRS)
        return Workspace(
            id=new_id("ws"),
            root_path=dest,
            source_type=self.source_type,
            has_git=sha is not None,
            base_ref=base_ref,
        )
