"""REST API routes for scans and their documentation."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from codebase_architect.api.dashboard import INDEX_HTML
from codebase_architect.api.schemas import (
    ArchitectureResponse,
    CodeModelResponse,
    DocumentationResponse,
    ScanRef,
    ScanRequest,
    ScanStatusResponse,
    to_architecture_response,
    to_code_model_response,
    to_documentation_response,
    to_status_response,
)
from codebase_architect.application.services.scan_service import (
    ScanJob,
    ScanOptions,
    ScanService,
    ScanStatus,
)
from codebase_architect.infrastructure.export.zip_archive import zip_directory
from codebase_architect.shared.errors import NotFoundError

router = APIRouter()


def get_service(request: Request) -> ScanService:
    service: ScanService = request.app.state.scan_service
    return service


def _job_or_404(service: ScanService, scan_id: str) -> ScanJob:
    try:
        return service.get(scan_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _require_done(job: ScanJob) -> ScanJob:
    if job.status is ScanStatus.FAILED:
        raise HTTPException(status_code=409, detail=f"Scan failed: {job.error}")
    if job.status is not ScanStatus.DONE or job.result is None:
        raise HTTPException(status_code=409, detail=f"Scan not finished (status: {job.status})")
    return job


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    """Serve the web dashboard."""
    return INDEX_HTML


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/scans", status_code=202, response_model=ScanRef)
def create_scan(
    body: ScanRequest,
    background: BackgroundTasks,
    service: ScanService = Depends(get_service),
) -> ScanRef:
    job = service.submit(
        ScanOptions(
            location=body.location,
            title=body.title,
            static_only=body.static_only,
            ai_provider=body.ai_provider,
        )
    )
    background.add_task(service.execute, job.id)
    return ScanRef(id=job.id, status=job.status)


@router.get("/scans", response_model=list[ScanRef])
def list_scans(service: ScanService = Depends(get_service)) -> list[ScanRef]:
    return [ScanRef(id=j.id, status=j.status) for j in service.list()]


@router.get("/scans/{scan_id}", response_model=ScanStatusResponse)
def get_scan(scan_id: str, service: ScanService = Depends(get_service)) -> ScanStatusResponse:
    return to_status_response(_job_or_404(service, scan_id))


@router.get("/scans/{scan_id}/documentation", response_model=DocumentationResponse)
def get_documentation(
    scan_id: str, service: ScanService = Depends(get_service)
) -> DocumentationResponse:
    job = _require_done(_job_or_404(service, scan_id))
    assert job.result is not None
    return to_documentation_response(job.result)


@router.get("/scans/{scan_id}/code-model", response_model=CodeModelResponse)
def get_code_model(
    scan_id: str, service: ScanService = Depends(get_service)
) -> CodeModelResponse:
    job = _require_done(_job_or_404(service, scan_id))
    assert job.result is not None
    return to_code_model_response(job.result)


@router.get("/scans/{scan_id}/architecture", response_model=ArchitectureResponse)
def get_architecture(
    scan_id: str, service: ScanService = Depends(get_service)
) -> ArchitectureResponse:
    job = _require_done(_job_or_404(service, scan_id))
    assert job.result is not None
    return to_architecture_response(job.result)


@router.get("/scans/{scan_id}/pages/{slug}")
def get_page(
    scan_id: str, slug: str, service: ScanService = Depends(get_service)
) -> dict[str, str]:
    """Return one documentation page's Markdown (for the dashboard's live view)."""
    job = _require_done(_job_or_404(service, scan_id))
    assert job.result is not None
    titles = {p.slug: p.title for p in job.result.documentation.pages}
    if slug not in titles or job.docs_dir is None:
        raise HTTPException(status_code=404, detail=f"No such page: {slug}")
    path = Path(job.docs_dir) / f"{slug}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Page file not found")
    return {"slug": slug, "title": titles[slug], "markdown": path.read_text(encoding="utf-8")}


@router.get("/scans/{scan_id}/download")
def download_documentation(
    scan_id: str, service: ScanService = Depends(get_service)
) -> FileResponse:
    job = _require_done(_job_or_404(service, scan_id))
    if job.docs_dir is None or not Path(job.docs_dir).is_dir():
        raise HTTPException(status_code=404, detail="No documentation bundle for this scan")
    archive = zip_directory(Path(job.docs_dir), Path(job.docs_dir).parent / "documentation.zip")
    return FileResponse(
        path=str(archive),
        media_type="application/zip",
        filename=f"{scan_id}-documentation.zip",
    )
