"""Derive a functionality catalog deterministically, without the AI pass.

Entrypoints are the clearest static signal of *what a system does from the
outside*, so features are grouped by entrypoint kind (HTTP API, Web UI, CLI,
bootstrap). Each feature is grounded in real evidence (``related`` lists the
entrypoint names/modules it was derived from), and is marked ``STATIC`` so the
documentation can distinguish it from AI-written prose. When the AI pass runs it
can enrich or replace these.
"""

from __future__ import annotations

from codebase_architect.domain.model.entrypoint import Entrypoint, EntrypointKind
from codebase_architect.domain.model.feature import Feature, FeatureSource

# kind -> (feature name, sentence template). {n} = count, {modules} = module list.
_KIND_FEATURE: dict[EntrypointKind, tuple[str, str]] = {
    EntrypointKind.HTTP_ENDPOINT: (
        "HTTP API",
        "Exposes {n} HTTP endpoint(s) across {modules}.",
    ),
    EntrypointKind.UI_COMPONENT: (
        "Web UI",
        "Renders {n} UI component(s) across {modules}.",
    ),
    EntrypointKind.NG_MODULE: (
        "Web application modules",
        "Wires {n} application/routing module(s) across {modules}.",
    ),
    EntrypointKind.APP_BOOTSTRAP: (
        "Application bootstrap",
        "Boots the application from {n} entrypoint(s) in {modules}.",
    ),
    EntrypointKind.CLI_MAIN: (
        "Command-line interface",
        "Provides {n} command-line entrypoint(s) in {modules}.",
    ),
}

_MAX_MODULES_LISTED = 5


def derive_static_features(entrypoints: list[Entrypoint]) -> list[Feature]:
    """Group entrypoints into a small, grounded list of capabilities."""
    by_kind: dict[EntrypointKind, list[Entrypoint]] = {}
    for entrypoint in entrypoints:
        by_kind.setdefault(entrypoint.kind, []).append(entrypoint)

    features: list[Feature] = []
    for kind in EntrypointKind:
        group = by_kind.get(kind)
        if not group:
            continue
        name, template = _KIND_FEATURE[kind]
        modules = sorted({e.module for e in group})
        description = template.format(n=len(group), modules=_join_modules(modules))
        related = tuple(sorted({e.name for e in group}))
        features.append(
            Feature(
                name=name,
                description=description,
                related=related,
                source=FeatureSource.STATIC,
            )
        )
    return features


def _join_modules(modules: list[str]) -> str:
    shown = modules[:_MAX_MODULES_LISTED]
    rendered = ", ".join(f"`{m}`" for m in shown)
    if len(modules) > _MAX_MODULES_LISTED:
        rendered += f" (+{len(modules) - _MAX_MODULES_LISTED} more)"
    return rendered
