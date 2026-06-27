"""Null AI provider used for static-only scans (no AI narrative)."""

from __future__ import annotations

from typing import ClassVar

from codebase_architect.domain.model.ai import Completion
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.shared.errors import CapabilityUnavailableError


class NullAIProvider(AIProvider):
    """A provider that is never available; selecting it yields static-only docs."""

    name: ClassVar[str] = "null"

    def available(self) -> bool:
        return False

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        raise CapabilityUnavailableError("No AI provider configured (running static-only).")
