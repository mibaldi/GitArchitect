"""Unit tests for the shared layer."""

from __future__ import annotations

import logging

import pytest

from codebase_architect.shared import (
    CodebaseArchitectError,
    Settings,
    UnsupportedSourceError,
    configure_logging,
    get_logger,
    new_id,
)
from codebase_architect.shared.config import Settings as DirectSettings


class TestIds:
    def test_new_id_is_unique(self) -> None:
        assert new_id() != new_id()

    def test_new_id_without_prefix_is_bare_hex(self) -> None:
        value = new_id()
        assert "_" not in value
        assert len(value) == 32

    def test_new_id_with_prefix(self) -> None:
        value = new_id("scan")
        assert value.startswith("scan_")
        assert len(value) == len("scan_") + 32


class TestErrors:
    def test_specific_errors_subclass_root(self) -> None:
        assert issubclass(UnsupportedSourceError, CodebaseArchitectError)

    def test_root_is_an_exception(self) -> None:
        with pytest.raises(CodebaseArchitectError):
            raise CodebaseArchitectError("boom")


class TestLogging:
    def test_configure_and_get_logger(self) -> None:
        configure_logging(level="DEBUG", json=True)
        logger = get_logger("test", component="unit")
        # Bound logger exposes the standard methods and does not raise.
        logger.info("hello", extra_field=1)

    def test_get_logger_autoconfigures(self) -> None:
        # Even without an explicit configure call, get_logger must work.
        logger = get_logger()
        logger.debug("noop")


class TestSettings:
    def test_defaults_are_capability_conservative(self) -> None:
        settings = Settings()
        assert settings.environment == "development"
        assert settings.ai.default_provider == "claude"
        assert settings.git.enabled is True
        assert settings.scan.static_only is False

    def test_env_prefix_and_nesting(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CA_ENVIRONMENT", "production")
        monkeypatch.setenv("CA_AI__DEFAULT_PROVIDER", "openai")
        monkeypatch.setenv("CA_GIT__ENABLED", "false")
        settings = DirectSettings(_env_file=None)
        assert settings.environment == "production"
        assert settings.ai.default_provider == "openai"
        assert settings.git.enabled is False

    def test_log_level_maps_to_stdlib(self) -> None:
        settings = Settings()
        assert getattr(logging, settings.log_level) == logging.INFO
