"""Tests for AI flow enrichment (with a deterministic fake provider)."""

from __future__ import annotations

from codebase_architect.application.use_cases.enrich_flows import enrich_spec_flows
from codebase_architect.domain.model.ai import Completion, TokenUsage
from codebase_architect.domain.model.functional_spec import (
    EndpointRef,
    FlowStep,
    FunctionalSpec,
    SpecFeature,
)
from codebase_architect.domain.ports.ai_provider import AIProvider


class _FakeProvider(AIProvider):
    name = "fake"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def available(self) -> bool:
        return True

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        self.prompts.append(prompt)
        return Completion(text=f"Narrative ({len(prompt)} chars)", usage=TokenUsage(1, 2))


def _spec() -> FunctionalSpec:
    return FunctionalSpec(
        id="s",
        product="Shop",
        features=(
            SpecFeature(
                name="Place order",
                systems=("Frontend", "Backend"),
                main_flow=(FlowStep("User", "POST /orders", "Backend"),),
                endpoints=(EndpointRef("POST", "/orders"),),
            ),
            SpecFeature(name="Abstract one", detail="conceptual", systems=("Frontend",)),
        ),
    )


def test_enrich_produces_a_narrative_per_feature() -> None:
    provider = _FakeProvider()
    out = enrich_spec_flows(provider, _spec(), confirmed_paths=["/orders"])
    assert set(out) == {"Place order", "Abstract one"}
    assert out["Place order"].startswith("Narrative")
    # grounded feature's prompt states the endpoint was found; conceptual stays abstract
    grounded_prompt = next(p for p in provider.prompts if "Place order" in p)
    assert "POST /orders — found in code" in grounded_prompt
    abstract_prompt = next(p for p in provider.prompts if "Abstract one" in p)
    assert "abstract" in abstract_prompt.lower()
    assert "found in code" not in abstract_prompt


def test_provider_error_is_swallowed_per_feature() -> None:
    class _Boom(_FakeProvider):
        def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
            raise RuntimeError("boom")

    out = enrich_spec_flows(_Boom(), _spec(), confirmed_paths=[])
    assert out == {}  # failures yield no narrative, never raise
