"""Detect entrypoints from parsed files.

Detection relies on imports and filename conventions (which the parser already
captures) rather than annotation arguments, so it stays robust across grammar
versions while covering the Spring and Angular cases that matter here.
"""

from __future__ import annotations

import posixpath

from codebase_architect.domain.model.code import Language, ParsedFile, SymbolKind
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.entrypoint import Entrypoint, EntrypointKind

_SPRING_WEB = "org.springframework.web"
_SPRING_BOOT_APP = "org.springframework.boot.autoconfigure.SpringBootApplication"


def detect_entrypoints(model: CodeModel) -> list[Entrypoint]:
    entrypoints: list[Entrypoint] = []
    for parsed in model.parsed_files:
        if parsed.language in (Language.JAVA, Language.KOTLIN):
            entrypoints.extend(_jvm_entrypoints(parsed))
        elif parsed.language in (Language.TYPESCRIPT, Language.TSX):
            entrypoints.extend(_angular_entrypoints(parsed))
        elif parsed.language is Language.PYTHON:
            entrypoints.extend(_python_entrypoints(parsed))
    return entrypoints


def _python_entrypoints(parsed: ParsedFile) -> list[Entrypoint]:
    module = _module_of(parsed.path)
    has_main = any(
        s.kind is SymbolKind.FUNCTION and s.name == "main" for s in parsed.symbols
    )
    if has_main or posixpath.basename(parsed.path) == "__main__.py":
        name = posixpath.basename(parsed.path)
        return [Entrypoint(name, EntrypointKind.CLI_MAIN, parsed.path, module, "main()/__main__")]
    return []


def _module_of(path: str) -> str:
    return posixpath.dirname(path) or "(root)"


def _first_class_name(parsed: ParsedFile) -> str | None:
    for symbol in parsed.symbols:
        if symbol.kind is SymbolKind.CLASS:
            return symbol.name
    return None


def _jvm_entrypoints(parsed: ParsedFile) -> list[Entrypoint]:
    found: list[Entrypoint] = []
    imports = [i.target for i in parsed.imports]
    module = parsed.package or _module_of(parsed.path)

    if any(i.startswith(_SPRING_WEB) for i in imports):
        name = _first_class_name(parsed) or posixpath.basename(parsed.path)
        found.append(
            Entrypoint(name, EntrypointKind.HTTP_ENDPOINT, parsed.path, module, "Spring web import")
        )
    if any(i == _SPRING_BOOT_APP for i in imports):
        name = _first_class_name(parsed) or posixpath.basename(parsed.path)
        found.append(
            Entrypoint(
                name, EntrypointKind.APP_BOOTSTRAP, parsed.path, module, "@SpringBootApplication"
            )
        )
    if any(s.kind is SymbolKind.METHOD and s.name == "main" for s in parsed.symbols):
        name = _first_class_name(parsed) or posixpath.basename(parsed.path)
        found.append(
            Entrypoint(name, EntrypointKind.CLI_MAIN, parsed.path, module, "main() method")
        )
    return found


def _angular_entrypoints(parsed: ParsedFile) -> list[Entrypoint]:
    found: list[Entrypoint] = []
    base = posixpath.basename(parsed.path).lower()
    module = _module_of(parsed.path)
    class_name = _first_class_name(parsed)

    # Only treat true Angular components/modules as entrypoints. Services, pipes
    # and directives also import @angular/core but are not driven from outside.
    if base.endswith(".module.ts"):
        found.append(
            Entrypoint(
                class_name or base, EntrypointKind.NG_MODULE, parsed.path, module, "Angular module"
            )
        )
    elif base.endswith(".component.ts"):
        found.append(
            Entrypoint(
                class_name or base,
                EntrypointKind.UI_COMPONENT,
                parsed.path,
                module,
                "Angular component",
            )
        )
    return found
