"""REST API routes for scans and their documentation."""

from __future__ import annotations

import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse, Response

from codebase_architect.api.dashboard import INDEX_HTML
from codebase_architect.api.schemas import (
    ApiFlowResponse,
    ArchitectureResponse,
    CodeModelResponse,
    DocumentationResponse,
    DocumentRequest,
    FunctionalSpecPayload,
    FunctionalSpecResponse,
    ReconciliationResponse,
    RunnerCheckRequest,
    RunnerCheckResponse,
    ScanMetaRequest,
    ScanRef,
    ScanRequest,
    ScanStatusResponse,
    SequenceResponse,
    SpecSummaryResponse,
    api_flow_to_response,
    reconciliation_to_response,
    sequences_to_response,
    spec_payload_to_domain,
    spec_summary,
    spec_to_response,
    to_architecture_response,
    to_code_model_response,
    to_documentation_response,
    to_status_response,
)
from codebase_architect.application.registries.ai_registry import build_ai_provider
from codebase_architect.application.services.scan_service import (
    ScanJob,
    ScanOptions,
    ScanService,
    ScanStatus,
)
from codebase_architect.application.services.spec_service import SpecService
from codebase_architect.application.use_cases.enrich_flows import enrich_spec_flows
from codebase_architect.domain.model.code import ParsedFile
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.entrypoint import Entrypoint
from codebase_architect.domain.model.functional_spec import FunctionalSpec
from codebase_architect.domain.model.module import Module, ModuleEdge, ModuleGraph
from codebase_architect.domain.services.api_match import ScanSurface, match_api_flows
from codebase_architect.domain.services.http_flows import collect_http
from codebase_architect.domain.services.reconcile import reconcile_spec
from codebase_architect.domain.services.sequence_diagram import spec_sequences
from codebase_architect.domain.services.spec_document import build_spec_document
from codebase_architect.infrastructure.export.zip_archive import zip_directory
from codebase_architect.shared.errors import NotFoundError
from codebase_architect.shared.logging import get_logger
from codebase_architect.shared.redaction import redact_url_credentials

logger = get_logger(__name__)
router = APIRouter()


def get_service(request: Request) -> ScanService:
    service: ScanService = request.app.state.scan_service
    return service


def get_spec_service(request: Request) -> SpecService:
    service: SpecService = request.app.state.spec_service
    return service


def _job_or_404(service: ScanService, scan_id: str) -> ScanJob:
    try:
        return service.get(scan_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _scan_ref(job: ScanJob) -> ScanRef:
    return ScanRef(
        id=job.id, status=job.status, title=job.options.title, tags=list(job.options.tags)
    )


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
            tags=tuple(body.tags),
            static_only=body.static_only,
            ai_provider=body.ai_provider,
            ai_api_key=body.ai_api_key,
            ai_base_url=body.ai_base_url,
            ai_model=body.ai_model,
        )
    )
    background.add_task(service.execute, job.id)
    return _scan_ref(job)


# Archive uploads are streamed to a temp file, scanned, then deleted — nothing
# is persisted. Cap the size and accept only the archive types we support.
_UPLOAD_SUFFIXES = (".zip", ".tar.gz", ".tgz", ".tar")
_MAX_UPLOAD_BYTES = 200 * 1024 * 1024
_UPLOAD_CHUNK = 1024 * 1024


@router.post("/scans/upload", status_code=202, response_model=ScanRef)
async def create_scan_upload(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="A .zip or .tar.gz archive of the codebase"),
    title: str | None = Form(default=None),
    tags: str | None = Form(default=None),  # comma-separated
    static_only: bool = Form(default=False),
    ai_provider: str | None = Form(default=None),
    ai_api_key: str | None = Form(default=None),
    ai_base_url: str | None = Form(default=None),
    ai_model: str | None = Form(default=None),
    service: ScanService = Depends(get_service),
) -> ScanRef:
    """Upload an archive, scan it, and discard the upload afterwards."""
    filename = file.filename or "upload"
    suffix = _archive_suffix(filename)
    if suffix is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported upload type; expected one of {', '.join(_UPLOAD_SUFFIXES)}.",
        )

    temp_path = await _save_upload(file, suffix)
    job = service.submit(
        ScanOptions(
            location=str(temp_path),
            title=title or _strip_suffix(filename, suffix),
            tags=_split_tags(tags),
            static_only=static_only,
            ai_provider=ai_provider,
            ai_api_key=ai_api_key,
            ai_base_url=ai_base_url,
            ai_model=ai_model,
        )
    )
    background.add_task(_run_and_cleanup, service, job.id, temp_path)
    return _scan_ref(job)


def _split_tags(raw: str | None) -> tuple[str, ...]:
    return tuple(t.strip() for t in (raw or "").split(",") if t.strip())


