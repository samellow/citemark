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
    # The abuse set's own database, holding its planted articles (QA plan 4.3). A report reads its gate there.
    abuse_database_url: str | None = None
    builder_name: str | None = None  # the name reports are prepared and signed with (content spec 10)
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

    @field_validator("abuse_database_url", "builder_name", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: str | None) -> str | None:
        """A line copied from .env.example with nothing after the = is a setting not given."""
        return (value.strip() or None) if isinstance(value, str) else value

    @field_validator("database_url", "abuse_database_url")
    @classmethod
    def _async_driver(cls, url: str | None) -> str | None:
        """Hosts give postgres:// or postgresql://; the async engine needs the driver named."""
        if url is None:
            return None
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url.removeprefix(prefix)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
