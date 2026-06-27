"""Tests for the regex secret scanner."""

from __future__ import annotations

from pathlib import Path

from codebase_architect.domain.model.source import SourceType
from codebase_architect.domain.model.workspace import Workspace
from codebase_architect.infrastructure.security.secret_scanner import RegexSecretScanner
from codebase_architect.shared.ids import new_id


def _workspace(root: Path) -> Workspace:
    return Workspace(id=new_id("ws"), root_path=root, source_type=SourceType.FOLDER)


def test_detects_and_redacts_secrets(tmp_path: Path) -> None:
    (tmp_path / "config.py").write_text(
        'API_KEY = "supersecretvalue1234"\n'
        "AWS = AKIAIOSFODNN7EXAMPLE\n",
        encoding="utf-8",
    )
    findings = RegexSecretScanner().scan(_workspace(tmp_path))

    rules = {f.rule for f in findings}
    assert "Hard-coded secret" in rules
    assert "AWS access key" in rules
    # The raw secret never appears verbatim in a finding.
    for finding in findings:
        assert "supersecretvalue1234" not in finding.redacted
        assert "*" in finding.redacted


def test_clean_codebase_has_no_findings(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    assert RegexSecretScanner().scan(_workspace(tmp_path)) == []
