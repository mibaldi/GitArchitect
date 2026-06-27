"""Tests for the standalone CLI runner (subprocess mocked, no real CLI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from cli_runner import main as runner
from cli_runner.main import RunResponse, app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("CLI_RUNNER_ALLOWED_DIRS", str(tmp_path))
    monkeypatch.delenv("CLI_RUNNER_SHARED_SECRET", raising=False)
    # Never actually invoke a CLI in tests.
    monkeypatch.setattr(
        runner, "_run_agent", lambda cmd, wd, t: RunResponse(status="succeeded", output="ok")
    )
    return TestClient(app)


def _req(tmp_path: Path, **kw: object) -> dict:
    base = {"agent": "claude", "prompt": "hi", "working_dir": str(tmp_path)}
    base.update(kw)
    return base


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_run_succeeds_within_allowed_dir(client: TestClient, tmp_path: Path) -> None:
    resp = client.post("/v1/run", json=_req(tmp_path))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded" and body["output"] == "ok"


def test_disallowed_agent_rejected(client: TestClient, tmp_path: Path) -> None:
    assert client.post("/v1/run", json=_req(tmp_path, agent="rm")).status_code == 400


def test_working_dir_outside_allowlist_rejected(client: TestClient) -> None:
    resp = client.post("/v1/run", json=_req(Path("/etc"), working_dir="/etc"))
    assert resp.status_code == 403


def test_shared_secret_enforced(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLI_RUNNER_ALLOWED_DIRS", str(tmp_path))
    monkeypatch.setenv("CLI_RUNNER_SHARED_SECRET", "top-secret")
    monkeypatch.setattr(
        runner, "_run_agent", lambda cmd, wd, t: RunResponse(status="succeeded", output="ok")
    )
    c = TestClient(app)
    assert c.post("/v1/run", json=_req(tmp_path)).status_code == 401  # no header
    wrong = c.post(
        "/v1/run", json=_req(tmp_path), headers={"Authorization": "Bearer wrong"}
    )
    assert wrong.status_code == 401
    ok = c.post(
        "/v1/run", json=_req(tmp_path), headers={"Authorization": "Bearer top-secret"}
    )
    assert ok.status_code == 200


def test_run_agent_reports_failed_exit_code(tmp_path: Path, monkeypatch) -> None:
    class _Proc:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: _Proc())
    out = runner._run_agent(["claude", "--print", "x"], str(tmp_path), 5)
    assert out.status == "failed" and out.exit_code == 1 and out.stderr == "boom"
