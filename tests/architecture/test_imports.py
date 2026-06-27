"""Architecture tests: the hexagonal contracts must hold.

Runs import-linter against the project's contracts. This is the executable
guarantee that the domain stays pure and the core stays decoupled from AI
providers, output formats and Git hosting.
"""

from __future__ import annotations

import subprocess
import sys


def test_import_linter_contracts_hold() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "importlinter.cli", "lint"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "import-linter contracts broken:\n" + result.stdout + result.stderr
    )
