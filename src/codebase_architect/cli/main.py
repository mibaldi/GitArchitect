"""CLI entrypoint.

Currently exposes ``version`` and ``scan``. In this phase ``scan`` performs the
import step (materializing any supported source into an isolated, read-only
workspace) and reports what it found; later phases add analysis, AI narrative
and documentation rendering. Typer is an optional dependency (the ``cli``
extra); importing this module without it raises a clear, actionable error.
"""

from __future__ import annotations

from pathlib import Path

from codebase_architect import __version__
from codebase_architect.shared.errors import ConfigurationError

try:
    import typer
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without the extra
    raise ConfigurationError(
        "The CLI requires the 'cli' extra. Install it with: pip install 'codebase-architect[cli]'"
    ) from exc

from codebase_architect.application.registries.source_resolver import SourceProviderResolver
from codebase_architect.application.use_cases.build_code_model import BuildCodeModelUseCase
from codebase_architect.application.use_cases.import_source import ImportSourceUseCase
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.infrastructure.detection.language_detector import ExtensionLanguageDetector
from codebase_architect.infrastructure.detection.manifest_detector import CompositeManifestDetector
from codebase_architect.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
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
def scan(
    location: str = typer.Argument(
        ..., help="Git URL, local folder, local Git repo, .zip or .tar.gz"
    ),
) -> None:
    """Import a codebase and run static analysis, printing a summary.

    Later phases extend this command to infer architecture, narrate with AI and
    render documentation. For now it materializes the source and reports the
    detected languages, stacks and code symbols.
    """
    settings = get_settings()
    importer = ImportSourceUseCase(
        resolver=SourceProviderResolver(default_source_providers()),
        workspaces_dir=Path(settings.workspaces_dir),
    )
    analyzer = BuildCodeModelUseCase(
        language_detector=ExtensionLanguageDetector(),
        parser=TreeSitterParser(),
        manifest_detector=CompositeManifestDetector(),
    )
    try:
        workspace = importer.execute(location)
        model = analyzer.execute(workspace)
    except CodebaseArchitectError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho("Imported codebase", fg=typer.colors.GREEN)
    typer.echo(f"  workspace:  {workspace.id}")
    typer.echo(f"  type:       {workspace.source_type.value}")
    typer.echo(f"  path:       {workspace.root_path}")
    typer.echo(f"  has_git:    {workspace.has_git}")
    typer.echo(f"  base_ref:   {workspace.base_ref}")
    _print_code_model(model)


def _print_code_model(model: CodeModel) -> None:
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
    typer.echo(f"  parsed files: {len(model.parsed_files)}")
    typer.echo(f"  symbols:      {model.symbol_count}")
    typer.echo(f"  dependencies: {len(model.dependencies)}")
    typer.echo(f"  other files:  {model.other_file_count}")


if __name__ == "__main__":  # pragma: no cover
    app()
