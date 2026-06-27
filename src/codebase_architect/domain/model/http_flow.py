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
