"""Reconcile a functional spec against the facts extracted from a scan.

Each functionality's keywords (its name, declared systems, endpoint paths and
flow targets) are matched against the keyword fingerprint of every scanned
artifact (entrypoints and modules, the latter enriched with their declared
symbol names). Token overlap is the score; the best score decides the status.
Deliberately simple and explainable — the AI pass (later) can refine it, but the
evidence is always real code identifiers, never invented.
"""

from __future__ import annotations

import re
from collections import defaultdict

from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.entrypoint import Entrypoint
from codebase_architect.domain.model.functional_spec import FunctionalSpec, SpecFeature
from codebase_architect.domain.model.module import ModuleGraph
from codebase_architect.domain.model.reconciliation import (
    ArtifactMatch,
    FeatureCoverage,
    MatchStatus,
    ReconciliationReport,
)
from codebase_architect.domain.services.module_graph import module_id_of

_WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z]+|[a-z]+|[A-Z]+|[0-9]+")
# Structural/boilerplate tokens that would match almost anything.
_STOPWORDS = frozenset(
    {
        "api",
        "app",
        "src",
        "com",
        "org",
        "net",
        "java",
        "kotlin",
        "main",
        "index",
        "service",
        "services",
        "controller",
        "controllers",
        "module",
        "modules",
        "the",
        "and",
        "for",
        "get",
        "post",
        "put",
        "delete",
        "patch",
    }
)
_MAX_MATCHES = 6


def reconcile_spec(
    spec: FunctionalSpec,
    *,
    scan_id: str,
    entrypoints: list[Entrypoint],
    graph: ModuleGraph,
    model: CodeModel,
) -> ReconciliationReport:
    artifacts = _artifacts(entrypoints, graph, model)
    coverage: list[FeatureCoverage] = []
    matched_entrypoints: set[str] = set()

    for feature in spec.features:
        tokens = _feature_tokens(feature)
        scored = [
            ArtifactMatch(kind, ident, len(tokens & art_tokens))
            for (kind, ident, art_tokens) in artifacts
            if tokens & art_tokens
        ]
        scored.sort(key=lambda m: (-m.score, m.kind, m.id))
        top = tuple(scored[:_MAX_MATCHES])
        coverage.append(FeatureCoverage(feature.name, _status(scored), top))
        for match in scored:
            if match.kind == "entrypoint":
                matched_entrypoints.add(match.id)

    undocumented = tuple(
        sorted({_entrypoint_id(ep) for ep in entrypoints} - matched_entrypoints)
    )
    return ReconciliationReport(
        spec_id=spec.id,
        scan_id=scan_id,
        coverage=tuple(coverage),
        undocumented_entrypoints=undocumented,
    )


def _status(matches: list[ArtifactMatch]) -> MatchStatus:
    best = max((m.score for m in matches), default=0)
    if best >= 2:
        return MatchStatus.IMPLEMENTED
    if best == 1:
        return MatchStatus.PARTIAL
    return MatchStatus.MISSING


def _artifacts(
    entrypoints: list[Entrypoint], graph: ModuleGraph, model: CodeModel
) -> list[tuple[str, str, set[str]]]:
    symbol_tokens: dict[str, set[str]] = defaultdict(set)
    for parsed in model.parsed_files:
        module_id = module_id_of(parsed)
        for symbol in parsed.symbols:
            symbol_tokens[module_id] |= _tokens(symbol.name)

    artifacts: list[tuple[str, str, set[str]]] = []
    for ep in entrypoints:
        artifacts.append(
            ("entrypoint", _entrypoint_id(ep), _tokens(ep.name) | _tokens(ep.module))
        )
    for module in graph.modules:
        artifacts.append(
            ("module", module.id, _tokens(module.id) | symbol_tokens.get(module.id, set()))
        )
    return artifacts


def _entrypoint_id(ep: Entrypoint) -> str:
    return f"{ep.name} ({ep.module})"


def _feature_tokens(feature: SpecFeature) -> set[str]:
    parts = [feature.name, *feature.systems, *feature.data_entities]
    parts.extend(e.path for e in feature.endpoints)
    for step in feature.main_flow:
        parts.extend((step.action, step.target))
    tokens: set[str] = set()
    for part in parts:
        tokens |= _tokens(part)
    return tokens


def _tokens(text: str) -> set[str]:
    return {
        token
        for raw in _WORD.findall(text)
        if (token := raw.lower()) not in _STOPWORDS and len(token) >= 3
    }
