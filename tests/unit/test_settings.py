"""Settings from the environment (PRD 5.13)."""

import pytest
from pydantic import ValidationError

from citemark.settings import Settings


@pytest.mark.parametrize(
    "given",
    ["postgres://u:p@host:5432/db", "postgresql://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"],
)
def test_the_database_url_names_the_async_driver(monkeypatch, given):
    monkeypatch.setenv("DATABASE_URL", given)
    assert Settings(_env_file=None).database_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_the_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_keys_are_kept_out_of_printed_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    assert "not-a-real-key" not in repr(Settings(_env_file=None))
