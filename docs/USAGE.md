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
`--no-ai-cache`.

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

Narratives are cached (keyed by the analysis facts + provider), so re-scanning
an unchanged codebase reuses the result and spends 0 tokens. Bypass with
`--no-ai-cache` or `CA_AI__CACHE_ENABLED=false`.

## REST API

```bash
architect serve --port 8000

curl localhost:8000/health
# Submit a scan (async): returns 202 {id, status}
curl -X POST localhost:8000/scans -H 'content-type: application/json' \
  -d '{"location": "/path/to/project", "static_only": true}'
# Poll status until "done", then read the docs / download the bundle
curl localhost:8000/scans/<id>
curl localhost:8000/scans/<id>/documentation
curl localhost:8000/scans/<id>/architecture
curl localhost:8000/scans/<id>/code-model
curl -OJ localhost:8000/scans/<id>/download   # documentation.zip
```

OpenAPI docs are served at `/docs`.

## Docker Compose

```bash
docker compose up --build
curl localhost:8000/health
```

To scan a local project via the API, mount it and POST its in-container path —
uncomment the `./myproject:/scan/myproject:ro` volume in `docker-compose.yml`,
then:

```bash
curl -X POST localhost:8000/scans -H 'content-type: application/json' \
  -d '{"location": "/scan/myproject", "static_only": true}'
```

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
