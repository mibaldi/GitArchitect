"""Contract tests shared by every SourceProvider adapter.

Each provider, given a location it supports, must materialize a read-only
workspace whose files are readable and whose metadata is consistent.
"""

from __future__ import annotations

import shutil
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from codebase_architect.domain.model.source import SourceLocation, SourceType
from codebase_architect.domain.ports.source_provider import SourceProvider
from codebase_architect.infrastructure.source_providers.folder import LocalFolderSourceProvider
from codebase_architect.infrastructure.source_providers.local_git import LocalGitSourceProvider
from codebase_architect.infrastructure.source_providers.targz import TarGzSourceProvider
from codebase_architect.infrastructure.source_providers.zip import ZipSourceProvider

# Each case builds a concrete location from the sample codebase. The third
# argument lays down a fake ``.git`` for the local-git case (ignored otherwise).
GitFactory = Callable[[Path], None]
LocationBuilder = Callable[[Path, Path, GitFactory], str]


def _folder_location(sample: Path, _tmp: Path, _git: GitFactory) -> str:
    return str(sample)


def _git_location(sample: Path, _tmp: Path, make_git: GitFactory) -> str:
    make_git(sample)
    return str(sample)


def _zip_location(sample: Path, tmp: Path, _git: GitFactory) -> str:
    archive = tmp / "sample.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in sample.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(sample.parent).as_posix())
    return str(archive)


def _targz_location(sample: Path, tmp: Path, _git: GitFactory) -> str:
    archive = tmp / "sample.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(sample, arcname="sample")
    return str(archive)


CASES: dict[str, tuple[Callable[[], SourceProvider], LocationBuilder, SourceType]] = {
    "folder": (LocalFolderSourceProvider, _folder_location, SourceType.FOLDER),
    "local_git": (LocalGitSourceProvider, _git_location, SourceType.LOCAL_GIT),
    "zip": (ZipSourceProvider, _zip_location, SourceType.ZIP),
    "targz": (TarGzSourceProvider, _targz_location, SourceType.TARGZ),
}


@pytest.fixture(params=list(CASES), ids=list(CASES))
def case(
    request: pytest.FixtureRequest,
    sample_codebase: Path,
    tmp_path: Path,
    make_fake_git: GitFactory,
) -> tuple[SourceProvider, SourceLocation, SourceType, Path]:
    factory, builder, source_type = CASES[request.param]
    raw = builder(sample_codebase, tmp_path, make_fake_git)
    return factory(), SourceLocation(raw=raw), source_type, tmp_path


def test_supports_its_own_location(
    case: tuple[SourceProvider, SourceLocation, SourceType, Path],
) -> None:
    provider, location, _type, _tmp = case
    assert provider.supports(location) is True


def test_fetch_materializes_readable_workspace(
    case: tuple[SourceProvider, SourceLocation, SourceType, Path],
) -> None:
    provider, location, source_type, tmp = case
    dest = tmp / "ws"
    dest.mkdir()

    workspace = provider.fetch(location, dest)

    assert workspace.source_type is source_type
    assert workspace.base_ref
    assert workspace.read_text("README.md").startswith("# Sample")
    names = {workspace.relative(p) for p in workspace.iter_files()}
    assert "src/main.py" in names
    # Ignored directories must not appear in the analyzable file set.
    assert not any(n.startswith("node_modules/") for n in names)


def test_fetch_does_not_mutate_the_source(
    case: tuple[SourceProvider, SourceLocation, SourceType, Path],
) -> None:
    provider, location, _type, tmp = case
    dest = tmp / "ws2"
    dest.mkdir()
    before = _snapshot(Path(location.raw))
    provider.fetch(location, dest)
    after = _snapshot(Path(location.raw))
    assert before == after


def _snapshot(path: Path) -> str:
    if path.is_file():
        return f"file:{path.stat().st_size}"
    return ",".join(sorted(p.name for p in path.iterdir()))


def test_provider_can_be_cleaned_up(
    case: tuple[SourceProvider, SourceLocation, SourceType, Path],
) -> None:
    provider, location, _type, tmp = case
    dest = tmp / "ws3"
    dest.mkdir()
    workspace = provider.fetch(location, dest)
    shutil.rmtree(workspace.root_path, ignore_errors=True)
    assert not workspace.root_path.exists() or workspace.root_path == dest
