"""Narrative report: the AI pass output, woven into the documentation."""

from __future__ import annotations

from dataclasses import dataclass, field

from codebase_architect.domain.model.ai import TokenUsage
from codebase_architect.domain.model.feature import Feature


@dataclass
class NarrativeReport:
    """Natural-language documentation grounded in the static analysis."""

    overview: str = ""
    features: list[Feature] = field(default_factory=list)
    flows: dict[str, str] = field(default_factory=dict)  # entrypoint name -> narrative
    usage: TokenUsage = field(default_factory=TokenUsage)
