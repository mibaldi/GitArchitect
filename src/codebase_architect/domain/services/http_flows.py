"""Assemble the HTTP surface (routes + outbound calls) from a CodeModel.

The parser records each file's exposed endpoints and outbound calls; this lifts
them to module-qualified :class:`HttpRoute`/:class:`HttpCall` values for the
documentation and for cross-scan matching.
"""

from __future__ import annotations

from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.http_flow import HttpCall, HttpRoute
from codebase_architect.domain.services.module_graph import module_id_of


def collect_http(model: CodeModel) -> tuple[list[HttpRoute], list[HttpCall]]:
    routes: list[HttpRoute] = []
    calls: list[HttpCall] = []
    for parsed in model.parsed_files:
        module = module_id_of(parsed)
        for route in parsed.routes:
            routes.append(HttpRoute(route.method, route.path, module, parsed.path, route.handler))
        for call in parsed.http_calls:
            calls.append(HttpCall(call.method, call.path, module, parsed.path))
    routes.sort(key=lambda r: (r.path, r.method, r.module))
    calls.sort(key=lambda c: (c.path, c.method, c.module))
    return routes, calls
