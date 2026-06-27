"""NarrativeCache port: avoid re-calling the AI for an unchanged codebase."""

from __future__ import annotations

from abc import ABC, abstractmethod

from codebase_architect.domain.model.narrative import NarrativeReport


class NarrativeCache(ABC):
    """Caches AI narrative reports keyed by the grounding facts they came from."""

    @abstractmethod
    def get(self, key: str) -> NarrativeReport | None:
        """Return the cached report for ``key``, or None on a miss."""

    @abstractmethod
    def put(self, key: str, report: NarrativeReport) -> None:
        """Store ``report`` under ``key``."""
