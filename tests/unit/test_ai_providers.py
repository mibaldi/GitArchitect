"""Tests for AI provider adapters and the registry."""

from __future__ import annotations

import pytest

from codebase_architect.application.registries.ai_registry import build_ai_provider
from codebase_architect.infrastructure.ai_providers.claude import ClaudeProvider
from codebase_architect.infrastructure.ai_providers.null import NullAIProvider
from codebase_architect.shared.errors import CapabilityUnavailableError


def test_null_provider_is_unavailable() -> None:
    provider = NullAIProvider()
    assert provider.available() is False
    with pytest.raises(CapabilityUnavailableError):
        provider.complete(system="s", prompt="p")


def test_claude_availability_follows_env(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = ClaudeProvider(api_key_env="CA_TEST_KEY")
    monkeypatch.delenv("CA_TEST_KEY", raising=False)
    assert provider.available() is False
    monkeypatch.setenv("CA_TEST_KEY", "sk-test")
    assert provider.available() is True


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("claude", "claude"),
        ("anthropic", "claude"),
        ("null", "null"),
        (None, "null"),
        ("unknown-provider", "null"),
    ],
)
def test_registry_resolves_providers(name: str | None, expected: str) -> None:
    assert build_ai_provider(name).name == expected
