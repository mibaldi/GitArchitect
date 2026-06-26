"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def sample_codebase(tmp_path: Path) -> Path:
    """Create a small, representative codebase tree and return its root."""
    root = tmp_path / "sample"
    (root / "src").mkdir(parents=True)
    (root / "README.md").write_text("# Sample\n", encoding="utf-8")
    (root / "src" / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (root / "src" / "util.py").write_text("X = 42\n", encoding="utf-8")
    # A directory that must be ignored during analysis.
    (root / "node_modules").mkdir()
    (root / "node_modules" / "junk.js").write_text("// noise\n", encoding="utf-8")
    return root


def _make_fake_git(repo_root: Path, sha: str = "a" * 40, branch: str = "main") -> None:
    git = repo_root / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    (git / "refs" / "heads" / branch).write_text(f"{sha}\n", encoding="utf-8")


@pytest.fixture
def make_fake_git() -> Callable[[Path], None]:
    """Return a helper that lays down a minimal ``.git`` in a directory."""
    return _make_fake_git
