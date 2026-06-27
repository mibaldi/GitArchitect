"""AIProvider backed by a remote CLI runner (Claude CLI / Codex CLI).

    GitArchitect  ->  HTTP  ->  Remote CLI Runner  ->  claude/codex CLI  ->  repo

No provider API keys and no local model: the runner runs an already-authenticated
CLI on another machine (e.g. a Mac on your tailnet) and returns its text output.
This provider performs **only** HTTP against the runner — it never executes a
local command. Every failure becomes a :class:`CapabilityUnavailableError`, which
the narrative/enrichment use cases already catch to degrade to static docs.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import ClassVar

from codebase_architect.domain.model.ai import Completion, TokenUsage
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.shared.config import get_settings
from codebase_architect.shared.errors import CapabilityUnavailableError
from codebase_architect.shared.logging import get_logger
from codebase_architect.shared.redaction import redact_url_credentials

logger = get_logger(__name__)

_RUN_PATH = "/v1/run"
_MAX_STDERR = 500


class CliRunnerProvider(AIProvider):
    """Delegates completions to a remote CLI runner over HTTP."""

    name: ClassVar[str] = "cli_runner"

    def __init__(
        self,
        *,
        api_key: str | None = None,  # unused; kept for a uniform registry call
        base_url: str | None = None,
        model: str | None = None,  # unused
        agent: str | None = None,
        timeout_seconds: int | None = None,
        shared_secret: str | None = None,
        working_dir: str | None = None,
    ) -> None:
        cfg = get_settings().cli_runner
        self._base_url = (base_url or cfg.base_url or "").rstrip("/")
        self._agent = agent or cfg.agent or "claude"
        self._timeout = int(timeout_seconds or cfg.timeout_seconds or 600)
        self._secret = shared_secret if shared_secret is not None else cfg.shared_secret
        self._working_dir = working_dir if working_dir is not None else cfg.working_dir

    def available(self) -> bool:
        return bool(self._base_url)

    def fingerprint(self) -> str:
        return f"{self.name}:{self._agent}:{self._base_url}"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4096) -> Completion:
        if not self._base_url:
            raise CapabilityUnavailableError(
                "CLI runner base URL is not configured (set CA_CLI_RUNNER__BASE_URL)."
            )
        url = self._base_url + _RUN_PATH
        payload = json.dumps(
            {
                "agent": self._agent,
                "task": "narrate",
                "working_dir": self._working_dir or "",
                "prompt": f"{system}\n\n{prompt}" if system else prompt,
                "timeout_seconds": self._timeout,
                "metadata": {},
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._secret:
            headers["Authorization"] = f"Bearer {self._secret}"

        # Never log the prompt or the secret — only the agent and the host.
        logger.info("cli_runner_request", agent=self._agent, url=redact_url_credentials(url))
        try:
            status, body = _http_post_json(url, payload, headers, self._timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise CapabilityUnavailableError(
                f"CLI runner not reachable at {redact_url_credentials(url)}."
            ) from exc

        if status in (401, 403):
            raise CapabilityUnavailableError(
                "CLI runner rejected the request (check CA_CLI_RUNNER__SHARED_SECRET)."
            )
        if status >= 500:
            raise CapabilityUnavailableError(f"CLI runner returned a server error ({status}).")
        if status != 200:
            raise CapabilityUnavailableError(f"CLI runner returned status {status}.")

        try:
            data = json.loads(body)
        except (ValueError, TypeError) as exc:
            raise CapabilityUnavailableError("CLI runner returned an invalid response.") from exc

        if not isinstance(data, dict) or data.get("status") != "succeeded":
            stderr = str(data.get("stderr", ""))[:_MAX_STDERR] if isinstance(data, dict) else ""
            raise CapabilityUnavailableError(
                f"CLI runner agent failed: {stderr or 'unknown error'}"
            )

        output = data.get("output")
        if not isinstance(output, str) or not output.strip():
            raise CapabilityUnavailableError("CLI runner returned an empty output.")

        # The CLI does not report token counts; report zeros (safe default).
        return Completion(text=output, usage=TokenUsage())


def _http_post_json(
    url: str, data: bytes, headers: dict[str, str], timeout: int
) -> tuple[int, str]:
    """POST JSON and return (status, body). HTTP error codes are returned, not raised."""
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if exc.fp is not None else ""
        return int(exc.code), body
