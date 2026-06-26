"""Feature: a functionality of the system, described in natural language."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class FeatureSource(StrEnum):
    """Where a feature description came from."""

    STATIC = "static"  # derived deterministically
    AI = "ai"  # written by the AI pass


@dataclass(frozen=True)
class Feature:
    """A capability of the system.

    ``related`` references the static evidence (module ids or entrypoint names)
    the description is grounded in, so the documentation can link claims back to
    real code rather than presenting AI prose as unverifiable fact.
    """

    name: str
    description: str
    related: tuple[str, ...] = field(default_factory=tuple)
    source: FeatureSource = FeatureSource.AI
