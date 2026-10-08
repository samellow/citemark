"""Indexing a source (PRD 5.1; QA promises 14 and 15): the Zulip crawl, re-indexing, removals,
failures and uploads, against the database."""

import json
import uuid
from pathlib import Path

import httpx2
import pytest
from sqlalchemy import func, select

from citemark.db.models import Chunk, Document, Source
from citemark.embed import EmbedError
from citemark.evals import testset
from citemark.evals.dbcheck import check_sources_in_db
from citemark.ingest.guard import BlockedAddress, PublicOnlyTransport
from citemark.ingest.pipeline import index_files, index_source
from citemark.testing.fakes import FakeEmbedder

ROOT = Path(__file__).parents[2]
ZULIP = ROOT / "fixtures" / "zulip"
AGENT = "CitemarkBot (+test)"
SITE = "https://docs.example.com"
HTML = {"content-type": "text/html; charset=utf-8"}


async def no_wait(seconds: float) -> None:
    pass


async def add_source(sessions, **fields) -> uuid.UUID:
    async with sessions.begin() as session:
        source = Source(**fields)
        session.add(source)
        await session.flush()
        return source.id


async def index(sessions, source_id, http, embedder=None, **kwargs):
    embedder = embedder or FakeEmbedder()
    return await index_source(
        source_id, sessions=sessions, http=http, embedder=embedder, agent=AGENT, interval=0, sleep=no_wait, **kwargs
    )


async def live(sessions, source_id) -> dict[str, list[str]]:
    """Each document's live passages, in order."""
    async with sessions() as session:
        rows = await session.execute(
            select(Document.url, Chunk.text)
            .join(Chunk, Chunk.document_id == Document.id)
            .where(Document.source_id == source_id, Chunk.retired_at.is_(None))
            .order_by(Document.url, Chunk.position)
        )
    passages: dict[str, list[str]] = {}
    for url, text in rows:
        passages.setdefault(url, []).append(text)
    return passages


async def documents(sessions, source_id) -> dict[str, tuple[str, str | None]]:
    async with sessions() as session:
        rows = await session.execute(
            select(Document.url, Document.status, Document.error).where(Document.source_id == source_id)
        )
    return {url: (status, error) for url, status, error in rows}


# --- Zulip's whole help center, from the snapshot ---


