"""Tests for GitRemoteSourceProvider (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from codebase_architect.domain.model.source import SourceLocation
from codebase_architect.infrastructure.source_providers.git_remote import GitRemoteSourceProvider
from codebase_architect.shared.errors import CapabilityUnavailableError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("git@github.com:u/r.git", True),
        ("https://h/u/r.git", True),
        ("ssh://git@h/r", True),
        ("git://h/r", True),
        ("https://h/u/r", False),  # ambiguous http without .git -> not claimed
        ("/local/path", False),
        ("./folder", False),
    ],
)
def test_supports(raw: str, expected: bool) -> None:
    assert GitRemoteSourceProvider().supports(SourceLocation(raw=raw)) is expected


def test_clone_failure_is_capability_error(tmp_path: Path) -> None:
    # Cloning a non-existent local repo fails fast without touching the network.
    dest = tmp_path / "ws"
    dest.mkdir()
    provider = GitRemoteSourceProvider()
    with pytest.raises(CapabilityUnavailableError):
        provider.fetch(SourceLocation(raw=str(tmp_path / "nonexistent-repo.git")), dest)
