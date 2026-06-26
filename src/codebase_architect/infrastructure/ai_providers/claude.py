"""Claude (Anthropic) AI provider adapter.

Uses the official ``anthropic`` SDK, which is an optional dependency (the ``ai``
extra). The import is lazy so the core runs without it; selecting Claude without
the package installed raises a clear, actionable error.
"""

from __future__ import annotations

import os
from typing import ClassVar

from codebase_architect.domain.model.ai import Completion, TokenUsage
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.shared.errors import CapabilityUnavailableError

# Default model. claude-opus-4-8 is Anthropic's current flagship; override via
# settings when a cheaper tier is preferred for high-volume scanning.
_DEFAULT_MODEL = "claude-opus-4-8"


class ClaudeProvider(AIProvider):
    """Text completions backed by the Anthropic Messages API."""

    name: ClassVar[str] = "claude"

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        api_key_env: str = "ANTHROPIC_API_KEY",
    ) -> None:
        self._model = model
        self._api_key_env = api_key_env

    def available(self) -> bool:
        return bool(os.environ.get(self._api_key_env))

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        try:
            import anthropic
        except ModuleNotFoundError as exc:  # pragma: no cover - exercised without the extra
            raise CapabilityUnavailableError(
                "The Claude provider requires the 'ai' extra. Install it with: "
                "pip install 'codebase-architect[ai]'"
            ) from exc

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in message.content if block.type == "text")
        usage = TokenUsage(
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )
        return Completion(text=text, usage=usage)
