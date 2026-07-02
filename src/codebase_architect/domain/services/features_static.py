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
from codebase_architect.domain.services.doc_strings import doc_strings

# kind -> (name string key, description template string key). {n} = count,
# {modules} = module list. Actual text is looked up per-language via doc_strings.
_KIND_FEATURE: dict[EntrypointKind, tuple[str, str]] = {
    EntrypointKind.HTTP_ENDPOINT: ("feature_http_api_name", "feature_http_api_desc_template"),
    EntrypointKind.UI_COMPONENT: ("feature_web_ui_name", "feature_web_ui_desc_template"),
    EntrypointKind.NG_MODULE: (
        "feature_web_app_modules_name",
        "feature_web_app_modules_desc_template",
    ),
    EntrypointKind.APP_BOOTSTRAP: (
        "feature_app_bootstrap_name",
        "feature_app_bootstrap_desc_template",
    ),
    EntrypointKind.CLI_MAIN: ("feature_cli_name", "feature_cli_desc_template"),
}

_MAX_MODULES_LISTED = 5


def derive_static_features(
    entrypoints: list[Entrypoint], *, strings: dict[str, str] | None = None
) -> list[Feature]:
    """Group entrypoints into a small, grounded list of capabilities.

    ``strings`` is a resolved ``doc_strings`` table; callers that already hold
    one pass it through so there is a single source of truth for the locale.
    """
    strings = strings if strings is not None else doc_strings("en")
    by_kind: dict[EntrypointKind, list[Entrypoint]] = {}
    for entrypoint in entrypoints:
        by_kind.setdefault(entrypoint.kind, []).append(entrypoint)

    features: list[Feature] = []
    for kind in EntrypointKind:
        group = by_kind.get(kind)
        if not group:
            continue
        name_key, template_key = _KIND_FEATURE[kind]
        name, template = strings[name_key], strings[template_key]
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
