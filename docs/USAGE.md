# Usage

Codebase Architect scans any source and generates clean documentation of its
architecture, functionalities and flows as Markdown + Mermaid (or HTML via a
plugin). It works as a CLI and a REST API.

## Install

```bash
# Dev environment (uv recommended)
uv venv --python 3.11 .venv
. .venv/bin/activate
uv pip install -e '.[dev,cli,api]'

# Optional AI providers and the example HTML renderer plugin
uv pip install -e '.[ai]'            # Claude (anthropic)
uv pip install -e '.[ai-openai]'     # OpenAI / OpenRouter / local servers
uv pip install -e '.[ai-gemini]'     # Google Gemini
uv pip install -e plugins/html_site  # --renderer html
```

## CLI

```bash
architect scan <source> --out ./docs            # generate Markdown + Mermaid
architect scan <source> --out ./site --renderer html
architect scan <source> --out ./docs --static-only   # skip the AI pass
architect serve --host 0.0.0.0 --port 8000      # run the REST API
architect version
```

`<source>` is a remote Git URL, a local Git repo, a folder, a `.zip` or a
`.tar.gz`. The generated bundle contains: `README.md` (overview), `architecture.md`
(layers + module-dependency Mermaid graph), `modules.md`, `features.md`
(AI), `entrypoints.md`, `flows.md`, `dependencies.md`, `security.md`.

Useful flags: `--title`, `--ai-provider <name>`, `--renderer <name>`,
`--no-ai-cache`, `--include <glob>`, `--exclude <glob>`, `--no-gitignore`.
By default a repository's `.gitignore` is honored and common build/output dirs
are skipped.

## Private repositories

The Git provider just runs `git clone`, so authenticate the way `git` already
expects. Three options, easiest first:

1. **Scan a local checkout (no token in the tool).** Clone it yourself where you
   already have credentials, then point the scan at the folder. With Docker,
   mount it read-only and use its in-container path:
   ```bash
   git clone git@github.com:me/private.git ./private
   architect scan ./private --out ./docs
   # Docker: mount `- ./private:/scan/private:ro` then scan "/scan/private"
   ```
2. **HTTPS + a read-only token in the URL.** Use a token with read access to the
   repository's contents:
   ```bash
   # GitHub (fine-grained PAT, Contents: read)
   architect scan https://x-access-token:<TOKEN>@github.com/me/private.git --out ./docs
   # GitLab:    https://oauth2:<TOKEN>@gitlab.com/me/private.git
   # Bitbucket: https://x-token-auth:<TOKEN>@bitbucket.org/me/private.git
   ```
   Credentials in the source URL are redacted from logs and API errors, but
   prefer option 1 or 3 if you'd rather the token never enter the tool.
3. **SSH.** Use `git@host:me/private.git` with a (read-only deploy) key available
   to `git`. In the Docker image add `openssh-client` and mount the key, since
   the slim image ships `git` without an SSH client.

## Functional specs & coverage

The dashboard's **Functional specs** panel captures the *intended* behaviour via a
guided wizard (product, actors, then functionalities with structured flow steps
`actor > action > target` and `METHOD /path` endpoints). Specs are global and
persisted. Pick **Coverage** on a spec and a finished scan to reconcile the two:
each functionality is classified **implemented / partial / missing** by matching
its keywords against the scanned entrypoints, modules and symbols, and anything
in the code that no functionality describes is listed as a gap. Matching is
heuristic and evidence-bearing (it shows which artifacts it matched). Reconciling
links the scan to the spec.

```bash
# Reconcile a spec against a scan (after both exist):
curl localhost:47800/specs/<spec_id>/reconcile/<scan_id>
```

### Cross-project flows & sequence diagrams

Projects are scanned **separately**; a spec's **project group** links the scans
that make up one product (frontend, backend, microservices). From there:

- **API flow** — the matcher joins each project's outbound HTTP calls to the
  endpoints another project exposes (template-matched method + path), giving a
  cross-project call graph plus calls nothing serves.
- **Sequence diagrams** — each functionality's structured flow renders as a
  Mermaid `sequenceDiagram` (actors/systems as participants, steps as
  request/response messages, alternative flows as `alt` blocks), with declared
  endpoints annotated ✓ found / ✗ not found from the API flow.

```bash
curl -X POST localhost:47800/specs/<spec_id>/scans/<scan_id>   # link a scan
curl localhost:47800/specs/<spec_id>/api-flow                  # cross-project graph
curl localhost:47800/specs/<spec_id>/sequence                 # sequence diagrams
```

## AI providers

The AI narrative pass is provider-agnostic and **grounded in the static facts**
(module ids, symbols, entrypoints) — never your source code. Without a
configured provider, scans run static-only.

| Provider | `--ai-provider` | Credentials |
|----------|-----------------|-------------|
| Claude (default) | `claude` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai` | `OPENAI_API_KEY` (`CA_OPENAI_MODEL`) |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` |
| Gemini | `gemini` | `GOOGLE_API_KEY` (`CA_GEMINI_MODEL`) |
| Local (Ollama, …) | `local` | none (`CA_LOCAL_ENDPOINT`, `CA_LOCAL_MODEL`) |
| Remote CLI runner | `cli_runner` | none — uses a logged-in `claude`/`codex` CLI |

