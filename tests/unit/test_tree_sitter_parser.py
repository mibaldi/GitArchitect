"""Tests for the tree-sitter based code parser."""

from __future__ import annotations

import pytest

from codebase_architect.domain.model.code import Language, SymbolKind
from codebase_architect.infrastructure.parsing.tree_sitter_parser import TreeSitterParser


@pytest.fixture(scope="module")
def parser() -> TreeSitterParser:
    return TreeSitterParser()


def _names(parsed, kind: SymbolKind) -> set[str]:
    return {s.name for s in parsed.symbols if s.kind is kind}


def test_java(parser: TreeSitterParser) -> None:
    src = b"""package com.demo.service;
import java.util.List;
import static java.lang.Math.PI;

public class Greeter {
    private int count;
    public String hello(String name) { return "hi " + name; }
}

interface Speaker { void speak(); }
enum Color { RED, GREEN }
"""
    parsed = parser.parse("Greeter.java", Language.JAVA, src)
    assert parsed.package == "com.demo.service"
    assert _names(parsed, SymbolKind.CLASS) == {"Greeter"}
    assert _names(parsed, SymbolKind.INTERFACE) == {"Speaker"}
    assert _names(parsed, SymbolKind.ENUM) == {"Color"}
    assert "hello" in _names(parsed, SymbolKind.METHOD)
    assert {i.target for i in parsed.imports} == {"java.util.List", "java.lang.Math.PI"}


def test_kotlin(parser: TreeSitterParser) -> None:
    src = b"""package com.demo

import kotlin.math.PI

class Greeter(val name: String) {
    fun hello(): String = "hi"
}

object Registry

fun topLevel() {}
"""
    parsed = parser.parse("Greeter.kt", Language.KOTLIN, src)
    assert parsed.package == "com.demo"
    assert "Greeter" in _names(parsed, SymbolKind.CLASS)
    assert "Registry" in _names(parsed, SymbolKind.OBJECT)
    assert {"hello", "topLevel"} <= _names(parsed, SymbolKind.FUNCTION)
    assert "kotlin.math.PI" in {i.target for i in parsed.imports}


def test_typescript_angular_component(parser: TreeSitterParser) -> None:
    src = b"""import { Component } from '@angular/core';
import { UserService } from './user.service';

@Component({ selector: 'app-root' })
export class AppComponent {
    title = 'demo';
    greet(name: string): string { return name; }
}

export function helper(): void {}
"""
    parsed = parser.parse("app.component.ts", Language.TYPESCRIPT, src)
    assert "AppComponent" in _names(parsed, SymbolKind.CLASS)
    assert "greet" in _names(parsed, SymbolKind.METHOD)
    assert "helper" in _names(parsed, SymbolKind.FUNCTION)
    assert {"@angular/core", "./user.service"} == {i.target for i in parsed.imports}


def test_python(parser: TreeSitterParser) -> None:
    src = b"""import os
from collections import OrderedDict
from .helpers import build
from mypkg.services import Worker as W


class Greeter:
    def hello(self, name: str) -> str:
        return name


def main() -> None:
    pass
"""
    parsed = parser.parse("greeter.py", Language.PYTHON, src)
    assert "Greeter" in _names(parsed, SymbolKind.CLASS)
    assert {"main"} <= _names(parsed, SymbolKind.FUNCTION)
    targets = {i.target for i in parsed.imports}
    assert {"os", "collections", ".helpers", "mypkg.services"} <= targets


def test_unsupported_language_counts_loc_only(parser: TreeSitterParser) -> None:
    assert parser.supports(Language.HTML) is False
    parsed = parser.parse("a.html", Language.HTML, b"<div>\n<span>\n</div>\n")
    assert parsed.loc == 3
    assert parsed.symbols == ()


def test_loc_counts_final_unterminated_line(parser: TreeSitterParser) -> None:
    parsed = parser.parse("X.java", Language.JAVA, b"class X {}")
    assert parsed.loc == 1
