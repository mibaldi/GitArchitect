"""Match outbound HTTP calls to the endpoints that serve them, across scans.

Each project is scanned separately; this joins them. A consumer call in one scan
is matched to a producer route in another (or the same) scan when their HTTP
methods are compatible and their paths match as templates — so a call to
``/orders/{}`` (a dynamic segment) lines up with a route ``/orders/{id}``.
The result is a cross-project edge: which project calls which project's endpoint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from codebase_architect.domain.model.http_flow import (
    ApiFlowEdge,
    ApiFlowGraph,
    HttpCall,
    HttpRoute,
    UnmatchedCall,
)

_PARAM = re.compile(r"\{[^}]*\}|:[^/]+|<[^>]+>")


@dataclass(frozen=True)
class ScanSurface:
    """The HTTP surface (routes it exposes, calls it makes) of one scan."""

    scan_id: str
    routes: tuple[HttpRoute, ...]
    calls: tuple[HttpCall, ...]


def match_api_flows(surfaces: list[ScanSurface]) -> ApiFlowGraph:
    # Index every route by (method, canonical path); ANY-method routes are
    # indexed under a wildcard so any verb can resolve to them.
    index: dict[tuple[str, str], list[tuple[str, HttpRoute]]] = {}
    for surface in surfaces:
        for route in surface.routes:
            index.setdefault((route.method, _canon(route.path)), []).append(
                (surface.scan_id, route)
            )

    edges: list[ApiFlowEdge] = []
    unmatched: list[UnmatchedCall] = []
    for surface in surfaces:
        for call in surface.calls:
            targets = _lookup(index, call)
            if not targets:
                unmatched.append(
                    UnmatchedCall(call.method, call.path, surface.scan_id, call.module)
                )
                continue
            for to_scan, route in targets:
                edges.append(
                    ApiFlowEdge(
                        method=route.method,
                        path=route.path,
                        from_scan=surface.scan_id,
                        from_module=call.module,
                        to_scan=to_scan,
                        to_module=route.module,
                        handler=route.handler,
                    )
                )

    edges = _dedupe(edges)
    edges.sort(key=lambda e: (e.from_scan, e.to_scan, e.path, e.method))
    unmatched.sort(key=lambda u: (u.from_scan, u.path, u.method))
    return ApiFlowGraph(
        edges=tuple(edges),
        unmatched=tuple(unmatched),
        scans=tuple(s.scan_id for s in surfaces),
    )


def _lookup(
    index: dict[tuple[str, str], list[tuple[str, HttpRoute]]], call: HttpCall
) -> list[tuple[str, HttpRoute]]:
    path = _canon(call.path)
    methods = {call.method, "ANY"}
    hits: list[tuple[str, HttpRoute]] = []
    seen = set()
    for method in methods:
        for to_scan, route in index.get((method, path), []):
            key = (to_scan, route.module, route.method, route.path)
            if key not in seen:
                seen.add(key)
                hits.append((to_scan, route))
    return hits


def _canon(path: str) -> str:
    # Drop scheme/host and query, collapse path params to a single placeholder.
    path = path.split("?", 1)[0].split("#", 1)[0]
    if "://" in path:
        after_host = path.split("://", 1)[1]
        path = "/" + after_host.split("/", 1)[1] if "/" in after_host else "/"
    path = _PARAM.sub("{}", path)
    return path.rstrip("/").lower() or "/"


def _dedupe(edges: list[ApiFlowEdge]) -> list[ApiFlowEdge]:
    seen: set[tuple[str, ...]] = set()
    out: list[ApiFlowEdge] = []
    for edge in edges:
        key = (
            edge.method,
            edge.path,
            edge.from_scan,
            edge.from_module,
            edge.to_scan,
            edge.to_module,
        )
        if key not in seen:
            seen.add(key)
            out.append(edge)
    return out
