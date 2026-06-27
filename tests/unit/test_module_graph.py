"""Tests for the module graph builder."""

from __future__ import annotations

from codebase_architect.domain.model.code import ImportRef, Language, ParsedFile
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.services.module_graph import build_module_graph


def _model(*files: ParsedFile) -> CodeModel:
    return CodeModel(parsed_files=list(files))


def test_jvm_packages_become_modules_with_internal_edges() -> None:
    model = _model(
        ParsedFile(
            path="web/GreetController.java",
            language=Language.JAVA,
            loc=10,
            imports=(ImportRef("com.demo.service.GreeterService"),),
            package="com.demo.web",
        ),
        ParsedFile(
            path="service/GreeterService.java",
            language=Language.JAVA,
            loc=8,
            imports=(ImportRef("com.demo.repo.GreetRepository"),),
            package="com.demo.service",
        ),
        ParsedFile(
            path="repo/GreetRepository.java",
            language=Language.JAVA,
            loc=4,
            package="com.demo.repo",
        ),
    )
    graph = build_module_graph(model)
    assert graph.module_ids() == {"com.demo.web", "com.demo.service", "com.demo.repo"}
    edges = {(e.source, e.target) for e in graph.edges}
    assert edges == {
        ("com.demo.web", "com.demo.service"),
        ("com.demo.service", "com.demo.repo"),
    }


def test_external_imports_are_dropped() -> None:
    model = _model(
        ParsedFile(
            path="web/X.java",
            language=Language.JAVA,
            loc=3,
            imports=(ImportRef("java.util.List"), ImportRef("org.springframework.web.X")),
            package="com.demo.web",
        )
    )
    graph = build_module_graph(model)
    assert graph.edges == []


def test_typescript_relative_imports_resolve_by_directory() -> None:
    model = _model(
        ParsedFile(
            path="src/app/app.component.ts",
            language=Language.TYPESCRIPT,
            loc=5,
            imports=(ImportRef("../core/auth.service"), ImportRef("@angular/core")),
        ),
        ParsedFile(path="src/core/auth.service.ts", language=Language.TYPESCRIPT, loc=4),
    )
    graph = build_module_graph(model)
    assert graph.module_ids() == {"src/app", "src/core"}
    assert {(e.source, e.target) for e in graph.edges} == {("src/app", "src/core")}


def test_wildcard_import_resolves_to_package() -> None:
    model = _model(
        ParsedFile(
            path="a/A.java",
            language=Language.JAVA,
            loc=2,
            imports=(ImportRef("com.demo.b.*"),),
            package="com.demo.a",
        ),
        ParsedFile(path="b/B.java", language=Language.JAVA, loc=2, package="com.demo.b"),
    )
    graph = build_module_graph(model)
    assert {(e.source, e.target) for e in graph.edges} == {("com.demo.a", "com.demo.b")}
