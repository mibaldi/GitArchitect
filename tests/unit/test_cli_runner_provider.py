"""Tests for the CLI runner AI provider (HTTP mocked, no real runner)."""

from __future__ import annotations

import json
import urllib.error

import pytest

from codebase_architect.application.registries.ai_registry import build_ai_provider
from codebase_architect.infrastructure.ai_providers import cli_runner
from codebase_architect.infrastructure.ai_providers.cli_runner import CliRunnerProvider
from codebase_architect.shared.config import CliRunnerSettings, Settings
from codebase_architect.shared.errors import CapabilityUnavailableError


@pytest.fixture
def captured(monkeypatch):
    """Stub the HTTP POST; record the call and return a programmable response."""
    calls: dict = {}

    def fake_post(url, data, headers, timeout):
        calls["url"] = url
        calls["headers"] = headers
        calls["payload"] = json.loads(data)
        calls["timeout"] = timeout
        return calls["status"], calls["body"]

    monkeypatch.setattr(cli_runner, "_http_post_json", fake_post)
    return calls


def _ok_body(output: str = "narrative text") -> str:
    return json.dumps({"status": "succeeded", "output": output, "exit_code": 0})


def test_available_only_with_base_url() -> None:
    assert CliRunnerProvider(base_url="").available() is False
    assert CliRunnerProvider(base_url="http://100.1.1.1:8787").available() is True


def test_registry_builds_cli_runner() -> None:
    provider = build_ai_provider("cli_runner", base_url="http://100.1.1.1:8787")
    assert isinstance(provider, CliRunnerProvider)


def test_generic_fields_map_to_secret_and_agent(captured) -> None:
    # The dashboard drives the runner via the generic fields: api_key -> shared
    # secret, model -> agent. Verify the registry's uniform call maps them.
    captured["status"], captured["body"] = 200, _ok_body()
    provider = build_ai_provider(
        "cli_runner", base_url="http://host:8787", api_key="sek", model="codex"
    )
    provider.complete(system="", prompt="hi")
    assert captured["payload"]["agent"] == "codex"
    assert captured["headers"]["Authorization"] == "Bearer sek"


def test_success_returns_completion_and_posts_expected_payload(captured) -> None:
    captured["status"], captured["body"] = 200, _ok_body("hello from claude")
    provider = CliRunnerProvider(base_url="http://host:8787", agent="claude", working_dir="/dev/p")
    completion = provider.complete(system="SYS", prompt="PROMPT")
    assert completion.text == "hello from claude"
    assert completion.usage.total == 0  # runner sent no usage
    assert captured["url"] == "http://host:8787/v1/run"
    assert captured["payload"]["agent"] == "claude"
    assert captured["payload"]["working_dir"] == "/dev/p"
    assert "PROMPT" in captured["payload"]["prompt"]
    assert "Authorization" not in captured["headers"]  # no secret configured


def test_runner_usage_mapped_to_token_usage(captured) -> None:
    captured["status"] = 200
    captured["body"] = json.dumps(
        {
            "status": "succeeded",
            "output": "narrative",
            "exit_code": 0,
            "usage": {"input_tokens": 9486, "output_tokens": 20},
        }
    )
    provider = CliRunnerProvider(base_url="http://host:8787")
    completion = provider.complete(system="", prompt="hi")
    assert completion.usage.input_tokens == 9486
    assert completion.usage.output_tokens == 20


def test_malformed_usage_defaults_to_zero(captured) -> None:
    captured["status"] = 200
    captured["body"] = json.dumps(
        {"status": "succeeded", "output": "n", "usage": {"input_tokens": "x", "output_tokens": -5}}
    )
    provider = CliRunnerProvider(base_url="http://host:8787")
    assert provider.complete(system="", prompt="hi").usage.total == 0


def test_shared_secret_sets_bearer_header(captured) -> None:
    captured["status"], captured["body"] = 200, _ok_body()
    provider = CliRunnerProvider(base_url="http://host:8787", shared_secret="s3cret")
    provider.complete(system="", prompt="hi")
    assert captured["headers"]["Authorization"] == "Bearer s3cret"


def test_failed_status_raises(captured) -> None:
    captured["status"], captured["body"] = 200, json.dumps(
        {"status": "failed", "output": "", "stderr": "boom", "exit_code": 1}
    )
    with pytest.raises(CapabilityUnavailableError, match="failed"):
        CliRunnerProvider(base_url="http://host:8787").complete(system="", prompt="x")


def test_auth_error_raises(captured) -> None:
    captured["status"], captured["body"] = 401, ""
    with pytest.raises(CapabilityUnavailableError, match="rejected"):
        CliRunnerProvider(base_url="http://host:8787").complete(system="", prompt="x")


def test_server_error_raises(captured) -> None:
    captured["status"], captured["body"] = 503, ""
    with pytest.raises(CapabilityUnavailableError, match="server error"):
        CliRunnerProvider(base_url="http://host:8787").complete(system="", prompt="x")


def test_invalid_json_raises(captured) -> None:
    captured["status"], captured["body"] = 200, "not json"
    with pytest.raises(CapabilityUnavailableError, match="invalid response"):
        CliRunnerProvider(base_url="http://host:8787").complete(system="", prompt="x")


def test_unreachable_runner_raises(monkeypatch) -> None:
    def boom(url, data, headers, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(cli_runner, "_http_post_json", boom)
    with pytest.raises(CapabilityUnavailableError, match="not reachable"):
        CliRunnerProvider(base_url="http://host:8787").complete(system="", prompt="x")


def test_timeout_raises(monkeypatch) -> None:
    def slow(url, data, headers, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(cli_runner, "_http_post_json", slow)
    with pytest.raises(CapabilityUnavailableError, match="not reachable"):
        CliRunnerProvider(base_url="http://host:8787").complete(system="", prompt="x")


def test_settings_parse_cli_runner_env(monkeypatch) -> None:
    monkeypatch.setenv("CA_CLI_RUNNER__BASE_URL", "http://100.83.238.95:8787")
    monkeypatch.setenv("CA_CLI_RUNNER__AGENT", "codex")
    monkeypatch.setenv("CA_CLI_RUNNER__TIMEOUT_SECONDS", "300")
    settings = Settings(_env_file=None)
    assert settings.cli_runner.base_url == "http://100.83.238.95:8787"
    assert settings.cli_runner.agent == "codex"
    assert settings.cli_runner.timeout_seconds == 300


def test_settings_default_cli_runner_is_unconfigured() -> None:
    assert CliRunnerSettings().base_url is None
