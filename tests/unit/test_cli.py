"""Smoke tests for the CLI entrypoint."""

from __future__ import annotations

from typer.testing import CliRunner

from codebase_architect import __version__
from codebase_architect.cli.main import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.stdout
