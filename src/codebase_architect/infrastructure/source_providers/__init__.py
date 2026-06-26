"""Built-in source provider adapters."""

from __future__ import annotations

from codebase_architect.domain.ports.source_provider import SourceProvider
from codebase_architect.infrastructure.source_providers.folder import LocalFolderSourceProvider
from codebase_architect.infrastructure.source_providers.git_remote import GitRemoteSourceProvider
from codebase_architect.infrastructure.source_providers.local_git import LocalGitSourceProvider
from codebase_architect.infrastructure.source_providers.targz import TarGzSourceProvider
from codebase_architect.infrastructure.source_providers.zip import ZipSourceProvider

__all__ = [
    "GitRemoteSourceProvider",
    "LocalGitSourceProvider",
    "LocalFolderSourceProvider",
    "ZipSourceProvider",
    "TarGzSourceProvider",
    "default_source_providers",
]


def default_source_providers() -> list[SourceProvider]:
    """Return the built-in providers in resolution priority order."""
    return [
        GitRemoteSourceProvider(),
        ZipSourceProvider(),
        TarGzSourceProvider(),
        LocalGitSourceProvider(),
        LocalFolderSourceProvider(),
    ]
