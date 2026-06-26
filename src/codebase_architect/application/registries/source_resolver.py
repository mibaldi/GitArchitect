"""Resolve a SourceLocation to the SourceProvider that can handle it."""

from __future__ import annotations

from codebase_architect.domain.model.source import SourceLocation
from codebase_architect.domain.ports.source_provider import SourceProvider
from codebase_architect.shared.errors import UnsupportedSourceError


class SourceProviderResolver:
    """Picks the first registered provider that supports a given location."""

    def __init__(self, providers: list[SourceProvider]) -> None:
        if not providers:
            raise ValueError("SourceProviderResolver requires at least one provider")
        self._providers = providers

    def resolve(self, location: SourceLocation) -> SourceProvider:
        for provider in self._providers:
            if provider.supports(location):
                return provider
        raise UnsupportedSourceError(
            f"No source provider can handle: {location.raw!r}. "
            "Expected a Git URL, a local folder, a local Git repo, a .zip or a .tar.gz."
        )
