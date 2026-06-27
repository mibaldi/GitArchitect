"""OpenAI-compatible chat-completions providers (OpenAI, OpenRouter, Local).

OpenAI, OpenRouter and most local servers (Ollama/llama.cpp/LM Studio, and many
"local Codex/Claude runners") expose the same ``/chat/completions`` shape, so a
single base class — parameterized by base URL, model and API key — covers all
three. The ``openai`` SDK is an optional dependency (``ai-openai``), imported
lazily. Point ``base_url`` at a machine on your tailnet to run with no token
spend.
"""

from __future__ import annotations

import os
from typing import ClassVar

from codebase_architect.domain.model.ai import Completion, TokenUsage
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.shared.errors import CapabilityUnavailableError


class OpenAICompatibleProvider(AIProvider):
    """Base for any provider speaking the OpenAI chat-completions protocol."""

    name: ClassVar[str] = "openai_compatible"

    def __init__(
        self,
        *,
        model: str,
        api_key_env: str | None,
        base_url: str | None = None,
        requires_key: bool = True,
        api_key: str | None = None,
    ) -> None:
        self._model = model
        self._api_key_env = api_key_env
        self._base_url = base_url
        self._requires_key = requires_key
        self._api_key = api_key

    def _key(self) -> str | None:
        return self._api_key or (os.environ.get(self._api_key_env) if self._api_key_env else None)

    def available(self) -> bool:
        if not self._requires_key:
            return True
        return bool(self._key())

    def fingerprint(self) -> str:
        return f"{self.name}:{self._model}:{self._base_url or ''}"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:  # pragma: no cover - exercised without the extra
            raise CapabilityUnavailableError(
                f"The '{self.name}' provider requires the 'ai-openai' extra. Install it with: "
                "pip install 'codebase-architect[ai-openai]'"
            ) from exc

        client = OpenAI(api_key=self._key() or "not-needed", base_url=self._base_url)
        response = client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        text = response.choices[0].message.content or ""
        usage = TokenUsage()
        if response.usage is not None:
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )
        return Completion(text=text, usage=usage)


class OpenAIProvider(OpenAICompatibleProvider):
    name: ClassVar[str] = "openai"

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None, model: str | None = None
    ) -> None:
        super().__init__(
            model=model or os.environ.get("CA_OPENAI_MODEL", "gpt-4o-mini"),
            api_key_env="OPENAI_API_KEY",
            base_url=base_url,
            api_key=api_key,
        )


class OpenRouterProvider(OpenAICompatibleProvider):
    name: ClassVar[str] = "openrouter"

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None, model: str | None = None
    ) -> None:
        super().__init__(
            model=model or os.environ.get("CA_OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            api_key_env="OPENROUTER_API_KEY",
            base_url=base_url or "https://openrouter.ai/api/v1",
            api_key=api_key,
        )


class LocalProvider(OpenAICompatibleProvider):
    """A local/remote OpenAI-compatible server (Ollama, LM Studio, a Mac mini
    runner reachable over your tailnet). No API key required by default."""

    name: ClassVar[str] = "local"

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None, model: str | None = None
    ) -> None:
        super().__init__(
            model=model or os.environ.get("CA_LOCAL_MODEL", "llama3"),
            api_key_env=None,
            base_url=base_url or os.environ.get("CA_LOCAL_ENDPOINT", "http://localhost:11434/v1"),
            requires_key=False,
            api_key=api_key,
        )
