"""Resolve an AIProvider by name (built-ins + plugins).

Built-in providers always win over plugins of the same name, so a plugin cannot
silently shadow a first-party provider. Unknown names degrade to NullAIProvider
(static-only) rather than crashing a scan.
"""

from __future__ import annotations

from collections.abc import Callable

from codebase_architect.application.registries.plugins import discover_plugins
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.infrastructure.ai_providers.claude import ClaudeProvider
from codebase_architect.infrastructure.ai_providers.gemini import GeminiProvider
from codebase_architect.infrastructure.ai_providers.null import NullAIProvider
from codebase_architect.infrastructure.ai_providers.openai_compatible import (
    LocalProvider,
    OpenAIProvider,
    OpenRouterProvider,
)
from codebase_architect.shared.logging import get_logger

logger = get_logger(__name__)

AI_PROVIDER_GROUP = "codebase_architect.ai_providers"

_BUILTINS: dict[str, Callable[[], AIProvider]] = {
    "claude": ClaudeProvider,
    "anthropic": ClaudeProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "local": LocalProvider,
    "gemini": GeminiProvider,
    "google": GeminiProvider,
    "null": NullAIProvider,
    "none": NullAIProvider,
    "static": NullAIProvider,
}


def build_ai_provider(name: str | None) -> AIProvider:
    """Return the AI provider for ``name`` (NullAIProvider when unknown/None)."""
    key = (name or "").lower()
    factory = _BUILTINS.get(key)
    if factory is None:
        factory = discover_plugins(AI_PROVIDER_GROUP).get(key)  # type: ignore[assignment]
    if factory is None:
        return NullAIProvider()

    provider = factory()
    if not isinstance(provider, AIProvider):
        logger.warning("ai_plugin_not_conformant", name=key, type=type(provider).__name__)
        return NullAIProvider()
    return provider
