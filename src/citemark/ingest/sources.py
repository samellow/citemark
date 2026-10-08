"""Sources from the command line (`citemark sources`): add one, list them, index them with the
progress shown as counts, and upload files. The admin page does the same in Phase 2."""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx2
from cssselect import SelectorError
from lxml.cssselect import CSSSelector
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from citemark.db.models import Chunk, Document, Job, Source
from citemark.db.session import make_sessionmaker
from citemark.ingest import IngestError
from citemark.ingest.crawl import SourceSpec
from citemark.ingest.pipeline import IndexResult, index_files
from citemark.jobs.queue import enqueue
from citemark.jobs.worker import Worker, handlers

CRAWLED = ("sitemap", "start_page", "url")
VERBS = {"articles": "Fetched", "passages": "Embedded"}
POLL_SECONDS = 1.0


async def add_source(
    sessions: async_sessionmaker[AsyncSession],
    kind: str,
    url: str,
    *,
    path_prefix: str | None = None,
    content_selector: str | None = None,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
) -> Source:
    spec = SourceSpec(kind, url, path_prefix, list(include), list(exclude), content_selector)
    spec.scope()  # an address that can't be crawled is refused now, not at the first crawl
    if content_selector:
        try:
            CSSSelector(content_selector)
        except SelectorError as exc:
            raise IngestError(f'"{content_selector}" isn\'t a valid CSS selector.') from exc
    async with sessions.begin() as session:
        source = Source(
            kind=kind,
            url=url,
            path_prefix=path_prefix,
            include=list(include),
            exclude=list(exclude),
            content_selector=content_selector,
        )
        session.add(source)
        await session.flush()
        return source


@dataclass(frozen=True)
class Summary:
    id: uuid.UUID
    kind: str
    url: str | None
    documents: int
    failed: int
    passages: int
    last_crawled_at: dt.datetime | None


async def summaries(sessions: async_sessionmaker[AsyncSession]) -> list[Summary]:
    live = (
        select(Document.source_id, func.count(Chunk.id).label("passages"))
        .join(Chunk, Chunk.document_id == Document.id)
        .where(Chunk.retired_at.is_(None))
        .group_by(Document.source_id)
        .subquery()
    )
    counts = (
        select(
            Document.source_id,
            func.count().filter(Document.status == "active").label("documents"),
            func.count().filter(Document.status == "failed").label("failed"),
        )
        .group_by(Document.source_id)
        .subquery()
    )
    query = (
        select(
            Source,
            func.coalesce(counts.c.documents, 0),
            func.coalesce(counts.c.failed, 0),
            func.coalesce(live.c.passages, 0),
        )
        .outerjoin(counts, counts.c.source_id == Source.id)
        .outerjoin(live, live.c.source_id == Source.id)
        .order_by(case((Source.kind == "upload", 1), else_=0), Source.created_at)
    )
    async with sessions() as session:
        rows = (await session.execute(query)).all()
    return [
        Summary(source.id, source.kind, source.url, documents, failed, passages, source.last_crawled_at)
        for source, documents, failed, passages in rows
    ]


def describe(done: int, total: int | None, label: str) -> str:
    """ "Fetched 120 of 257 articles", "Embedded 1,180 of 1,906 passages" (PRD 5.1)."""
    counted = f"{done:,} of {total:,}" if total is not None else f"{done:,}"
    return f"{VERBS.get(label, 'Done')} {counted} {label}"


async def index_and_show(engine: AsyncEngine, source_id: uuid.UUID | None, echo: Callable[[str], None]) -> list[str]:
    """Queue an `ingest` job for the source (or every crawled source), run the worker here until
    nothing is waiting, and show each job's progress as it changes. Returns the jobs' errors."""
    sessions = make_sessionmaker(engine)
    async with sessions.begin() as session:
        if source_id is None:
            ids = list(await session.scalars(select(Source.id).where(Source.kind.in_(CRAWLED))))
        else:
            source = await session.get(Source, source_id)
            if source is None or source.kind not in CRAWLED:
                raise IngestError(f"There's no crawled source {source_id}. citemark sources list shows them.")
            ids = [source_id]
        if not ids:
            raise IngestError("There are no sources to index yet. Add one with: citemark sources add")
        jobs = [await enqueue(session, "ingest", {"source_id": str(id)}) for id in ids]

    worker = asyncio.create_task(Worker(engine, handlers()).run_until_idle())
    shown: dict[uuid.UUID, str] = {}
    while True:
        finished = worker.done()
        async with sessions() as session:
            rows = await session.execute(
                select(Job.id, Job.status, Job.progress_done, Job.progress_total, Job.progress_label, Job.error).where(
                    Job.id.in_(jobs)
                )
            )
            states = rows.all()
        for job_id, _, done, total, label, _ in states:
            line = describe(done, total, label) if label else ""
            if line and shown.get(job_id) != line:
                echo(line)
                shown[job_id] = line
        if finished:
            break
        await asyncio.sleep(POLL_SECONDS)
    await worker  # raises if the worker itself failed
    return [error.split(": ", 1)[-1] for _, status, *_, error in states if status == "failed" and error]


async def upload_files(
    sessions: async_sessionmaker[AsyncSession], paths: Sequence[Path], source_id: uuid.UUID | None, voyage_key: str
) -> IndexResult:
    """Index files into an upload source: the one given, or this deployment's first, made if needed."""
    from citemark.embed.voyage import VoyageEmbedder

    async with sessions.begin() as session:
        if source_id is None:
            source_id = await session.scalar(
                select(Source.id).where(Source.kind == "upload").order_by(Source.created_at).limit(1)
            )
            if source_id is None:
                source = Source(kind="upload")
                session.add(source)
                await session.flush()
                source_id = source.id
    files = [(path.name, path.read_bytes()) for path in paths]
    async with httpx2.AsyncClient() as api:
        return await index_files(source_id, files, sessions=sessions, embedder=VoyageEmbedder(voyage_key, api))