def zulip(raw: Path):
    """Zulip's help center as the snapshot saved it, served from its raw HTML."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        slug = path.removeprefix("/help/").strip("/").replace("/", "__") or "index"
        page = raw / f"{slug}.html"
        if not path.startswith("/help/") or not page.is_file():
            return httpx2.Response(404)
        return httpx2.Response(200, headers=HTML, content=page.read_bytes())

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handle))


@pytest.mark.anyio
async def test_zulips_help_center_loads_whole_and_an_unchanged_reindex_makes_no_embedding_call(sessions, zulip_raw):
    source_id = await add_source(
        sessions, kind="start_page", url="https://zulip.com/help/", content_selector=".sl-markdown-content"
    )
    first_embedder = FakeEmbedder()
    async with zulip(zulip_raw) as http:
        first = await index(sessions, source_id, http, first_embedder)

    manifest = json.loads((ZULIP / "manifest.json").read_text(encoding="utf-8"))
    passages = await live(sessions, source_id)
    assert set(passages) == {page["url"] for page in manifest["pages"]}  # all 257, and the redirect stub isn't one
    assert (first.added, first.updated, first.failed, first.removed, first.complete) == (257, 0, 0, 0, True)
    count = sum(len(texts) for texts in passages.values())
    assert first.passages == count == len(first_embedder.texts)

    # Every expected source in the frozen test set is among the passages (citemark test check --against-db)
    async with sessions() as session:
        findings = await check_sources_in_db(testset.load(ROOT / "test-sets" / "zulip-v1.yaml"), session)
    assert findings == []

    second_embedder = FakeEmbedder()
    async with zulip(zulip_raw) as http:
        second = await index(sessions, source_id, http, second_embedder)
    assert second_embedder.calls == 0
    assert (second.unchanged, second.added, second.updated, second.removed) == (257, 0, 0, 0)
    async with sessions() as session:
        retired = await session.scalar(
            select(func.count())
            .select_from(Chunk)
            .join(Document)
            .where(Document.source_id == source_id, Chunk.retired_at.is_not(None))
        )
    assert retired == 0
    assert await live(sessions, source_id) == passages


# --- A small site, for what changes between crawls ---


def article(title: str, text: str) -> str:
    return (
        f"<html><body><h1>{title}</h1><div class='content'><h2 id='how-it-works'>How it works</h2>"
        f"<p>{text}</p></div></body></html>"
    )


ARTICLES = {
    f"/help/{name}": article(name.title(), f"The {name} feature works like this, step by step, on every plan.")
    for name in ("alpha", "beta", "gamma", "delta")
}


def small_site(articles: dict[str, str | int], linked: list[str] | None = None):
    """A help center: an index page linking to each article (or to `linked`). An article given
    as a number answers with that status."""
    links = "".join(f'<a href="{path}">{path}</a>' for path in (articles if linked is None else linked))
    index_page = (
        f"<html><body><nav>{links}</nav><h1>Help</h1><div class='content'>"
        "<p>Welcome to the help center, where every article about the product lives.</p></div></body></html>"
    )

    def handle(request: httpx2.Request) -> httpx2.Response:
        page = index_page if request.url.path == "/help/" else articles.get(request.url.path)
        if page is None:
            return httpx2.Response(404)
        if isinstance(page, int):
            return httpx2.Response(page)
        return httpx2.Response(200, headers=HTML, text=page)

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handle))


async def small_source(sessions) -> uuid.UUID:
    return await add_source(sessions, kind="start_page", url=f"{SITE}/help/", content_selector=".content")


@pytest.mark.anyio
async def test_a_changed_page_gets_new_passages_and_its_old_ones_are_retired_not_deleted(sessions):
    source_id = await small_source(sessions)
    async with small_site(ARTICLES) as http:
        await index(sessions, source_id, http)
    async with sessions() as session:
        old = await session.scalar(
            select(Chunk).join(Document).where(Document.url == f"{SITE}/help/beta", Chunk.retired_at.is_(None))
        )

    changed = {**ARTICLES, "/help/beta": article("Beta", "Beta now works differently: turn it on in settings first.")}
    embedder = FakeEmbedder()
    async with small_site(changed) as http:
        result = await index(sessions, source_id, http, embedder)
    assert (result.updated, result.unchanged, result.added) == (1, 4, 0)  # the index page is unchanged too
    assert len(embedder.texts) == 1 and "turn it on in settings" in embedder.texts[0]
    assert "turn it on in settings" in (await live(sessions, source_id))[f"{SITE}/help/beta"][0]

    # QA promise 14: the old passage is still there, unchanged, so a citation to it still opens it
    async with sessions() as session:
        kept = await session.get(Chunk, old.id, populate_existing=True)
    assert kept.retired_at is not None and kept.text == old.text


@pytest.mark.anyio
async def test_a_page_taken_down_is_removed_and_its_passages_retired(sessions):
    source_id = await small_source(sessions)
    async with small_site(ARTICLES) as http:
        await index(sessions, source_id, http)
    async with small_site({**ARTICLES, "/help/gamma": 404}) as http:
        result = await index(sessions, source_id, http)
    assert result.removed == 1
    assert (await documents(sessions, source_id))[f"{SITE}/help/gamma"] == ("removed", None)
    assert f"{SITE}/help/gamma" not in await live(sessions, source_id)


@pytest.mark.anyio
async def test_a_page_no_longer_linked_is_removed_only_after_a_crawl_that_reached_every_page(sessions):
    source_id = await small_source(sessions)
    async with small_site(ARTICLES) as http:
        await index(sessions, source_id, http)

    # delta is no longer linked, but alpha failed, so the crawl may have missed links: nothing is removed
    unlinked = ["/help/alpha", "/help/beta", "/help/gamma"]
    async with small_site({**ARTICLES, "/help/alpha": 503}, linked=unlinked) as http:
        incomplete = await index(sessions, source_id, http)
    assert not incomplete.complete and incomplete.removed == 0
    assert f"{SITE}/help/delta" in await live(sessions, source_id)

    async with small_site(ARTICLES, linked=unlinked) as http:
        complete = await index(sessions, source_id, http)
    assert complete.complete and complete.removed == 1
    assert (await documents(sessions, source_id))[f"{SITE}/help/delta"][0] == "removed"


@pytest.mark.anyio
async def test_a_page_that_fails_keeps_its_passages_and_records_why(sessions):
    source_id = await small_source(sessions)
    async with small_site(ARTICLES) as http:
        await index(sessions, source_id, http)
    before = await live(sessions, source_id)
    async with small_site({**ARTICLES, "/help/alpha": 500}) as http:
        result = await index(sessions, source_id, http)
    assert result.failed == 1
    status, error = (await documents(sessions, source_id))[f"{SITE}/help/alpha"]
    assert status == "active" and "status 500" in error
    assert await live(sessions, source_id) == before


@pytest.mark.anyio
async def test_a_half_failed_reindex_leaves_the_old_passages_searchable(sessions):
    """QA promise 15. Every article changes, and embedding fails on the third. The first two are
    updated, the rest keep their old passages, and no page is left without any. Running it
    again embeds only what's left."""
    source_id = await small_source(sessions)
    async with small_site(ARTICLES) as http:
        await index(sessions, source_id, http)
    before = await live(sessions, source_id)

    rewritten = {path: html.replace("step by step", "in three steps") for path, html in ARTICLES.items()}
    async with small_site(rewritten) as http:
        with pytest.raises(EmbedError):
            await index(sessions, source_id, http, FakeEmbedder(max_batch=1, fail_on=3))
    halfway = await live(sessions, source_id)
    assert set(halfway) == set(before)
    updated = {url for url, texts in halfway.items() if "in three steps" in texts[0]}
    assert len(updated) == 2
    assert all(halfway[url] == before[url] for url in set(before) - updated)

    retry = FakeEmbedder(max_batch=1)
    async with small_site(rewritten) as http:
        result = await index(sessions, source_id, http, retry)
    assert retry.calls == 2 and result.updated == 2
    articles = {url: texts for url, texts in (await live(sessions, source_id)).items() if url != f"{SITE}/help/"}
    assert all("in three steps" in texts[0] for texts in articles.values())


