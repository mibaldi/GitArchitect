"""Tests for cross-scan API flow matching."""

from __future__ import annotations

from codebase_architect.domain.model.http_flow import HttpCall, HttpRoute
from codebase_architect.domain.services.api_match import ScanSurface, match_api_flows


def test_call_matches_route_in_another_scan() -> None:
    frontend = ScanSurface(
        scan_id="scan_front",
        routes=(),
        calls=(HttpCall("GET", "/api/orders", "app/orders", "orders.service.ts"),),
    )
    backend = ScanSurface(
        scan_id="scan_back",
        routes=(
            HttpRoute("GET", "/api/orders", "com.shop.orders", "OrderController.java", "list"),
        ),
        calls=(),
    )
    graph = match_api_flows([frontend, backend])
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert (edge.from_scan, edge.to_scan) == ("scan_front", "scan_back")
    assert edge.to_module == "com.shop.orders"
    assert not graph.unmatched


def test_templated_paths_match() -> None:
    front = ScanSurface(
        "front",
        routes=(),
        calls=(HttpCall("GET", "/api/orders/{}", "ui", "f.ts"),),
    )
    back = ScanSurface(
        "back",
        routes=(HttpRoute("GET", "/api/orders/{id}", "orders", "C.java", "get"),),
        calls=(),
    )
    graph = match_api_flows([front, back])
    assert len(graph.edges) == 1
    assert graph.edges[0].to_module == "orders"


def test_unmatched_call_is_reported() -> None:
    front = ScanSurface(
        "front", routes=(), calls=(HttpCall("POST", "/api/unknown", "ui", "f.ts"),)
    )
    graph = match_api_flows([front])
    assert not graph.edges
    assert len(graph.unmatched) == 1
    assert graph.unmatched[0].path == "/api/unknown"


def test_method_must_be_compatible() -> None:
    front = ScanSurface("f", routes=(), calls=(HttpCall("DELETE", "/api/orders", "ui", "f.ts"),))
    back = ScanSurface(
        "b", routes=(HttpRoute("GET", "/api/orders", "orders", "C.java", "list"),), calls=()
    )
    graph = match_api_flows([front, back])
    assert not graph.edges  # DELETE call does not match a GET route
    assert len(graph.unmatched) == 1


def test_any_method_route_matches_any_call() -> None:
    front = ScanSurface("f", routes=(), calls=(HttpCall("PUT", "/api/orders", "ui", "f.ts"),))
    back = ScanSurface(
        "b", routes=(HttpRoute("ANY", "/api/orders", "orders", "C.java", "handle"),), calls=()
    )
    graph = match_api_flows([front, back])
    assert len(graph.edges) == 1
