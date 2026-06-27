"""Module-level call edges, derived from call references in the parsed files.

The import graph says which modules *know about* each other; the call graph adds
which modules *invoke* each other. A call name (a constructor or function) is
resolved to the module(s) that declare a matching class/function symbol, and an
edge is added from the calling module to that declaring module.

This is name-based and therefore approximate (a name can be declared in more than
one place); it is used only to enrich the flow diagrams, never to assert facts
about coupling. Names declared in many modules are too ambiguous to be useful, so
they are dropped.
"""

from __future__ import annotations

from collections import defaultdict

from codebase_architect.domain.model.code import SymbolKind
from codebase_architect.domain.model.code_model import CodeModel
from codebase_architect.domain.model.module import ModuleEdge
from codebase_architect.domain.services.module_graph import module_id_of

# Symbol kinds whose names are worth resolving call targets against.
_CALLABLE_KINDS = frozenset(
    {SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.OBJECT, SymbolKind.FUNCTION}
)
# A name declared in more than this many modules is too ambiguous to resolve.
_MAX_DECL_MODULES = 3


def build_call_edges(model: CodeModel) -> list[ModuleEdge]:
    """Resolve call names to declaring modules and return weighted edges."""
    declarers: dict[str, set[str]] = defaultdict(set)
    for parsed in model.parsed_files:
        module = module_id_of(parsed)
        for symbol in parsed.symbols:
            if symbol.kind in _CALLABLE_KINDS:
                declarers[symbol.name].add(module)

    weights: dict[tuple[str, str], int] = defaultdict(int)
    for parsed in model.parsed_files:
        source = module_id_of(parsed)
        for name in parsed.calls:
            targets = declarers.get(name)
            if not targets or len(targets) > _MAX_DECL_MODULES:
                continue
            for target in targets:
                if target != source:
                    weights[(source, target)] += 1

    return [
        ModuleEdge(source=src, target=dst, weight=count)
        for (src, dst), count in sorted(weights.items())
    ]
