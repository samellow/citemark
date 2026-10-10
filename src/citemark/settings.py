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
    # The visitor's address, as the host's proxy passes it: CF-Connecting-IP on Render. Unset, the
    # connection's own address is used, which behind a proxy is the proxy's (T16, T18).
    client_ip_header: str | None = None
    # The public demo page (PRD 8.2), served at / when demo_company is set
    demo_company: str | None = None  # the product the help center is for, as the bot names it
    demo_model: str = "claude-haiku-5-5"  # until the test picks the cheapest that met every target
    demo_audit_url: str | None = None  # the audit listing on Upwork, or the profile until it's approved
    demo_audit_price: str | None = None  # as the listing shows it, such as $300
    demo_results: str | None = None  # the published results file, once the decision runs exist (T20)

    @field_validator(
        "abuse_database_url",
        "builder_name",
        "client_ip_header",
        "demo_company",
        "demo_audit_url",
        "demo_audit_price",
        "demo_results",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value: str | None) -> str | None:
        """A line copied from .env.example with nothing after the = is a setting not given."""
        return (value.strip() or None) if isinstance(value, str) else value

    @field_validator("demo_audit_url")
    @classmethod
    def _https(cls, url: str | None) -> str | None:
        """The audit button leaves the page for this address, so only a secure web page will do."""
        if url is not None and not url.startswith("https://"):
            raise ValueError("DEMO_AUDIT_URL must be an https:// address, the audit listing on Upwork.")
        return url

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
