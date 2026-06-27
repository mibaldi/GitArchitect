"""Tests for scan persistence: codec round-trip and the file store."""

from __future__ import annotations

from pathlib import Path

from codebase_architect.domain.model.architecture import Architecture, Component, Layer
from codebase_architect.domain.model.code import Language, ParsedFile, Symbol, SymbolKind
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.documentation import (
    DocPage,
    DocSection,
    Documentation,
    MermaidDiagram,
)
from codebase_architect.domain.model.entrypoint import Entrypoint, EntrypointKind
from codebase_architect.domain.model.module import Module, ModuleEdge, ModuleGraph
from codebase_architect.domain.model.scan_record import ScanRecord
from codebase_architect.infrastructure.persistence._codec import from_jsonable, to_jsonable
from codebase_architect.infrastructure.persistence.file_scan_store import FileScanStore


def _record(scan_id: str = "scan_1", created_at: str = "2026-01-01") -> ScanRecord:
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "web/C.java",
                Language.JAVA,
                10,
                symbols=(Symbol("C", SymbolKind.CLASS, 1, 9),),
                calls=("Service",),
                package="com.demo.web",
            )
        ]
    )
    graph = ModuleGraph(
        modules=[Module(id="com.demo.web", name="web", languages={Language.JAVA}, loc=10)],
        edges=[ModuleEdge("com.demo.web", "com.demo.svc", 2)],
    )
    section = DocSection(body="hi", diagram=MermaidDiagram("d", "graph"))
    docs = Documentation(
        title="Demo",
        generated_at="t",
        base_ref="abc",
        pages=(DocPage("README", "Demo", (section,)),),
    )
    arch = Architecture(components=[Component("com.demo.web", Layer.PRESENTATION, "kw")])
    return ScanRecord(
        id=scan_id,
        status="done",
        title="Demo",
        location="src",
        created_at=created_at,
        source_type="folder",
        base_ref="abc",
        documentation=docs,
        code_model=model,
        architecture=arch,
        module_graph=graph,
        entrypoints=(Entrypoint("C", EntrypointKind.HTTP_ENDPOINT, "web/C.java", "com.demo.web"),),
    )


def test_codec_round_trips_a_record() -> None:
    record = _record()
    back = from_jsonable(ScanRecord, to_jsonable(record))
    assert back.code_model is not None and back.module_graph is not None
    assert back.code_model.symbol_count == record.code_model.symbol_count
    assert back.module_graph.modules[0].languages == {Language.JAVA}  # set preserved
    assert back.entrypoints[0].kind is EntrypointKind.HTTP_ENDPOINT  # enum preserved
    assert back.documentation.pages[0].sections[0].diagram.code == "graph"


def test_store_save_get_list_delete(tmp_path: Path) -> None:
    store = FileScanStore(tmp_path / "records")
    store.save(_record("scan_a", "2026-01-01"))
    store.save(_record("scan_b", "2026-01-02"))

    got = store.get("scan_a")
    assert got is not None and got.title == "Demo"
    assert store.get("missing") is None
    assert [r.id for r in store.list()] == ["scan_a", "scan_b"]  # oldest-first

    assert store.delete("scan_a") is True
    assert store.delete("scan_a") is False
    assert [r.id for r in store.list()] == ["scan_b"]


def test_corrupt_record_is_skipped(tmp_path: Path) -> None:
    store = FileScanStore(tmp_path / "records")
    store.save(_record("good"))
    (tmp_path / "records" / "bad.json").write_text("{ not json", encoding="utf-8")
    assert [r.id for r in store.list()] == ["good"]
