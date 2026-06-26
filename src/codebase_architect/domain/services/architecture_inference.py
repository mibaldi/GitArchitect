"""Infer a layered architecture from the module graph.

The heuristic is deliberately simple and explainable: each module is assigned to
a layer based on keywords found in its id/path, and the matching keyword is kept
as evidence. This is a starting point that an AI pass can later refine; keeping
it transparent avoids presenting guesses as facts.
"""

from __future__ import annotations

from codebase_architect.domain.model.architecture import Architecture, Component, Layer
from codebase_architect.domain.model.module import ModuleGraph

# Order matters: the first matching layer wins.
_LAYER_KEYWORDS: list[tuple[Layer, tuple[str, ...]]] = [
    (Layer.PRESENTATION, ("controller", "resource", "rest", "endpoint", "api", "web")),
    (Layer.UI, ("component", "page", "view", "widget")),
    (Layer.DATA, ("repository", "repositories", "repo", "dao", "persistence", "mapper", "store")),
    (Layer.APPLICATION, ("service", "services", "usecase", "use_case", "handler", "facade")),
    (Layer.DOMAIN, ("domain", "entity", "entities", "model")),
    (Layer.CONFIG, ("config", "configuration", "bootstrap")),
    (Layer.SHARED, ("util", "utils", "common", "shared", "helper", "core")),
]


def infer_architecture(graph: ModuleGraph) -> Architecture:
    components: list[Component] = []
    for module in graph.modules:
        layer, evidence = _classify(module.id, module.name)
        components.append(Component(module_id=module.id, layer=layer, evidence=evidence))
    return Architecture(components=components)


def _classify(module_id: str, module_name: str) -> tuple[Layer, str]:
    haystack = f"{module_id} {module_name}".lower()
    tokens = set(_tokenize(haystack))
    for layer, keywords in _LAYER_KEYWORDS:
        for keyword in keywords:
            if keyword in tokens:
                return layer, f"keyword '{keyword}'"
    return Layer.OTHER, "no layer keyword matched"


def _tokenize(text: str) -> list[str]:
    out: list[str] = []
    for chunk in text.replace("/", " ").replace(".", " ").replace("-", " ").split():
        out.append(chunk)
    return out
