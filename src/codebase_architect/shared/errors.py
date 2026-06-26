"""Base exception hierarchy for the whole project.

Outer layers translate these into transport-specific errors (HTTP status codes,
CLI exit codes). The domain only ever raises ``CodebaseArchitectError`` subtypes.
"""

from __future__ import annotations


class CodebaseArchitectError(Exception):
    """Root of every error raised intentionally by this project."""


class ConfigurationError(CodebaseArchitectError):
    """Invalid or missing configuration."""


class ValidationError(CodebaseArchitectError):
    """A value or invariant failed validation."""


class NotFoundError(CodebaseArchitectError):
    """A requested aggregate or resource does not exist."""


class UnsupportedSourceError(CodebaseArchitectError):
    """No registered :class:`SourceProvider` can handle the given location."""


class CapabilityUnavailableError(CodebaseArchitectError):
    """An optional capability (git, sandbox, hosting plugin) is not available."""
