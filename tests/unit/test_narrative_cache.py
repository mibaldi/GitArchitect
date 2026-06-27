"""Tests for the narrative cache (file adapter + use-case integration)."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from codebase_architect.application.use_cases.generate_narrative import GenerateNarrativeUseCase
from codebase_architect.domain.model.ai import Completion, TokenUsage
from codebase_architect.domain.model.architecture import Architecture, Component, Layer
from codebase_architect.domain.model.code import ImportRef, Language, ParsedFile
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.entrypoint import Entrypoint
from codebase_architect.domain.model.feature import Feature
from codebase_architect.domain.model.narrative import NarrativeReport
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.domain.services.module_graph import build_module_graph
from codebase_architect.infrastructure.cache.file_narrative_cache import FileNarrativeCache


def test_file_cache_round_trip(tmp_path: Path) -> None:
    cache = FileNarrativeCache(tmp_path / "cache")
    report = NarrativeReport(
        overview="An app.",
        features=[Feature("F", "does things", ("com.demo",))],
        flows={"C": "flows"},
        usage=TokenUsage(10, 20),
    )
    assert cache.get("k") is None
    cache.put("k", report)
    loaded = cache.get("k")
    assert loaded is not None
    assert loaded.overview == "An app."
    assert loaded.features[0].related == ("com.demo",)
    assert loaded.flows == {"C": "flows"}
    assert loaded.usage.total == 30


class CountingProvider(AIProvider):
    name: ClassVar[str] = "counting"

    def __init__(self) -> None:
        self.calls = 0

    def available(self) -> bool:
        return True

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        self.calls += 1
        return Completion(text='{"overview":"x","features":[],"flows":[]}', usage=TokenUsage(1, 1))


def _fixture() -> tuple[CodeModel, object, Architecture, list[Entrypoint]]:
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "web/C.java",
                Language.JAVA,
                10,
                imports=(ImportRef("com.demo.service.S"),),
                package="com.demo.web",
            ),
        ]
    )
    graph = build_module_graph(model)
    architecture = Architecture(components=[Component("com.demo.web", Layer.PRESENTATION, "web")])
    return model, graph, architecture, []


def test_use_case_uses_cache_to_skip_second_call(tmp_path: Path) -> None:
    cache = FileNarrativeCache(tmp_path / "cache")
    provider = CountingProvider()
    model, graph, architecture, entrypoints = _fixture()

    def run() -> None:
        GenerateNarrativeUseCase(provider, cache=cache).execute(
            model=model, graph=graph, architecture=architecture, entrypoints=entrypoints
        )

    run()
    run()
    # The second run is served from cache; the provider is called only once.
    assert provider.calls == 1
