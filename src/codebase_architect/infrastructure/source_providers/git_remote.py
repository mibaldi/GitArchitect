"""Import a remote Git repository via ``git clone``.

This is the only provider that needs an external tool. When ``git`` is not
available it raises :class:`CapabilityUnavailableError` so the rest of the
system keeps working for non-Git sources.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import ClassVar

from codebase_architect.domain.model.source import SourceLocation, SourceType
from codebase_architect.domain.model.workspace import Workspace
from codebase_architect.domain.ports.source_provider import SourceProvider
from codebase_architect.infrastructure.source_providers._common import read_git_head_sha
from codebase_architect.shared.errors import CapabilityUnavailableError
from codebase_architect.shared.ids import new_id

_REMOTE_PREFIXES = ("git@", "git://", "ssh://")


class GitRemoteSourceProvider(SourceProvider):
    """Clones a remote Git repository into the workspace."""

    source_type: ClassVar[SourceType] = SourceType.GIT_REMOTE

    def __init__(self, *, depth: int = 1) -> None:
        self._depth = depth

    def supports(self, location: SourceLocation) -> bool:
        raw = location.raw.strip()
        if raw.startswith(_REMOTE_PREFIXES):
            return True
        return raw.startswith(("http://", "https://")) and raw.endswith(".git")

    def fetch(self, location: SourceLocation, dest: Path) -> Workspace:
        git = shutil.which("git")
        if git is None:
            raise CapabilityUnavailableError(
                "Importing a remote Git repository requires the 'git' binary, which "
                "is not available. Use a local folder, zip or tar.gz instead."
            )
        cmd = [git, "clone", "--depth", str(self._depth), location.raw, str(dest)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise CapabilityUnavailableError(
                f"git clone failed for {location.raw}:\n{result.stderr.strip()}"
            )
        sha = read_git_head_sha(dest)
        # Drop the .git directory: analysis is read-only and never needs history.
        git_dir = dest / ".git"
        if git_dir.is_dir():
            shutil.rmtree(git_dir, ignore_errors=True)
        return Workspace(
            id=new_id("ws"),
            root_path=dest,
            source_type=self.source_type,
            has_git=True,
            base_ref=sha,
        )
