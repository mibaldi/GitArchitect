"""AI provider adapters."""

from codebase_architect.infrastructure.ai_providers.claude import ClaudeProvider
from codebase_architect.infrastructure.ai_providers.gemini import GeminiProvider
from codebase_architect.infrastructure.ai_providers.null import NullAIProvider
from codebase_architect.infrastructure.ai_providers.openai_compatible import (
    LocalProvider,
    OpenAIProvider,
    OpenRouterProvider,
)

__all__ = [
    "ClaudeProvider",
    "GeminiProvider",
    "LocalProvider",
    "NullAIProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
]
