"""Minimal remote CLI runner for GitArchitect.

Runs an already-authenticated `claude` or `codex` CLI on this machine and returns
its text output over HTTP. Intended to run on a Mac where the CLI is logged in,
reachable over a private network (e.g. Tailscale). It only ever runs the two
fixed commands below — never an arbitrary command sent by the client.

    POST /v1/run   {agent, prompt, working_dir, timeout_seconds, metadata}
    GET  /health

Config (environment):
    CLI_RUNNER_ALLOWED_DIRS=/Users/me/dev,/Users/me/projects   (required)
    CLI_RUNNER_SHARED_SECRET=...                                (optional bearer)
    CLI_RUNNER_DEFAULT_TIMEOUT_SECONDS=600

Run it:
    uvicorn cli_runner.main:app --host 0.0.0.0 --port 8787
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# agent -> argv builder. The prompt is always a single, separate argv element
# (never a shell string), so the client cannot inject extra commands.
# claude runs in JSON mode so we can report token usage alongside the text.
_AGENTS: dict[str, list[str]] = {
    "claude": ["claude", "--print", "--output-format", "json"],
    "codex": ["codex", "exec"],
}

app = FastAPI(title="GitArchitect CLI Runner", version="1.0.0")


class RunRequest(BaseModel):
    agent: str
    prompt: str
    task: str = "narrate"
    working_dir: str = ""
    timeout_seconds: int | None = None
    metadata: dict = {}


class RunResponse(BaseModel):
    status: str  # "succeeded" | "failed"
    output: str = ""
    stderr: str = ""
    duration_ms: int = 0
    exit_code: int = 0
    usage: dict[str, int] = {}  # {"input_tokens": N, "output_tokens": M} when known


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/run", response_model=RunResponse)
def run(req: RunRequest, authorization: str | None = Header(default=None)) -> RunResponse:
    _check_auth(authorization)
    if req.agent not in _AGENTS:
        raise HTTPException(status_code=400, detail=f"agent not allowed: {req.agent}")
    working_dir = _resolve_dir(req.working_dir)
    timeout = req.timeout_seconds or _default_timeout()
    cmd = [*_AGENTS[req.agent], req.prompt]
    response = _run_agent(cmd, working_dir, timeout)
    if req.agent == "claude":
        response = _parse_claude_json(response)
    return response


def _run_agent(cmd: list[str], working_dir: str, timeout: int) -> RunResponse:
    started = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, prompt is one element
            cmd, cwd=working_dir, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return RunResponse(
            status="failed",
            stderr=f"agent timed out after {timeout}s",
            duration_ms=_ms(started),
            exit_code=124,
        )
    except FileNotFoundError as exc:
        return RunResponse(status="failed", stderr=f"agent CLI not found: {exc}", exit_code=127)
    return RunResponse(
        status="succeeded" if proc.returncode == 0 else "failed",
        output=proc.stdout,
        stderr=proc.stderr[:4000],
        duration_ms=_ms(started),
        exit_code=proc.returncode,
    )


def _parse_claude_json(response: RunResponse) -> RunResponse:
    """Unwrap a `claude --output-format json` envelope: text, errors, token usage.

    Falls back to the raw output when stdout is not the expected envelope, so a
    CLI that ignores the flag still works (just without usage numbers).
    """
    try:
        data = json.loads(response.output)
    except ValueError:
        return response
    if not isinstance(data, dict) or data.get("type") != "result":
        return response
    result = data.get("result")
    result_text = result if isinstance(result, str) else ""
    if data.get("is_error") or response.exit_code != 0:
        stderr = response.stderr or result_text or "agent reported an error"
        return response.model_copy(update={"status": "failed", "stderr": stderr[:4000]})
    if not isinstance(result, str):
        return response.model_copy(
            update={"status": "failed", "stderr": "agent returned a non-text result"}
        )
    return response.model_copy(
        update={"output": result, "usage": _envelope_usage(data.get("usage"))}
    )


def _envelope_usage(raw: object) -> dict[str, int]:
    """Token counts from the envelope; cache reads/writes count as input."""
    if not isinstance(raw, dict):
        return {}

    def count(key: str) -> int:
        value = raw.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

    input_tokens = (
        count("input_tokens")
        + count("cache_creation_input_tokens")
        + count("cache_read_input_tokens")
    )
    output_tokens = count("output_tokens")
    if not input_tokens and not output_tokens:
        return {}
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def _check_auth(authorization: str | None) -> None:
    secret = os.environ.get("CLI_RUNNER_SHARED_SECRET")
    if secret and authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="unauthorized")


def _allowed_dirs() -> list[Path]:
    raw = os.environ.get("CLI_RUNNER_ALLOWED_DIRS", "")
    return [Path(d.strip()).resolve() for d in raw.split(",") if d.strip()]


def _default_timeout() -> int:
    return int(os.environ.get("CLI_RUNNER_DEFAULT_TIMEOUT_SECONDS", "600"))


def _resolve_dir(working_dir: str) -> str:
    allowed = _allowed_dirs()
    if not allowed:
        raise HTTPException(status_code=500, detail="CLI_RUNNER_ALLOWED_DIRS is not configured")
    if not working_dir:
        return str(allowed[0])
    target = Path(working_dir).resolve()
    for base in allowed:
        if target == base or base in target.parents:
            return str(target)
    raise HTTPException(status_code=403, detail="working_dir is outside the allowed directories")


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
