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
    budget_per_task_usd: float = 5.0


class GitSettings(BaseModel):
    enabled: bool = True


class SandboxSettings(BaseModel):
    enabled: bool = True
    driver: str = "docker"


class ReviewSettings(BaseModel):
    require_human_approval: bool = True


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

    ai: AISettings = Field(default_factory=AISettings)
    git: GitSettings = Field(default_factory=GitSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)
    review: ReviewSettings = Field(default_factory=ReviewSettings)


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
