"""Pydantic request/response models and mappers for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from codebase_architect.application.pipeline.scan_pipeline import ScanResult
from codebase_architect.application.services.scan_service import ScanJob, ScanStatus
from codebase_architect.shared.redaction import redact_url_credentials

# -- Requests ---------------------------------------------------------------


class ScanRequest(BaseModel):
    location: str = Field(..., description="Git URL, local folder, local Git repo, .zip or .tar.gz")
    title: str | None = None
    static_only: bool = False
    ai_provider: str | None = None
    # Optional per-scan AI overrides; never echoed back in any response.
    ai_api_key: str | None = Field(default=None, description="API key for the selected provider")
    ai_base_url: str | None = Field(default=None, description="Custom/local AI endpoint URL")
    ai_model: str | None = None


# -- Responses --------------------------------------------------------------


class ScanRef(BaseModel):
    id: str
    status: ScanStatus


class LanguageStatSchema(BaseModel):
    language: str
    files: int
    loc: int


class StackSchema(BaseModel):
    name: str
    category: str
    version: str | None = None
    evidence: str


class ScanSummary(BaseModel):
    source_type: str
    base_ref: str | None
    languages: list[LanguageStatSchema]
    stacks: list[StackSchema]
    modules: int
    internal_dependencies: int
    external_dependencies: int
    symbols: int
    entrypoints: int
    secrets: int
    features: int | None = None
    ai_tokens: int | None = None


class ScanStatusResponse(BaseModel):
    id: str
    status: ScanStatus
    title: str | None
    location: str
    error: str | None = None
    duration_seconds: float | None = None
    summary: ScanSummary | None = None


class DocPageRef(BaseModel):
    slug: str
    title: str


class DocumentationResponse(BaseModel):
    title: str
    generated_at: str
    base_ref: str | None
    pages: list[DocPageRef]


class ModuleSchema(BaseModel):
    id: str
    files: int
    symbols: int
    loc: int
    languages: list[str]


class CodeModelResponse(BaseModel):
    languages: list[LanguageStatSchema]
    stacks: list[StackSchema]
    modules: list[ModuleSchema]
    symbols: int
    total_loc: int


class ComponentSchema(BaseModel):
    module_id: str
    layer: str
    evidence: str


class EdgeSchema(BaseModel):
    source: str
    target: str
    weight: int


class ArchitectureResponse(BaseModel):
    components: list[ComponentSchema]
    edges: list[EdgeSchema]


# -- Mappers ----------------------------------------------------------------


def _languages(result: ScanResult) -> list[LanguageStatSchema]:
    return [
        LanguageStatSchema(language=s.language.value, files=s.files, loc=s.loc)
        for s in result.code_model.language_breakdown()
    ]


def _stacks(result: ScanResult) -> list[StackSchema]:
    return [
        StackSchema(
            name=s.name, category=s.category.value, version=s.version, evidence=s.evidence
        )
        for s in result.code_model.stacks
    ]


def to_status_response(job: ScanJob) -> ScanStatusResponse:
    summary = None
    if job.result is not None:
        result = job.result
        summary = ScanSummary(
            source_type=result.workspace.source_type.value,
            base_ref=result.workspace.base_ref,
            languages=_languages(result),
            stacks=_stacks(result),
            modules=len(result.module_graph.modules),
            internal_dependencies=len(result.module_graph.edges),
            external_dependencies=len(result.code_model.dependencies),
            symbols=result.code_model.symbol_count,
            entrypoints=len(result.entrypoints),
            secrets=len(result.findings),
            features=len(result.narrative.features) if result.narrative else None,
            ai_tokens=result.narrative.usage.total if result.narrative else None,
        )
    return ScanStatusResponse(
        id=job.id,
        status=job.status,
        title=job.options.title,
        location=redact_url_credentials(job.options.location),
        error=job.error,
        duration_seconds=job.duration_seconds,
        summary=summary,
    )


def to_documentation_response(result: ScanResult) -> DocumentationResponse:
    doc = result.documentation
    return DocumentationResponse(
        title=doc.title,
        generated_at=doc.generated_at,
        base_ref=doc.base_ref,
        pages=[DocPageRef(slug=p.slug, title=p.title) for p in doc.pages],
    )


def to_code_model_response(result: ScanResult) -> CodeModelResponse:
    return CodeModelResponse(
        languages=_languages(result),
        stacks=_stacks(result),
        modules=[
            ModuleSchema(
                id=m.id,
                files=len(m.files),
                symbols=m.symbol_count,
                loc=m.loc,
                languages=sorted(lang.value for lang in m.languages),
            )
            for m in result.module_graph.modules
        ],
        symbols=result.code_model.symbol_count,
        total_loc=result.code_model.total_loc,
    )


def to_architecture_response(result: ScanResult) -> ArchitectureResponse:
    return ArchitectureResponse(
        components=[
            ComponentSchema(module_id=c.module_id, layer=c.layer.value, evidence=c.evidence)
            for c in result.architecture.components
        ],
        edges=[
            EdgeSchema(source=e.source, target=e.target, weight=e.weight)
            for e in result.module_graph.edges
        ],
    )
