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


def test_calls_extracted_skipping_member_calls(parser: TreeSitterParser) -> None:
    src = b"""package com.demo;
class X {
    void run() {
        new Greeter();
        helper();
        this.ignored();
        other.alsoIgnored();
    }
}
"""
    parsed = parser.parse("X.java", Language.JAVA, src)
    assert "Greeter" in parsed.calls  # constructor
    assert "helper" in parsed.calls  # unqualified call
    assert "ignored" not in parsed.calls  # member call skipped
    assert "alsoIgnored" not in parsed.calls


def test_spring_routes_extracted_with_class_base(parser: TreeSitterParser) -> None:
    src = b"""package com.demo;
@RestController
@RequestMapping("/api/orders")
public class OrderController {
    @GetMapping("/{id}")
    public Order get(Long id) { return null; }
    @PostMapping
    public Order create() { return null; }
}
"""
    parsed = parser.parse("OrderController.java", Language.JAVA, src)
    routes = {(r.method, r.path) for r in parsed.routes}
    assert ("GET", "/api/orders/{id}") in routes
    assert ("POST", "/api/orders") in routes


def test_fastapi_routes_extracted(parser: TreeSitterParser) -> None:
    src = b"""from fastapi import APIRouter
router = APIRouter()

@router.get("/users")
def list_users():
    return []

@router.post("/users/{uid}/orders")
def place(uid):
    return None
"""
    parsed = parser.parse("api.py", Language.PYTHON, src)
    routes = {(r.method, r.path) for r in parsed.routes}
    assert ("GET", "/users") in routes
    assert ("POST", "/users/{uid}/orders") in routes


def test_ts_http_calls_extracted_and_dynamic_skipped(parser: TreeSitterParser) -> None:
    src = b"""export class OrdersService {
    constructor(private http) {}
    list() { return this.http.get('/api/orders'); }
    create(o) { return this.http.post('/api/orders', o); }
    one(id) { return this.http.get(`/api/orders/${id}`); }
    notAnApi() { const m = new Map(); return m.get('key'); }
}
"""
    parsed = parser.parse("orders.service.ts", Language.TYPESCRIPT, src)
    calls = {(c.method, c.path) for c in parsed.http_calls}
    assert ("GET", "/api/orders") in calls
    assert ("POST", "/api/orders") in calls
    assert not any(c.path == "key" for c in parsed.http_calls)  # map.get ignored
    # dynamic template path is skipped (not a static literal)
    assert not any("${" in c.path for c in parsed.http_calls)


def test_unsupported_language_counts_loc_only(parser: TreeSitterParser) -> None:
    assert parser.supports(Language.HTML) is False
    parsed = parser.parse("a.html", Language.HTML, b"<div>\n<span>\n</div>\n")
    assert parsed.loc == 3
    assert parsed.symbols == ()


def test_loc_counts_final_unterminated_line(parser: TreeSitterParser) -> None:
    parsed = parser.parse("X.java", Language.JAVA, b"class X {}")
    assert parsed.loc == 1
