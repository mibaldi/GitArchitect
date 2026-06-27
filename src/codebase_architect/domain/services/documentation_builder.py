"""Assemble the Documentation IR from the static analysis facts.

Pure and deterministic: ``generated_at`` is provided by the caller so the same
inputs always produce the same documentation (important for tests and for
re-scans that should yield stable diffs).
"""

from __future__ import annotations

from codebase_architect.domain.model.architecture import (
    Architecture,
    ArchitectureReport,
    Layer,
)
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.documentation import (
    DocPage,
    DocSection,
    Documentation,
    MermaidDiagram,
)
from codebase_architect.domain.model.entrypoint import Entrypoint
from codebase_architect.domain.model.finding import Finding
from codebase_architect.domain.model.module import ModuleEdge, ModuleGraph
from codebase_architect.domain.model.narrative import NarrativeReport
from codebase_architect.domain.services.architecture_rules import analyze_architecture
from codebase_architect.domain.services.call_graph import build_call_edges
from codebase_architect.domain.services.features_static import derive_static_features
from codebase_architect.domain.services.http_flows import collect_http

# Caps keep generated diagrams readable on large codebases.
_MAX_GRAPH_NODES = 60
_MAX_FLOWS = 20
_MAX_FLOW_DEPTH = 3
_MAX_FLOW_NODES = 12


def build_documentation(
    *,
    title: str,
    generated_at: str,
    base_ref: str | None,
    model: CodeModel,
    graph: ModuleGraph,
    architecture: Architecture,
    entrypoints: list[Entrypoint],
    narrative: NarrativeReport | None = None,
    findings: list[Finding] | None = None,
) -> Documentation:
    pages = (
        _overview_page(title, generated_at, base_ref, model, narrative),
        _architecture_page(architecture, graph),
        _modules_page(graph),
        _features_page(narrative, entrypoints),
        _entrypoints_page(entrypoints),
        _flows_page(entrypoints, graph, model, narrative),
        _api_page(model),
        _dependencies_page(model),
        _security_page(findings),
    )
    return Documentation(
        title=title, generated_at=generated_at, base_ref=base_ref, pages=pages
    )


def _overview_page(
    title: str,
    generated_at: str,
    base_ref: str | None,
    model: CodeModel,
    narrative: NarrativeReport | None,
) -> DocPage:
    meta = f"_Generated at {generated_at}"
    if base_ref:
        meta += f" · base ref `{base_ref[:12]}`"
    meta += "._"

    sections: list[DocSection] = [DocSection(body=meta)]
    if narrative and narrative.overview:
        sections.append(DocSection(heading="Overview", body=narrative.overview))

    lang_rows = [
        f"| {s.language.value} | {s.files} | {s.loc} |" for s in model.language_breakdown()
    ]
    languages = _table(["Language", "Files", "LOC"], lang_rows) or "_No recognized source files._"

    stack_lines = [
        f"- **{s.name}**{_v(s.version)} — {s.category.value} (`{s.evidence}`)" for s in model.stacks
    ]
    stacks = "\n".join(stack_lines) or "_None detected._"

    totals = (
        f"- Parsed files: **{len(model.parsed_files)}**\n"
        f"- Symbols: **{model.symbol_count}**\n"
        f"- Lines of code: **{model.total_loc}**\n"
        f"- Dependencies: **{len(model.dependencies)}**"
    )

    sections.append(DocSection(heading="Languages", body=languages))
    sections.append(DocSection(heading="Technology stack", body=stacks))
    sections.append(DocSection(heading="Totals", body=totals))
    return DocPage(slug="README", title=title, sections=tuple(sections))


