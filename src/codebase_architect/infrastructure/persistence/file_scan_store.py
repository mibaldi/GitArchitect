"""File-based ScanStore: one JSON document per scan under a directory.

Pragmatic persistence with no external dependency — enough for scan history to
survive restarts and for later phases to load previous scans. A Postgres-backed
adapter can replace this behind the same port without touching callers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from codebase_architect.domain.model.scan_record import ScanRecord
from codebase_architect.domain.ports.scan_store import ScanStore
from codebase_architect.infrastructure.persistence._codec import from_jsonable, to_jsonable
from codebase_architect.shared.logging import get_logger

logger = get_logger(__name__)


class FileScanStore(ScanStore):
    """Persists each scan as ``<root>/<id>.json``."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, scan_id: str) -> Path:
        return self._root / f"{scan_id}.json"

    def save(self, record: ScanRecord) -> None:
        payload = to_jsonable(record)
        tmp = self._path(record.id).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self._path(record.id))  # atomic on the same filesystem

    def get(self, scan_id: str) -> ScanRecord | None:
        path = self._path(scan_id)
        if not path.is_file():
            return None
        return self._load(path)

    def list(self) -> list[ScanRecord]:
        records: list[ScanRecord] = []
        for path in self._root.glob("*.json"):
            record = self._load(path)
            if record is not None:
                records.append(record)
        records.sort(key=lambda r: r.created_at)
        return records

    def delete(self, scan_id: str) -> bool:
        path = self._path(scan_id)
        if path.is_file():
            path.unlink()
            return True
        return False

    def _load(self, path: Path) -> ScanRecord | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cast(ScanRecord, from_jsonable(ScanRecord, data))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # A corrupt or schema-shifted record must not break listing.
            logger.warning("scan_record_unreadable", path=str(path), error=str(exc))
            return None
