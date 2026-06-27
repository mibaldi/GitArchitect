"""Tests for the AI narrative use case (grounding and parsing)."""

from __future__ import annotations

from typing import ClassVar

from codebase_architect.application.use_cases.generate_narrative import GenerateNarrativeUseCase
from codebase_architect.domain.model.ai import Completion, TokenUsage
from codebase_architect.domain.model.architecture import Architecture, Component, Layer
from codebase_architect.domain.model.code import ImportRef, Language, ParsedFile
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.entrypoint import Entrypoint, EntrypointKind
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.domain.services.module_graph import build_module_graph


class FakeAIProvider(AIProvider):
    name: ClassVar[str] = "fake"

    def __init__(self, text: str) -> None:
        self._text = text
        self.last_prompt: str | None = None

    def available(self) -> bool:
        return True

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        self.last_prompt = prompt
        return Completion(text=self._text, usage=TokenUsage(100, 50))


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
            ParsedFile("svc/S.java", Language.JAVA, 8, package="com.demo.service"),
        ]
    )
    graph = build_module_graph(model)
    architecture = Architecture(
        components=[
            Component("com.demo.web", Layer.PRESENTATION, "keyword 'web'"),
            Component("com.demo.service", Layer.APPLICATION, "keyword 'service'"),
        ]
    )
    entrypoints = [
        Entrypoint("GreetController", EntrypointKind.HTTP_ENDPOINT, "web/C.java", "com.demo.web")
    ]
    return model, graph, architecture, entrypoints


def _run(text: str) -> object:
    model, graph, architecture, entrypoints = _fixture()
    return GenerateNarrativeUseCase(FakeAIProvider(text)).execute(
        model=model, graph=graph, architecture=architecture, entrypoints=entrypoints
    )


def test_parses_features_flows_and_overview() -> None:
    payload = """Here is the documentation:
    {
      "overview": "A small Spring web service.",
      "features": [
        {"name": "Greeting", "description": "Returns a greeting.",
         "related": ["com.demo.web", "com.demo.service"]}
      ],
      "flows": [
        {"entrypoint": "GreetController", "description": "HTTP request reaches the service."}
      ]
    }
    Thanks!"""
    report = _run(payload)
    assert report.overview == "A small Spring web service."
    assert len(report.features) == 1
    assert report.features[0].name == "Greeting"
    assert report.flows["GreetController"].startswith("HTTP request")
    assert report.usage.total == 150


def test_unknown_related_references_are_dropped() -> None:
    payload = """{
      "overview": "x",
      "features": [{"name": "F", "description": "d",
                    "related": ["com.demo.web", "com.demo.invented", "GhostEntry"]}],
      "flows": []
    }"""
    report = _run(payload)
    # Only the real module id survives; hallucinated references are filtered out.
    assert report.features[0].related == ("com.demo.web",)


def test_unparseable_response_yields_empty_report() -> None:
    report = _run("Sorry, I cannot help with that.")
    assert report.overview == ""
    assert report.features == []
    assert report.flows == {}


def test_prompt_is_grounded_in_static_facts() -> None:
    model, graph, architecture, entrypoints = _fixture()
    provider = FakeAIProvider('{"overview":"x","features":[],"flows":[]}')
    GenerateNarrativeUseCase(provider).execute(
        model=model, graph=graph, architecture=architecture, entrypoints=entrypoints
    )
    assert provider.last_prompt is not None
    # The prompt carries real module ids and entrypoint names, not source code.
    assert "com.demo.web" in provider.last_prompt
    assert "GreetController" in provider.last_prompt
