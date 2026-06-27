"""Tests for SourceProviderResolver and provider detection precedence."""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from codebase_architect.application.registries.source_resolver import SourceProviderResolver
from codebase_architect.domain.model.source import SourceLocation, SourceType
from codebase_architect.infrastructure.source_providers import default_source_providers
from codebase_architect.shared.errors import UnsupportedSourceError


@pytest.fixture
def resolver() -> SourceProviderResolver:
    return SourceProviderResolver(default_source_providers())


def test_resolves_plain_folder(resolver: SourceProviderResolver, sample_codebase: Path) -> None:
    provider = resolver.resolve(SourceLocation(raw=str(sample_codebase)))
    assert provider.source_type is SourceType.FOLDER


def test_local_git_takes_precedence_over_folder(
    resolver: SourceProviderResolver,
    sample_codebase: Path,
    make_fake_git: Callable[[Path], None],
) -> None:
    make_fake_git(sample_codebase)
    provider = resolver.resolve(SourceLocation(raw=str(sample_codebase)))
    assert provider.source_type is SourceType.LOCAL_GIT


def test_resolves_zip(resolver: SourceProviderResolver, tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("x.txt", "hi")
    provider = resolver.resolve(SourceLocation(raw=str(archive)))
    assert provider.source_type is SourceType.ZIP


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:user/repo.git",
        "https://example.com/user/repo.git",
        "ssh://git@host/repo",
        "git://host/repo",
    ],
)
def test_resolves_git_remote_urls(resolver: SourceProviderResolver, url: str) -> None:
    provider = resolver.resolve(SourceLocation(raw=url))
    assert provider.source_type is SourceType.GIT_REMOTE


def test_unsupported_location_raises(resolver: SourceProviderResolver) -> None:
    with pytest.raises(UnsupportedSourceError):
        resolver.resolve(SourceLocation(raw="/path/that/does/not/exist/anywhere"))


def test_resolver_requires_providers() -> None:
    with pytest.raises(ValueError):
        SourceProviderResolver([])
