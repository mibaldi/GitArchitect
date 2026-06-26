"""CLI entrypoint.

Exposes ``version`` and ``scan``. ``scan`` runs the full static pipeline
(import → analyze → infer architecture → build & render documentation) and, when
given ``--out``, writes a Markdown + Mermaid documentation bundle. Typer is an
optional dependency (the ``cli`` extra); importing this module without it raises
a clear, actionable error.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codebase_architect import __version__
from codebase_architect.shared.errors import ConfigurationError

try:
    import typer
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without the extra
    raise ConfigurationError(
        "The CLI requires the 'cli' extra. Install it with: pip install 'codebase-architect[cli]'"
    ) from exc

from codebase_architect.application.pipeline.scan_pipeline import ScanPipeline, ScanResult
from codebase_architect.application.registries.ai_registry import build_ai_provider
from codebase_architect.application.registries.source_resolver import SourceProviderResolver
from codebase_architect.application.use_cases.build_code_model import BuildCodeModelUseCase
from codebase_architect.application.use_cases.import_source import ImportSourceUseCase
from codebase_architect.infrastructure.detection.language_detector import ExtensionLanguageDetector
from codebase_architect.infrastructure.detection.manifest_detector import CompositeManifestDetector
from codebase_architect.infrastructure.export.folder_exporter import FolderExporter
from codebase_architect.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from codebase_architect.infrastructure.rendering.markdown_renderer import MarkdownMermaidRenderer
from codebase_architect.infrastructure.source_providers import default_source_providers
from codebase_architect.shared.config import get_settings
from codebase_architect.shared.errors import CodebaseArchitectError

app = typer.Typer(
    name="architect",
    help="Codebase Architect — analyze any codebase and generate clean documentation.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Codebase Architect command-line interface."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", help="Bind port"),
) -> None:
    """Run the REST API (requires the 'api' extra)."""
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        typer.secho(
            "The API requires the 'api' extra: pip install 'codebase-architect[api]'",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc
    uvicorn.run("codebase_architect.api.app:create_app", host=host, port=port, factory=True)


@app.command()
def scan(
    location: str = typer.Argument(
        ..., help="Git URL, local folder, local Git repo, .zip or .tar.gz"
    ),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="Write the Markdown + Mermaid documentation to this folder"
    ),
    title: str | None = typer.Option(
        None, "--title", "-t", help="Project title for the documentation"
    ),
    static_only: bool = typer.Option(
        False, "--static-only", help="Skip the AI narrative pass (deterministic output only)"
    ),
    ai_provider: str | None = typer.Option(
        None, "--ai-provider", help="AI provider for the narrative (default: from config)"
    ),
) -> None:
    """Scan a codebase and generate clean documentation.

    Runs the full pipeline and prints a summary. With ``--out`` it also writes a
    Markdown + Mermaid documentation bundle (overview, architecture, modules,
    functionalities, entrypoints, flows and dependencies). The AI narrative is
    used when a provider is configured; otherwise the scan degrades to static.
    """
    settings = get_settings()
    use_static_only = static_only or settings.scan.static_only
    provider = build_ai_provider(ai_provider or settings.ai.default_provider)
    if not use_static_only and not provider.available():
        typer.secho(
            f"AI provider '{provider.name}' is not configured; running static-only.",
            fg=typer.colors.YELLOW,
        )

    pipeline = ScanPipeline(
        importer=ImportSourceUseCase(
            resolver=SourceProviderResolver(default_source_providers()),
            workspaces_dir=Path(settings.workspaces_dir),
        ),
        model_builder=BuildCodeModelUseCase(
            language_detector=ExtensionLanguageDetector(),
            parser=TreeSitterParser(),
            manifest_detector=CompositeManifestDetector(),
        ),
        renderer=MarkdownMermaidRenderer(),
        exporter=FolderExporter(),
        ai_provider=provider,
    )
    try:
        result = pipeline.run(
            location,
            project_title=title or _default_title(location),
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            out_dir=out,
            static_only=use_static_only,
        )
    except CodebaseArchitectError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    _print_summary(result)


def _default_title(location: str) -> str:
    name = Path(location.rstrip("/")).name
    for suffix in (".git", ".zip", ".tar.gz", ".tgz", ".tar"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name or "Codebase"


def _print_summary(result: ScanResult) -> None:
    model = result.code_model
    typer.secho("Scanned codebase", fg=typer.colors.GREEN)
    typer.echo(f"  type:     {result.workspace.source_type.value}")
    typer.echo(f"  base_ref: {result.workspace.base_ref}")

    typer.secho("\nLanguages", fg=typer.colors.CYAN)
    breakdown = model.language_breakdown()
    if breakdown:
        for stat in breakdown:
            typer.echo(f"  {stat.language.value:<12} {stat.files:>4} files  {stat.loc:>7} LOC")
    else:
        typer.echo("  (no recognized source files)")

    typer.secho("\nStacks", fg=typer.colors.CYAN)
    if model.stacks:
        for stack in model.stacks:
            version = f" {stack.version}" if stack.version else ""
            typer.echo(f"  {stack.name}{version}  ({stack.category.value}) — {stack.evidence}")
    else:
        typer.echo("  (none detected)")

    typer.secho("\nTotals", fg=typer.colors.CYAN)
    typer.echo(f"  modules:      {len(result.module_graph.modules)}")
    internal = len(result.module_graph.edges)
    external = len(model.dependencies)
    typer.echo(f"  dependencies: {internal} internal / {external} external")
    typer.echo(f"  symbols:      {model.symbol_count}")
    typer.echo(f"  entrypoints:  {len(result.entrypoints)}")

    typer.secho("\nAI narrative", fg=typer.colors.CYAN)
    if result.narrative is not None:
        narrative = result.narrative
        typer.echo(f"  features:     {len(narrative.features)}")
        typer.echo(f"  flows:        {len(narrative.flows)}")
        typer.echo(f"  tokens:       {narrative.usage.total}")
    else:
        typer.echo("  (static-only; no AI narrative)")

    if result.bundle is not None:
        typer.secho("\nDocumentation written", fg=typer.colors.GREEN)
        typer.echo(f"  {result.bundle.root}  ({len(result.bundle.files)} files)")
        typer.echo(f"  open {result.bundle.root}/README.md")
    else:
        typer.echo("\n(no --out given; documentation not written)")


if __name__ == "__main__":  # pragma: no cover
    app()
