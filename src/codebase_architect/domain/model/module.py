"""Module graph: logical groupings of files and their internal dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field

from codebase_architect.domain.model.code import Language


@dataclass
class Module:
    """A logical unit: a Java/Kotlin package or a TypeScript directory."""

    id: str
    name: str
    files: list[str] = field(default_factory=list)
    languages: set[Language] = field(default_factory=set)
    symbol_count: int = 0
    loc: int = 0


@dataclass(frozen=True)
class ModuleEdge:
    """A directed dependency from one module to another, with a weight."""

    source: str
    target: str
    weight: int = 1


@dataclass
class ModuleGraph:
    """All modules of a codebase and the dependency edges between them."""

    modules: list[Module] = field(default_factory=list)
    edges: list[ModuleEdge] = field(default_factory=list)

    def module_ids(self) -> set[str]:
        return {m.id for m in self.modules}

    def dependencies_of(self, module_id: str) -> list[ModuleEdge]:
        return [e for e in self.edges if e.source == module_id]
