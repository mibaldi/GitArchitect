"""Resolve an AIProvider by name.

Today this knows the built-in providers; later phases add OpenAI/Gemini/
OpenRouter/Local and plugin discovery via entry points.
"""

from __future__ import annotations

from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.infrastructure.ai_providers.claude import ClaudeProvider
from codebase_architect.infrastructure.ai_providers.null import NullAIProvider


def build_ai_provider(name: str | None) -> AIProvider:
    """Return the provider for ``name`` (NullAIProvider when unknown/None)."""
    match (name or "").lower():
        case "claude" | "anthropic":
            return ClaudeProvider()
        case "null" | "" | "none" | "static":
            return NullAIProvider()
        case _:
            # Unknown providers degrade to static-only rather than crashing the scan.
            return NullAIProvider()
