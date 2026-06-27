"""Regex-based secret scanner.

Best-effort detection of common credential shapes (cloud keys, tokens, private
keys, hard-coded secret assignments). Matches are redacted before they leave
this module, so findings can be surfaced safely. Binary and oversized files are
skipped.
"""

from __future__ import annotations

import re

from codebase_architect.domain.model.finding import Finding
from codebase_architect.domain.model.workspace import Workspace
from codebase_architect.domain.ports.secret_scanner import SecretScanner

_MAX_BYTES = 1_000_000
_MAX_FINDINGS = 200

# (rule, compiled pattern, group index holding the secret value)
_RULES: list[tuple[str, re.Pattern[str], int]] = [
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 0),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), 0),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"), 0),
    ("GitHub token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}\b"), 0),
    ("Private key", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"), 0),
    (
        "Hard-coded secret",
        re.compile(
            r"""(?i)\b(?:api[_-]?key|secret|token|password|passwd|access[_-]?key)\b"""
            r"""\s*[:=]\s*['"]([^'"]{12,})['"]""",
        ),
        1,
    ),
]


class RegexSecretScanner(SecretScanner):
    """Detects likely secrets line-by-line across analyzable text files."""

    def scan(self, workspace: Workspace) -> list[Finding]:
        findings: list[Finding] = []
        for path in workspace.iter_files():
            try:
                if path.stat().st_size > _MAX_BYTES:
                    continue
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            rel = workspace.relative(path)
            for lineno, line in enumerate(text.splitlines(), start=1):
                for rule, pattern, group in _RULES:
                    match = pattern.search(line)
                    if match is None:
                        continue
                    secret = match.group(group)
                    findings.append(
                        Finding(rule=rule, path=rel, line=lineno, redacted=_redact(secret))
                    )
                    if len(findings) >= _MAX_FINDINGS:
                        return findings
        return findings


def _redact(secret: str) -> str:
    secret = secret.strip()
    if len(secret) <= 6:
        return "*" * len(secret)
    return f"{secret[:3]}{'*' * 6}{secret[-2:]}"
