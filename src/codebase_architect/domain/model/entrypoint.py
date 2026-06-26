"""Entrypoints: the places where the system is driven from the outside."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EntrypointKind(StrEnum):
    """The kind of an entrypoint."""

    HTTP_ENDPOINT = "http_endpoint"  # Spring @RestController / @Controller
    UI_COMPONENT = "ui_component"  # Angular component
    NG_MODULE = "ng_module"  # Angular module / routing
    APP_BOOTSTRAP = "app_bootstrap"  # Spring Boot application
    CLI_MAIN = "cli_main"  # main() method


@dataclass(frozen=True)
class Entrypoint:
    """A detected entrypoint into the system."""

    name: str
    kind: EntrypointKind
    file: str
    module: str
    detail: str | None = None  # how it was detected
