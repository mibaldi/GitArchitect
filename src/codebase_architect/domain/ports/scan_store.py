"""ScanStore port: persist completed scans so they outlive the process."""

from __future__ import annotations

from abc import ABC, abstractmethod

from codebase_architect.domain.model.scan_record import ScanRecord


class ScanStore(ABC):
    """Stores and retrieves :class:`ScanRecord` snapshots."""

    @abstractmethod
    def save(self, record: ScanRecord) -> None:
        """Persist (or overwrite) a scan by its id."""

    @abstractmethod
    def get(self, scan_id: str) -> ScanRecord | None:
        """Return the stored scan, or None if absent."""

    @abstractmethod
    def list(self) -> list[ScanRecord]:
        """Return all stored scans (ordered oldest-first by created_at)."""

    @abstractmethod
    def delete(self, scan_id: str) -> bool:
        """Remove a stored scan; return True if it existed."""
