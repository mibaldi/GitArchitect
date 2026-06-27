"""Detected technology stacks and external dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StackCategory(StrEnum):
    """What role a detected technology plays."""

    LANGUAGE = "language"
    BUILD_TOOL = "build_tool"
    PACKAGE_MANAGER = "package_manager"
    FRAMEWORK = "framework"
    RUNTIME = "runtime"


@dataclass(frozen=True)
class DetectedStack:
    """A technology detected from a manifest or project marker file."""

    name: str
    category: StackCategory
    evidence: str  # relative path of the file that revealed it
    version: str | None = None


@dataclass(frozen=True)
class Dependency:
    """An external dependency declared in a manifest."""

    name: str
    version: str | None
    manifest: str  # relative path of the declaring manifest
    scope: str | None = None  # e.g. compile, test, dev
