"""HTTP surface of a codebase: endpoints it exposes and calls it makes.

These are the producer/consumer halves that the phase-C matcher joins (a call's
``(method, path)`` against a route's) to draw end-to-end flows across a frontend,
a backend and downstream services.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HttpRoute:
    """An endpoint the codebase exposes (server side)."""

    method: str
    path: str
    module: str
    file: str
    handler: str = ""


@dataclass(frozen=True)
class HttpCall:
    """An outbound HTTP call the codebase makes (client side)."""

    method: str
    path: str
    module: str
    file: str


@dataclass(frozen=True)
class ApiFlowEdge:
    """A consumer call matched to the producer endpoint that serves it."""

    method: str
    path: str
    from_scan: str
    from_module: str
    to_scan: str
    to_module: str
    handler: str = ""


@dataclass(frozen=True)
class UnmatchedCall:
    """A consumer call no scanned project was found to serve."""

    method: str
    path: str
    from_scan: str
    from_module: str


@dataclass
class ApiFlowGraph:
    """Cross-project HTTP call graph over a set of scans."""

    edges: tuple[ApiFlowEdge, ...] = ()
    unmatched: tuple[UnmatchedCall, ...] = ()
    scans: tuple[str, ...] = ()
