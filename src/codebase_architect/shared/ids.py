"""Identifier generation.

Uses UUIDv4 hex strings. Centralised so the rest of the codebase never calls
``uuid`` directly, which keeps id generation easy to stub in tests.
"""

from __future__ import annotations

import uuid


def new_id(prefix: str = "") -> str:
    """Return a new unique id, optionally namespaced with ``prefix``.

    Example: ``new_id("task")`` -> ``"task_3f2a...".``
    """
    value = uuid.uuid4().hex
    return f"{prefix}_{value}" if prefix else value