def _archive_suffix(filename: str) -> str | None:
    lowered = filename.lower()
    for suffix in _UPLOAD_SUFFIXES:
        if lowered.endswith(suffix):
            return suffix
    return None


def _strip_suffix(filename: str, suffix: str) -> str:
    return Path(filename[: -len(suffix)]).name or "Uploaded archive"


async def _save_upload(file: UploadFile, suffix: str) -> Path:
    fd, temp_name = tempfile.mkstemp(suffix=suffix, prefix="ca-upload-")
    temp_path = Path(temp_name)
    written = 0
    try:
        with open(fd, "wb") as out:
            while chunk := await file.read(_UPLOAD_CHUNK):
                written += len(chunk)
                if written > _MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Upload exceeds the size limit.")
                out.write(chunk)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def _run_and_cleanup(service: ScanService, scan_id: str, temp_path: Path) -> None:
    try:
        service.execute(scan_id)
    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/scans", response_model=list[ScanRef])
def list_scans(service: ScanService = Depends(get_service)) -> list[ScanRef]:
    return [_scan_ref(j) for j in service.list()]


@router.put("/scans/{scan_id}/meta", response_model=ScanRef)
def set_scan_meta(
    scan_id: str, body: ScanMetaRequest, service: ScanService = Depends(get_service)
) -> ScanRef:
    """Rename / re-tag a scan, so it can be grouped meaningfully after scanning."""
    try:
        job = service.set_meta(scan_id, title=body.title, tags=tuple(body.tags))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _scan_ref(job)


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


# -- Functional specs (phase B) ---------------------------------------------


