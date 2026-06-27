"""Inferred architecture: layers and components with supporting evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Layer(StrEnum):
    """A coarse architectural layer a module is assigned to."""

    PRESENTATION = "presentation"  # REST controllers / HTTP endpoints / CLI
    UI = "ui"  # Angular components / views
    APPLICATION = "application"  # services, use cases, handlers
    DOMAIN = "domain"  # entities, domain model, ports
    DATA = "data"  # repositories, persistence
    INFRASTRUCTURE = "infrastructure"  # adapters, gateways, external integrations
    CONFIG = "config"  # configuration / bootstrap
    SHARED = "shared"  # utilities, common code
    OTHER = "other"  # unclassified


@dataclass(frozen=True)
class Component:
    """A module placed in a layer, with the heuristic evidence for the choice."""

    module_id: str
    layer: Layer
    evidence: str


@dataclass
class Architecture:
    """The inferred layered view of a codebase."""

    components: list[Component] = field(default_factory=list)

    def by_layer(self) -> dict[Layer, list[Component]]:
        grouped: dict[Layer, list[Component]] = {}
        for component in self.components:
            grouped.setdefault(component.layer, []).append(component)
        return grouped

    def layers_present(self) -> list[Layer]:
        seen = {c.layer for c in self.components}
        return [layer for layer in Layer if layer in seen]

    def layer_of(self) -> dict[str, Layer]:
        return {c.module_id: c.layer for c in self.components}


@dataclass(frozen=True)
class LayerViolation:
    """A dependency that points outward, against the inward-pointing rule."""

    source: str
    target: str
    source_layer: Layer
    target_layer: Layer


@dataclass(frozen=True)
class Cycle:
    """A group of modules that depend on each other (a dependency cycle)."""

    modules: tuple[str, ...]


@dataclass(frozen=True)
class ArchitectureReport:
    """Findings about how well the module graph respects its layering."""

    violations: tuple[LayerViolation, ...] = ()
    cycles: tuple[Cycle, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not self.violations and not self.cycles
