# Codebase Architect

Scan any codebase and generate clean documentation of its **architecture,
functionalities and flows** — as Markdown + Mermaid — with a single command.

Codebase Architect is **read-only**: it never modifies the code it analyzes.
It is not coupled to any Git hosting provider (GitHub/GitLab/Bitbucket) nor to
any single AI provider.

```
architect scan <source> --out ./docs-output
```

`<source>` can be a remote Git repo, a local Git repo, a folder, a `.zip` or a
`.tar.gz`.

It also exposes a REST API (the `api` extra):

```
architect serve --port 8000
# POST /scans {"location": "...", "static_only": true}  -> 202 {id, status}
# GET  /scans/{id}                  scan status + summary
# GET  /scans/{id}/documentation    generated pages
# GET  /scans/{id}/download         documentation bundle as a .zip
```

Scans run asynchronously; poll the status endpoint until it reports `done`.

### AI providers & plugins

The AI narrative pass is provider-agnostic. Built-in providers: `claude`,
`openai`, `openrouter`, `gemini`, `local` (any OpenAI-compatible server). Select
with `--ai-provider` or `CA_AI__DEFAULT_PROVIDER`; install the matching extra
(`ai`, `ai-openai`, `ai-gemini`).

Every scan also runs a **secret scan** (redacted findings on the `security`
page) and **caches the AI narrative** so re-scanning an unchanged codebase
reuses the previous result instead of calling the model again
(`--no-ai-cache` forces a fresh call).

Output renderers and AI providers are extensible via entry-point plugins. The
example HTML renderer ships under `plugins/html_site`:

```
pip install -e plugins/html_site
architect scan <source> --out ./site --renderer html   # browsable index.html
```

## How it works

A single scan runs a pipeline:

```
import → discover → parse → model → infer → narrate(AI) → render(Markdown+Mermaid) → write
```

- **Static pass (deterministic):** detects languages, frameworks and
  dependencies; parses code (tree-sitter) into symbols; builds module and
  dependency graphs; infers architecture.
- **AI pass (optional, hybrid):** writes the functionality catalog and flow
  narratives, grounded in the static facts to avoid hallucination. Disable with
  `--static-only`.

## Status

Early development. See [`docs/SDD.md`](docs/SDD.md) for the full design.

## Architecture

Hexagonal (ports & adapters). The core (`domain`) knows nothing about AI
providers, Git hosting or output formats — those live in `infrastructure` and
external `plugins`. Enforced by import-linter.

## License

Apache-2.0.
