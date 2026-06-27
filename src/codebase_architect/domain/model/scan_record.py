"""ScanRecord: the persistable snapshot of a completed scan.

This is what survives a process restart and what later phases (linking projects,
reconciling against a functional spec) load. It holds only domain facts plus the
job metadata — no live workspace handle — so it is fully serializable.
"""

from __future__ import annotations

from dataclasses import dataclass

from codebase_architect.domain.model.architecture import Architecture
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.documentation import Documentation
from codebase_architect.domain.model.entrypoint import Entrypoint
from codebase_architect.domain.model.finding import Finding
from codebase_architect.domain.model.module import ModuleGraph
from codebase_architect.domain.model.narrative import NarrativeReport


@dataclass
class ScanRecord:
    """A completed scan, persisted as facts (no workspace, no secrets in clear)."""

    id: str
    status: str
    title: str | None
    location: str  # already redacted of any credentials
    created_at: str
    finished_at: str | None = None
    duration_seconds: float | None = None
    error: str | None = None
    source_type: str | None = None
    base_ref: str | None = None
    docs_dir: str | None = None
    documentation: Documentation | None = None
    code_model: CodeModel | None = None
    architecture: Architecture | None = None
    module_graph: ModuleGraph | None = None
    entrypoints: tuple[Entrypoint, ...] = ()
    findings: tuple[Finding, ...] = ()
    narrative: NarrativeReport | None = None
