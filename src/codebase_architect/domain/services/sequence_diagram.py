"""Render a Mermaid sequence diagram for a functional spec's functionality.

The spec's structured flow is turned into a sequence diagram: the actors and
systems become participants, each ``main_flow`` step becomes a message (solid
request / dashed response), and the alternative flows become an ``alt`` block.
When a set of endpoint paths confirmed by the cross-scan API flow (phase C2) is
supplied, the declared endpoints are annotated as found / not found in code, so
the diagram is grounded in the real implementation, not just the theory.
"""

from __future__ import annotations

from collections.abc import Iterable

from codebase_architect.domain.model.functional_spec import FunctionalSpec, SpecFeature
from codebase_architect.domain.services.api_match import canon_path

# Message text starting with one of these reads as a response -> dashed arrow.
_RESPONSE_PREFIXES = (
    "200",
    "201",
    "202",
    "204",
    "400",
    "401",
    "403",
    "404",
    "409",
    "422",
    "500",
    "error",
    "ok",
    "return",
    "resp",
    "response",
    "fail",
    "success",
)


def spec_sequences(
    spec: FunctionalSpec, *, confirmed_paths: Iterable[str] = ()
) -> list[tuple[str, str]]:
    """Return ``(feature name, mermaid)`` for every functionality in the spec."""
    confirmed = {canon_path(p) for p in confirmed_paths}
    return [(f.name, feature_sequence(f, confirmed=confirmed)) for f in spec.features]


def feature_sequence(feature: SpecFeature, *, confirmed: set[str] | None = None) -> str:
    confirmed = confirmed or set()
    participants = _participants(feature)
    alias = {name: f"p{i}" for i, name in enumerate(participants)}

    lines = ["sequenceDiagram"]
    for name in participants:
        lines.append(f'  participant {alias[name]} as "{_escape(name)}"')

    if not feature.main_flow:
        lines.append(f"  Note over {alias[participants[0]]}: No flow steps defined")
    for step in feature.main_flow:
        source = alias.get(step.actor.strip())
        target = alias.get(step.target.strip())
        if source is None or target is None:
            continue
        arrow = "-->>" if _is_response(step.action) else "->>"
        lines.append(f"  {source} {arrow} {target} : {_message(step.action)}")

    _emit_alt(lines, feature, alias, participants)
    _emit_endpoint_notes(lines, feature, alias, participants, confirmed)
    return "\n".join(lines)


def _participants(feature: SpecFeature) -> list[str]:
    order: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        name = raw.strip()
        if name and name not in seen:
            seen.add(name)
            order.append(name)

    for actor in feature.actors:
        add(actor)
    for step in feature.main_flow:
        add(step.actor)
        add(step.target)
    for system in feature.systems:
        add(system)
    if not order:
        order.append("System")
    return order


def _emit_alt(
    lines: list[str], feature: SpecFeature, alias: dict[str, str], participants: list[str]
) -> None:
    if not feature.alternative_flows:
        return
    span = f"{alias[participants[0]]},{alias[participants[-1]]}"
    first, *rest = feature.alternative_flows
    lines.append(f"  alt {_message(first)}")
    lines.append(f"    Note over {span}: {_message(first)}")
    for alt in rest:
        lines.append(f"  else {_message(alt)}")
        lines.append(f"    Note over {span}: {_message(alt)}")
    lines.append("  end")


def _emit_endpoint_notes(
    lines: list[str],
    feature: SpecFeature,
    alias: dict[str, str],
    participants: list[str],
    confirmed: set[str],
) -> None:
    if not feature.endpoints:
        return
    span = f"{alias[participants[0]]},{alias[participants[-1]]}"
    for endpoint in feature.endpoints:
        label = f"{endpoint.method} {endpoint.path}".strip()
        if confirmed:
            mark = "✓ found in code" if canon_path(endpoint.path) in confirmed else "✗ not found"
            label = f"{label} — {mark}"
        lines.append(f"  Note over {span}: {_message(label)}")


def _is_response(action: str) -> bool:
    return action.strip().lower().startswith(_RESPONSE_PREFIXES)


def _message(text: str) -> str:
    # Mermaid message text is single-line; keep it readable and unambiguous.
    return " ".join(text.split()).replace(":", "∶") or "—"


def _escape(text: str) -> str:
    return text.replace('"', "'")
