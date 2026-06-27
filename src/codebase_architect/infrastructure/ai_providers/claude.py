"""Claude (Anthropic) AI provider adapter.

Uses the official ``anthropic`` SDK (optional ``ai`` extra), imported lazily.
Credentials, model and endpoint can be provided per scan (e.g. from the
dashboard) or via ``ANTHROPIC_API_KEY``. A ``base_url`` lets you target a local
Anthropic-compatible runner (no token spend).
"""

from __future__ import annotations

import os
from typing import ClassVar

from codebase_architect.domain.model.ai import Completion, TokenUsage
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.shared.errors import CapabilityUnavailableError

# Default model. claude-opus-4-8 is Anthropic's current flagship; override per
# scan or via settings when a cheaper tier is preferred for high-volume scanning.
_DEFAULT_MODEL = "claude-opus-4-8"


class ClaudeProvider(AIProvider):
    """Text completions backed by the Anthropic Messages API."""

    name: ClassVar[str] = "claude"

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
    ) -> None:
        self._model = model or _DEFAULT_MODEL
        self._api_key = api_key
        self._base_url = base_url
        self._api_key_env = api_key_env

    def _key(self) -> str | None:
        return self._api_key or os.environ.get(self._api_key_env)

    def available(self) -> bool:
        # A base_url means a local/compatible endpoint that may need no key.
        return bool(self._key() or self._base_url)

    def fingerprint(self) -> str:
        return f"claude:{self._model}:{self._base_url or ''}"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        try:
            import anthropic
        except ModuleNotFoundError as exc:  # pragma: no cover - exercised without the extra
            raise CapabilityUnavailableError(
                "The Claude provider requires the 'ai' extra. Install it with: "
                "pip install 'codebase-architect[ai]'"
            ) from exc

        client = anthropic.Anthropic(
            api_key=self._key() or "not-needed",
            base_url=self._base_url or None,
        )
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
