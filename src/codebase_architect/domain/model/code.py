"""Static code facts extracted from a workspace.

These value objects are produced by the parsing/detection adapters and are
deliberately language-agnostic: a :class:`Symbol` or :class:`ImportRef` means
the same thing whether it came from Java, Kotlin or TypeScript. Higher-level
structures (module graph, architecture) are built on top of these in later
phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Language(StrEnum):
    """A source language recognized by the analyzer."""

    JAVA = "java"
    KOTLIN = "kotlin"
    TYPESCRIPT = "typescript"
    TSX = "tsx"
    JAVASCRIPT = "javascript"
    PYTHON = "python"
    HTML = "html"
    UNKNOWN = "unknown"


class SymbolKind(StrEnum):
    """The kind of a declared code symbol."""

    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    OBJECT = "object"
    METHOD = "method"
    FUNCTION = "function"


@dataclass(frozen=True)
class Symbol:
    """A top-level or nested declaration found in a file."""

    name: str
    kind: SymbolKind
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ImportRef:
    """A reference to something imported by a file (raw target as written)."""

    target: str


@dataclass(frozen=True)
class HttpEndpointDecl:
    """An HTTP endpoint a file exposes (e.g. Spring @GetMapping, FastAPI route)."""

    method: str  # GET/POST/... or "ANY"
    path: str
    handler: str = ""  # the function/method name serving it


@dataclass(frozen=True)
class HttpCallDecl:
    """An outbound HTTP call a file makes (e.g. Angular HttpClient, fetch)."""

    method: str  # GET/POST/... or "ANY"
    path: str


@dataclass(frozen=True)
class ParsedFile:
    """The result of parsing a single source file."""

    path: str
    language: Language
    loc: int
    symbols: tuple[Symbol, ...] = ()
    imports: tuple[ImportRef, ...] = ()
    #: Namespace/package the file declares, when the language has one.
    package: str | None = None
    #: Names referenced as calls/instantiations (e.g. ``new Foo()``, ``foo()``),
    #: used to build a call graph on top of the import graph.
    calls: tuple[str, ...] = ()
    #: HTTP endpoints this file exposes (server side).
    routes: tuple[HttpEndpointDecl, ...] = ()
    #: Outbound HTTP calls this file makes (client side).
    http_calls: tuple[HttpCallDecl, ...] = ()
