# CLAUDE.md

Guidance for working in this repository.

## What this is

Codebase Architect scans any source (Git remote/local, folder, `.zip`,
`.tar.gz`) and generates clean documentation of its **architecture,
functionalities and flows** (Markdown + Mermaid, or HTML via a plugin). It is
**read-only** — it never modifies the analyzed code — and not coupled to any Git
hosting provider or AI vendor.

Full design: `docs/SDD.md`. Usage: `docs/USAGE.md`.

## Architecture (hexagonal — non-negotiable)

Dependencies point **inward**; the domain is pure. Enforced by import-linter
(`lint-imports`), which is part of the gate.

```
cli / api / workers     (drivers)
        │
   application           use cases, pipeline, registries, services
        │
     domain              model + ports (interfaces) + pure services   ← imports nothing outward
        │
 infrastructure          adapters implementing the ports
        │
   plugins               discovered via entry points
   shared                config, logging, errors, ids (innermost)
```

Rules (all checked in CI):
- `domain` must not import `application`/`infrastructure`/`api`/`cli`/`workers`/
  `agents`/`plugins`. It uses only stdlib + `shared`.
- The core never imports `plugins` directly (only via registries) or any Git
  hosting SDK.
- New capabilities are **adapters** implementing a domain **port**; wiring
  happens in the composition roots (`cli/main.py`, `api/app.py`).

Layout: `src/codebase_architect/{domain,application,infrastructure,api,cli,
workers,agents,shared}`. Example plugin: `plugins/html_site`.

## The pipeline

`ScanPipeline.run()` (application) is the single flow both CLI and API drive:

```
import → build CodeModel → module graph → infer architecture → entrypoints
       → secret scan → (AI narrative, cached) → build Documentation IR
       → render → export
```

Everything is injected as ports, so swapping an adapter (renderer, AI provider,
exporter) changes nothing in the pipeline.

## Dev setup & the gate

```bash
make install        # uv venv + install .[dev,cli] (+ api/plugin as needed)
. .venv/bin/activate
uv pip install -e '.[dev,cli,api]' && uv pip install -e plugins/html_site

make check          # the full gate, same as CI:
#   ruff check src tests plugins   (lint + import sort)
#   mypy                           (strict)
#   lint-imports                   (hexagonal contracts)
#   pytest                         (unit/contract/architecture/api)
```

Always run `make check` before committing. Keep it green.

## Conventions

- **Optional dependencies** (anthropic, openai, google-generativeai, fastapi,
  typer) are lazy-imported behind extras (`ai`, `ai-openai`, `ai-gemini`,
  `api`, `cli`); the core runs without them. Selecting an absent capability
  raises a clear `CapabilityUnavailableError`/`ConfigurationError`.
- **AI is grounded**: narrative prompts contain only static facts (module ids,
  symbols, entrypoints) — never source code — and any hallucinated reference is
  filtered out. Don't put file contents in prompts.
- **Determinism**: domain services take `generated_at`/timestamps as arguments
  (no `datetime.now()` in the domain) so output is reproducible and testable.
- **Tests**: pure logic in `tests/unit`; shared port behavior in
  `tests/contract`; the hexagonal contracts in `tests/architecture`. AI is
  tested with deterministic fakes (no network).
- Line length 100; ruff + mypy strict; Python ≥ 3.11.

## Current state & what's not done

Implemented F0–F8 (see `docs/SDD.md` §13). Verified end-to-end for the static
path (CLI, API, Docker). **Not implemented yet**: Postgres persistence + Arq
workers (scan state is in memory), hosting plugins (GitHub/GitLab/Bitbucket),
broader language coverage. **Not exercised live**: real LLM calls (no API keys
in CI) — implemented per the official SDKs and covered by fakes.

## Run it

```bash
architect scan <source> --out ./docs            # CLI
architect serve --port 8000                     # API
docker compose up --build                        # container
```
