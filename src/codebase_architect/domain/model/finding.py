"""Security findings from secret scanning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """A likely secret found in the codebase.

    ``redacted`` is the masked match — the raw secret is never stored or
    surfaced, so a Finding is safe to put in generated documentation.
    """

    rule: str
    path: str
    line: int
    redacted: str
