"""Plugin discovery via importlib entry points.

Plugins register factories under named groups (e.g. ``codebase_architect.
renderers``). Discovery is best-effort: a plugin that fails to import is logged
and skipped rather than breaking the host. Callers validate the loaded object
against the expected port (conformance) before using it.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points
from typing import TypeVar

from codebase_architect.shared.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def discover_plugins(group: str) -> dict[str, Callable[[], object]]:
    """Return a mapping of plugin name -> factory for an entry-point ``group``."""
    found: dict[str, Callable[[], object]] = {}
    try:
        eps = entry_points(group=group)
    except Exception as exc:  # noqa: BLE001 - never let discovery break the host
        logger.warning("plugin_discovery_failed", group=group, error=str(exc))
        return found

    for ep in eps:
        try:
            found[ep.name] = ep.load()
        except Exception as exc:  # noqa: BLE001 - one bad plugin must not break others
            logger.warning("plugin_load_failed", group=group, plugin=ep.name, error=str(exc))
    return found
