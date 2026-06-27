"""Tests for Workspace file iteration: .gitignore, default dirs and globs."""

from __future__ import annotations

from pathlib import Path

from codebase_architect.domain.model.source import SourceType
from codebase_architect.domain.model.workspace import Workspace
from codebase_architect.shared.ids import new_id


def _ws(root: Path, **kw: object) -> Workspace:
    return Workspace(id=new_id("ws"), root_path=root, source_type=SourceType.FOLDER, **kw)


def _rels(ws: Workspace) -> set[str]:
    return {ws.relative(p) for p in ws.iter_files()}


def _touch(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")


def test_gitignore_is_honored(tmp_path: Path) -> None:
    _touch(tmp_path, "src/app.py")
    _touch(tmp_path, "secret.env")
    _touch(tmp_path, "logs/run.log")
    _touch(tmp_path, "keep/run.log")
    (tmp_path / ".gitignore").write_text("*.env\nlogs/\n", encoding="utf-8")

    rels = _rels(_ws(tmp_path))
    assert "src/app.py" in rels
    assert "keep/run.log" in rels  # only the anchored logs/ dir is excluded
    assert "secret.env" not in rels
    assert "logs/run.log" not in rels


def test_gitignore_negation(tmp_path: Path) -> None:
    _touch(tmp_path, "a.log")
    _touch(tmp_path, "important.log")
    (tmp_path / ".gitignore").write_text("*.log\n!important.log\n", encoding="utf-8")

    rels = _rels(_ws(tmp_path))
    assert "important.log" in rels
    assert "a.log" not in rels


def test_gitignore_can_be_disabled(tmp_path: Path) -> None:
    _touch(tmp_path, "a.log")
    (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
    assert "a.log" in _rels(_ws(tmp_path, use_gitignore=False))


def test_default_output_dirs_are_skipped(tmp_path: Path) -> None:
    _touch(tmp_path, "src/Main.java")
    _touch(tmp_path, "target/Main.class")
    _touch(tmp_path, "workspaces/copy/x.py")
    rels = _rels(_ws(tmp_path))
    assert rels == {"src/Main.java"}


def test_exclude_and_include_globs(tmp_path: Path) -> None:
    _touch(tmp_path, "src/app.py")
    _touch(tmp_path, "src/app_test.py")
    _touch(tmp_path, "README.md")

    excluded = _rels(_ws(tmp_path, exclude_globs=("*_test.py",)))
    assert "src/app_test.py" not in excluded
    assert {"src/app.py", "README.md"} <= excluded

    included = _rels(_ws(tmp_path, include_globs=("*.py",)))
    assert included == {"src/app.py", "src/app_test.py"}
