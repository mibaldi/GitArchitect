"""Import a ``.zip`` archive."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import ClassVar

from codebase_architect.domain.model.source import SourceLocation, SourceType
from codebase_architect.domain.model.workspace import DEFAULT_IGNORED_DIRS, Workspace
from codebase_architect.domain.ports.source_provider import SourceProvider
from codebase_architect.domain.services.tree_checksum import compute_tree_checksum
from codebase_architect.infrastructure.source_providers._common import assert_within
from codebase_architect.shared.errors import ValidationError
from codebase_architect.shared.ids import new_id


class ZipSourceProvider(SourceProvider):
    """Materializes a Zip archive by extracting it into the workspace."""

    source_type: ClassVar[SourceType] = SourceType.ZIP

    def supports(self, location: SourceLocation) -> bool:
        path = Path(location.raw)
        if not path.is_file():
            return False
        return path.suffix.lower() == ".zip" or zipfile.is_zipfile(path)

    def fetch(self, location: SourceLocation, dest: Path) -> Workspace:
        path = Path(location.raw)
        if not zipfile.is_zipfile(path):
            raise ValidationError(f"Not a valid zip archive: {location.raw}")
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                assert_within(dest, dest / member)
            archive.extractall(dest)
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
    """If the archive wrapped everything in a single top dir, use it as root."""
    entries = [p for p in dest.iterdir() if not p.name.startswith("__MACOSX")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest
