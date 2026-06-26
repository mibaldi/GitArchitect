"""CLI entrypoint.

Foundation only: exposes ``architect version``. Real commands (import, analyze,
task, plan, run, status, diff, export) are added in later phases. Typer is an
optional dependency (the ``cli`` extra); importing this module without it raises
a clear, actionable error instead of a bare ``ImportError``.
"""

from __future__ import annotations

from codebase_architect import __version__
from codebase_architect.shared.errors import ConfigurationError

try:
    import typer
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without the extra
    raise ConfigurationError(
        "The CLI requires the 'cli' extra. Install it with: pip install 'codebase-architect[cli]'"
    ) from exc

app = typer.Typer(
    name="architect",
    help="Codebase Architect — analyze, plan and implement changes on any codebase.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


if __name__ == "__main__":  # pragma: no cover
    app()
