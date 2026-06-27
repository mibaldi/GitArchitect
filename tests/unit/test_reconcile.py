"""Tests for spec↔code reconciliation."""

from __future__ import annotations

from codebase_architect.domain.model.code import Language, ParsedFile, Symbol, SymbolKind
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.entrypoint import Entrypoint, EntrypointKind
from codebase_architect.domain.model.functional_spec import (
    EndpointRef,
    FlowStep,
    FunctionalSpec,
    SpecFeature,
)
from codebase_architect.domain.model.module import ModuleGraph
from codebase_architect.domain.model.reconciliation import MatchStatus
from codebase_architect.domain.services.module_graph import build_module_graph
from codebase_architect.domain.services.reconcile import reconcile_spec


def _scan() -> tuple[list[Entrypoint], ModuleGraph, CodeModel]:
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "orders/PlaceOrderController.java",
                Language.JAVA,
                10,
                symbols=(Symbol("PlaceOrderController", SymbolKind.CLASS, 1, 9),),
                package="com.shop.orders",
            ),
            ParsedFile(
                "inventory/StockService.java",
                Language.JAVA,
                8,
                symbols=(Symbol("StockService", SymbolKind.CLASS, 1, 7),),
                package="com.shop.inventory",
            ),
        ]
    )
    graph = build_module_graph(model)
    entrypoints = [
        Entrypoint(
            "PlaceOrderController",
            EntrypointKind.HTTP_ENDPOINT,
            "orders/PlaceOrderController.java",
            "com.shop.orders",
        )
    ]
    return entrypoints, graph, model


def _feature(name: str, **kw: object) -> SpecFeature:
    return SpecFeature(name=name, **kw)  # type: ignore[arg-type]


def test_described_and_implemented_feature_is_covered() -> None:
    eps, graph, model = _scan()
    spec = FunctionalSpec(
        id="spec_1",
        product="Shop",
        features=(
            _feature(
                "Place order",
                systems=("Orders",),
                main_flow=(FlowStep("User", "POST /orders", "Orders"),),
                endpoints=(EndpointRef("POST", "/orders"),),
            ),
        ),
    )
    report = reconcile_spec(spec, scan_id="scan_1", entrypoints=eps, graph=graph, model=model)
    cov = report.coverage[0]
    assert cov.status is MatchStatus.IMPLEMENTED
    assert any(m.kind == "entrypoint" and "PlaceOrder" in m.id for m in cov.matches)


def test_described_but_missing_feature() -> None:
    eps, graph, model = _scan()
    spec = FunctionalSpec(
        id="spec_1",
        product="Shop",
        features=(_feature("Generate invoices PDF export"),),
    )
    report = reconcile_spec(spec, scan_id="s", entrypoints=eps, graph=graph, model=model)
    assert report.coverage[0].status is MatchStatus.MISSING
    assert report.missing == 1


def test_undocumented_entrypoint_is_reported() -> None:
    eps, graph, model = _scan()
    # A spec that covers nothing about the order controller.
    spec = FunctionalSpec(
        id="spec_1", product="Shop", features=(_feature("Manage inventory stock"),)
    )
    report = reconcile_spec(spec, scan_id="s", entrypoints=eps, graph=graph, model=model)
    assert any("PlaceOrderController" in e for e in report.undocumented_entrypoints)


def test_counts_aggregate() -> None:
    eps, graph, model = _scan()
    spec = FunctionalSpec(
        id="spec_1",
        product="Shop",
        features=(
            _feature("Place order", systems=("Orders",)),
            _feature("Inventory stock", systems=("Inventory",)),
            _feature("Send marketing emails"),
        ),
    )
    report = reconcile_spec(spec, scan_id="s", entrypoints=eps, graph=graph, model=model)
    assert report.implemented + report.partial + report.missing == 3
    assert report.missing >= 1