Narratives are cached (keyed by the analysis facts + provider), so re-scanning
an unchanged codebase reuses the result and spends 0 tokens. Bypass with
`--no-ai-cache` or `CA_AI__CACHE_ENABLED=false`.

### Remote CLI runner (no API key, no local model)

Reuse an **already-authenticated** Claude or Codex CLI on another machine — e.g.
a Mac on your tailnet — instead of a provider API key. GitArchitect POSTs the
(grounded) prompt to a small runner that runs the CLI and returns its text. It
performs HTTP only; it never runs a local command.

```
GitArchitect ──HTTP──▶ CLI runner (Mac) ──▶ claude/codex CLI
```

1. On the Mac, start the runner (see [`tools/cli_runner/README.md`](../tools/cli_runner/README.md)):
   ```bash
   export CLI_RUNNER_ALLOWED_DIRS="$HOME/dev"
   export CLI_RUNNER_SHARED_SECRET="…"
   uvicorn cli_runner.main:app --host 0.0.0.0 --port 8787
   ```
2. Point GitArchitect at it (the Mac's Tailscale IP from `tailscale ip -4`):
   ```bash
   export CA_CLI_RUNNER__BASE_URL=http://100.83.238.95:8787
   export CA_CLI_RUNNER__AGENT=claude        # or codex
   export CA_CLI_RUNNER__SHARED_SECRET=…      # same secret
   architect scan <source> --out ./docs --ai-provider cli_runner
   ```

If the runner is unreachable or the agent fails, the scan degrades to static
docs with a clear error in the logs (credentials/URLs are redacted).

**From the dashboard** you don't need env vars: open **Settings**, pick provider
`cli_runner`, and the fields become *Runner URL*, *Shared secret* and *Agent*
(claude/codex). Use **Test runner connection** to verify it, then uncheck
"Static only" when scanning. Settings stay in your browser; the runner URL/secret
travel with each scan request (in memory, never persisted or logged).

## Web dashboard + REST API

```bash
architect serve            # http://127.0.0.1:47800  (non-standard port)
```

Open `http://127.0.0.1:47800/` for the dashboard: enter a source **or upload a
`.zip` / `.tar.gz`**, launch a scan, watch the status, **download** the `.zip`,
and **view** each page (Markdown + Mermaid) rendered live. Uploaded archives are
streamed to a temp file, scanned, and **discarded** — nothing is persisted on
the server, so you don't need to place a file on the host first. OpenAPI docs
are at `/docs`.

REST endpoints (everything the dashboard uses):

```bash
curl localhost:47800/health
# Submit a scan (async): returns 202 {id, status}
curl -X POST localhost:47800/scans -H 'content-type: application/json' \
  -d '{"location": "/path/to/project", "static_only": true}'
# Or upload an archive (multipart); it is scanned then deleted:
curl -X POST localhost:47800/scans/upload \
  -F file=@project.zip -F static_only=true
# Poll status until "done", then read the docs / download the bundle
curl localhost:47800/scans/<id>
curl localhost:47800/scans/<id>/documentation
curl localhost:47800/scans/<id>/pages/architecture
curl localhost:47800/scans/<id>/architecture
curl -OJ localhost:47800/scans/<id>/download   # documentation.zip
```

## Docker Compose

```bash
docker compose up --build -d
curl localhost:47800/health
```

The container binds to `127.0.0.1:47800` (host-only, non-standard port). To
reach the dashboard over your tailnet without exposing anything publicly, use
Tailscale Serve on the VPS:

```bash
tailscale serve --bg 47800      # serves it on your MagicDNS hostname over HTTPS
```

To scan a local project, mount it and use its in-container path as the Source —
uncomment the `./myproject:/scan/myproject:ro` volume in `docker-compose.yml`.

Set `ANTHROPIC_API_KEY` (env or `.env`) to enable the AI narrative. The
`postgres`/`redis` services are opt-in for future phases:
`docker compose --profile full up`.

## Configuration

Environment variables use the `CA_` prefix and `__` for nesting (see
`.env.example`). Common ones:

```
CA_LOG_JSON=true
CA_DATA_DIR=./data
CA_WORKSPACES_DIR=./workspaces
CA_SCAN__STATIC_ONLY=false
CA_AI__DEFAULT_PROVIDER=claude
CA_AI__MAX_TOKENS=4096
CA_AI__CACHE_ENABLED=true
CA_GIT__ENABLED=true
```

## Extending

- **Renderers** and **AI providers** are plugins discovered from the
  `codebase_architect.renderers` / `codebase_architect.ai_providers`
  entry-point groups. See `plugins/html_site` for a working renderer plugin.
- New source providers, parsers (languages) and exporters are added as
  infrastructure adapters implementing the matching domain port — the core
  never changes.
