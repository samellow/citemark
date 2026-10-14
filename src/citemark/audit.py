"""Audit mode (PRD 2 and 5.11): each client's audit gets its own local database and its own
folder, and a purge leaves nothing of either (QA plan promise 20).

`citemark audit new` makes the database, migrated to the newest schema, on the server
DATABASE_URL names, and the folder under `audits/`, which git ignores. Every other command reaches
the audit's database through DATABASE_URL, as it reaches any other. `citemark audit purge` counts
what the database holds, drops it, deletes the folder, checks both are gone, and only then gives
the deletion note (content spec 8.3), since the note tells the client nothing was kept.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import URL, make_url, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.pool import NullPool

from citemark import strings
from citemark.db import migrate
from citemark.db.session import make_engine
from citemark.report import numbers
from citemark.settings import get_settings

KIT = Path(__file__).resolve().parents[2]
FOLDERS = KIT / "audits"
PREFIX = "citemark_audit_"
MAX_NAME = 63 - len(PREFIX)  # Postgres keeps the first 63 bytes of a database's name
SERVER = "postgres"  # the server's own database, which audits are made and dropped from


class AuditError(Exception):
    """An audit can't be made or purged. The message is one plain sentence."""


@dataclass(frozen=True)
class Audit:
    name: str  # the client's name in lowercase letters, digits and underscores: acme_chat
    database: str  # citemark_audit_acme_chat
    folder: Path


@dataclass(frozen=True)
class Contents:
    """What a purge deletes, counted before it does."""

    database: bool  # whether the audit's database exists
    folder: bool
    articles: int
    questions: int


def audit(client: str, folders: Path | None = None) -> Audit:
    """The audit for a client's name. Only lowercase letters, digits and underscores are kept, so
    the name is safe in a database's name and a folder's, and can't reach outside `audits/`."""
    name = re.sub(r"[^a-z0-9]+", "_", client.lower()).strip("_")
    if not name:
        raise AuditError(f"{client!r} has no letters or digits to name an audit by.")
    if len(name) > MAX_NAME:
        raise AuditError(
            f"{client!r} makes a name of {len(name)} characters, over the {MAX_NAME} a database's name "
            "allows. Use a shorter one."
        )
    return Audit(name, PREFIX + name, (folders or FOLDERS) / name)


def _url(database: str) -> URL:
    return make_url(get_settings().database_url).set(database=database)


def database_url(found: Audit) -> str:
    """The audit's database, on the server DATABASE_URL names."""
    return _url(found.database).render_as_string(hide_password=False)


def shown_url(found: Audit) -> str:
    """The audit's DATABASE_URL to export, as `.env` would hold it, with any password hidden."""
    return _url(found.database).set(drivername="postgresql").render_as_string(hide_password=True)


async def _on(url: str, work: Any) -> Any:
    """`work(connection)` outside a transaction, as CREATE and DROP DATABASE need. A server that
    can't be reached, or refuses, is one plain sentence."""
    engine = make_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            return await work(connection)
    except OSError as exc:
        where = make_url(url)
        raise AuditError(
            f"The database server at {where.host}:{where.port} can't be reached ({type(exc).__name__}). "
            "Is it running? docker compose up -d db starts the local one."
        ) from exc
    except DBAPIError as exc:
        raise AuditError(f"The database server refused it: {exc.orig}") from exc
    finally:
        await engine.dispose()


def _server(sql: str, **params: str) -> Any:
    """One statement on the server's own database, and its value if it has one."""

    async def run(connection: AsyncConnection) -> Any:
        result = await connection.execute(text(sql), params)
        return result.scalar() if result.returns_rows else None

    return asyncio.run(_on(_url(SERVER).render_as_string(hide_password=False), run))


def _exists(found: Audit) -> bool:
    return bool(_server("SELECT 1 FROM pg_database WHERE datname = :name", name=found.database))


def _drop(found: Audit) -> None:
    # The name is lowercase letters, digits and underscores (`audit`), so quoting it is enough
    _server(f'DROP DATABASE IF EXISTS "{found.database}" WITH (FORCE)')


def _has_folder(found: Audit) -> bool:
    return found.folder.exists() or found.folder.is_symlink()


def new(found: Audit) -> str:
    """Make the audit's database, migrated, and its folder. Returns the schema's revision."""
    if _exists(found) or _has_folder(found):
        what = f"the database {found.database}" if _exists(found) else f"the folder {found.folder}"
        raise AuditError(f"An audit called {found.name} exists already: {what}. Purge it first, or use another name.")
    _server(f'CREATE DATABASE "{found.database}"')
    try:
        revision = migrate.upgrade(url=database_url(found))
    except Exception:  # a half-made database would hold the name: drop it, and say why it failed
        _drop(found)
        raise
    found.folder.mkdir(parents=True)
    return revision


async def _count(connection: AsyncConnection) -> tuple[int, int]:
    """The articles the database holds, and its distinct test questions. A table that was never
    made holds nothing."""
    counts = []
    for table, counted in (("document", "*"), ("test_question", "DISTINCT question")):
        made = await connection.scalar(text("SELECT to_regclass(:table)"), {"table": table})
        counts.append(await connection.scalar(text(f"SELECT count({counted}) FROM {table}")) if made else 0)
    return counts[0], counts[1]


def contents(found: Audit) -> Contents:
    """What purging the audit would delete. Refuses an audit with neither a database nor a
    folder, and a folder that's a link or a file, which this audit can't have made."""
    database, folder = _exists(found), _has_folder(found)
    if not database and not folder:
        raise AuditError(
            f"There's no audit called {found.name}: no database {found.database} and no folder {found.folder}."
        )
    if folder and (found.folder.is_symlink() or not found.folder.is_dir()):
        raise AuditError(f"{found.folder} isn't a folder an audit made, so it isn't deleted. Remove it yourself.")
    articles, questions = asyncio.run(_on(database_url(found), _count)) if database else (0, 0)
    return Contents(database, folder, articles, questions)


def purge(found: Audit, held: Contents) -> None:
    """Drop the database and delete the folder, then check both are gone."""
    if held.database:
        _drop(found)
    if held.folder:
        try:
            shutil.rmtree(found.folder)
        except OSError as exc:
            raise AuditError(f"The folder {found.folder} couldn't be deleted ({exc.strerror}).") from exc
    if _exists(found):
        raise AuditError(f"The database {found.database} is still there after it was dropped.")
    if _has_folder(found):
        raise AuditError(f"The folder {found.folder} is still there after it was deleted.")


def note(held: Contents, today: dt.date) -> str:
    """The deletion note to send the client (content spec 8.3), with what the database held."""
    return strings.text(
        "outbound",
        "audit.deletion_note",
        date=numbers.date(today),
        doc_count=held.articles,
        question_count=held.questions,
    )
