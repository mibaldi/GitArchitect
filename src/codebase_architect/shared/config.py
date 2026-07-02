"""Application configuration (12-factor, env + optional .env).

Settings model the *capabilities* of a deployment. Optional capabilities (git,
sandbox, hosting plugins) default to a conservative state so the core can run in
minimal environments, as required by the SDD.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AIProviderSettings(BaseModel):
    """Configuration for a single AI provider adapter."""

    model: str | None = None
    api_key_env: str | None = None
    endpoint: str | None = None


class AISettings(BaseModel):
    default_provider: str = "claude"
    budget_per_scan_usd: float = 2.0
    max_tokens: int = 4096
    cache_enabled: bool = True


class CliRunnerSettings(BaseModel):
    """Remote CLI runner (an already-authenticated Claude/Codex CLI over HTTP).

    No provider API keys and no local model — GitArchitect POSTs prompts to a
    runner (e.g. a Mac on your tailnet) that runs the CLI and returns its text.
    """

    base_url: str | None = None  # e.g. http://100.x.x.x:8787
    agent: str = "claude"  # "claude" | "codex"
    timeout_seconds: int = 600
    shared_secret: str | None = None
    working_dir: str | None = None  # path on the runner host (within its allowlist)


class GitSettings(BaseModel):
    enabled: bool = True


class ScanSettings(BaseModel):
    static_only: bool = False
    default_out: str = "./docs-output"
    #: Language for generated documentation ("en" or "es"); unsupported codes fall back to "en".
    language: str = "en"


class Settings(BaseSettings):
    """Root settings object.

    Environment variables use the ``CA_`` prefix and ``__`` as a nesting
    delimiter, e.g. ``CA_AI__DEFAULT_PROVIDER=openai``.
    """

    model_config = SettingsConfigDict(
        env_prefix="CA_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    log_json: bool = False

    data_dir: str = "./data"
    workspaces_dir: str = "./workspaces"

    database_url: str | None = None
    redis_url: str | None = None

    scan: ScanSettings = Field(default_factory=ScanSettings)
    ai: AISettings = Field(default_factory=AISettings)
    cli_runner: CliRunnerSettings = Field(default_factory=CliRunnerSettings)
    git: GitSettings = Field(default_factory=GitSettings)


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
