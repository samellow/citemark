"""Indexing a source (PRD 5.1): crawl it, keep what changed, embed the new passages, and save.

Each document is saved in its own transaction: its new passages, its old ones retired, and its
new content hash, together. So a re-index that stops partway leaves every document either
updated or untouched, with its old passages still searchable (QA promise 15), and running it
again picks up where it stopped, since a saved document's hash now matches. An unchanged
document costs no embedding call.

A page counts as removed when it's gone (404 or 410), or when a crawl that reached every page
it found didn't find it (`Crawl.complete`). So a site that's down for an hour doesn't empty
the bot.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Protocol

import anyio
import httpx2
import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from citemark.db.models import Chunk, Document, Source
from citemark.embed import Embedder
from citemark.ingest import IngestError
from citemark.ingest.chunk import Passage, chunk_document, estimate_tokens
from citemark.ingest.crawl import Crawl, Failed, Page, SourceSpec
from citemark.ingest.extract import Extracted, ExtractError
from citemark.ingest.fetch import MIN_INTERVAL, Fetcher, Sleep
from citemark.ingest.files import extract_file

if TYPE_CHECKING:
    from citemark.jobs.worker import JobContext

log = structlog.get_logger()

# Part of every content hash. Raise it when extraction or chunking changes, so the next
# re-index rebuilds every document's passages instead of keeping ones made the old way.
INGEST_VERSION = 1
UPLOAD_PREFIX = "upload:"  # an uploaded file's address: there's no page to link to


class Progress(Protocol):
    async def __call__(
        self, done: int, total: int | None = None, label: str | None = None, *, session: AsyncSession | None = None
    ) -> None: ...


async def no_progress(
    done: int, total: int | None = None, label: str | None = None, *, session: AsyncSession | None = None
) -> None:
    return None


def content_hash(extracted: Extracted) -> str:
    payload = [INGEST_VERSION, extracted.title, extracted.markdown, list(extracted.anchors)]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass
class IndexResult:
    found: int = 0  # pages or files looked at
    unchanged: int = 0
    added: int = 0
    updated: int = 0
    removed: int = 0
    failed: int = 0
    passages: int = 0  # new passages saved
    embed_calls: int = 0
    embed_tokens: int = 0
    complete: bool = False  # the crawl reached every page it found, so removals were applied
    problems: list[str] = field(default_factory=list)  # why each failed page or file failed


@dataclass(frozen=True)
class _Known:
    id: uuid.UUID
    content_hash: str | None
    status: str


@dataclass(frozen=True)
class _Changed:
    url: str
    title: str
    digest: str
    last_modified: dt.datetime | None
    passages: list[Passage]


async def _known(session: AsyncSession, source_id: uuid.UUID) -> dict[str, _Known]:
    rows = await session.execute(
        select(Document.url, Document.id, Document.content_hash, Document.status).where(Document.source_id == source_id)
    )
    return {url: _Known(id, digest, status) for url, id, digest, status in rows}


async def index_source(
    source_id: uuid.UUID,
    *,
    sessions: async_sessionmaker[AsyncSession],
    http: httpx2.AsyncClient,
    embedder: Embedder,
    agent: str,
    progress: Progress = no_progress,
    interval: float = MIN_INTERVAL,
    sleep: Sleep = anyio.sleep,
) -> IndexResult:
    """Crawl a sitemap, start-page or single-address source, and bring its passages up to date."""
    async with sessions() as session:
        source = await session.get(Source, source_id)
        if source is None:
            raise IngestError(f"There's no source {source_id}.")
        if source.kind == "upload":
            raise IngestError("An upload source is indexed as its files are uploaded, so there's nothing to crawl.")
        spec = SourceSpec(
            source.kind, source.url or "", source.path_prefix, source.include, source.exclude, source.content_selector
        )
        known = await _known(session, source_id)

    crawl = Crawl(spec, Fetcher(http, spec.scope(), agent=agent, interval=interval, sleep=sleep))
    items: list[Page | Failed] = []
    await progress(0, None, "articles")
    async for item in crawl.pages():
        items.append(item)
        await progress(crawl.done, crawl.found, "articles")
    await progress(crawl.done, crawl.found, "articles")
    result = IndexResult(found=crawl.found, complete=crawl.complete)
    await _apply(source_id, items, known, sessions=sessions, embedder=embedder, progress=progress, result=result)
    log.info("source_indexed", source_id=str(source_id), **asdict(result))
    return result


async def index_files(
    source_id: uuid.UUID,
    files: Sequence[tuple[str, bytes]],
    *,
    sessions: async_sessionmaker[AsyncSession],
    embedder: Embedder,
    progress: Progress = no_progress,
) -> IndexResult:
    """Add uploaded files to an upload source. A file uploaded again under the same name
    replaces the earlier one's passages; the source's other files are left as they are."""
    async with sessions() as session:
        source = await session.get(Source, source_id)
        if source is None or source.kind != "upload":
            raise IngestError(f"There's no upload source {source_id}.")
        known = await _known(session, source_id)
    items: list[Page | Failed] = []
    for name, data in files:
        url = UPLOAD_PREFIX + name
        try:
            items.append(Page(url, extract_file(name, data)))
        except ExtractError as exc:
            items.append(Failed(url, str(exc)))
    result = IndexResult(found=len(files))
    await _apply(source_id, items, known, sessions=sessions, embedder=embedder, progress=progress, result=result)
    log.info("files_indexed", source_id=str(source_id), **asdict(result))
    return result


async def _apply(
    source_id: uuid.UUID,
    items: list[Page | Failed],
    known: dict[str, _Known],
    *,
    sessions: async_sessionmaker[AsyncSession],
    embedder: Embedder,
    progress: Progress,
    result: IndexResult,
) -> None:
    changed: list[_Changed] = []
    failures: list[Failed] = []
    unchanged: list[uuid.UUID] = []
    for item in items:
        if isinstance(item, Failed):
            failures.append(item)
            continue
        digest = content_hash(item.extracted)
        old = known.get(item.url)
        if old is not None and old.status == "active" and old.content_hash == digest:
            unchanged.append(old.id)
            continue
        title, markdown, anchors = item.extracted.title, item.extracted.markdown, item.extracted.anchors
        passages = chunk_document(title, markdown, item.url, anchors)
        if passages:
            changed.append(_Changed(item.url, title, digest, item.last_modified, passages))
        else:
            failures.append(Failed(item.url, "No text was found on this page."))
    result.unchanged = len(unchanged)

    total = sum(len(doc.passages) for doc in changed)
    done = 0
    await progress(0, total, "passages")
    for group in _groups(changed, embedder):
        vectors = await _embed(embedder, [passage.text for doc in group for passage in doc.passages], result)
        for doc in group:
            mine, vectors = vectors[: len(doc.passages)], vectors[len(doc.passages) :]
            async with sessions.begin() as session:
                saved = await _save(session, source_id, doc, mine)
                done += len(doc.passages)
                await progress(done, total, "passages", session=session)
            if saved is not None:
                result.passages += len(doc.passages)
                result.added += saved == "added"
                result.updated += saved == "updated"

    accounted_for = {item.url for item in items}  # kept, failed, or gone and removed just below
    async with sessions.begin() as session:
        if unchanged:
            await session.execute(
                update(Document).where(Document.id.in_(unchanged)).values(fetched_at=func.now(), error=None)
            )
        for failure in failures:
            old = known.get(failure.url)
            if failure.gone:
                if old is not None and old.status != "removed":
                    await _remove(session, old.id)
                    result.removed += 1
                continue  # a link to a page that never existed here: nothing to record
            result.failed += 1
            result.problems.append(failure.error)
            # A page that fails keeps whatever passages it had; it only gains the error
            await session.execute(
                insert(Document)
                .values(source_id=source_id, url=failure.url, status="failed", error=failure.error)
                .on_conflict_do_update(index_elements=["source_id", "url"], set_={"error": failure.error})
            )
        if result.complete:
            for url, old in known.items():
                if old.status != "removed" and url not in accounted_for:
                    await _remove(session, old.id)
                    result.removed += 1
        await session.execute(update(Source).where(Source.id == source_id).values(last_crawled_at=func.now()))


def _groups(docs: list[_Changed], embedder: Embedder) -> Iterator[list[_Changed]]:
    """Whole documents in groups that fit one embedding call, so each document is saved as soon
    as its call returns. A document too big for one call is a group of its own."""
    group: list[_Changed] = []
    count = tokens = 0
    for doc in docs:
        size = sum(passage.token_count for passage in doc.passages)
        if group and (count + len(doc.passages) > embedder.max_batch or tokens + size > embedder.max_batch_tokens):
            yield group
            group, count, tokens = [], 0, 0
        group.append(doc)
        count += len(doc.passages)
        tokens += size
    if group:
        yield group


def _batches(texts: list[str], embedder: Embedder) -> Iterator[list[str]]:
    batch: list[str] = []
    tokens = 0
    for text in texts:
        size = estimate_tokens(text)
        if batch and (len(batch) == embedder.max_batch or tokens + size > embedder.max_batch_tokens):
            yield batch
            batch, tokens = [], 0
        batch.append(text)
        tokens += size
    if batch:
        yield batch


async def _embed(embedder: Embedder, texts: list[str], result: IndexResult) -> list[list[float]]:
    vectors: list[list[float]] = []
    for batch in _batches(texts, embedder):
        embedded = await embedder.embed_documents(batch)
        vectors += embedded.vectors
        result.embed_calls += 1
        result.embed_tokens += embedded.tokens
    return vectors


async def _save(session: AsyncSession, source_id: uuid.UUID, doc: _Changed, vectors: list[list[float]]) -> str | None:
    """Save a document's new passages and retire its old ones. Returns "added" or "updated",
    or None when another run already saved this same content."""
    added = await session.scalar(
        insert(Document)
        .values(source_id=source_id, url=doc.url, status="failed")  # a placeholder, completed below
        .on_conflict_do_nothing(index_elements=["source_id", "url"])
        .returning(Document.id)
    )
    row = await session.scalar(
        select(Document).where(Document.source_id == source_id, Document.url == doc.url).with_for_update()
    )
    assert row is not None
    if added is None and row.status == "active" and row.content_hash == doc.digest:
        return None
    await _retire(session, row.id)
    session.add_all(
        Chunk(
            document_id=row.id,
            position=passage.position,
            heading_path=passage.heading_path,
            anchor_url=passage.anchor_url,
            blocks=list(passage.blocks),
            text=passage.text,
            token_count=passage.token_count,
            embedding=vector,
        )
        for passage, vector in zip(doc.passages, vectors, strict=True)
    )
    row.title, row.content_hash, row.status, row.error = doc.title, doc.digest, "active", None
    row.last_modified = doc.last_modified
    row.fetched_at = func.now()
    await session.flush()
    return "added" if added is not None else "updated"


async def _retire(session: AsyncSession, document_id: uuid.UUID) -> None:
    """Retire a document's live passages: the one change the database allows on a chunk."""
    await session.execute(
        update(Chunk).where(Chunk.document_id == document_id, Chunk.retired_at.is_(None)).values(retired_at=func.now())
    )


async def _remove(session: AsyncSession, document_id: uuid.UUID) -> None:
    await _retire(session, document_id)
    await session.execute(
        update(Document).where(Document.id == document_id).values(status="removed", error=None, fetched_at=func.now())
    )


async def ingest(job: JobContext) -> None:
    """The `ingest` job: index the source in `payload["source_id"]`, with Voyage embeddings."""
    from citemark.embed.voyage import VoyageEmbedder
    from citemark.ingest.fetch import user_agent
    from citemark.ingest.guard import PublicOnlyTransport
    from citemark.settings import get_settings

    settings = get_settings()
    if settings.voyage_api_key is None:
        raise IngestError("VOYAGE_API_KEY isn't set, so passages can't be embedded.")
    async with httpx2.AsyncClient(transport=PublicOnlyTransport()) as web, httpx2.AsyncClient() as api:
        await index_source(
            uuid.UUID(job.payload["source_id"]),
            sessions=job.sessions,
            http=web,
            embedder=VoyageEmbedder(settings.voyage_api_key.get_secret_value(), api),
            agent=user_agent(settings.public_base_url),
            progress=job.progress,
        )
