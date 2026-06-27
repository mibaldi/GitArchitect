"""Workspace: a materialized, read-only copy of a codebase.

A workspace points at a local directory where a :class:`SourceProvider` has
already placed the codebase (cloned, copied or extracted). The rest of the
system reads from it; **nothing ever writes to it**.

File access helpers use only the standard library, so this entity is safe to
live in the domain layer.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from codebase_architect.domain.model.source import SourceType

# Directories that are never relevant to documentation analysis and are skipped
# while iterating files. ``.git`` is excluded from analysis even when present
# (a local-git import keeps it only to read the base ref).
DEFAULT_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".idea",
        ".gradle",
        "Pods",
    }
)


@dataclass(frozen=True)
class Workspace:
    """A read-only, isolated copy of an imported codebase.

    Attributes:
        id: unique workspace id.
        root_path: absolute path to the materialized codebase.
        source_type: how the codebase was imported.
        has_git: whether a usable Git repository is present.
        base_ref: commit sha (Git sources) or a tree checksum (non-Git sources).
    """

    id: str
    root_path: Path
    source_type: SourceType
    has_git: bool = False
    base_ref: str | None = None
    ignored_dirs: frozenset[str] = field(default=DEFAULT_IGNORED_DIRS)

    def iter_files(self) -> Iterator[Path]:
        """Yield every analyzable file path, skipping ignored directories."""
        yield from self._walk(self.root_path)

    def _walk(self, directory: Path) -> Iterator[Path]:
        for entry in sorted(directory.iterdir()):
            if entry.is_dir():
                if entry.name in self.ignored_dirs:
                    continue
                yield from self._walk(entry)
            elif entry.is_file():
                yield entry

    def relative(self, path: Path) -> str:
        """Return ``path`` as a POSIX-style string relative to the root."""
        return path.relative_to(self.root_path).as_posix()

    def read_text(self, relative_path: str, encoding: str = "utf-8") -> str:
        return (self.root_path / relative_path).read_text(encoding=encoding)

    def read_bytes(self, relative_path: str) -> bytes:
        return (self.root_path / relative_path).read_bytes()

    def exists(self, relative_path: str) -> bool:
        return (self.root_path / relative_path).exists()
