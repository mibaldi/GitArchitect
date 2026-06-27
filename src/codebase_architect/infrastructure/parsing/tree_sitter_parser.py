"""Tree-sitter based code parser for Java, Kotlin and TypeScript/Angular.

Grammars are loaded from precompiled wheels, so no network access is needed.
Symbol extraction walks the concrete syntax tree for a small, curated set of
declaration node types per language; this is robust and fast, and degrades to
"no symbols" rather than failing when a grammar version shifts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tree_sitter_html
import tree_sitter_java
import tree_sitter_kotlin
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language as TSLanguage
from tree_sitter import Node, Parser

from codebase_architect.domain.model.code import (
    HttpCallDecl,
    HttpEndpointDecl,
    ImportRef,
    Language,
    ParsedFile,
    Symbol,
    SymbolKind,
)
from codebase_architect.domain.ports.analysis import CodeParser

_NAME_NODE_TYPES = {"identifier", "type_identifier", "simple_identifier"}

# Spring mapping annotations and FastAPI/HttpClient verbs -> HTTP method.
_SPRING_MAPPING = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
    "RequestMapping": "ANY",
}
_HTTP_VERBS = frozenset({"get", "post", "put", "delete", "patch"})


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

        routes, http_calls = _extract_http(tree.root_node, language)
        return ParsedFile(
            path=relative_path,
            language=language,
            loc=loc,
            symbols=tuple(symbols),
            imports=tuple(imports),
            package=package,
            calls=tuple(sorted(calls)),
            routes=tuple(routes),
            http_calls=tuple(http_calls),
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


# -- HTTP route / call extraction (phase C) ---------------------------------


def _extract_http(
    root: Node, language: Language
) -> tuple[list[HttpEndpointDecl], list[HttpCallDecl]]:
    routes: list[HttpEndpointDecl] = []
    calls: list[HttpCallDecl] = []
    if language is Language.JAVA:
        _walk_java_http(root, "", routes)
    elif language is Language.PYTHON:
        _walk_python_routes(root, routes)
    if language in (Language.TYPESCRIPT, Language.TSX, Language.JAVASCRIPT):
        _walk_ts_http_calls(root, calls)
    return routes, calls


def _text_of(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8", "replace")


def _string_value(node: Node | None) -> str | None:
    """Literal value of a string/template node.

    Template interpolations (``${...}``) are collapsed to a ``{}`` placeholder so
    a dynamic call path like ``/orders/${id}`` can still be matched against a
    route template ``/orders/{id}``.
    """
    if node is None:
        return None
    raw = _text_of(node)
    if node.type == "template_string":
        inner = raw.strip("`")
        return re.sub(r"\$\{[^}]*\}", "{}", inner)
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] in "\"'" and raw[-1] in "\"'":
        return raw[1:-1]
    return None


def _join_path(base: str, path: str) -> str:
    combined = base.rstrip("/") + "/" + path.lstrip("/") if base and path else base or path
    if combined and not combined.startswith(("/", "http")):
        combined = "/" + combined
    return combined or "/"


def _annotations(node: Node) -> list[Node]:
    found: list[Node] = []
    for child in node.children:
        if child.type in ("annotation", "marker_annotation"):
            found.append(child)
        elif child.type == "modifiers":
            found.extend(
                c for c in child.children if c.type in ("annotation", "marker_annotation")
            )
    return found


def _annotation_path(annotation: Node) -> str:
    args = annotation.child_by_field_name("arguments")
    if args is None:
        return ""
    for child in args.children:
        if child.type == "element_value_pair":
            key = _text_of(child.child_by_field_name("key"))
            if key in ("value", "path"):
                value = _string_value(child.child_by_field_name("value"))
                if value is not None:
                    return value
        elif child.type == "string_literal":
            value = _string_value(child)
            if value is not None:
                return value
    return ""


def _walk_java_http(node: Node, base: str, routes: list[HttpEndpointDecl]) -> None:
    if node.type == "class_declaration":
        class_base = base
        for annotation in _annotations(node):
            name = _text_of(annotation.child_by_field_name("name")).rsplit(".", 1)[-1]
            if name == "RequestMapping":
                class_base = _join_path(base, _annotation_path(annotation))
        for child in node.children:
            # The class body carries the base path down to its method mappings.
            _walk_java_http(child, class_base if child.type == "class_body" else base, routes)
        return
    if node.type in ("method_declaration", "constructor_declaration"):
        handler = _text_of(node.child_by_field_name("name"))
        for annotation in _annotations(node):
            name = _text_of(annotation.child_by_field_name("name")).rsplit(".", 1)[-1]
            method = _SPRING_MAPPING.get(name)
            if method:
                path = _join_path(base, _annotation_path(annotation))
                routes.append(HttpEndpointDecl(method, path, handler))
        return
    for child in node.children:
        _walk_java_http(child, base, routes)


def _walk_python_routes(node: Node, routes: list[HttpEndpointDecl]) -> None:
    if node.type == "decorated_definition":
        func = node.child_by_field_name("definition")
        handler = _text_of(func.child_by_field_name("name")) if func is not None else ""
        for child in node.children:
            if child.type == "decorator":
                route = _python_decorator_route(child, handler)
                if route is not None:
                    routes.append(route)
    for child in node.children:
        _walk_python_routes(child, routes)


def _python_decorator_route(decorator: Node, handler: str) -> HttpEndpointDecl | None:
    call = next((c for c in decorator.children if c.type == "call"), None)
    if call is None:
        return None
    func = call.child_by_field_name("function")
    if func is None or func.type != "attribute":
        return None
    verb = _text_of(func.child_by_field_name("attribute")).lower()
    if verb not in _HTTP_VERBS:
        return None
    args = call.child_by_field_name("arguments")
    path = _first_string_arg(args)
    if path is None:
        return None
    return HttpEndpointDecl(verb.upper(), _join_path("", path), handler)


def _walk_ts_http_calls(node: Node, calls: list[HttpCallDecl]) -> None:
    if node.type == "call_expression":
        call = _ts_http_call(node)
        if call is not None:
            calls.append(call)
    for child in node.children:
        _walk_ts_http_calls(child, calls)


def _ts_http_call(node: Node) -> HttpCallDecl | None:
    func = node.child_by_field_name("function")
    args = node.child_by_field_name("arguments")
    if func is None:
        return None
    if func.type == "identifier" and _text_of(func) == "fetch":
        path = _first_string_arg(args)
        return HttpCallDecl("ANY", path) if path is not None and _is_url(path) else None
    if func.type == "member_expression":
        verb = _text_of(func.child_by_field_name("property")).lower()
        receiver = _text_of(func.child_by_field_name("object")).lower()
        if verb in _HTTP_VERBS and ("http" in receiver or "axios" in receiver):
            path = _first_string_arg(args)
            if path is not None and _is_url(path):
                return HttpCallDecl(verb.upper(), path)
    return None


def _first_string_arg(args: Node | None) -> str | None:
    if args is None:
        return None
    for child in args.children:
        if child.type in ("string", "string_literal", "template_string"):
            return _string_value(child)
    return None


def _is_url(path: str) -> bool:
    return path.startswith(("/", "http"))
