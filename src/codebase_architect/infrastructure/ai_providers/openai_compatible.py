"""OpenAI-compatible chat-completions providers (OpenAI, OpenRouter, Local).

OpenAI, OpenRouter and most local servers (Ollama/llama.cpp/LM Studio) expose
the same ``/chat/completions`` shape, so a single base class — parameterized by
base URL, model and API-key env var — covers all three. The ``openai`` SDK is an
optional dependency (the ``ai-openai`` extra), imported lazily.
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
    ) -> None:
        self._model = model
        self._api_key_env = api_key_env
        self._base_url = base_url
        self._requires_key = requires_key

    def available(self) -> bool:
        if not self._requires_key:
            return True
        return bool(self._api_key_env and os.environ.get(self._api_key_env))

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:  # pragma: no cover - exercised without the extra
            raise CapabilityUnavailableError(
                f"The '{self.name}' provider requires the 'ai-openai' extra. Install it with: "
                "pip install 'codebase-architect[ai-openai]'"
            ) from exc

        api_key = (os.environ.get(self._api_key_env) if self._api_key_env else None) or "not-needed"
        client = OpenAI(api_key=api_key, base_url=self._base_url)
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

    def __init__(self) -> None:
        super().__init__(
            model=os.environ.get("CA_OPENAI_MODEL", "gpt-4o-mini"),
            api_key_env="OPENAI_API_KEY",
        )


class OpenRouterProvider(OpenAICompatibleProvider):
    name: ClassVar[str] = "openrouter"

    def __init__(self) -> None:
        super().__init__(
            model=os.environ.get("CA_OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            api_key_env="OPENROUTER_API_KEY",
            base_url="https://openrouter.ai/api/v1",
        )


class LocalProvider(OpenAICompatibleProvider):
    """A local OpenAI-compatible server (e.g. Ollama). No API key required."""

    name: ClassVar[str] = "local"

    def __init__(self) -> None:
        super().__init__(
            model=os.environ.get("CA_LOCAL_MODEL", "llama3"),
            api_key_env=None,
            base_url=os.environ.get("CA_LOCAL_ENDPOINT", "http://localhost:11434/v1"),
            requires_key=False,
        )
