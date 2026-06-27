"""AIProvider port: a provider-agnostic text completion interface.

Kept intentionally narrow (text in, text out) so adapters for Claude, OpenAI,
Gemini, OpenRouter or a local model all satisfy the same contract. Structured
output is obtained by asking for JSON in the prompt and parsing the result,
which keeps the port free of any one provider's schema mechanism.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from codebase_architect.domain.model.ai import Completion


class AIProvider(ABC):
    """Generates text completions for the narrative documentation pass."""

    #: Stable provider identifier (e.g. "claude", "openai", "null").
    name: ClassVar[str]

    def fingerprint(self) -> str:
        """A cache identity for this provider's configuration (name + model + endpoint).

        Used so the narrative cache distinguishes runs made with different
        models or endpoints. Overridden by providers that carry a model/base URL.
        """
        return self.name

    @abstractmethod
    def available(self) -> bool:
        """Whether this provider is configured and usable (e.g. API key present)."""

    @abstractmethod
    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        """Return a completion for ``prompt`` under the given ``system`` guidance."""
