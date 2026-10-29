"""Typed configuration loaded from environment variables / .env files.

This is the only module allowed to read secrets. Values default to safe local
development settings; secrets (API keys) have no hardcoded defaults.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
ENV_FILES = (ROOT_DIR / ".env", BACKEND_DIR / ".env")
PLACEHOLDER_PREFIXES = ("your-", "replace", "changeme", "example")


class AppSettings(BaseSettings):
    """Non-secret application settings (prefix: CHAOSPILOT_)."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        env_prefix="CHAOSPILOT_",
        extra="ignore",
        case_sensitive=False,
    )

    env: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    db_path: str = "./data/chaospilot.db"
    model_dir: str = "./models"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    collector_enabled: bool = True
    collector_interval_seconds: float = 5.0
    simulation_mode: bool = True
    history_minutes: int = 60
    docker_enabled: bool = False
    docker_network: str = "chaospilot"
    compose_project: str = "chaospilot"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def db_file(self) -> Path:
        return self._resolve(self.db_path)

    @property
    def model_path(self) -> Path:
        return self._resolve(self.model_dir) / "anomaly_detector.pkl"

    def _resolve(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


class LLMSettings(BaseSettings):
    """Provider configuration. The API key is wrapped so it cannot leak via repr."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    provider: Literal["ollama", "openai"] = Field("ollama", validation_alias="LLM_PROVIDER")
    timeout_seconds: float = Field(60.0, validation_alias="LLM_TIMEOUT_SECONDS")
    max_tokens: int = Field(900, validation_alias="LLM_MAX_TOKENS")
    temperature: float = Field(0.2, validation_alias="LLM_TEMPERATURE")
    ollama_base_url: str = Field("http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_model: str = Field("llama3.1", validation_alias="OLLAMA_MODEL")
    openai_base_url: str = Field(
        "https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL"
    )
    openai_model: str = Field("gpt-4o-mini", validation_alias="OPENAI_MODEL")
    openai_api_key: SecretStr | None = Field(None, validation_alias="OPENAI_API_KEY")

    @property
    def api_key(self) -> str | None:
        """Return a usable key, treating obvious placeholders as unset."""
        if self.openai_api_key is None:
            return None
        value = self.openai_api_key.get_secret_value().strip()
        if not value or value.lower().startswith(PLACEHOLDER_PREFIXES):
            return None
        return value

    @property
    def model_label(self) -> str:
        return self.ollama_model if self.provider == "ollama" else self.openai_model


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


@lru_cache(maxsize=1)
def get_llm_settings() -> LLMSettings:
    return LLMSettings()


def clear_settings_cache() -> None:
    """Used by tests that override the environment."""
    get_settings.cache_clear()
    get_llm_settings.cache_clear()
