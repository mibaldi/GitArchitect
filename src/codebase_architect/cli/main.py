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
from codebase_architect.application.use_cases.import_source import ImportSourceUseCase
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
    """Import a codebase into an isolated, read-only workspace.

    Later phases extend this command to also analyze the codebase and generate
    documentation. For now it materializes the source and prints a summary.
    """
    settings = get_settings()
    use_case = ImportSourceUseCase(
        resolver=SourceProviderResolver(default_source_providers()),
        workspaces_dir=Path(settings.workspaces_dir),
    )
    try:
        workspace = use_case.execute(location)
    except CodebaseArchitectError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    file_count = sum(1 for _ in workspace.iter_files())
    typer.secho("Imported codebase", fg=typer.colors.GREEN)
    typer.echo(f"  workspace:  {workspace.id}")
    typer.echo(f"  type:       {workspace.source_type.value}")
    typer.echo(f"  path:       {workspace.root_path}")
    typer.echo(f"  has_git:    {workspace.has_git}")
    typer.echo(f"  base_ref:   {workspace.base_ref}")
    typer.echo(f"  files:      {file_count}")


if __name__ == "__main__":  # pragma: no cover
    app()
