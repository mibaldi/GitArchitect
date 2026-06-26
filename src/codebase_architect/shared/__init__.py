"""Shared, cross-cutting concerns.

This is the innermost layer. It depends on nothing else inside the project and
may be imported by any layer. It must stay free of business logic.
"""

from codebase_architect.shared.config import Settings, get_settings
from codebase_architect.shared.errors import (
    CapabilityUnavailableError,
    CodebaseArchitectError,
    ConfigurationError,
    NotFoundError,
    UnsupportedSourceError,
    ValidationError,
)
from codebase_architect.shared.ids import new_id
from codebase_architect.shared.logging import configure_logging, get_logger

__all__ = [
    "Settings",
    "get_settings",
    "CapabilityUnavailableError",
    "CodebaseArchitectError",
    "ConfigurationError",
    "NotFoundError",
    "UnsupportedSourceError",
    "ValidationError",
    "new_id",
    "configure_logging",
    "get_logger",
]
