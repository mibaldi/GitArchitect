# GitArchitect CLI Runner

A tiny HTTP service that runs an **already-authenticated** `claude` or `codex`
CLI on this machine and returns its text output. GitArchitect points its
`cli_runner` AI provider at it, so you get AI narratives **without any provider
API key and without running a local model** — the runner reuses your CLI login.

```
GitArchitect  ──HTTP──▶  CLI Runner (this)  ──▶  claude/codex CLI  ──▶  repo
```

Run it on the machine where the CLI is logged in (e.g. your Mac), reachable over
a private network such as Tailscale. It only ever runs the two fixed commands
below — never an arbitrary command from the client.

## Install & run (macOS)

```bash
cd tools/cli_runner
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# the CLI you want must already be installed and logged in:
claude --version        # or: codex --version

export CLI_RUNNER_ALLOWED_DIRS="$HOME/dev,$HOME/projects"
export CLI_RUNNER_SHARED_SECRET="$(openssl rand -hex 24)"   # optional but recommended
export CLI_RUNNER_DEFAULT_TIMEOUT_SECONDS=600

uvicorn cli_runner.main:app --host 0.0.0.0 --port 8787
```

Check it: `curl http://localhost:8787/health` → `{"status":"ok"}`.

## Configuration (environment)

| Variable | Required | Meaning |
|----------|----------|---------|
| `CLI_RUNNER_ALLOWED_DIRS` | yes | Comma-separated absolute dirs; `working_dir` must be inside one |
| `CLI_RUNNER_SHARED_SECRET` | no | If set, requests must send `Authorization: Bearer <secret>` |
| `CLI_RUNNER_DEFAULT_TIMEOUT_SECONDS` | no | Default subprocess timeout (600) |

Allowed agents and the exact command each runs:

| agent | command |
|-------|---------|
| `claude` | `claude --print "<prompt>"` |
| `codex` | `codex exec "<prompt>"` |

## API

`GET /health` → `{"status":"ok"}`

`POST /v1/run`

```json
{ "agent": "claude", "task": "narrate",
  "working_dir": "/Users/me/dev/GitArchitect",
  "prompt": "…", "timeout_seconds": 600, "metadata": {} }
```

→ `{"status":"succeeded","output":"…","stderr":"","duration_ms":1234,"exit_code":0,
"usage":{"input_tokens":9486,"output_tokens":20}}`
(or `"status":"failed"` with `stderr` on a non-zero exit / timeout / missing CLI).
`usage` is filled for `claude` (run in `--output-format json` mode; requires a
claude CLI that supports that flag) and empty for agents that do not report
token counts. Cache read/creation tokens are counted as input.

## Reach it over Tailscale

The runner binds `0.0.0.0:8787`; from GitArchitect set:

```
CA_AI__DEFAULT_PROVIDER=cli_runner
CA_CLI_RUNNER__BASE_URL=http://<tailscale-ip-of-the-mac>:8787
CA_CLI_RUNNER__AGENT=claude
CA_CLI_RUNNER__SHARED_SECRET=<same secret>
```

Get the Mac's Tailscale IP with `tailscale ip -4`.

## Keep it running (launchd)

Edit `com.gitarchitect.cli-runner.plist` (paths, dirs, secret), then:

```bash
cp com.gitarchitect.cli-runner.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.gitarchitect.cli-runner.plist
launchctl start com.gitarchitect.cli-runner
```

## Security

- Only `claude`/`codex` are allowed; the prompt is passed as a single argv
  element (no shell), so a client cannot inject extra commands.
- `working_dir` is validated against `CLI_RUNNER_ALLOWED_DIRS`.
- Set `CLI_RUNNER_SHARED_SECRET` and keep the port on your tailnet (never public).
