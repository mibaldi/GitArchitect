"""Tests for plugin discovery and the renderer registry."""

from __future__ import annotations

import pytest

from codebase_architect.application.registries import renderer_registry
from codebase_architect.application.registries.ai_registry import build_ai_provider
from codebase_architect.application.registries.renderer_registry import (
    available_renderers,
    build_renderer,
)
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.domain.ports.documentation import DocRenderer
from codebase_architect.infrastructure.ai_providers.null import NullAIProvider
from codebase_architect.infrastructure.rendering.markdown_renderer import MarkdownMermaidRenderer
from codebase_architect.shared.errors import ConfigurationError


def test_builtin_markdown_renderer() -> None:
    assert isinstance(build_renderer("markdown"), MarkdownMermaidRenderer)
    assert isinstance(build_renderer(None), MarkdownMermaidRenderer)
    assert "markdown" in available_renderers()


def test_unknown_renderer_raises() -> None:
    with pytest.raises(ConfigurationError):
        build_renderer("does-not-exist")


def test_renderer_plugin_is_discovered(monkeypatch: pytest.MonkeyPatch) -> None:
    class PluginRenderer(DocRenderer):
        def render(self, documentation: object) -> list:  # type: ignore[override]
            return []

    monkeypatch.setattr(
        renderer_registry, "discover_plugins", lambda group: {"custom": PluginRenderer}
    )
    assert isinstance(build_renderer("custom"), PluginRenderer)


def test_non_conformant_renderer_plugin_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class NotARenderer:
        pass

    monkeypatch.setattr(
        renderer_registry, "discover_plugins", lambda group: {"bad": NotARenderer}
    )
    with pytest.raises(ConfigurationError):
        build_renderer("bad")


def test_ai_provider_plugin_is_discovered(monkeypatch: pytest.MonkeyPatch) -> None:
    class PluginProvider(AIProvider):
        name = "plugin"

        def available(self) -> bool:
            return False

        def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> object:
            raise NotImplementedError

    import codebase_architect.application.registries.ai_registry as reg

    monkeypatch.setattr(reg, "discover_plugins", lambda group: {"plugin": PluginProvider})
    assert build_ai_provider("plugin").name == "plugin"


def test_non_conformant_ai_plugin_degrades_to_null(monkeypatch: pytest.MonkeyPatch) -> None:
    import codebase_architect.application.registries.ai_registry as reg

    monkeypatch.setattr(reg, "discover_plugins", lambda group: {"bad": object})
    assert isinstance(build_ai_provider("bad"), NullAIProvider)
