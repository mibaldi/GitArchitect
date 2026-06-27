"""SpecService: create, read, update and delete functional specs.

Thin orchestration over the SpecStore — assigns ids and timestamps and keeps
the store as the single source of truth. Specs are global and may later be
linked to one or more scans for reconciliation.
"""

from __future__ import annotations

import dataclasses
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from codebase_architect.domain.model.functional_spec import FunctionalSpec
from codebase_architect.domain.ports.spec_store import SpecStore
from codebase_architect.shared.errors import NotFoundError
from codebase_architect.shared.ids import new_id


class SpecService:
    """CRUD for functional specs, persisted via a SpecStore."""

    def __init__(self, store: SpecStore, *, clock: Callable[[], str] | None = None) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC).isoformat(timespec="seconds"))
        self._lock = threading.Lock()

    def create(self, spec: FunctionalSpec) -> FunctionalSpec:
        now = self._clock()
        created = dataclasses.replace(
            spec, id=new_id("spec"), created_at=now, updated_at=now
        )
        with self._lock:
            self._store.save(created)
        return created

    def update(self, spec_id: str, spec: FunctionalSpec) -> FunctionalSpec:
        with self._lock:
            existing = self._store.get(spec_id)
            if existing is None:
                raise NotFoundError(f"Spec not found: {spec_id}")
            updated = dataclasses.replace(
                spec,
                id=spec_id,
                created_at=existing.created_at,
                updated_at=self._clock(),
            )
            self._store.save(updated)
        return updated

    def get(self, spec_id: str) -> FunctionalSpec:
        spec = self._store.get(spec_id)
        if spec is None:
            raise NotFoundError(f"Spec not found: {spec_id}")
        return spec

    def link_scan(self, spec_id: str, scan_id: str) -> FunctionalSpec:
        """Record that this spec has been reconciled against a scan."""
        with self._lock:
            spec = self._store.get(spec_id)
            if spec is None:
                raise NotFoundError(f"Spec not found: {spec_id}")
            if scan_id in spec.linked_scan_ids:
                return spec
            linked = dataclasses.replace(
                spec,
                linked_scan_ids=(*spec.linked_scan_ids, scan_id),
                updated_at=self._clock(),
            )
            self._store.save(linked)
        return linked

    def list(self) -> list[FunctionalSpec]:
        return self._store.list()

    def delete(self, spec_id: str) -> None:
        if not self._store.delete(spec_id):
            raise NotFoundError(f"Spec not found: {spec_id}")
