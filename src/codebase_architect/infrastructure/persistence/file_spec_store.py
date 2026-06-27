"""File-based SpecStore: one JSON document per functional spec."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from codebase_architect.domain.model.functional_spec import FunctionalSpec
from codebase_architect.domain.ports.spec_store import SpecStore
from codebase_architect.infrastructure.persistence._codec import from_jsonable, to_jsonable
from codebase_architect.shared.logging import get_logger

logger = get_logger(__name__)


class FileSpecStore(SpecStore):
    """Persists each spec as ``<root>/<id>.json``."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, spec_id: str) -> Path:
        return self._root / f"{spec_id}.json"

    def save(self, spec: FunctionalSpec) -> None:
        tmp = self._path(spec.id).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(to_jsonable(spec)), encoding="utf-8")
        tmp.replace(self._path(spec.id))

    def get(self, spec_id: str) -> FunctionalSpec | None:
        path = self._path(spec_id)
        if not path.is_file():
            return None
        return self._load(path)

    def list(self) -> list[FunctionalSpec]:
        specs: list[FunctionalSpec] = []
        for path in self._root.glob("*.json"):
            spec = self._load(path)
            if spec is not None:
                specs.append(spec)
        specs.sort(key=lambda s: s.created_at)
        return specs

    def delete(self, spec_id: str) -> bool:
        path = self._path(spec_id)
        if path.is_file():
            path.unlink()
            return True
        return False

    def _load(self, path: Path) -> FunctionalSpec | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cast(FunctionalSpec, from_jsonable(FunctionalSpec, data))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("spec_unreadable", path=str(path), error=str(exc))
            return None
