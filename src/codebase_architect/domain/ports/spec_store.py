"""SpecStore port: persist functional specs across restarts."""

from __future__ import annotations

from abc import ABC, abstractmethod

from codebase_architect.domain.model.functional_spec import FunctionalSpec


class SpecStore(ABC):
    """Stores and retrieves :class:`FunctionalSpec` documents."""

    @abstractmethod
    def save(self, spec: FunctionalSpec) -> None:
        """Persist (or overwrite) a spec by its id."""

    @abstractmethod
    def get(self, spec_id: str) -> FunctionalSpec | None:
        """Return the stored spec, or None if absent."""

    @abstractmethod
    def list(self) -> list[FunctionalSpec]:
        """Return all stored specs (ordered oldest-first by created_at)."""

    @abstractmethod
    def delete(self, spec_id: str) -> bool:
        """Remove a stored spec; return True if it existed."""
