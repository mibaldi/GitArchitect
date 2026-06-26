"""Deterministic checksum of a directory tree.

Used as the ``base_ref`` for non-Git sources (folder, zip, tar.gz), giving the
generated documentation a stable, traceable identifier for the exact bytes that
were analyzed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def compute_tree_checksum(root: Path, ignored_dirs: frozenset[str] = frozenset()) -> str:
    """Return a hex SHA-256 over the tree's relative paths and file contents.

    The result is independent of filesystem iteration order, so the same tree
    always yields the same checksum.
    """
    digest = hashlib.sha256()
    files = sorted(
        (p for p in _walk(root, ignored_dirs) if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    for path in files:
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _walk(directory: Path, ignored_dirs: frozenset[str]) -> list[Path]:
    result: list[Path] = []
    for entry in directory.iterdir():
        if entry.is_dir():
            if entry.name in ignored_dirs:
                continue
            result.extend(_walk(entry, ignored_dirs))
        else:
            result.append(entry)
    return result
