"""Google Gemini AI provider adapter.

Uses the ``google-generativeai`` SDK (optional ``ai-gemini`` extra), imported
lazily. Credentials and model can be provided per scan or via ``GOOGLE_API_KEY``.
"""

from __future__ import annotations

import os
from typing import ClassVar

from codebase_architect.domain.model.ai import Completion, TokenUsage
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.shared.errors import CapabilityUnavailableError


class GeminiProvider(AIProvider):
    name: ClassVar[str] = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,  # accepted for a uniform factory; unused by the SDK
        model: str | None = None,
        api_key_env: str = "GOOGLE_API_KEY",
    ) -> None:
        self._api_key = api_key
        self._api_key_env = api_key_env
        self._model = model or os.environ.get("CA_GEMINI_MODEL", "gemini-1.5-flash")

    def _key(self) -> str | None:
        return self._api_key or os.environ.get(self._api_key_env)

    def available(self) -> bool:
        return bool(self._key())

    def fingerprint(self) -> str:
        return f"gemini:{self._model}"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        try:
            import google.generativeai as genai
        except ModuleNotFoundError as exc:  # pragma: no cover - exercised without the extra
            raise CapabilityUnavailableError(
                "The 'gemini' provider requires the 'ai-gemini' extra. Install it with: "
                "pip install 'codebase-architect[ai-gemini]'"
            ) from exc

        genai.configure(api_key=self._key())
        model = genai.GenerativeModel(self._model, system_instruction=system)
        response = model.generate_content(
            prompt, generation_config={"max_output_tokens": max_tokens}
        )
        usage = TokenUsage()
        metadata = getattr(response, "usage_metadata", None)
        if metadata is not None:
            usage = TokenUsage(
                input_tokens=getattr(metadata, "prompt_token_count", 0),
                output_tokens=getattr(metadata, "candidates_token_count", 0),
            )
        return Completion(text=response.text, usage=usage)
