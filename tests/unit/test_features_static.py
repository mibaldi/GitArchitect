"""Tests for the static functionality catalog."""

from __future__ import annotations

from codebase_architect.domain.model.entrypoint import Entrypoint, EntrypointKind
from codebase_architect.domain.model.feature import FeatureSource
from codebase_architect.domain.services.features_static import derive_static_features


def _ep(name: str, kind: EntrypointKind, module: str) -> Entrypoint:
    return Entrypoint(name=name, kind=kind, file=f"{module}/{name}", module=module)


def test_no_entrypoints_yields_no_features() -> None:
    assert derive_static_features([]) == []


def test_features_grouped_by_kind() -> None:
    eps = [
        _ep("GreetController", EntrypointKind.HTTP_ENDPOINT, "web"),
        _ep("UserController", EntrypointKind.HTTP_ENDPOINT, "users"),
        _ep("AppComponent", EntrypointKind.UI_COMPONENT, "app"),
        _ep("main", EntrypointKind.CLI_MAIN, "cli"),
    ]
    features = derive_static_features(eps)
    names = {f.name for f in features}
    assert names == {"HTTP API", "Web UI", "Command-line interface"}
    assert all(f.source is FeatureSource.STATIC for f in features)

    http = next(f for f in features if f.name == "HTTP API")
    assert "2 HTTP endpoint" in http.description
    assert "`users`" in http.description and "`web`" in http.description
    assert http.related == ("GreetController", "UserController")


def test_module_list_is_truncated() -> None:
    eps = [
        _ep(f"C{i}", EntrypointKind.HTTP_ENDPOINT, f"m{i}") for i in range(8)
    ]
    http = derive_static_features(eps)[0]
    assert "+3 more" in http.description
