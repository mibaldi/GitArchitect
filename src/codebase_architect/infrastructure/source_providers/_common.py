"""Shared helpers for source provider adapters."""

from __future__ import annotations

import shutil
from pathlib import Path

from codebase_architect.shared.errors import ValidationError


def copy_tree(src: Path, dest: Path, ignore: frozenset[str] = frozenset()) -> None:
    """Copy ``src`` into ``dest``, skipping top-level-ignored directory names."""

    def _ignore(_dir: str, names: list[str]) -> set[str]:
        return {n for n in names if n in ignore}

    shutil.copytree(src, dest, ignore=_ignore, dirs_exist_ok=True, symlinks=True)


def read_git_head_sha(repo_root: Path) -> str | None:
    """Best-effort read of the current commit sha without invoking ``git``.

    Returns None when the repository layout is unusual (worktrees, missing refs)
    so callers can degrade gracefully.
    """
    git_dir = repo_root / ".git"
    if not git_dir.is_dir():
        return None

    head = git_dir / "HEAD"
    if not head.is_file():
        return None

    content = head.read_text(encoding="utf-8").strip()
    if not content.startswith("ref:"):
        # Detached HEAD: the file already contains the sha.
        return content or None

    ref = content[len("ref:") :].strip()
    loose = git_dir / ref
    if loose.is_file():
        return loose.read_text(encoding="utf-8").strip() or None

    # Fall back to packed-refs.
    packed = git_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "^")):
                continue
            sha, _, name = line.partition(" ")
            if name == ref:
                return sha
    return None


def assert_within(base: Path, target: Path) -> None:
    """Guard against path traversal (zip/tar slip)."""
    base_resolved = base.resolve()
    target_resolved = target.resolve()
    if base_resolved != target_resolved and base_resolved not in target_resolved.parents:
        raise ValidationError(f"Unsafe archive path escapes destination: {target}")
