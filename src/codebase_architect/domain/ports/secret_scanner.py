"""SecretScanner port: find likely secrets in a workspace."""

from __future__ import annotations

from abc import ABC, abstractmethod

from codebase_architect.domain.model.finding import Finding
from codebase_architect.domain.model.workspace import Workspace


class SecretScanner(ABC):
    """Scans a read-only workspace for likely secrets."""

    @abstractmethod
    def scan(self, workspace: Workspace) -> list[Finding]:
        """Return redacted findings; the raw secret values are never returned."""
