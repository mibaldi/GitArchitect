"""Tests for dependency-rule and cycle analysis."""

from __future__ import annotations

from codebase_architect.domain.model.architecture import (
    Architecture,
    Component,
    Layer,
)
from codebase_architect.domain.model.module import Module, ModuleEdge, ModuleGraph
from codebase_architect.domain.services.architecture_rules import (
    analyze_architecture,
    find_cycles,
)


def _graph(modules: list[str], edges: list[tuple[str, str]]) -> ModuleGraph:
    return ModuleGraph(
        modules=[Module(id=m, name=m) for m in modules],
        edges=[ModuleEdge(source=s, target=t) for s, t in edges],
    )


def _arch(layers: dict[str, Layer]) -> Architecture:
    return Architecture(
        components=[
            Component(module_id=m, layer=layer, evidence="test")
            for m, layer in layers.items()
        ]
    )


def test_inward_dependencies_are_clean() -> None:
    graph = _graph(
        ["web", "service", "domain"],
        [("web", "service"), ("service", "domain")],
    )
    arch = _arch(
        {"web": Layer.PRESENTATION, "service": Layer.APPLICATION, "domain": Layer.DOMAIN}
    )
    report = analyze_architecture(arch, graph)
    assert report.is_clean


def test_outward_dependency_is_a_violation() -> None:
    # domain (inner) depending on infrastructure (outer) points the wrong way.
    graph = _graph(["domain", "infra"], [("domain", "infra")])
    arch = _arch({"domain": Layer.DOMAIN, "infra": Layer.INFRASTRUCTURE})
    report = analyze_architecture(arch, graph)
    assert len(report.violations) == 1
    v = report.violations[0]
    assert (v.source, v.target) == ("domain", "infra")
    assert v.source_layer is Layer.DOMAIN and v.target_layer is Layer.INFRASTRUCTURE


def test_unknown_layers_are_skipped() -> None:
    graph = _graph(["a", "b"], [("a", "b")])
    arch = _arch({"a": Layer.OTHER, "b": Layer.DOMAIN})
    assert analyze_architecture(arch, graph).is_clean


def test_cycles_are_detected() -> None:
    graph = _graph(
        ["a", "b", "c", "d"],
        [("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")],
    )
    cycles = find_cycles(graph)
    assert len(cycles) == 1
    assert cycles[0].modules == ("a", "b", "c")


def test_no_cycle_in_a_dag() -> None:
    graph = _graph(["a", "b", "c"], [("a", "b"), ("a", "c"), ("b", "c")])
    assert find_cycles(graph) == []
