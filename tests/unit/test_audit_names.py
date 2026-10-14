"""Audit mode's names and its deletion note (T17, PRD 5.11). Making and purging an audit's
database is in tests/integration/test_audit.py."""

import datetime as dt

import pytest

from citemark import audit
from citemark.audit import AuditError, Contents
from citemark.settings import get_settings


@pytest.mark.parametrize(
    ("client", "name"),
    [
        ("Acme Chat", "acme_chat"),
        ("  ACME -- Chat!! ", "acme_chat"),
        ("Zoë's Café 2", "zo_s_caf_2"),
        ("../../etc", "etc"),  # never a folder outside audits/
    ],
)
def test_a_clients_name_becomes_lowercase_letters_digits_and_underscores(client, name, tmp_path):
    found = audit.audit(client, tmp_path)
    assert (found.name, found.database, found.folder) == (name, f"citemark_audit_{name}", tmp_path / name)


def test_a_name_with_nothing_to_keep_or_too_long_for_postgres_is_refused(tmp_path):
    with pytest.raises(AuditError, match="has no letters or digits"):
        audit.audit("!!!", tmp_path)
    with pytest.raises(AuditError, match="over the 48"):
        audit.audit("a" * 49, tmp_path)
    assert len(audit.audit("a" * 48, tmp_path).database) == 63  # Postgres keeps 63 bytes


def test_the_deletion_note_is_the_content_specs_with_what_the_database_held():
    held = Contents(database=True, folder=True, articles=1_204, questions=1)
    assert audit.note(held, dt.date(2026, 11, 12)) == (
        "On Nov 12, 2026, I deleted every copy of the help-center content and test questions used for your "
        "Citemark accuracy audit: the audit database (1,204 articles, 1 question) and the local files. "
        "Nothing was kept. The report you received is the only remaining copy."
    )


def test_the_database_to_export_is_on_the_same_server_with_its_password_hidden(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://citemark:s3cret@localhost:54320/citemark")
    get_settings.cache_clear()
    try:
        found = audit.audit("Acme Chat")
        shown, real = audit.shown_url(found), audit.database_url(found)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
    assert shown == "postgresql://citemark:***@localhost:54320/citemark_audit_acme_chat"
    assert real == "postgresql+asyncpg://citemark:s3cret@localhost:54320/citemark_audit_acme_chat"