def _features_page(
    narrative: NarrativeReport | None, entrypoints: list[Entrypoint]
) -> DocPage:
    # Prefer the AI catalog; fall back to a deterministic one derived from
    # entrypoints so the page is never empty on a static-only scan.
    ai_features = list(narrative.features) if narrative else []
    features = ai_features or derive_static_features(entrypoints)

    sections: list[DocSection] = []
    if not ai_features and features:
        sections.append(
            DocSection(
                body=(
                    "_Derived statically from entrypoints. Run with an AI provider "
                    "(without `--static-only`) to enrich these descriptions._"
                )
            )
        )

    if not features:
        body = "_No functionalities were derived (no entrypoints detected)._"
    else:
        chunks: list[str] = []
        for feature in features:
            badge = "" if feature.source.value == "ai" else " _(static)_"
            chunks.append(f"### {feature.name}{badge}")
            chunks.append(feature.description)
            if feature.related:
                refs = ", ".join(f"`{r}`" for r in feature.related)
                chunks.append(f"_Related: {refs}_")
            chunks.append("")
        body = "\n".join(chunks).strip()
    sections.append(DocSection(heading="Features", body=body))
    return DocPage(slug="features", title="Functionalities", sections=tuple(sections))


def _architecture_page(architecture: Architecture, graph: ModuleGraph) -> DocPage:
    sections: list[DocSection] = []
    report = analyze_architecture(architecture, graph)
    grouped = architecture.by_layer()
    body_lines: list[str] = []
    for layer in architecture.layers_present():
        components = grouped[layer]
        body_lines.append(f"### {_layer_title(layer)} ({len(components)})")
        for component in sorted(components, key=lambda c: c.module_id):
            body_lines.append(f"- `{component.module_id}` — _{component.evidence}_")
        body_lines.append("")
    layers_body = "\n".join(body_lines).strip() or "_No modules to classify._"
    sections.append(DocSection(heading="Layers", body=layers_body))

    diagram = _layered_graph_diagram(graph, architecture, report)
    sections.append(
        DocSection(
            heading="Module dependencies",
            body=_graph_caption(graph),
            diagram=diagram,
        )
    )
    sections.append(
        DocSection(heading="Dependency rules", body=_dependency_rules_body(report))
    )
    return DocPage(slug="architecture", title="Architecture", sections=tuple(sections))


def _dependency_rules_body(report: ArchitectureReport) -> str:
    if report.is_clean:
        return "✓ No layering violations or dependency cycles detected."
    chunks: list[str] = []
    if report.violations:
        chunks.append(
            f"**{len(report.violations)} layering violation(s)** "
            "(an inner layer depends on an outer one):"
        )
        for v in report.violations:
            chunks.append(
                f"- `{v.source}` ({v.source_layer.value}) → "
                f"`{v.target}` ({v.target_layer.value})"
            )
        chunks.append("")
    if report.cycles:
        chunks.append(f"**{len(report.cycles)} dependency cycle(s):**")
        for cycle in report.cycles:
            chunks.append("- " + " ↔ ".join(f"`{m}`" for m in cycle.modules))
    return "\n".join(chunks).strip()


def _modules_page(graph: ModuleGraph) -> DocPage:
    rows: list[str] = []
    for module in graph.modules:
        langs = ", ".join(sorted(lang.value for lang in module.languages))
        deps = len(graph.dependencies_of(module.id))
        rows.append(
            f"| `{module.id}` | {len(module.files)} | {module.symbol_count} "
            f"| {module.loc} | {langs} | {deps} |"
        )
    table = _table(
        ["Module", "Files", "Symbols", "LOC", "Languages", "Depends on"], rows
    ) or "_No modules._"
    return DocPage(
        slug="modules",
        title="Modules",
        sections=(DocSection(heading="Modules", body=table),),
    )


def _entrypoints_page(entrypoints: list[Entrypoint]) -> DocPage:
    if not entrypoints:
        body = "_No entrypoints detected._"
    else:
        by_kind: dict[str, list[Entrypoint]] = {}
        for ep in entrypoints:
            by_kind.setdefault(ep.kind.value, []).append(ep)
        chunks: list[str] = []
        for kind in sorted(by_kind):
            chunks.append(f"### {kind} ({len(by_kind[kind])})")
            for ep in sorted(by_kind[kind], key=lambda e: e.file):
                chunks.append(f"- **{ep.name}** — `{ep.file}`")
            chunks.append("")
        body = "\n".join(chunks).strip()
    return DocPage(
        slug="entrypoints",
        title="Entrypoints",
        sections=(DocSection(heading="Entrypoints", body=body),),
    )


def _flows_page(
    entrypoints: list[Entrypoint],
    graph: ModuleGraph,
    model: CodeModel,
    narrative: NarrativeReport | None,
) -> DocPage:
    # Trace each entrypoint through what its module transitively depends on or
    # calls, combining the import graph with the (name-resolved) call graph.
    adjacency = _combined_adjacency(graph, build_call_edges(model))
    sections: list[DocSection] = [
        DocSection(
            body=(
                "Flows traced from each entrypoint through the modules it "
                "transitively depends on or calls."
            )
        )
    ]
    flow_text = narrative.flows if narrative else {}
    shown = 0
    for ep in entrypoints:
        if shown >= _MAX_FLOWS:
            break
        edges = _flow_subgraph(ep.module, adjacency)
        description = flow_text.get(ep.name, "")
        if not edges and not description:
            continue
        diagram = _flow_diagram(ep, edges) if edges else None
        sections.append(
            DocSection(
                heading=f"{ep.name} ({ep.kind.value})",
                body=description,
                diagram=diagram,
            )
        )
        shown += 1
    if shown == 0:
        sections.append(DocSection(body="_No multi-module flows detected._"))
    return DocPage(slug="flows", title="Flows", sections=tuple(sections))


def _combined_adjacency(
    graph: ModuleGraph, call_edges: list[ModuleEdge]
) -> dict[str, list[str]]:
    pairs: set[tuple[str, str]] = {(e.source, e.target) for e in graph.edges}
    pairs |= {(e.source, e.target) for e in call_edges}
    adjacency: dict[str, list[str]] = {}
    for source, target in sorted(pairs):
        adjacency.setdefault(source, []).append(target)
    return adjacency


def _flow_subgraph(start: str, adjacency: dict[str, list[str]]) -> list[tuple[str, str]]:
    """BFS from ``start`` up to depth/node caps; return edges among visited."""
    visited = {start}
    frontier = [start]
    depth = 0
    while frontier and depth < _MAX_FLOW_DEPTH and len(visited) < _MAX_FLOW_NODES:
        nxt: list[str] = []
        for node in sorted(frontier):
            for target in adjacency.get(node, []):
                if target not in visited:
                    if len(visited) >= _MAX_FLOW_NODES:
                        break
                    visited.add(target)
                    nxt.append(target)
        frontier = nxt
        depth += 1
    return sorted(
        {(s, t) for s in visited for t in adjacency.get(s, []) if t in visited}
    )


def _api_page(model: CodeModel) -> DocPage:
    routes, calls = collect_http(model)
    sections: list[DocSection] = []

    route_rows = [f"| `{r.method}` | `{r.path}` | `{r.module}` | {r.handler} |" for r in routes]
    routes_body = _table(["Method", "Path", "Module", "Handler"], route_rows) or (
        "_No exposed HTTP endpoints detected (Spring / FastAPI supported)._"
    )
    sections.append(DocSection(heading="Exposed endpoints", body=routes_body))

    call_rows = [f"| `{c.method}` | `{c.path}` | `{c.module}` |" for c in calls]
    calls_body = _table(["Method", "Path", "From module"], call_rows) or (
        "_No outbound HTTP calls detected (Angular HttpClient / fetch / axios supported)._"
    )
    sections.append(DocSection(heading="Outbound calls", body=calls_body))
    return DocPage(slug="api", title="API surface", sections=tuple(sections))


def _dependencies_page(model: CodeModel) -> DocPage:
    by_manifest: dict[str, list[str]] = {}
    for dep in model.dependencies:
        version = f"@{dep.version}" if dep.version else ""
        scope = f" ({dep.scope})" if dep.scope else ""
        by_manifest.setdefault(dep.manifest, []).append(f"- `{dep.name}{version}`{scope}")
    if not by_manifest:
        body = "_No external dependencies detected._"
    else:
        chunks = []
        for manifest in sorted(by_manifest):
            chunks.append(f"### `{manifest}`")
            chunks.extend(sorted(by_manifest[manifest]))
            chunks.append("")
        body = "\n".join(chunks).strip()
    return DocPage(
        slug="dependencies",
        title="Dependencies",
        sections=(DocSection(heading="External dependencies", body=body),),
    )


def _security_page(findings: list[Finding] | None) -> DocPage:
    if findings is None:
        body = "_Secret scanning was not run._"
    elif not findings:
        body = "_No secrets detected._"
    else:
        by_rule: dict[str, list[Finding]] = {}
        for finding in findings:
            by_rule.setdefault(finding.rule, []).append(finding)
        chunks = [f"**{len(findings)}** potential secret(s) found (values redacted):", ""]
        for rule in sorted(by_rule):
            chunks.append(f"### {rule} ({len(by_rule[rule])})")
            for finding in sorted(by_rule[rule], key=lambda f: (f.path, f.line)):
                chunks.append(f"- `{finding.path}:{finding.line}` — `{finding.redacted}`")
            chunks.append("")
        body = "\n".join(chunks).strip()
    return DocPage(
        slug="security",
        title="Security",
        sections=(DocSection(heading="Secret scan", body=body),),
    )


# -- Mermaid helpers --------------------------------------------------------


def _layered_graph_diagram(
    graph: ModuleGraph, architecture: Architecture, report: ArchitectureReport
) -> MermaidDiagram:
    """Module graph grouped into a mermaid subgraph per layer.

    Nodes are clustered by their inferred layer so the picture reads top-down by
    responsibility instead of as a flat blob; edges that violate the layering
    rule are drawn dotted with a warning marker.
    """
    modules = graph.modules[:_MAX_GRAPH_NODES]
    ids = {m.id for m in modules}
    node_id = {m.id: f"n{i}" for i, m in enumerate(modules)}
    layer_of = architecture.layer_of()
    violations = {(v.source, v.target) for v in report.violations}

    by_layer: dict[Layer, list[str]] = {}
    for module in modules:
        layer = layer_of.get(module.id, Layer.OTHER)
        by_layer.setdefault(layer, []).append(module.id)

    lines = ["flowchart LR"]
    for layer in Layer:
        members = by_layer.get(layer)
        if not members:
            continue
        lines.append(f"    subgraph {_layer_title(layer)}")
        for module_id in members:
            lines.append(f'        {node_id[module_id]}["{_escape(module_id)}"]')
        lines.append("    end")
    for edge in graph.edges:
        if edge.source in ids and edge.target in ids:
            if (edge.source, edge.target) in violations:
                lines.append(f"    {node_id[edge.source]} -.->|⚠| {node_id[edge.target]}")
            else:
                lines.append(f"    {node_id[edge.source]} --> {node_id[edge.target]}")
    return MermaidDiagram(title="Module dependencies", code="\n".join(lines))


def _flow_diagram(entrypoint: Entrypoint, edges: list[tuple[str, str]]) -> MermaidDiagram:
    nodes = sorted({entrypoint.module} | {n for edge in edges for n in edge})
    node_id = {module: f"m{i}" for i, module in enumerate(nodes)}
    lines = ["flowchart LR", f'    ep["{_escape(entrypoint.name)}"]']
    for module in nodes:
        lines.append(f'    {node_id[module]}["{_escape(module)}"]')
    if entrypoint.module in node_id:
        lines.append(f"    ep --> {node_id[entrypoint.module]}")
    for source, target in edges:
        lines.append(f"    {node_id[source]} --> {node_id[target]}")
    return MermaidDiagram(title=entrypoint.name, code="\n".join(lines))


def _graph_caption(graph: ModuleGraph) -> str:
    shown = min(len(graph.modules), _MAX_GRAPH_NODES)
    note = ""
    if len(graph.modules) > _MAX_GRAPH_NODES:
        note = f" (showing first {shown} of {len(graph.modules)})"
    return f"{len(graph.modules)} modules, {len(graph.edges)} internal dependencies{note}."


# -- small formatting utilities --------------------------------------------


def _table(headers: list[str], rows: list[str]) -> str:
    if not rows:
        return ""
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    return "\n".join([head, sep, *rows])


def _layer_title(layer: Layer) -> str:
    return layer.value.capitalize()


def _v(version: str | None) -> str:
    return f" `{version}`" if version else ""


def _escape(text: str) -> str:
    return text.replace('"', "'")
