"""Tests for the ImportSourceUseCase."""

from __future__ import annotations

from pathlib import Path

from codebase_architect.application.registries.source_resolver import SourceProviderResolver
from codebase_architect.application.use_cases.import_source import ImportSourceUseCase
from codebase_architect.domain.model.source import SourceType
from codebase_architect.infrastructure.source_providers import default_source_providers


def _use_case(workspaces_dir: Path) -> ImportSourceUseCase:
    return ImportSourceUseCase(
        resolver=SourceProviderResolver(default_source_providers()),
        workspaces_dir=workspaces_dir,
    )


def test_import_folder_creates_isolated_workspace(
    sample_codebase: Path, tmp_path: Path
) -> None:
    workspaces = tmp_path / "workspaces"
    workspace = _use_case(workspaces).execute(str(sample_codebase))

    assert workspace.source_type is SourceType.FOLDER
    assert workspace.root_path.is_dir()
    # Materialized under the managed workspaces dir, not the original source.
    assert workspaces in workspace.root_path.parents
    assert workspace.root_path != sample_codebase
    assert workspace.read_text("README.md").startswith("# Sample")


def test_import_folder_with_workspace_inside_does_not_recurse(tmp_path: Path) -> None:
    # Scanning a folder whose workspaces dir lives *inside* it must not copy the
    # growing destination into itself (which would recurse without bound).
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
    workspaces = source / "workspaces"

    workspace = _use_case(workspaces).execute(str(source))

    assert workspace.read_text("main.py").startswith("def main")
    # The destination did not get copied inside itself.
    assert not (workspace.root_path / "workspaces" / workspace.root_path.name).exists()


def test_two_imports_do_not_collide(sample_codebase: Path, tmp_path: Path) -> None:
    use_case = _use_case(tmp_path / "workspaces")
    a = use_case.execute(str(sample_codebase))
    b = use_case.execute(str(sample_codebase))
    assert a.root_path != b.root_path
    assert a.base_ref == b.base_ref  # same content -> same checksum
