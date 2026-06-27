"""SourceProvider port: materializes a SourceLocation into a Workspace.

Each concrete provider (folder, local git, remote git, zip, tar.gz) is an
adapter in the infrastructure layer. The domain only depends on this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from codebase_architect.domain.model.source import SourceLocation, SourceType
from codebase_architect.domain.model.workspace import Workspace


class SourceProvider(ABC):
    """Turns a raw :class:`SourceLocation` into a read-only :class:`Workspace`."""

    #: The kind of source this provider handles.
    source_type: ClassVar[SourceType]

    @abstractmethod
    def supports(self, location: SourceLocation) -> bool:
        """Return True if this provider can handle ``location``.

        Implementations inspect the raw value (scheme, extension) and, for
        archives, the file's magic bytes. Must not raise for a location it
        simply does not handle — it returns False instead.
        """

    @abstractmethod
    def fetch(self, location: SourceLocation, dest: Path) -> Workspace:
        """Materialize ``location`` into ``dest`` and return a Workspace.

        ``dest`` is an existing empty directory owned by the caller. The
        provider must not mutate the original source. May raise
        :class:`~codebase_architect.shared.errors.CapabilityUnavailableError`
        when a required external tool (e.g. ``git``) is missing.
        """
