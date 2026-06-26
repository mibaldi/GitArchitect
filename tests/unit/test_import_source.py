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


def test_two_imports_do_not_collide(sample_codebase: Path, tmp_path: Path) -> None:
    use_case = _use_case(tmp_path / "workspaces")
    a = use_case.execute(str(sample_codebase))
    b = use_case.execute(str(sample_codebase))
    assert a.root_path != b.root_path
    assert a.base_ref == b.base_ref  # same content -> same checksum
