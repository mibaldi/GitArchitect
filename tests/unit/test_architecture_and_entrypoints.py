"""Tests for architecture inference and entrypoint detection."""

from __future__ import annotations

from codebase_architect.domain.model.architecture import Layer
from codebase_architect.domain.model.code import ImportRef, Language, ParsedFile, Symbol, SymbolKind
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.entrypoint import EntrypointKind
from codebase_architect.domain.services.architecture_inference import infer_architecture
from codebase_architect.domain.services.entrypoints import detect_entrypoints
from codebase_architect.domain.services.module_graph import build_module_graph


def test_layers_inferred_from_keywords() -> None:
    model = CodeModel(
        parsed_files=[
            ParsedFile("web/C.java", Language.JAVA, 3, package="com.demo.web"),
            ParsedFile("svc/S.java", Language.JAVA, 3, package="com.demo.service"),
            ParsedFile("repo/R.java", Language.JAVA, 3, package="com.demo.repo"),
            ParsedFile("misc/M.java", Language.JAVA, 3, package="com.demo.misc"),
        ]
    )
    architecture = infer_architecture(build_module_graph(model))
    layers = {c.module_id: c.layer for c in architecture.components}
    assert layers["com.demo.web"] is Layer.PRESENTATION
    assert layers["com.demo.service"] is Layer.APPLICATION
    assert layers["com.demo.repo"] is Layer.DATA
    assert layers["com.demo.misc"] is Layer.OTHER


def test_hexagonal_layers_inferred_for_python_dirs() -> None:
    model = CodeModel(
        parsed_files=[
            ParsedFile("src/demo/api/routes.py", Language.PYTHON, 3),
            ParsedFile("src/demo/application/services/scan.py", Language.PYTHON, 3),
            ParsedFile("src/demo/domain/ports/source.py", Language.PYTHON, 3),
            ParsedFile("src/demo/infrastructure/parsing/parser.py", Language.PYTHON, 3),
            ParsedFile("src/demo/cli/main.py", Language.PYTHON, 3),
        ]
    )
    architecture = infer_architecture(build_module_graph(model))
    layers = {c.module_id: c.layer for c in architecture.components}
    assert layers["src/demo/api"] is Layer.PRESENTATION
    assert layers["src/demo/cli"] is Layer.PRESENTATION
    assert layers["src/demo/application/services"] is Layer.APPLICATION
    assert layers["src/demo/domain/ports"] is Layer.DOMAIN
    assert layers["src/demo/infrastructure/parsing"] is Layer.INFRASTRUCTURE


def test_python_main_is_cli_entrypoint() -> None:
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "src/demo/cli/main.py",
                Language.PYTHON,
                5,
                symbols=(Symbol("main", SymbolKind.FUNCTION, 1, 4),),
            )
        ]
    )
    eps = detect_entrypoints(model)
    assert any(e.kind is EntrypointKind.CLI_MAIN for e in eps)


def test_spring_controller_is_http_entrypoint() -> None:
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "web/GreetController.java",
                Language.JAVA,
                10,
                symbols=(Symbol("GreetController", SymbolKind.CLASS, 1, 9),),
                imports=(ImportRef("org.springframework.web.bind.annotation.RestController"),),
                package="com.demo.web",
            )
        ]
    )
    eps = detect_entrypoints(model)
    assert len(eps) == 1
    assert eps[0].kind is EntrypointKind.HTTP_ENDPOINT
    assert eps[0].name == "GreetController"


def test_angular_component_yes_service_no() -> None:
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "src/app/app.component.ts",
                Language.TYPESCRIPT,
                6,
                symbols=(Symbol("AppComponent", SymbolKind.CLASS, 1, 5),),
                imports=(ImportRef("@angular/core"),),
            ),
            ParsedFile(
                "src/app/greet.service.ts",
                Language.TYPESCRIPT,
                4,
                symbols=(Symbol("GreetService", SymbolKind.CLASS, 1, 3),),
                imports=(ImportRef("@angular/core"),),
            ),
        ]
    )
    eps = detect_entrypoints(model)
    kinds = {e.name: e.kind for e in eps}
    assert kinds == {"AppComponent": EntrypointKind.UI_COMPONENT}


def test_main_method_is_cli_entrypoint() -> None:
    model = CodeModel(
        parsed_files=[
            ParsedFile(
                "App.java",
                Language.JAVA,
                5,
                symbols=(
                    Symbol("App", SymbolKind.CLASS, 1, 5),
                    Symbol("main", SymbolKind.METHOD, 2, 4),
                ),
                package="com.demo",
            )
        ]
    )
    eps = detect_entrypoints(model)
    assert any(e.kind is EntrypointKind.CLI_MAIN for e in eps)
