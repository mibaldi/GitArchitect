"""Tests for the name-resolved call graph."""

from __future__ import annotations

from codebase_architect.domain.model.code import Language, ParsedFile, Symbol, SymbolKind
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.services.call_graph import build_call_edges


def _sym(name: str, kind: SymbolKind = SymbolKind.CLASS) -> Symbol:
    return Symbol(name=name, kind=kind, start_line=1, end_line=2)


def test_call_resolves_to_declaring_module() -> None:
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "web/Controller.java",
                Language.JAVA,
                5,
                symbols=(_sym("Controller"),),
                calls=("GreeterService",),
                package="com.demo.web",
            ),
            ParsedFile(
                "svc/GreeterService.java",
                Language.JAVA,
                5,
                symbols=(_sym("GreeterService"),),
                package="com.demo.svc",
            ),
        ]
    )
    edges = build_call_edges(model)
    assert {(e.source, e.target) for e in edges} == {("com.demo.web", "com.demo.svc")}


def test_unresolved_and_self_calls_are_dropped() -> None:
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "a/A.py",
                Language.PYTHON,
                5,
                symbols=(_sym("A", SymbolKind.CLASS),),
                calls=("A", "println", "Unknown"),  # self, external, undeclared
            ),
        ]
    )
    assert build_call_edges(model) == []


def test_ambiguous_names_are_skipped() -> None:
    # "Helper" declared in three+ modules -> too ambiguous to resolve.
    decls = [
        ParsedFile(f"m{i}/H.py", Language.PYTHON, 2, symbols=(_sym("Helper"),), package=f"p{i}")
        for i in range(4)
    ]
    caller = ParsedFile(
        "caller/C.py", Language.PYTHON, 3, symbols=(_sym("C"),), calls=("Helper",), package="caller"
    )
    edges = build_call_edges(CodeModel(parsed_files=[*decls, caller]))
    assert edges == []
