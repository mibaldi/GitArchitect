"""Resolve a DocRenderer by name (built-in markdown + renderer plugins)."""

from __future__ import annotations

from collections.abc import Callable

from codebase_architect.application.registries.plugins import discover_plugins
from codebase_architect.domain.ports.documentation import DocRenderer
from codebase_architect.infrastructure.rendering.markdown_renderer import MarkdownMermaidRenderer
from codebase_architect.shared.errors import ConfigurationError

RENDERER_GROUP = "codebase_architect.renderers"

_BUILTINS: dict[str, Callable[[], DocRenderer]] = {
    "markdown": MarkdownMermaidRenderer,
    "md": MarkdownMermaidRenderer,
}


def build_renderer(name: str | None) -> DocRenderer:
    """Return the renderer for ``name`` (defaults to Markdown)."""
    key = (name or "markdown").lower()
    factory = _BUILTINS.get(key)
    if factory is None:
        factory = discover_plugins(RENDERER_GROUP).get(key)  # type: ignore[assignment]
    if factory is None:
        available = ", ".join(sorted(_BUILTINS)) or "(none)"
        raise ConfigurationError(
            f"Unknown renderer: {name!r}. Built-in renderers: {available}. "
            "Renderer plugins are discovered from the "
            f"'{RENDERER_GROUP}' entry-point group."
        )

    renderer = factory()
    if not isinstance(renderer, DocRenderer):
        raise ConfigurationError(
            f"Renderer plugin {name!r} does not implement DocRenderer "
            f"(got {type(renderer).__name__})."
        )
    return renderer


def available_renderers() -> list[str]:
    """Names of all resolvable renderers (built-in + discovered plugins)."""
    return sorted(set(_BUILTINS) | set(discover_plugins(RENDERER_GROUP)))
