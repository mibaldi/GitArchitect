"""Functional spec: a structured, template-driven description of what the system
does — the "theory" that later gets reconciled against the scanned code.

It is a global entity (not tied to one scan): one functionality typically spans
a frontend, a backend and several microservices, so a spec can be linked to many
scans. The structure mirrors the dashboard template exactly (header + a list of
functionalities), and the structured ``main_flow`` steps and ``endpoints`` are
what the reconciliation pass (phase B2/C) matches against extracted artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FlowStep:
    """One step of a functional flow: an actor does an action against a target."""

    actor: str = ""
    action: str = ""
    target: str = ""  # the system/service/component the step reaches


@dataclass(frozen=True)
class EndpointRef:
    """An HTTP endpoint a functionality is known to use (method + path)."""

    method: str = ""
    path: str = ""


@dataclass(frozen=True)
class SpecFeature:
    """A single functionality, as filled in the template wizard."""

    name: str
    actors: tuple[str, ...] = ()
    goal: str = ""
    preconditions: tuple[str, ...] = ()
    main_flow: tuple[FlowStep, ...] = ()
    alternative_flows: tuple[str, ...] = ()
    systems: tuple[str, ...] = ()
    endpoints: tuple[EndpointRef, ...] = ()
    data_entities: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()


@dataclass
class FunctionalSpec:
    """A full functional specification document."""

    id: str
    product: str
    objective: str = ""
    actors: tuple[str, ...] = ()  # global actor catalog
    features: tuple[SpecFeature, ...] = ()
    linked_scan_ids: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = ""
    updated_at: str = ""
