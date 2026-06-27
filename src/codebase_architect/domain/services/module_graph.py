"""Build the module graph from a CodeModel.

A *module* is a Java/Kotlin package or, for languages without packages
(TypeScript/HTML/JS), the directory a file lives in. Internal dependency edges
are derived by resolving each file's imports back to a known module; imports
that resolve outside the codebase (e.g. ``@angular/core``, ``java.util``) are
treated as external and dropped from the graph.
"""

from __future__ import annotations

import posixpath
from collections import Counter

from codebase_architect.domain.model.code import ImportRef, ParsedFile
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.module import Module, ModuleEdge, ModuleGraph

_ROOT = "(root)"


def build_module_graph(model: CodeModel) -> ModuleGraph:
    modules: dict[str, Module] = {}
    for parsed in model.parsed_files:
        key = _module_key(parsed)
        module = modules.get(key)
        if module is None:
            module = Module(id=key, name=_module_name(key))
            modules[key] = module
        module.files.append(parsed.path)
        module.languages.add(parsed.language)
        module.symbol_count += len(parsed.symbols)
        module.loc += parsed.loc

    index = set(modules)
    weights: Counter[tuple[str, str]] = Counter()
    for parsed in model.parsed_files:
        source = _module_key(parsed)
        for imp in parsed.imports:
            target = _resolve_import(parsed, imp, index)
            if target is not None and target != source:
                weights[(source, target)] += 1

    edges = [
        ModuleEdge(source=src, target=dst, weight=count)
        for (src, dst), count in sorted(weights.items())
    ]
    ordered = [modules[k] for k in sorted(modules)]
    return ModuleGraph(modules=ordered, edges=edges)


def module_id_of(parsed: ParsedFile) -> str:
    """The module a file belongs to: its package, else its directory."""
    if parsed.package:
        return parsed.package
    parent = posixpath.dirname(parsed.path)
    return parent or _ROOT


def _module_key(parsed: ParsedFile) -> str:
    return module_id_of(parsed)


def _module_name(key: str) -> str:
    if key == _ROOT:
        return _ROOT
    if "." in key and "/" not in key:
        return key.rsplit(".", 1)[-1]
    return posixpath.basename(key) or key


def _resolve_import(parsed: ParsedFile, imp: ImportRef, index: set[str]) -> str | None:
    target = imp.target.strip()
    if not target:
        return None
    if target.startswith(("./", "../")):
        return _resolve_relative(parsed.path, target, index)
    if target.startswith("."):
        # Python dotted relative import (".services", "..core") — leading dots
        # count levels up from the file's own package directory.
        return _resolve_python_relative(parsed.path, target, index)
    return _resolve_dotted(target, index)


def _resolve_relative(from_path: str, target: str, index: set[str]) -> str | None:
    base = posixpath.dirname(from_path)
    resolved = posixpath.normpath(posixpath.join(base, target))
    candidate = posixpath.dirname(resolved) or _ROOT
    return candidate if candidate in index else None


def _resolve_python_relative(from_path: str, target: str, index: set[str]) -> str | None:
    dots = len(target) - len(target.lstrip("."))
    suffix = target[dots:]  # remaining dotted module path, possibly empty
    base = posixpath.dirname(from_path)
    for _ in range(dots - 1):  # one dot = current package; each extra goes up
        base = posixpath.dirname(base)
    candidate = base or _ROOT
    if suffix:
        sub = suffix.replace(".", "/")
        candidate = posixpath.normpath(posixpath.join(base, sub)) if base else sub
    return candidate if candidate in index else _resolve_as_path(suffix, index)


def _resolve_dotted(target: str, index: set[str]) -> str | None:
    if target.endswith(".*"):
        pkg = target[:-2]
        return pkg if pkg in index else _resolve_as_path(pkg, index)
    package = target.rsplit(".", 1)[0] if "." in target else target
    if package in index:
        return package
    if target in index:
        return target
    # Directory-keyed modules (Python/TS absolute imports): match the dotted
    # path against a module id that is (or ends with) the same directory path.
    return _resolve_as_path(target, index) or _resolve_as_path(package, index)


def _resolve_as_path(dotted: str, index: set[str]) -> str | None:
    if not dotted or "/" in dotted:
        return None
    suffix = dotted.replace(".", "/")
    matches = [m for m in index if "/" in m and (m == suffix or m.endswith("/" + suffix))]
    return max(matches, key=len) if matches else None