def _spec_or_404(service: SpecService, spec_id: str) -> FunctionalSpecResponse:
    try:
        return spec_to_response(service.get(spec_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/specs", status_code=201, response_model=FunctionalSpecResponse)
def create_spec(
    payload: FunctionalSpecPayload,
    service: SpecService = Depends(get_spec_service),
) -> FunctionalSpecResponse:
    spec = service.create(spec_payload_to_domain(payload))
    return spec_to_response(spec)


@router.get("/specs", response_model=list[SpecSummaryResponse])
def list_specs(service: SpecService = Depends(get_spec_service)) -> list[SpecSummaryResponse]:
    return [spec_summary(s) for s in service.list()]


@router.get("/specs/{spec_id}", response_model=FunctionalSpecResponse)
def get_spec(
    spec_id: str, service: SpecService = Depends(get_spec_service)
) -> FunctionalSpecResponse:
    return _spec_or_404(service, spec_id)


@router.put("/specs/{spec_id}", response_model=FunctionalSpecResponse)
def update_spec(
    spec_id: str,
    payload: FunctionalSpecPayload,
    service: SpecService = Depends(get_spec_service),
) -> FunctionalSpecResponse:
    try:
        spec = service.update(spec_id, spec_payload_to_domain(payload, spec_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return spec_to_response(spec)


@router.delete("/specs/{spec_id}", status_code=204)
def delete_spec(spec_id: str, service: SpecService = Depends(get_spec_service)) -> None:
    try:
        service.delete(spec_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/specs/{spec_id}/reconcile/{scan_id}", response_model=ReconciliationResponse)
def reconcile(
    spec_id: str,
    scan_id: str,
    specs: SpecService = Depends(get_spec_service),
    scans: ScanService = Depends(get_service),
) -> ReconciliationResponse:
    """Match a functional spec against a completed scan (coverage matrix)."""
    try:
        spec = specs.get(spec_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    job = _require_done(_job_or_404(scans, scan_id))
    assert job.result is not None
    report = reconcile_spec(
        spec,
        scan_id=scan_id,
        entrypoints=job.result.entrypoints,
        graph=job.result.module_graph,
        model=job.result.code_model,
    )
    specs.link_scan(spec_id, scan_id)  # remember the spec was reconciled here
    return reconciliation_to_response(report)


@router.post("/specs/{spec_id}/scans/{scan_id}", response_model=FunctionalSpecResponse)
def link_scan(
    spec_id: str, scan_id: str, specs: SpecService = Depends(get_spec_service)
) -> FunctionalSpecResponse:
    """Add a scan to a spec's project group (for cross-project flows)."""
    try:
        return spec_to_response(specs.link_scan(spec_id, scan_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/specs/{spec_id}/scans/{scan_id}", response_model=FunctionalSpecResponse)
def unlink_scan(
    spec_id: str, scan_id: str, specs: SpecService = Depends(get_spec_service)
) -> FunctionalSpecResponse:
    try:
        return spec_to_response(specs.unlink_scan(spec_id, scan_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/specs/{spec_id}/api-flow", response_model=ApiFlowResponse)
def api_flow(
    spec_id: str,
    specs: SpecService = Depends(get_spec_service),
    scans: ScanService = Depends(get_service),
) -> ApiFlowResponse:
    """Cross-project HTTP call graph over the scans linked to a spec."""
    try:
        spec = specs.get(spec_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    surfaces: list[ScanSurface] = []
    for sid in spec.linked_scan_ids:
        try:
            job = scans.get(sid)
        except NotFoundError:
            continue
        if job.status is ScanStatus.DONE and job.result is not None:
            routes, calls = collect_http(job.result.code_model)
            surfaces.append(ScanSurface(sid, tuple(routes), tuple(calls)))
    return api_flow_to_response(spec_id, match_api_flows(surfaces))


@router.get("/specs/{spec_id}/sequence", response_model=SequenceResponse)
def sequence_diagrams(
    spec_id: str,
    specs: SpecService = Depends(get_spec_service),
    scans: ScanService = Depends(get_service),
) -> SequenceResponse:
    """Per-functionality Mermaid sequence diagrams, grounded by the API flow."""
    try:
        spec = specs.get(spec_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    surfaces: list[ScanSurface] = []
    for sid in spec.linked_scan_ids:
        try:
            job = scans.get(sid)
        except NotFoundError:
            continue
        if job.status is ScanStatus.DONE and job.result is not None:
            routes, calls = collect_http(job.result.code_model)
            surfaces.append(ScanSurface(sid, tuple(routes), tuple(calls)))
    # An endpoint is "found in code" when a linked scan exposes it as a route.
    confirmed = [r.path for s in surfaces for r in s.routes]
    return sequences_to_response(spec_id, spec_sequences(spec, confirmed_paths=confirmed))


def _spec_group_facts(
    spec_id: str, specs: SpecService, scans: ScanService
) -> tuple[FunctionalSpec, list[ScanSurface], list[Entrypoint], ModuleGraph, CodeModel]:
    """Merge the facts of a spec's linked, completed scans for group analysis."""
    try:
        spec = specs.get(spec_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    parsed: list[ParsedFile] = []
    modules: list[Module] = []
    edges: list[ModuleEdge] = []
    entrypoints: list[Entrypoint] = []
    surfaces: list[ScanSurface] = []
    for sid in spec.linked_scan_ids:
        try:
            job = scans.get(sid)
        except NotFoundError:
            continue
        if job.status is not ScanStatus.DONE or job.result is None:
            continue
        result = job.result
        parsed.extend(result.code_model.parsed_files)
        modules.extend(result.module_graph.modules)
        edges.extend(result.module_graph.edges)
        entrypoints.extend(result.entrypoints)
        routes, calls = collect_http(result.code_model)
        surfaces.append(ScanSurface(sid, tuple(routes), tuple(calls)))
    model = CodeModel(parsed_files=parsed)
    graph = ModuleGraph(modules=modules, edges=edges)
    return spec, surfaces, entrypoints, graph, model


@router.post("/specs/{spec_id}/document")
def spec_document(
    spec_id: str,
    options: DocumentRequest | None = None,
    specs: SpecService = Depends(get_spec_service),
    scans: ScanService = Depends(get_service),
) -> Response:
    """A single Markdown document: coverage + sequence diagrams + API flow.

    Pass ``enrich: true`` with AI settings to weave in a grounded narrative per
    functionality; without them the document is fully deterministic.
    """
    options = options or DocumentRequest()
    spec, surfaces, entrypoints, graph, model = _spec_group_facts(spec_id, specs, scans)
    report = reconcile_spec(
        spec, scan_id="group", entrypoints=entrypoints, graph=graph, model=model
    )
    api_flow = match_api_flows(surfaces)
    confirmed = [r.path for s in surfaces for r in s.routes]
    sequences = spec_sequences(spec, confirmed_paths=confirmed)

    narratives: dict[str, str] = {}
    if options.enrich:
        provider = build_ai_provider(
            options.ai_provider,
            api_key=options.ai_api_key,
            base_url=options.ai_base_url,
            model=options.ai_model,
        )
        if provider.available():
            narratives = enrich_spec_flows(provider, spec, confirmed_paths=confirmed)

    markdown = build_spec_document(
        spec, report=report, api_flow=api_flow, sequences=sequences, narratives=narratives
    )
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in spec.product) or "spec"
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe}.md"'},
    )


@router.post("/ai/runner-check", response_model=RunnerCheckResponse)
def runner_check(body: RunnerCheckRequest) -> RunnerCheckResponse:
    """Ping a CLI runner's /health from the server (the browser can't reach the
    tailnet directly), so the dashboard can verify the URL before scanning."""
    reachable, detail = _ping_runner(body.base_url)
    return RunnerCheckResponse(reachable=reachable, detail=detail)


def _ping_runner(base_url: str) -> tuple[bool, str]:
    url = base_url.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - internal runner
            ok = 200 <= int(response.status) < 300
        return ok, "ok" if ok else "unexpected status"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        logger.warning("runner_check_failed", url=redact_url_credentials(url), error=str(exc))
        return False, "not reachable"
