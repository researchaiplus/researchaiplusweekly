"""Configuration helpers loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenRouterSettings(BaseSettings):
    """Settings for interacting with the OpenRouter API."""

    base_url: AnyHttpUrl = Field(
        default="https://openrouter.ai/api/v1",
        alias="BASE_URL",
        description="OpenRouter API endpoint.",
    )
    api_key: str = Field(default="", description="API key used for OpenRouter authentication.")
    model: str = Field(
        default="anthropic/claude-3.5-sonnet",
        alias="MODEL",
        description="Default LLM model identifier to use.",
    )
    timeout_seconds: float = Field(default=30.0, alias="TIMEOUT", ge=1.0)

    model_config = SettingsConfigDict(env_file=".env", env_prefix="OPENROUTER_", extra="ignore", env_file_encoding="utf-8")


class JinaReaderSettings(BaseSettings):
    """Settings for Jina Reader content retrieval."""

    base_url: AnyHttpUrl = Field(
        default="https://r.jina.ai", alias="BASE_URL", description="Jina Reader base URL."
    )
    api_key: str = Field(default="", alias="API_KEY", description="Jina Reader API token.")
    timeout_seconds: float = Field(default=20.0, alias="TIMEOUT", ge=1.0)
    max_retries: int = Field(default=3, alias="MAX_RETRIES", ge=0)

    model_config = SettingsConfigDict(env_file=".env", env_prefix="JINA_READER_", extra="ignore", env_file_encoding="utf-8")


class NewsletterSettings(BaseSettings):
    """General workflow configuration."""

    output_dir: Path = Field(default=Path("./output"), alias="OUTPUT_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEWSLETTER_", extra="ignore", env_file_encoding="utf-8")


class AppSettings(BaseModel):
    """Aggregated settings object exposed to the rest of the application."""

    openrouter: OpenRouterSettings
    jina: JinaReaderSettings
    newsletter: NewsletterSettings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Load and cache application settings."""

    return AppSettings(
        openrouter=OpenRouterSettings(), jina=JinaReaderSettings(), newsletter=NewsletterSettings()
    )


__all__ = [
    "AppSettings",
    "JinaReaderSettings",
    "NewsletterSettings",
    "OpenRouterSettings",
    "get_settings",
]
