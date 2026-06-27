"""ScanService: submit scans, run them in the background, track their state.

This is the application-level orchestration the API drives. Scans run
asynchronously: ``submit`` registers a job and returns immediately; ``execute``
(invoked from a background task or worker) runs the pipeline and updates the
job. State is held in memory here; swapping in a Redis/Arq queue and a database
repository later does not change this interface.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from codebase_architect.application.pipeline.scan_pipeline import ScanPipeline, ScanResult
from codebase_architect.application.registries.ai_registry import build_ai_provider
from codebase_architect.domain.ports.ai_provider import AIProvider
from codebase_architect.shared.errors import CodebaseArchitectError, NotFoundError
from codebase_architect.shared.ids import new_id
from codebase_architect.shared.logging import get_logger
from codebase_architect.shared.redaction import redact_url_credentials

logger = get_logger(__name__)

PipelineBuilder = Callable[[AIProvider], ScanPipeline]


class ScanStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class ScanOptions:
    location: str
    title: str | None = None
    static_only: bool = False
    ai_provider: str | None = None
    # Per-scan AI credentials/endpoint (kept in memory only, never persisted or logged).
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None


@dataclass
class ScanJob:
    id: str
    options: ScanOptions
    status: ScanStatus = ScanStatus.QUEUED
    result: ScanResult | None = None
    error: str | None = None
    docs_dir: Path | None = None
    created_at: str = ""
    finished_at: str | None = None
    duration_seconds: float | None = None


class ScanService:
    """Runs and tracks scans, writing each documentation bundle under a job dir."""

    def __init__(
        self,
        pipeline_builder: PipelineBuilder,
        artifacts_dir: Path,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._build_pipeline = pipeline_builder
        self._artifacts_dir = artifacts_dir
        self._clock = clock or (lambda: datetime.now(UTC).isoformat(timespec="seconds"))
        self._jobs: dict[str, ScanJob] = {}
        self._lock = threading.Lock()

    def submit(self, options: ScanOptions) -> ScanJob:
        job = ScanJob(id=new_id("scan"), options=options, created_at=self._clock())
        with self._lock:
            self._jobs[job.id] = job
        logger.info(
            "scan_submitted", scan_id=job.id, location=redact_url_credentials(options.location)
        )
        return job

    def get(self, scan_id: str) -> ScanJob:
        with self._lock:
            job = self._jobs.get(scan_id)
        if job is None:
            raise NotFoundError(f"Scan not found: {scan_id}")
        return job

    def list(self) -> list[ScanJob]:
        with self._lock:
            return list(self._jobs.values())

    def execute(self, scan_id: str) -> None:
        """Run the pipeline for a queued job (called from a background task)."""
        job = self.get(scan_id)
        job.status = ScanStatus.RUNNING
        options = job.options
        docs_dir = self._artifacts_dir / scan_id / "docs"
        started = time.monotonic()
        try:
            provider = build_ai_provider(
                options.ai_provider,
                api_key=options.ai_api_key,
                base_url=options.ai_base_url,
                model=options.ai_model,
            )
            pipeline = self._build_pipeline(provider)
            result = pipeline.run(
                options.location,
                project_title=options.title or _default_title(options.location),
                generated_at=self._clock(),
                out_dir=docs_dir,
                static_only=options.static_only,
            )
            job.result = result
            job.docs_dir = docs_dir
            job.status = ScanStatus.DONE
            logger.info("scan_done", scan_id=scan_id)
        except CodebaseArchitectError as exc:
            job.error = str(exc)
            job.status = ScanStatus.FAILED
            logger.warning("scan_failed", scan_id=scan_id, error=str(exc))
        except Exception as exc:  # noqa: BLE001 - report any failure on the job, never crash
            job.error = f"Unexpected error: {exc}"
            job.status = ScanStatus.FAILED
            logger.error("scan_crashed", scan_id=scan_id, error=str(exc))
        finally:
            job.finished_at = self._clock()
            job.duration_seconds = round(time.monotonic() - started, 3)
            logger.info(
                "scan_metrics",
                scan_id=scan_id,
                status=job.status.value,
                duration_seconds=job.duration_seconds,
            )


def _default_title(location: str) -> str:
    name = Path(location.rstrip("/")).name
    for suffix in (".git", ".zip", ".tar.gz", ".tgz", ".tar"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name or "Codebase"
