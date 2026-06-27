"""Reconciliation: how a functional spec lines up with the scanned code.

The output is a coverage matrix — each described functionality is classified as
implemented / partially found / missing based on keyword evidence against the
scanned artifacts, plus the reverse gap (entrypoints found in code but not
described in the spec). Matching is heuristic and evidence-bearing: every match
records *what* it matched so nothing is asserted without a reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MatchStatus(StrEnum):
    IMPLEMENTED = "implemented"  # strong evidence in the code
    PARTIAL = "partial"  # weak/single-token evidence
    MISSING = "missing"  # described but nothing matched


@dataclass(frozen=True)
class ArtifactMatch:
    """A scanned artifact a feature matched, with its overlap score."""

    kind: str  # "entrypoint" | "module"
    id: str
    score: int


@dataclass(frozen=True)
class FeatureCoverage:
    """How one spec functionality maps onto the code."""

    feature: str
    status: MatchStatus
    matches: tuple[ArtifactMatch, ...] = ()


@dataclass
class ReconciliationReport:
    """Coverage of a spec against one scan."""

    spec_id: str
    scan_id: str
    coverage: tuple[FeatureCoverage, ...] = ()
    undocumented_entrypoints: tuple[str, ...] = ()

    def _count(self, status: MatchStatus) -> int:
        return sum(1 for c in self.coverage if c.status is status)

    @property
    def implemented(self) -> int:
        return self._count(MatchStatus.IMPLEMENTED)

    @property
    def partial(self) -> int:
        return self._count(MatchStatus.PARTIAL)

    @property
    def missing(self) -> int:
        return self._count(MatchStatus.MISSING)
