"""Assemble a single Markdown document for a functional spec.

Combines the theory (the spec) with what the scans proved: per-functionality
sequence diagrams, coverage status, and the cross-project API flow. Pure and
deterministic; an optional AI narrative per functionality can be woven in.
"""

from __future__ import annotations

from codebase_architect.domain.model.functional_spec import FunctionalSpec, SpecFeature
from codebase_architect.domain.model.http_flow import ApiFlowGraph
from codebase_architect.domain.model.reconciliation import ReconciliationReport

_STATUS_ICON = {"implemented": "✓", "partial": "~", "missing": "✗"}


def build_spec_document(
    spec: FunctionalSpec,
    *,
    report: ReconciliationReport,
    api_flow: ApiFlowGraph,
    sequences: list[tuple[str, str]],
    narratives: dict[str, str] | None = None,
) -> str:
    narratives = narratives or {}
    status_by_feature = {c.feature: c.status.value for c in report.coverage}
    diagram_by_feature = dict(sequences)

    out: list[str] = [f"# {spec.product} — Functional documentation", ""]
    if spec.objective:
        out += [spec.objective, ""]
    if spec.actors:
        out += ["**Actors:** " + ", ".join(spec.actors), ""]
    out += [
        f"**Coverage:** {report.implemented} ✓ implemented · "
        f"{report.partial} ~ partial · {report.missing} ✗ missing",
        "",
    ]

    out += ["## Functionalities", ""]
    for feature in spec.features:
        out += _feature_section(
            feature,
            status_by_feature.get(feature.name, ""),
            diagram_by_feature.get(feature.name, ""),
            narratives.get(feature.name, ""),
        )

    out += _api_flow_section(api_flow)
    return "\n".join(out).rstrip() + "\n"


def _feature_section(feature: SpecFeature, status: str, mermaid: str, narrative: str) -> list[str]:
    icon = _STATUS_ICON.get(status, "")
    head = f"### {feature.name}"
    if icon:
        head += f"  ·  {icon} {status}"
    out = [head, f"_Detail: {feature.detail}_", ""]
    if feature.goal:
        out += [feature.goal, ""]
    if narrative:
        out += [narrative.strip(), ""]
    if mermaid:
        out += ["```mermaid", mermaid, "```", ""]
    if feature.endpoints:
        eps = ", ".join(f"`{e.method} {e.path}`" for e in feature.endpoints)
        out += [f"**Endpoints:** {eps}", ""]
    return out


def _api_flow_section(graph: ApiFlowGraph) -> list[str]:
    out = ["## Cross-project API flow", ""]
    if not graph.edges and not graph.unmatched:
        out += ["_No cross-project calls matched (link the project scans)._", ""]
        return out
    if graph.edges:
        ids: dict[str, str] = {}
        lines = ["```mermaid", "flowchart LR"]
        for edge in graph.edges:
            src = ids.setdefault(edge.from_module, f"n{len(ids)}")
            dst = ids.setdefault(edge.to_module, f"n{len(ids)}")
            label = f"{edge.method} {edge.path}".replace('"', "'")
            lines.append(f'    {src}["{edge.from_module}"] -->|{label}| {dst}["{edge.to_module}"]')
        lines.append("```")
        out += lines + [""]
    if graph.unmatched:
        out += [f"**Calls to endpoints no linked project serves ({len(graph.unmatched)}):**", ""]
        out += [f"- `{u.method} {u.path}` from `{u.from_module}`" for u in graph.unmatched]
        out += [""]
    return out
