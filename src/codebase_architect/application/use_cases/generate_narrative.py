"""Use case: generate the AI narrative, grounded in the static facts.

The prompt contains ONLY deterministic facts already extracted (modules, layers,
entrypoints, stacks) — never raw source — and instructs the model to describe
solely what is present and to reference real ids. Anything the model invents
(features referencing unknown modules) is filtered out before it reaches the
documentation, so AI prose can never introduce claims without static evidence.
"""

from __future__ import annotations

import hashlib
import json

from codebase_architect.domain.model.architecture import Architecture
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.entrypoint import Entrypoint
from codebase_architect.domain.model.feature import Feature, FeatureSource
from codebase_architect.domain.model.module import ModuleGraph
from codebase_architect.domain.model.narrative import NarrativeReport
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.domain.ports.narrative_cache import NarrativeCache
from codebase_architect.domain.services.doc_strings import doc_strings
from codebase_architect.shared.logging import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are a senior software architect documenting an existing codebase. "
    "You are given only structured, factual analysis of the code (modules, "
    "layers, entrypoints, technology stacks) — never the source itself. "
    "Describe ONLY what these facts show. Do not invent modules, files, "
    "features or behaviours that are not present. When you reference code, use "
    "the exact module ids and entrypoint names provided. Respond with a single "
    "JSON object and nothing else."
)


class GenerateNarrativeUseCase:
    """Asks an :class:`AIProvider` for an overview, features and flow narratives."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        max_tokens: int = 4096,
        cache: NarrativeCache | None = None,
    ) -> None:
        self._provider = provider
        self._max_tokens = max_tokens
        self._cache = cache

    def execute(
        self,
        *,
        model: CodeModel,
        graph: ModuleGraph,
        architecture: Architecture,
        entrypoints: list[Entrypoint],
        language: str = "en",
    ) -> NarrativeReport:
        allowed = graph.module_ids() | {e.name for e in entrypoints}
        prompt = _build_prompt(model, graph, architecture, entrypoints, language)

        cache_key = _cache_key(self._provider.fingerprint(), prompt)
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.info("ai_narrative_cache_hit", features=len(cached.features))
                return cached

        try:
            completion = self._provider.complete(
                system=_SYSTEM, prompt=prompt, max_tokens=self._max_tokens
            )
        except Exception as exc:  # noqa: BLE001 - any AI failure degrades to static docs
            # Missing SDK, unreachable endpoint, bad key, etc. — the static
            # documentation is still produced; we just skip the narrative.
            logger.warning("ai_narrative_failed", provider=self._provider.name, error=str(exc))
            return NarrativeReport()

        data = _extract_json(completion.text)
        if data is None:
            logger.warning("ai_narrative_unparseable")
            return NarrativeReport(usage=completion.usage)

        report = _parse(data, allowed_refs=allowed)
        report.usage = completion.usage
        if self._cache is not None:
            self._cache.put(cache_key, report)
        logger.info(
            "ai_narrative_generated",
            features=len(report.features),
            flows=len(report.flows),
            tokens=completion.usage.total,
        )
        return report


def _cache_key(fingerprint: str, prompt: str) -> str:
    digest = hashlib.sha256(f"{fingerprint}\n{prompt}".encode())
    return digest.hexdigest()


def _build_prompt(
    model: CodeModel,
    graph: ModuleGraph,
    architecture: Architecture,
    entrypoints: list[Entrypoint],
    language: str,
) -> str:
    layer_of = {c.module_id: c.layer.value for c in architecture.components}
    modules = "\n".join(
        f"- {m.id} [layer={layer_of.get(m.id, 'other')}, languages="
        f"{','.join(sorted(lang.value for lang in m.languages))}, symbols={m.symbol_count}]"
        for m in graph.modules
    )
    edges = "\n".join(f"- {e.source} -> {e.target}" for e in graph.edges) or "(none)"
    eps = "\n".join(f"- {e.name} [{e.kind.value}] in {e.file}" for e in entrypoints) or "(none)"
    stacks = ", ".join(s.name for s in model.stacks) or "(none)"
    language_instruction = doc_strings(language)["narrative_language_instruction"]

    return (
        f"Technology stacks: {stacks}\n\n"
        f"Modules:\n{modules or '(none)'}\n\n"
        f"Internal module dependencies:\n{edges}\n\n"
        f"Entrypoints:\n{eps}\n\n"
        "Produce a JSON object with this exact shape:\n"
        "{\n"
        '  "overview": "2-4 sentence plain-language summary of what this system does '
        'and how it is structured",\n'
        '  "features": [{"name": "short feature name", "description": "1-2 sentences", '
        '"related": ["module-id-or-entrypoint-name", ...]}],\n'
        '  "flows": [{"entrypoint": "entrypoint name", "description": "how a request/'
        'invocation flows through the modules"}]\n'
        "}\n"
        "Base every statement on the facts above. Reference only the module ids and "
        "entrypoint names listed. "
        f"{language_instruction}"
    )


def _extract_json(text: str) -> dict[str, object] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse(data: dict[str, object], *, allowed_refs: set[str]) -> NarrativeReport:
    overview = str(data.get("overview", "")).strip()

    features: list[Feature] = []
    for raw in _as_list(data.get("features")):
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        description = str(raw.get("description", "")).strip()
        if not name or not description:
            continue
        related = tuple(
            ref for ref in _as_str_list(raw.get("related")) if ref in allowed_refs
        )
        features.append(
            Feature(name=name, description=description, related=related, source=FeatureSource.AI)
        )

    flows: dict[str, str] = {}
    for raw in _as_list(data.get("flows")):
        if not isinstance(raw, dict):
            continue
        entrypoint = str(raw.get("entrypoint", "")).strip()
        description = str(raw.get("description", "")).strip()
        if entrypoint and description:
            flows[entrypoint] = description

    return NarrativeReport(overview=overview, features=features, flows=flows)


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _as_str_list(value: object) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []
