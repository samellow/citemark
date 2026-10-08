"""Settings from environment variables (PRD 5.13), or from a local `.env` file.

Only the database is needed to start. The API keys are checked where they're
used, so commands that don't call a model work without them.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    anthropic_api_key: SecretStr | None = None
    voyage_api_key: SecretStr | None = None
    secret_key: SecretStr | None = None
    public_base_url: str | None = None
    # Handoff (Phase 2): Zendesk, or a webhook
    zendesk_subdomain: str | None = None
    zendesk_email: str | None = None
    zendesk_api_token: SecretStr | None = None
    webhook_url: str | None = None
    webhook_secret: SecretStr | None = None
    admin_reset_token: SecretStr | None = None  # set only during a password recovery (PRD 5.9)

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, url: str) -> str:
        """Hosts give postgres:// or postgresql://; the async engine needs the driver named."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url.removeprefix(prefix)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
