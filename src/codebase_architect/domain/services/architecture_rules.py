"""Check the module graph against its inferred layering.

Two checks, both explainable:

* **Dependency direction** — in a layered/hexagonal design dependencies point
  *inward*. Each layer gets a rank (inner = low); an edge whose source is more
  inner than its target (``rank(source) < rank(target)``) points outward and is
  flagged. Unknown (``OTHER``) modules are skipped rather than guessed about.
* **Cycles** — strongly-connected components of size > 1 in the module graph are
  dependency cycles. Found with an iterative Tarjan so deep graphs don't blow
  the recursion limit.
"""

from __future__ import annotations

from codebase_architect.domain.model.architecture import (
    Architecture,
    ArchitectureReport,
    Cycle,
    Layer,
    LayerViolation,
)
from codebase_architect.domain.model.module import ModuleGraph

# Inner = low. Dependencies should go from higher (outer) to lower-or-equal.
_LAYER_RANK: dict[Layer, int] = {
    Layer.SHARED: 0,
    Layer.DOMAIN: 1,
    Layer.APPLICATION: 2,
    Layer.DATA: 3,
    Layer.INFRASTRUCTURE: 3,
    Layer.PRESENTATION: 4,
    Layer.UI: 4,
    Layer.CONFIG: 5,
}


def analyze_architecture(architecture: Architecture, graph: ModuleGraph) -> ArchitectureReport:
    return ArchitectureReport(
        violations=tuple(check_dependency_rules(architecture, graph)),
        cycles=tuple(find_cycles(graph)),
    )


def check_dependency_rules(
    architecture: Architecture, graph: ModuleGraph
) -> list[LayerViolation]:
    layer_of = architecture.layer_of()
    violations: list[LayerViolation] = []
    for edge in graph.edges:
        source_layer = layer_of.get(edge.source)
        target_layer = layer_of.get(edge.target)
        if source_layer is None or target_layer is None:
            continue
        source_rank = _LAYER_RANK.get(source_layer)
        target_rank = _LAYER_RANK.get(target_layer)
        if source_rank is None or target_rank is None:
            continue
        if source_rank < target_rank:
            violations.append(
                LayerViolation(edge.source, edge.target, source_layer, target_layer)
            )
    return violations


def find_cycles(graph: ModuleGraph) -> list[Cycle]:
    """Return dependency cycles (SCCs of size > 1), deterministically ordered."""
    adj: dict[str, list[str]] = {m: [] for m in sorted(graph.module_ids())}
    for edge in sorted(graph.edges, key=lambda e: (e.source, e.target)):
        if edge.source in adj and edge.target in adj and edge.source != edge.target:
            adj[edge.source].append(edge.target)

    index = 0
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    sccs: list[list[str]] = []

    for root in adj:
        if root in indices:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, next_child = work[-1]
            if next_child == 0:
                indices[node] = index
                low[node] = index
                index += 1
                stack.append(node)
                on_stack.add(node)

            recursed = False
            neighbors = adj[node]
            i = next_child
            while i < len(neighbors):
                child = neighbors[i]
                if child not in indices:
                    work[-1] = (node, i + 1)
                    work.append((child, 0))
                    recursed = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], indices[child])
                i += 1
            if recursed:
                continue

            if low[node] == indices[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    sccs.append(sorted(component))

            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

    sccs.sort()
    return [Cycle(tuple(component)) for component in sccs]
