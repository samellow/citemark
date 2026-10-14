"""Audit mode on a real database server (T17): each audit is its own migrated database and
folder, and a purge leaves nothing of either behind (QA plan promise 20).

These make and drop real databases on DATABASE_URL's server, each with a name of its own, and
drop whatever a failed test left.
"""

import asyncio
import datetime as dt
import uuid

import pytest
from scripted_run import frozen_set
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from typer.testing import CliRunner
from zulip_subset import add_zulip

from citemark import audit
from citemark.audit import AuditError
from citemark.cli import app
from citemark.db import migrate
from citemark.db.session import make_engine, make_sessionmaker
from citemark.evals import runner
from citemark.report import numbers

HEAD = migrate.ScriptDirectory.from_config(migrate.config()).get_current_head()
TABLES = ("source", "document", "chunk", "test_set", "test_question")  # where an audit's rows would go


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client's name no other test uses, with audits made under the test's own folder."""
    monkeypatch.setattr(audit, "FOLDERS", tmp_path / "audits")
    name = f"Test Client {uuid.uuid4().hex[:8]}"
    yield name
    audit._drop(audit.audit(name))


async def _scalar(url: str | None, sql: str):
    engine = make_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return await connection.scalar(text(sql))
    finally:
        await engine.dispose()


def rows(url: str | None = None) -> dict[str, int]:
    """Every row a help center or a test set puts in a database, by table."""
    return {table: asyncio.run(_scalar(url, f"SELECT count(*) FROM {table}")) for table in TABLES}


async def _fill(url: str, folder) -> None:
    """Seven articles, as an audit's crawl leaves them, and five questions in two frozen sets, as
    a client's set and its next version share most of theirs. The note counts each question once."""
    engine = make_engine(url, poolclass=NullPool)
    try:
        async with make_sessionmaker(engine)() as session:
            await add_zulip(session)
            await runner.load_test_set(session, frozen_set(folder))
            await runner.load_test_set(session, frozen_set(folder, name="runner-test-next"))
            await session.commit()
    finally:
        await engine.dispose()


def test_a_new_audit_is_its_own_database_migrated_to_the_newest_schema_with_its_own_folder(client):
    found = audit.audit(client)
    assert audit.new(found) == HEAD
    assert asyncio.run(_scalar(audit.database_url(found), "SELECT version_num FROM alembic_version")) == HEAD
    assert found.folder.is_dir() and audit._exists(found)
    with pytest.raises(AuditError, match=f"An audit called {found.name} exists already: the database"):
        audit.new(found)


def test_a_purge_leaves_no_database_no_files_and_no_rows(client):
    """Promise 20. The audit's rows were only ever in its own database, so the one the tests use
    has the same rows before the audit and after its purge."""
    found = audit.audit(client)
    before = rows()
    audit.new(found)
    asyncio.run(_fill(audit.database_url(found), found.folder))
    (found.folder / "questions.csv").write_text("How do I export my data?\n", encoding="utf-8")
    (found.folder / "report").mkdir()
    (found.folder / "report" / "acme.html").write_text("<!doctype html>", encoding="utf-8")
    assert rows(audit.database_url(found))["document"] == 7

    held = audit.contents(found)
    assert (held.database, held.folder, held.articles, held.questions) == (True, True, 7, 5)
    audit.purge(found, held)
    assert not audit._exists(found) and not found.folder.exists()
    assert rows() == before
    assert "the audit database (7 articles, 5 questions) and the local files" in audit.note(held, dt.date.today())


def test_a_database_that_fails_to_migrate_is_dropped_so_its_name_stays_free(client, monkeypatch):
    found = audit.audit(client)

    def failing(**_):
        raise RuntimeError("a migration's own failure")

    monkeypatch.setattr(audit.migrate, "upgrade", failing)
    with pytest.raises(RuntimeError, match="a migration's own failure"):
        audit.new(found)
    assert not audit._exists(found) and not found.folder.exists()


def test_a_folder_that_isnt_the_audits_own_is_never_deleted(client, tmp_path):
    found = audit.audit(client)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("not the audit's", encoding="utf-8")
    found.folder.parent.mkdir(parents=True)
    found.folder.symlink_to(elsewhere)
    with pytest.raises(AuditError, match="isn't a folder an audit made"):
        audit.contents(found)
    assert (elsewhere / "keep.txt").exists()


def test_the_commands_make_an_audit_then_purge_it_and_print_the_note(client):
    found = audit.audit(client)
    made = CliRunner().invoke(app, ["audit", "new", client])
    assert made.exit_code == 0, made.output
    assert f"the database {found.database}" in made.output and "export DATABASE_URL=postgresql://" in made.output

    kept = CliRunner().invoke(app, ["audit", "purge", client], input="n\n")
    assert kept.exit_code == 0 and audit._exists(found) and found.folder.is_dir()  # asked, and nothing deleted

    purged = CliRunner().invoke(app, ["audit", "purge", client, "--yes"])
    assert purged.exit_code == 0, purged.output
    assert f"Deleted the database {found.database} (0 articles, 0 questions) and the folder" in purged.output
    assert f"On {numbers.date(dt.date.today())}, I deleted every copy" in purged.output
    assert not audit._exists(found) and not found.folder.exists()

    again = CliRunner().invoke(app, ["audit", "purge", client, "--yes"])
    assert again.exit_code == 1 and f"There's no audit called {found.name}" in again.output
