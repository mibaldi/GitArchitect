"""Assemble the Documentation IR from the static analysis facts.

Pure and deterministic: ``generated_at`` is provided by the caller so the same
inputs always produce the same documentation (important for tests and for
re-scans that should yield stable diffs). ``language`` is purely a lookup key
into :mod:`codebase_architect.domain.services.doc_strings`; no clock/locale
calls are ever made.
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
from codebase_architect.domain.services.doc_strings import doc_strings, normalize_language
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
    language: str = "en",
) -> Documentation:
    language = normalize_language(language)
    strings = doc_strings(language)
    pages = (
        _overview_page(title, generated_at, base_ref, model, narrative, strings),
        _architecture_page(architecture, graph, strings),
        _modules_page(graph, strings),
        _features_page(narrative, entrypoints, strings),
        _entrypoints_page(entrypoints, strings),
        _flows_page(entrypoints, graph, model, narrative, strings),
        _api_page(model, strings),
        _dependencies_page(model, strings),
        _security_page(findings, strings),
    )
    return Documentation(
        title=title,
        generated_at=generated_at,
        base_ref=base_ref,
        pages=pages,
        language=language,
    )


def _overview_page(
    title: str,
    generated_at: str,
    base_ref: str | None,
    model: CodeModel,
    narrative: NarrativeReport | None,
    strings: dict[str, str],
) -> DocPage:
    if base_ref:
        meta = strings["meta_generated_at_with_ref_template"].format(
            generated_at=generated_at, base_ref=base_ref[:12]
        )
    else:
        meta = strings["meta_generated_at_template"].format(generated_at=generated_at)

    sections: list[DocSection] = [DocSection(body=meta)]
    if narrative and narrative.overview:
        sections.append(DocSection(heading=strings["heading_overview"], body=narrative.overview))

    lang_rows = [
        f"| {s.language.value} | {s.files} | {s.loc} |" for s in model.language_breakdown()
    ]
    languages = _table(
        [strings["col_language"], strings["col_files"], strings["col_loc"]], lang_rows
    ) or strings["no_recognized_source_files"]

    stack_lines = [
        f"- **{s.name}**{_v(s.version)} — {s.category.value} (`{s.evidence}`)" for s in model.stacks
    ]
    stacks = "\n".join(stack_lines) or strings["none_detected"]

    totals = (
        f"- {strings['totals_parsed_files']}: **{len(model.parsed_files)}**\n"
        f"- {strings['totals_symbols']}: **{model.symbol_count}**\n"
        f"- {strings['totals_lines_of_code']}: **{model.total_loc}**\n"
        f"- {strings['totals_dependencies']}: **{len(model.dependencies)}**"
    )

    sections.append(DocSection(heading=strings["heading_languages"], body=languages))
    sections.append(DocSection(heading=strings["heading_technology_stack"], body=stacks))
    sections.append(DocSection(heading=strings["heading_totals"], body=totals))
    return DocPage(slug="README", title=title, sections=tuple(sections))


def _features_page(
    narrative: NarrativeReport | None,
    entrypoints: list[Entrypoint],
    strings: dict[str, str],
) -> DocPage:
    # Prefer the AI catalog; fall back to a deterministic one derived from
    # entrypoints so the page is never empty on a static-only scan.
    ai_features = list(narrative.features) if narrative else []
    features = ai_features or derive_static_features(entrypoints, strings=strings)

    sections: list[DocSection] = []
    if not ai_features and features:
        sections.append(DocSection(body=strings["static_features_hint"]))

    if not features:
        body = strings["no_functionalities"]
    else:
        chunks: list[str] = []
        for feature in features:
            badge = "" if feature.source.value == "ai" else strings["static_badge"]
            chunks.append(f"### {feature.name}{badge}")
            chunks.append(feature.description)
            if feature.related:
                refs = ", ".join(f"`{r}`" for r in feature.related)
                chunks.append(strings["related_prefix_template"].format(refs=refs))
            chunks.append("")
        body = "\n".join(chunks).strip()
    sections.append(DocSection(heading=strings["heading_features"], body=body))
    return DocPage(
        slug="features", title=strings["title_functionalities"], sections=tuple(sections)
    )


def _architecture_page(
    architecture: Architecture, graph: ModuleGraph, strings: dict[str, str]
) -> DocPage:
    sections: list[DocSection] = []
    report = analyze_architecture(architecture, graph)
    grouped = architecture.by_layer()
    body_lines: list[str] = []
    for layer in architecture.layers_present():
        components = grouped[layer]
        body_lines.append(f"### {_layer_title(layer, strings)} ({len(components)})")
        for component in sorted(components, key=lambda c: c.module_id):
            body_lines.append(f"- `{component.module_id}` — _{component.evidence}_")
        body_lines.append("")
    layers_body = "\n".join(body_lines).strip() or strings["no_modules_to_classify"]
    sections.append(DocSection(heading=strings["heading_layers"], body=layers_body))

    diagram = _layered_graph_diagram(graph, architecture, report, strings)
    sections.append(
        DocSection(
            heading=strings["heading_module_dependencies"],
            body=_graph_caption(graph, strings),
            diagram=diagram,
        )
    )
    sections.append(
        DocSection(
            heading=strings["heading_dependency_rules"],
            body=_dependency_rules_body(report, strings),
        )
    )
    return DocPage(
        slug="architecture", title=strings["title_architecture"], sections=tuple(sections)
    )


def _dependency_rules_body(report: ArchitectureReport, strings: dict[str, str]) -> str:
    if report.is_clean:
        return strings["no_layering_violations"]
    chunks: list[str] = []
    if report.violations:
        chunks.append(
            strings["layering_violations_count_template"].format(count=len(report.violations))
        )
        for v in report.violations:
            chunks.append(
                f"- `{v.source}` ({v.source_layer.value}) → "
                f"`{v.target}` ({v.target_layer.value})"
            )
        chunks.append("")
    if report.cycles:
        chunks.append(strings["dependency_cycles_count_template"].format(count=len(report.cycles)))
        for cycle in report.cycles:
            chunks.append("- " + " ↔ ".join(f"`{m}`" for m in cycle.modules))
    return "\n".join(chunks).strip()


def _modules_page(graph: ModuleGraph, strings: dict[str, str]) -> DocPage:
    rows: list[str] = []
    for module in graph.modules:
        langs = ", ".join(sorted(lang.value for lang in module.languages))
        deps = len(graph.dependencies_of(module.id))
        rows.append(
            f"| `{module.id}` | {len(module.files)} | {module.symbol_count} "
            f"| {module.loc} | {langs} | {deps} |"
        )
    table = _table(
        [
            strings["col_module"],
            strings["col_files"],
            strings["col_symbols"],
            strings["col_loc"],
            strings["col_languages"],
            strings["col_depends_on"],
        ],
        rows,
    ) or strings["no_modules"]
    return DocPage(
        slug="modules",
        title=strings["title_modules"],
        sections=(DocSection(heading=strings["heading_modules"], body=table),),
    )


def _entrypoints_page(entrypoints: list[Entrypoint], strings: dict[str, str]) -> DocPage:
    if not entrypoints:
        body = strings["no_entrypoints_detected"]
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
        title=strings["title_entrypoints"],
        sections=(DocSection(heading=strings["heading_entrypoints"], body=body),),
    )


def _flows_page(
    entrypoints: list[Entrypoint],
    graph: ModuleGraph,
    model: CodeModel,
    narrative: NarrativeReport | None,
    strings: dict[str, str],
) -> DocPage:
    # Trace each entrypoint through what its module transitively depends on or
    # calls, combining the import graph with the (name-resolved) call graph.
    adjacency = _combined_adjacency(graph, build_call_edges(model))
    sections: list[DocSection] = [DocSection(body=strings["flows_intro"])]
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
        sections.append(DocSection(body=strings["no_multi_module_flows"]))
    return DocPage(slug="flows", title=strings["title_flows"], sections=tuple(sections))


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


def _api_page(model: CodeModel, strings: dict[str, str]) -> DocPage:
    routes, calls = collect_http(model)
    sections: list[DocSection] = []

    route_rows = [f"| `{r.method}` | `{r.path}` | `{r.module}` | {r.handler} |" for r in routes]
    routes_body = _table(
        [
            strings["col_method"],
            strings["col_path"],
            strings["col_module"],
            strings["col_handler"],
        ],
        route_rows,
    ) or strings["no_http_endpoints"]
    sections.append(DocSection(heading=strings["heading_exposed_endpoints"], body=routes_body))

    call_rows = [f"| `{c.method}` | `{c.path}` | `{c.module}` |" for c in calls]
    calls_body = _table(
        [strings["col_method"], strings["col_path"], strings["col_from_module"]], call_rows
    ) or strings["no_outbound_calls"]
    sections.append(DocSection(heading=strings["heading_outbound_calls"], body=calls_body))
    return DocPage(slug="api", title=strings["title_api"], sections=tuple(sections))


def _dependencies_page(model: CodeModel, strings: dict[str, str]) -> DocPage:
    by_manifest: dict[str, list[str]] = {}
    for dep in model.dependencies:
        version = f"@{dep.version}" if dep.version else ""
        scope = f" ({dep.scope})" if dep.scope else ""
        by_manifest.setdefault(dep.manifest, []).append(f"- `{dep.name}{version}`{scope}")
    if not by_manifest:
        body = strings["no_external_dependencies"]
    else:
        chunks = []
        for manifest in sorted(by_manifest):
            chunks.append(f"### `{manifest}`")
            chunks.extend(sorted(by_manifest[manifest]))
            chunks.append("")
        body = "\n".join(chunks).strip()
    return DocPage(
        slug="dependencies",
        title=strings["title_dependencies"],
        sections=(DocSection(heading=strings["heading_external_dependencies"], body=body),),
    )


def _security_page(findings: list[Finding] | None, strings: dict[str, str]) -> DocPage:
    if findings is None:
        body = strings["secret_scan_not_run"]
    elif not findings:
        body = strings["no_secrets_detected"]
    else:
        by_rule: dict[str, list[Finding]] = {}
        for finding in findings:
            by_rule.setdefault(finding.rule, []).append(finding)
        chunks = [
            strings["secrets_found_count_template"].format(count=len(findings)),
            "",
        ]
        for rule in sorted(by_rule):
            chunks.append(f"### {rule} ({len(by_rule[rule])})")
            for finding in sorted(by_rule[rule], key=lambda f: (f.path, f.line)):
                chunks.append(f"- `{finding.path}:{finding.line}` — `{finding.redacted}`")
            chunks.append("")
        body = "\n".join(chunks).strip()
    return DocPage(
        slug="security",
        title=strings["title_security"],
        sections=(DocSection(heading=strings["heading_secret_scan"], body=body),),
    )


# -- Mermaid helpers --------------------------------------------------------


def _layered_graph_diagram(
    graph: ModuleGraph,
    architecture: Architecture,
    report: ArchitectureReport,
    strings: dict[str, str],
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
        lines.append(f"    subgraph {_layer_title(layer, strings)}")
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


def _graph_caption(graph: ModuleGraph, strings: dict[str, str]) -> str:
    shown = min(len(graph.modules), _MAX_GRAPH_NODES)
    note = ""
    if len(graph.modules) > _MAX_GRAPH_NODES:
        note = strings["graph_caption_note_template"].format(
            shown=shown, total=len(graph.modules)
        )
    return strings["graph_caption_template"].format(
        modules=len(graph.modules), edges=len(graph.edges), note=note
    )


# -- small formatting utilities --------------------------------------------


def _table(headers: list[str], rows: list[str]) -> str:
    if not rows:
        return ""
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    return "\n".join([head, sep, *rows])


def _layer_title(layer: Layer, strings: dict[str, str]) -> str:
    return strings.get(f"layer_{layer.value}", layer.value.capitalize())


def _v(version: str | None) -> str:
    return f" `{version}`" if version else ""


def _escape(text: str) -> str:
    return text.replace('"', "'")
