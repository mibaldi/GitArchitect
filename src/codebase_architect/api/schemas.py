"""Pydantic request/response models and mappers for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from codebase_architect.application.pipeline.scan_pipeline import ScanResult
from codebase_architect.application.services.scan_service import ScanJob, ScanStatus
from codebase_architect.domain.model.functional_spec import (
    EndpointRef,
    FlowStep,
    FunctionalSpec,
    SpecFeature,
)
from codebase_architect.domain.model.http_flow import ApiFlowGraph
from codebase_architect.domain.model.reconciliation import ReconciliationReport
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


# -- Functional spec (phase B) ----------------------------------------------


class FlowStepSchema(BaseModel):
    actor: str = ""
    action: str = ""
    target: str = ""


class EndpointRefSchema(BaseModel):
    method: str = ""
    path: str = ""


class SpecFeatureSchema(BaseModel):
    name: str
    actors: list[str] = []
    goal: str = ""
    preconditions: list[str] = []
    main_flow: list[FlowStepSchema] = []
    alternative_flows: list[str] = []
    systems: list[str] = []
    endpoints: list[EndpointRefSchema] = []
    data_entities: list[str] = []
    acceptance_criteria: list[str] = []


class FunctionalSpecPayload(BaseModel):
    product: str
    objective: str = ""
    actors: list[str] = []
    features: list[SpecFeatureSchema] = []
    linked_scan_ids: list[str] = []


class FunctionalSpecResponse(FunctionalSpecPayload):
    id: str
    created_at: str
    updated_at: str


class SpecSummaryResponse(BaseModel):
    id: str
    product: str
    features: int
    updated_at: str


def spec_payload_to_domain(payload: FunctionalSpecPayload, spec_id: str = "") -> FunctionalSpec:
    return FunctionalSpec(
        id=spec_id,
        product=payload.product,
        objective=payload.objective,
        actors=tuple(payload.actors),
        features=tuple(_feature_to_domain(f) for f in payload.features),
        linked_scan_ids=tuple(payload.linked_scan_ids),
    )


def _feature_to_domain(f: SpecFeatureSchema) -> SpecFeature:
    return SpecFeature(
        name=f.name,
        actors=tuple(f.actors),
        goal=f.goal,
        preconditions=tuple(f.preconditions),
        main_flow=tuple(FlowStep(s.actor, s.action, s.target) for s in f.main_flow),
        alternative_flows=tuple(f.alternative_flows),
        systems=tuple(f.systems),
        endpoints=tuple(EndpointRef(e.method, e.path) for e in f.endpoints),
        data_entities=tuple(f.data_entities),
        acceptance_criteria=tuple(f.acceptance_criteria),
    )


def spec_to_response(spec: FunctionalSpec) -> FunctionalSpecResponse:
    return FunctionalSpecResponse(
        id=spec.id,
        product=spec.product,
        objective=spec.objective,
        actors=list(spec.actors),
        features=[
            SpecFeatureSchema(
                name=f.name,
                actors=list(f.actors),
                goal=f.goal,
                preconditions=list(f.preconditions),
                main_flow=[
                    FlowStepSchema(actor=s.actor, action=s.action, target=s.target)
                    for s in f.main_flow
                ],
                alternative_flows=list(f.alternative_flows),
                systems=list(f.systems),
                endpoints=[
                    EndpointRefSchema(method=e.method, path=e.path) for e in f.endpoints
                ],
                data_entities=list(f.data_entities),
                acceptance_criteria=list(f.acceptance_criteria),
            )
            for f in spec.features
        ],
        linked_scan_ids=list(spec.linked_scan_ids),
        created_at=spec.created_at,
        updated_at=spec.updated_at,
    )


def spec_summary(spec: FunctionalSpec) -> SpecSummaryResponse:
    return SpecSummaryResponse(
        id=spec.id,
        product=spec.product,
        features=len(spec.features),
        updated_at=spec.updated_at,
    )


# -- Reconciliation (phase B2) ----------------------------------------------


class ArtifactMatchSchema(BaseModel):
    kind: str
    id: str
    score: int


class FeatureCoverageSchema(BaseModel):
    feature: str
    status: str
    matches: list[ArtifactMatchSchema]


class ReconciliationResponse(BaseModel):
    spec_id: str
    scan_id: str
    implemented: int
    partial: int
    missing: int
    coverage: list[FeatureCoverageSchema]
    undocumented_entrypoints: list[str]


class ApiFlowEdgeSchema(BaseModel):
    method: str
    path: str
    from_scan: str
    from_module: str
    to_scan: str
    to_module: str
    handler: str


class UnmatchedCallSchema(BaseModel):
    method: str
    path: str
    from_scan: str
    from_module: str


class ApiFlowResponse(BaseModel):
    spec_id: str
    scans: list[str]
    edges: list[ApiFlowEdgeSchema]
    unmatched: list[UnmatchedCallSchema]


def api_flow_to_response(spec_id: str, graph: ApiFlowGraph) -> ApiFlowResponse:
    return ApiFlowResponse(
        spec_id=spec_id,
        scans=list(graph.scans),
        edges=[
            ApiFlowEdgeSchema(
                method=e.method,
                path=e.path,
                from_scan=e.from_scan,
                from_module=e.from_module,
                to_scan=e.to_scan,
                to_module=e.to_module,
                handler=e.handler,
            )
            for e in graph.edges
        ],
        unmatched=[
            UnmatchedCallSchema(
                method=u.method, path=u.path, from_scan=u.from_scan, from_module=u.from_module
            )
            for u in graph.unmatched
        ],
    )


class FeatureSequenceSchema(BaseModel):
    feature: str
    mermaid: str


class SequenceResponse(BaseModel):
    spec_id: str
    diagrams: list[FeatureSequenceSchema]


def sequences_to_response(spec_id: str, diagrams: list[tuple[str, str]]) -> SequenceResponse:
    return SequenceResponse(
        spec_id=spec_id,
        diagrams=[FeatureSequenceSchema(feature=name, mermaid=code) for name, code in diagrams],
    )


def reconciliation_to_response(report: ReconciliationReport) -> ReconciliationResponse:
    return ReconciliationResponse(
        spec_id=report.spec_id,
        scan_id=report.scan_id,
        implemented=report.implemented,
        partial=report.partial,
        missing=report.missing,
        coverage=[
            FeatureCoverageSchema(
                feature=c.feature,
                status=c.status.value,
                matches=[
                    ArtifactMatchSchema(kind=m.kind, id=m.id, score=m.score) for m in c.matches
                ],
            )
            for c in report.coverage
        ],
        undocumented_entrypoints=list(report.undocumented_entrypoints),
    )
