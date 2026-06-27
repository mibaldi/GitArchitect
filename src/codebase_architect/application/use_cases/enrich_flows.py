"""Use case: enrich each functionality with a grounded AI narrative.

The prompt contains ONLY the spec's own facts (the steps the user authored, the
systems, the declared endpoints and whether each was found in the scanned code).
The model is asked to narrate the flow without inventing systems or endpoints, so
the prose stays grounded. Conceptual functionalities are kept abstract on purpose
(frontend/backend, no concrete project). Best-effort: any provider error simply
yields no narrative for that functionality rather than failing the document.
"""

from __future__ import annotations

from codebase_architect.domain.model.functional_spec import FunctionalSpec, SpecFeature
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.domain.services.api_match import canon_path
from codebase_architect.shared.logging import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are a senior software architect writing functional documentation. "
    "You are given only the structured facts of one functionality (its flow "
    "steps, the systems involved and its declared endpoints) plus whether each "
    "endpoint was found in the scanned code. Describe ONLY what these facts "
    "show, in two or three sentences. Do not invent systems, endpoints or "
    "behaviour. Respond with prose only."
)


def enrich_spec_flows(
    provider: AIProvider,
    spec: FunctionalSpec,
    *,
    confirmed_paths: list[str],
    max_tokens: int = 1024,
) -> dict[str, str]:
    confirmed = {canon_path(p) for p in confirmed_paths}
    narratives: dict[str, str] = {}
    for feature in spec.features:
        prompt = _prompt(feature, confirmed)
        try:
            completion = provider.complete(system=_SYSTEM, prompt=prompt, max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001 - enrichment is best-effort
            logger.warning("flow_enrich_failed", feature=feature.name, error=str(exc))
            continue
        text = completion.text.strip()
        if text:
            narratives[feature.name] = text
    return narratives


def _prompt(feature: SpecFeature, confirmed: set[str]) -> str:
    lines = [f"Functionality: {feature.name}"]
    if feature.goal:
        lines.append(f"Goal: {feature.goal}")
    if feature.actors:
        lines.append("Actors: " + ", ".join(feature.actors))
    if feature.systems:
        lines.append("Systems: " + ", ".join(feature.systems))
    if feature.main_flow:
        lines.append("Flow steps:")
        for i, step in enumerate(feature.main_flow, 1):
            lines.append(f"  {i}. {step.actor} -> {step.target}: {step.action}")
    if feature.detail == "conceptual":
        lines.append(
            "Keep the description abstract (talk about frontend/backend roles, "
            "not concrete projects or endpoints)."
        )
    elif feature.endpoints:
        lines.append("Endpoints (with code status):")
        for endpoint in feature.endpoints:
            in_code = canon_path(endpoint.path) in confirmed
            found = "found in code" if in_code else "NOT found in code"
            lines.append(f"  {endpoint.method} {endpoint.path} — {found}")
    lines.append("Write the functional narrative for this flow.")
    return "\n".join(lines)
