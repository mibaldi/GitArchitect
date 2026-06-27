"""Import a ``.tar.gz`` / ``.tgz`` archive."""

from __future__ import annotations

import tarfile
from pathlib import Path
from typing import ClassVar

from codebase_architect.domain.model.source import SourceLocation, SourceType
from codebase_architect.domain.model.workspace import DEFAULT_IGNORED_DIRS, Workspace
from codebase_architect.domain.ports.source_provider import SourceProvider
from codebase_architect.domain.services.tree_checksum import compute_tree_checksum
from codebase_architect.infrastructure.source_providers._common import assert_within
from codebase_architect.shared.errors import ValidationError
from codebase_architect.shared.ids import new_id

_SUFFIXES = (".tar.gz", ".tgz", ".tar")


class TarGzSourceProvider(SourceProvider):
    """Materializes a (gzipped) tar archive by extracting it into the workspace."""

    source_type: ClassVar[SourceType] = SourceType.TARGZ

    def supports(self, location: SourceLocation) -> bool:
        path = Path(location.raw)
        if not path.is_file():
            return False
        name = path.name.lower()
        if name.endswith(_SUFFIXES):
            return True
        return tarfile.is_tarfile(path)

    def fetch(self, location: SourceLocation, dest: Path) -> Workspace:
        path = Path(location.raw)
        if not tarfile.is_tarfile(path):
            raise ValidationError(f"Not a valid tar archive: {location.raw}")
        with tarfile.open(path) as archive:
            for member in archive.getmembers():
                assert_within(dest, dest / member.name)
            archive.extractall(dest, filter="data")
        root = _collapse_single_root(dest)
        checksum = compute_tree_checksum(root, DEFAULT_IGNORED_DIRS)
        return Workspace(
            id=new_id("ws"),
            root_path=root,
            source_type=self.source_type,
            has_git=False,
            base_ref=checksum,
        )


def _collapse_single_root(dest: Path) -> Path:
    entries = list(dest.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest
