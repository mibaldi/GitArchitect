"""REST API driver (FastAPI).

Import ``create_app`` to build the application. FastAPI is an optional
dependency (the ``api`` extra); importing this package without it raises a
clear, actionable error.
"""

from __future__ import annotations

from codebase_architect.shared.errors import ConfigurationError

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without the extra
    raise ConfigurationError(
        "The API requires the 'api' extra. Install it with: pip install 'codebase-architect[api]'"
    ) from exc

from codebase_architect.api.app import create_app

__all__ = ["create_app"]
