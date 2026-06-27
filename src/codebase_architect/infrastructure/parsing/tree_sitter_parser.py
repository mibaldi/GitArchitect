"""Tree-sitter based code parser for Java, Kotlin and TypeScript/Angular.

Grammars are loaded from precompiled wheels, so no network access is needed.
Symbol extraction walks the concrete syntax tree for a small, curated set of
declaration node types per language; this is robust and fast, and degrades to
"no symbols" rather than failing when a grammar version shifts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import tree_sitter_html
import tree_sitter_java
import tree_sitter_kotlin
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language as TSLanguage
from tree_sitter import Node, Parser

from codebase_architect.domain.model.code import (
    ImportRef,
    Language,
    ParsedFile,
    Symbol,
    SymbolKind,
)
from codebase_architect.domain.ports.analysis import CodeParser

_NAME_NODE_TYPES = {"identifier", "type_identifier", "simple_identifier"}


@dataclass(frozen=True)
class _LangSpec:
    ts_language: TSLanguage
    symbols: dict[str, SymbolKind]
    import_types: frozenset[str]
    package_types: frozenset[str] = frozenset()
    # How to read the imported target: "text" (whole node text) or "source"
    # (a string literal child field, used by ECMAScript import statements).
    import_style: str = "text"
    # Node types that denote a call/instantiation, used for the call graph.
    call_types: frozenset[str] = frozenset()
    parser: Parser = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parser", Parser(self.ts_language))


def _build_specs() -> dict[Language, _LangSpec]:
    java = _LangSpec(
        ts_language=TSLanguage(tree_sitter_java.language()),
        symbols={
            "class_declaration": SymbolKind.CLASS,
            "record_declaration": SymbolKind.CLASS,
            "interface_declaration": SymbolKind.INTERFACE,
            "annotation_type_declaration": SymbolKind.INTERFACE,
            "enum_declaration": SymbolKind.ENUM,
            "method_declaration": SymbolKind.METHOD,
            "constructor_declaration": SymbolKind.METHOD,
        },
        import_types=frozenset({"import_declaration"}),
        package_types=frozenset({"package_declaration"}),
        import_style="text",
        call_types=frozenset({"object_creation_expression", "method_invocation"}),
    )
    kotlin = _LangSpec(
        ts_language=TSLanguage(tree_sitter_kotlin.language()),
        symbols={
            "class_declaration": SymbolKind.CLASS,
            "object_declaration": SymbolKind.OBJECT,
            "function_declaration": SymbolKind.FUNCTION,
        },
        import_types=frozenset({"import"}),
        package_types=frozenset({"package_header"}),
        import_style="text",
        call_types=frozenset({"call_expression"}),
    )
    ts_symbols = {
        "class_declaration": SymbolKind.CLASS,
        "abstract_class_declaration": SymbolKind.CLASS,
        "interface_declaration": SymbolKind.INTERFACE,
        "enum_declaration": SymbolKind.ENUM,
        "function_declaration": SymbolKind.FUNCTION,
        "function_signature": SymbolKind.FUNCTION,
        "method_definition": SymbolKind.METHOD,
    }
    ts_calls = frozenset({"call_expression", "new_expression"})
    typescript = _LangSpec(
        ts_language=TSLanguage(tree_sitter_typescript.language_typescript()),
        symbols=ts_symbols,
        import_types=frozenset({"import_statement"}),
        import_style="source",
        call_types=ts_calls,
    )
    tsx = _LangSpec(
        ts_language=TSLanguage(tree_sitter_typescript.language_tsx()),
        symbols=ts_symbols,
        import_types=frozenset({"import_statement"}),
        import_style="source",
        call_types=ts_calls,
    )
    python = _LangSpec(
        ts_language=TSLanguage(tree_sitter_python.language()),
        symbols={
            "class_definition": SymbolKind.CLASS,
            "function_definition": SymbolKind.FUNCTION,
        },
        import_types=frozenset({"import_statement", "import_from_statement"}),
        import_style="python",
        call_types=frozenset({"call"}),
    )
    return {
        Language.JAVA: java,
        Language.KOTLIN: kotlin,
        Language.TYPESCRIPT: typescript,
        Language.TSX: tsx,
        # JavaScript is parsed with the TypeScript (superset) grammar.
        Language.JAVASCRIPT: typescript,
        Language.PYTHON: python,
    }


class TreeSitterParser(CodeParser):
    """Extracts symbols, imports and package from supported source files."""

    def __init__(self) -> None:
        self._specs = _build_specs()
        # Validate the HTML grammar loads (used for LOC/templates later).
        TSLanguage(tree_sitter_html.language())

    def supports(self, language: Language) -> bool:
        return language in self._specs

    def parse(self, relative_path: str, language: Language, content: bytes) -> ParsedFile:
        loc = content.count(b"\n") + (1 if content and not content.endswith(b"\n") else 0)
        spec = self._specs.get(language)
        if spec is None:
            return ParsedFile(path=relative_path, language=language, loc=loc)

        tree = spec.parser.parse(content)
        symbols: list[Symbol] = []
        imports: list[ImportRef] = []
        calls: set[str] = set()
        package: str | None = None

        stack: list[Node] = [tree.root_node]
        while stack:
            node = stack.pop()
            kind = spec.symbols.get(node.type)
            if kind is not None:
                name = _symbol_name(node)
                if name:
                    symbols.append(
                        Symbol(
                            name=name,
                            kind=kind,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                        )
                    )
            elif node.type in spec.import_types:
                target = _import_target(node, spec.import_style)
                if target:
                    imports.append(ImportRef(target=target))
            elif node.type in spec.package_types:
                package = _package_name(node)
            elif node.type in spec.call_types:
                callee = _call_target(node)
                if callee:
                    calls.add(callee)
            stack.extend(node.children)

        return ParsedFile(
            path=relative_path,
            language=language,
            loc=loc,
            symbols=tuple(symbols),
            imports=tuple(imports),
            package=package,
            calls=tuple(sorted(calls)),
        )


def _symbol_name(node: Node) -> str | None:
    field_name = node.child_by_field_name("name")
    if field_name is not None and field_name.text is not None:
        return field_name.text.decode("utf-8", "replace")
    for child in node.children:
        if child.type in _NAME_NODE_TYPES and child.text is not None:
            return child.text.decode("utf-8", "replace")
    return None


def _import_target(node: Node, style: str) -> str | None:
    if style == "source":
        source = node.child_by_field_name("source")
        if source is not None and source.text is not None:
            return source.text.decode("utf-8", "replace").strip("'\"")
        return None
    if style == "python":
        return _python_import_target(node)
    # text style (Java/Kotlin): strip the keyword, modifiers and terminator.
    if node.text is None:
        return None
    raw = node.text.decode("utf-8", "replace").strip()
    raw = raw.removeprefix("import").strip()
    raw = raw.removeprefix("static").strip()
    raw = raw.rstrip(";").strip()
    raw = raw.split(" as ", 1)[0].strip()
    return raw or None


def _python_import_target(node: Node) -> str | None:
    # `from a.b import c` -> "a.b" ; `from . import c` -> "."
    module = node.child_by_field_name("module_name")
    if module is not None and module.text is not None:
        return module.text.decode("utf-8", "replace").strip()
    # `import a.b[.c]` (possibly aliased) -> the first dotted name.
    for child in node.children:
        target = child
        if child.type == "aliased_import":
            named = child.child_by_field_name("name")
            target = named if named is not None else child
        if target.type in ("dotted_name", "identifier") and target.text is not None:
            return target.text.decode("utf-8", "replace").strip()
    return None


_IDENT_TYPES = frozenset(
    {"identifier", "type_identifier", "simple_identifier", "scoped_type_identifier"}
)


def _call_target(node: Node) -> str | None:
    """Best-effort callee/type name for a call or instantiation node.

    Only resolvable *names* are returned (constructor types and unqualified
    function calls); member calls like ``obj.method()`` are skipped to keep the
    call graph low-noise. Generic args and package qualifiers are stripped to the
    simple name so it can be matched against declared symbols.
    """
    t = node.type
    target: Node | None = None
    if t == "object_creation_expression":  # Java: new Foo()
        target = node.child_by_field_name("type")
    elif t == "new_expression":  # TypeScript: new Foo()
        target = node.child_by_field_name("constructor")
    elif t == "method_invocation":  # Java: foo()  (skip obj.foo())
        if node.child_by_field_name("object") is None:
            target = node.child_by_field_name("name")
    elif t == "call":  # Python: foo() / Foo()  (skip obj.foo())
        target = node.child_by_field_name("function")
    elif t == "call_expression":  # TypeScript/JS and Kotlin
        fn = node.child_by_field_name("function")
        if fn is not None:
            target = fn  # TypeScript/JS
        elif node.named_child_count:
            target = node.named_children[0]  # Kotlin: callee is the first child
    return _simple_name(target)


def _simple_name(node: Node | None) -> str | None:
    if node is None or node.type not in _IDENT_TYPES or node.text is None:
        return None
    name = node.text.decode("utf-8", "replace").strip()
    name = name.split("<", 1)[0]  # drop generic args
    name = name.rsplit(".", 1)[-1]  # drop package/scope qualifier
    return name or None


def _package_name(node: Node) -> str | None:
    if node.text is None:
        return None
    raw = node.text.decode("utf-8", "replace").strip()
    raw = raw.removeprefix("package").strip()
    return raw.rstrip(";").strip() or None
