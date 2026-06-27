"""Workspace: a materialized, read-only copy of a codebase.

A workspace points at a local directory where a :class:`SourceProvider` has
already placed the codebase (cloned, copied or extracted). The rest of the
system reads from it; **nothing ever writes to it**.

File access helpers use only the standard library, so this entity is safe to
live in the domain layer.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from codebase_architect.domain.model.source import SourceType

# Directories that are never relevant to documentation analysis and are skipped
# while iterating files. ``.git`` is excluded from analysis even when present
# (a local-git import keeps it only to read the base ref). Build/output and this
# tool's own data dirs are included so a self-scan can't recurse into its output.
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
        ".tox",
        ".cache",
        "dist",
        "build",
        "target",
        ".next",
        "coverage",
        ".nyc_output",
        ".idea",
        ".gradle",
        "Pods",
        "workspaces",
        "docs-output",
    }
)

_GITIGNORE = ".gitignore"


@dataclass(frozen=True)
class Workspace:
    """A read-only, isolated copy of an imported codebase.

    Attributes:
        id: unique workspace id.
        root_path: absolute path to the materialized codebase.
        source_type: how the codebase was imported.
        has_git: whether a usable Git repository is present.
        base_ref: commit sha (Git sources) or a tree checksum (non-Git sources).
        use_gitignore: honor a root ``.gitignore`` while iterating files.
        exclude_globs: extra glob patterns to skip (path- or name-matched).
        include_globs: if non-empty, only files matching one of these are kept.
    """

    id: str
    root_path: Path
    source_type: SourceType
    has_git: bool = False
    base_ref: str | None = None
    ignored_dirs: frozenset[str] = field(default=DEFAULT_IGNORED_DIRS)
    use_gitignore: bool = True
    exclude_globs: tuple[str, ...] = ()
    include_globs: tuple[str, ...] = ()

    def iter_files(self) -> Iterator[Path]:
        """Yield every analyzable file path, skipping ignored directories."""
        rules = self._ignore_rules()
        yield from self._walk(self.root_path, rules)

    def _ignore_rules(self) -> _IgnoreRules:
        patterns: list[str] = []
        if self.use_gitignore:
            gitignore = self.root_path / _GITIGNORE
            try:
                if gitignore.is_file():
                    patterns.extend(
                        gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
                    )
            except OSError:
                pass
        patterns.extend(self.exclude_globs)
        return _IgnoreRules(patterns)

    def _walk(self, directory: Path, rules: _IgnoreRules) -> Iterator[Path]:
        for entry in sorted(directory.iterdir()):
            rel = entry.relative_to(self.root_path).as_posix()
            if entry.is_dir():
                if entry.name in self.ignored_dirs or rules.ignored(rel, is_dir=True):
                    continue
                yield from self._walk(entry, rules)
            elif entry.is_file():
                if rules.ignored(rel, is_dir=False):
                    continue
                if self.include_globs and not _match_any(rel, self.include_globs):
                    continue
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


def _match_any(rel_posix: str, globs: Iterable[str]) -> bool:
    base = rel_posix.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatchcase(rel_posix, g) or fnmatch.fnmatchcase(base, g) for g in globs)


class _IgnoreRules:
    """A pragmatic subset of ``.gitignore`` matching (plus extra exclude globs).

    Supports comments, blank lines, ``!`` negation, trailing-``/`` (directory
    only), leading-``/`` or embedded-``/`` (anchored to the root) and ``*``
    globbing. Last matching rule wins, mirroring Git's precedence. This is
    deliberately approximate — good enough to skip the obvious noise without
    pulling in a dependency.
    """

    def __init__(self, patterns: Iterable[str]) -> None:
        self._rules: list[tuple[str, bool, bool, bool]] = []
        for raw in patterns:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            negated = stripped.startswith("!")
            if negated:
                stripped = stripped[1:].strip()
            dir_only = stripped.endswith("/")
            stripped = stripped.rstrip("/")
            anchored = stripped.startswith("/") or "/" in stripped
            stripped = stripped.lstrip("/")
            if stripped:
                self._rules.append((stripped, negated, dir_only, anchored))

    def ignored(self, rel_posix: str, *, is_dir: bool) -> bool:
        result = False
        base = rel_posix.rsplit("/", 1)[-1]
        for pattern, negated, dir_only, anchored in self._rules:
            if dir_only and not is_dir:
                continue
            target = rel_posix if anchored else base
            if fnmatch.fnmatchcase(target, pattern):
                result = not negated
        return result