@pytest.mark.anyio
async def test_embedding_calls_stay_under_a_token_cap_as_well_as_a_count(sessions):
    """An account on a low rate limit refuses a large call every time (T6's first live crawl)."""
    source_id = await small_source(sessions)
    embedder = FakeEmbedder(max_batch_tokens=40)  # each page here is one passage of about 25-35 tokens
    async with small_site(ARTICLES) as http:
        result = await index(sessions, source_id, http, embedder)
    assert embedder.calls == result.embed_calls == 5
    assert result.passages == 5


@pytest.mark.anyio
async def test_progress_is_reported_as_counts(sessions):
    source_id = await small_source(sessions)
    reports = []

    async def progress(done, total=None, label=None, *, session=None):
        reports.append((done, total, label))

    async with small_site(ARTICLES) as http:
        await index(sessions, source_id, http, progress=progress)
    assert (5, 5, "articles") in reports
    assert reports[-1] == (5, 5, "passages")


@pytest.mark.anyio
async def test_an_internal_address_is_refused_before_anything_is_fetched(sessions):
    source_id = await add_source(sessions, kind="start_page", url="http://127.0.0.1:9/help/")
    async with httpx2.AsyncClient(transport=PublicOnlyTransport()) as http:
        with pytest.raises(BlockedAddress):
            await index(sessions, source_id, http)
    assert await documents(sessions, source_id) == {}


@pytest.mark.anyio
async def test_uploaded_files_are_indexed_and_a_new_upload_replaces_the_old_by_name(sessions):
    source_id = await add_source(sessions, kind="upload")
    returns_v1 = b"# Returns\n\nYou can return an unused item within 30 days.\n"
    first = await index_files(
        source_id,
        [("returns.md", returns_v1), ("shipping.md", b"# Shipping\n\nOrders ship in two days.\n"), ("x.docx", b"PK")],
        sessions=sessions,
        embedder=FakeEmbedder(),
    )
    assert (first.added, first.failed) == (2, 1)
    assert (await documents(sessions, source_id))["upload:x.docx"][0] == "failed"

    returns_v2 = b"# Returns\n\nYou can return an unused item within 60 days.\n"
    second = await index_files(source_id, [("returns.md", returns_v2)], sessions=sessions, embedder=FakeEmbedder())
    assert second.updated == 1
    passages = await live(sessions, source_id)
    assert "60 days" in passages["upload:returns.md"][0]
    assert "two days" in passages["upload:shipping.md"][0]  # left as it was
