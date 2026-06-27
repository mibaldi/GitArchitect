"""Tests for the functional spec store and service."""

from __future__ import annotations

from pathlib import Path

import pytest

from codebase_architect.application.services.spec_service import SpecService
from codebase_architect.domain.model.functional_spec import (
    EndpointRef,
    FlowStep,
    FunctionalSpec,
    SpecFeature,
)
from codebase_architect.infrastructure.persistence.file_spec_store import FileSpecStore
from codebase_architect.shared.errors import NotFoundError


def _spec() -> FunctionalSpec:
    return FunctionalSpec(
        id="",
        product="Demo",
        objective="Greet people",
        actors=("User", "Admin"),
        features=(
            SpecFeature(
                name="Greet",
                actors=("User",),
                goal="Say hi",
                main_flow=(
                    FlowStep("User", "opens app", "Frontend"),
                    FlowStep("Frontend", "GET /greet", "Backend"),
                ),
                systems=("Frontend", "Backend"),
                endpoints=(EndpointRef("GET", "/greet"),),
            ),
        ),
    )


def _service(tmp_path: Path) -> SpecService:
    return SpecService(FileSpecStore(tmp_path / "specs"), clock=lambda: "2026-01-01T00:00:00")


def test_create_assigns_id_and_timestamps(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create(_spec())
    assert created.id.startswith("spec_")
    assert created.created_at == "2026-01-01T00:00:00"
    assert created.updated_at == created.created_at
    # Round-trips through disk with structure intact.
    loaded = service.get(created.id)
    assert loaded.features[0].main_flow[1].target == "Backend"
    assert loaded.features[0].endpoints[0] == EndpointRef("GET", "/greet")


def test_update_preserves_created_at(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create(_spec())
    changed = service.update(
        created.id, FunctionalSpec(id="", product="Renamed", objective="x")
    )
    assert changed.product == "Renamed"
    assert changed.created_at == created.created_at  # preserved


def test_update_and_delete_unknown_raise(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(NotFoundError):
        service.update("spec_missing", _spec())
    with pytest.raises(NotFoundError):
        service.delete("spec_missing")


def test_list_and_delete(tmp_path: Path) -> None:
    service = _service(tmp_path)
    a = service.create(_spec())
    service.create(_spec())
    assert len(service.list()) == 2
    service.delete(a.id)
    assert {s.id for s in service.list()} == {s.id for s in service.list()}
    assert len(service.list()) == 1
