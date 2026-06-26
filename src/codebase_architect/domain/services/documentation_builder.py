"""Assemble the Documentation IR from the static analysis facts.

Pure and deterministic: ``generated_at`` is provided by the caller so the same
inputs always produce the same documentation (important for tests and for
re-scans that should yield stable diffs).
"""

from __future__ import annotations

from codebase_architect.domain.model.architecture import Architecture, Layer
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.documentation import (
    DocPage,
    DocSection,
    Documentation,
    MermaidDiagram,
)
from codebase_architect.domain.model.entrypoint import Entrypoint
from codebase_architect.domain.model.module import ModuleEdge, ModuleGraph

# Caps keep generated diagrams readable on large codebases.
_MAX_GRAPH_NODES = 60
_MAX_FLOWS = 20


def build_documentation(
    *,
    title: str,
    generated_at: str,
    base_ref: str | None,
    model: CodeModel,
    graph: ModuleGraph,
    architecture: Architecture,
    entrypoints: list[Entrypoint],
) -> Documentation:
    pages = (
        _overview_page(title, generated_at, base_ref, model),
        _architecture_page(architecture, graph),
        _modules_page(graph),
        _entrypoints_page(entrypoints),
        _flows_page(entrypoints, graph),
        _dependencies_page(model),
    )
    return Documentation(
        title=title, generated_at=generated_at, base_ref=base_ref, pages=pages
    )


def _overview_page(
    title: str, generated_at: str, base_ref: str | None, model: CodeModel
) -> DocPage:
    meta = f"_Generated at {generated_at}"
    if base_ref:
        meta += f" · base ref `{base_ref[:12]}`"
    meta += "._"

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

    return DocPage(
        slug="README",
        title=title,
        sections=(
            DocSection(body=meta),
            DocSection(heading="Languages", body=languages),
            DocSection(heading="Technology stack", body=stacks),
            DocSection(heading="Totals", body=totals),
        ),
    )


def _architecture_page(architecture: Architecture, graph: ModuleGraph) -> DocPage:
    sections: list[DocSection] = []
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

    diagram = _module_graph_diagram(graph)
    sections.append(
        DocSection(
            heading="Module dependencies",
            body=_graph_caption(graph),
            diagram=diagram,
        )
    )
    return DocPage(slug="architecture", title="Architecture", sections=tuple(sections))


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
        title="Functionalities & entrypoints",
        sections=(DocSection(heading="Entrypoints", body=body),),
    )


def _flows_page(entrypoints: list[Entrypoint], graph: ModuleGraph) -> DocPage:
    sections: list[DocSection] = [
        DocSection(
            body="Static flows derived from entrypoints and their module "
            "dependencies. Narrative descriptions are added by the AI pass."
        )
    ]
    shown = 0
    for ep in entrypoints:
        if shown >= _MAX_FLOWS:
            break
        deps = graph.dependencies_of(ep.module)
        if not deps:
            continue
        diagram = _flow_diagram(ep, deps)
        sections.append(
            DocSection(heading=f"{ep.name} ({ep.kind.value})", diagram=diagram)
        )
        shown += 1
    if shown == 0:
        sections.append(DocSection(body="_No multi-module flows detected._"))
    return DocPage(slug="flows", title="Flows", sections=tuple(sections))


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


# -- Mermaid helpers --------------------------------------------------------


def _module_graph_diagram(graph: ModuleGraph) -> MermaidDiagram:
    modules = graph.modules[:_MAX_GRAPH_NODES]
    ids = {m.id for m in modules}
    node_id = {m.id: f"n{i}" for i, m in enumerate(modules)}
    lines = ["flowchart LR"]
    for module in modules:
        lines.append(f'    {node_id[module.id]}["{_escape(module.id)}"]')
    for edge in graph.edges:
        if edge.source in ids and edge.target in ids:
            lines.append(f"    {node_id[edge.source]} --> {node_id[edge.target]}")
    return MermaidDiagram(title="Module dependencies", code="\n".join(lines))


def _flow_diagram(entrypoint: Entrypoint, deps: list[ModuleEdge]) -> MermaidDiagram:
    lines = ["flowchart LR", f'    ep["{_escape(entrypoint.name)}"]']
    targets = sorted({e.target for e in deps})
    node_id = {t: f"m{i}" for i, t in enumerate(targets)}
    for target in targets:
        lines.append(f'    {node_id[target]}["{_escape(target)}"]')
        lines.append(f"    ep --> {node_id[target]}")
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
