"""Retrieval against the database (PRD 5.2): hybrid search, fusion, reranking, saved hits, the
retrieval setting and full-context assembly. The last test runs the real steps on a few Zulip
articles, with recorded Voyage replies."""

import uuid
from pathlib import Path

import httpx2
import pytest
from sqlalchemy import func, select, text, update

from citemark.db.models import Chunk, Conversation, Document, Message, RetrievalHit, Setting, Source
from citemark.embed import Ranking
from citemark.embed.voyage import VoyageEmbedder, VoyageReranker
from citemark.ingest.chunk import PATH_SEPARATOR
from citemark.ingest.pipeline import index_source
from citemark.retrieve import RetrievalConfig, RetrievalError, load_config
from citemark.retrieve.context import full_context
from citemark.retrieve.search import retrieve, save_hits
from citemark.testing.fakes import FakeEmbedder, FakeReranker, fake_vector

QUESTION = "can i hide that i'm typing"
SENDING = ("Typing notifications", "Disable sending typing notifications")
SEEING = ("Typing notifications", "Disable seeing typing notifications")
FONT = ("Font size", "Change font size")
SHORTCUTS = ("Keyboard shortcuts", "Composing messages")
TEXTS = {
    SENDING: "If you'd prefer that others not know whether you're typing, turn off typing notifications.",
    SEEING: "If you'd prefer not to see notifications when others type, you can disable them.",
    FONT: "You can change the font size in Preferences, under Information density.",
    SHORTCUTS: "Press Enter to send a message, or Ctrl and Enter if Enter makes a new line.",
}


def path(parts: tuple[str, ...]) -> str:
    return PATH_SEPARATOR.join(parts)


async def add_passages(session, passages: dict[tuple[str, str], str], *, near_question: tuple[str, str] | None = None):
    """Live passages, one article per title. The passage named `near_question` gets the
    question's own vector, so vector search ranks it first; the others get unrelated vectors."""
    source = Source(kind="url", url="https://docs.example.com/help/")
    session.add(source)
    await session.flush()
    ids: dict[tuple[str, str], uuid.UUID] = {}
    documents: dict[str, Document] = {}
    for position, (parts, body) in enumerate(passages.items()):
        title = parts[0]
        if title not in documents:
            slug = title.lower().replace(" ", "-")
            documents[title] = Document(
                source_id=source.id, url=f"https://docs.example.com/help/{slug}", title=title, content_hash=slug
            )
            session.add(documents[title])
            await session.flush()
        heading_path = path(parts)
        chunk = Chunk(
            document_id=documents[title].id,
            position=position,
            heading_path=heading_path,
            anchor_url=None,
            blocks=[body],
            text=f"{heading_path}\n\n{body}",
            token_count=len(body) // 4,
            embedding=fake_vector(QUESTION if parts == near_question else heading_path),
        )
        session.add(chunk)
        await session.flush()
        ids[parts] = chunk.id
    return ids


@pytest.mark.anyio
async def test_a_question_is_searched_by_meaning_and_by_words_then_reranked(session):
    ids = await add_passages(session, TEXTS, near_question=SENDING)
    reranker = FakeReranker()
    result = await retrieve(session, QUESTION, embedder=FakeEmbedder(), reranker=reranker, config=RetrievalConfig())
    first = result.hits[0]
    assert first.chunk_id == ids[SENDING] and first.rank == 1
    assert first.vector_score == pytest.approx(1.0)  # its vector is the question's
    assert first.keyword_score > 0  # it holds "typing"
    assert first.rerank_score is not None and first.fused_score > 0
    [(query, sent)] = reranker.calls
    assert query == QUESTION and len(sent) == len(TEXTS)  # every candidate went to the reranker
    assert result.embed_tokens > 0 and result.rerank_tokens > 0


class Reversing:
    """A reranker that puts the fused list in reverse, so the order can only have come from it."""

    model = "rerank-3"

    async def rerank(self, query, documents, top_k):
        order = list(reversed(range(len(documents))))[:top_k]
        return Ranking([(index, 1.0 - rank / 10) for rank, index in enumerate(order)], 1)


@pytest.mark.anyio
async def test_the_reranker_decides_the_order(session):
    await add_passages(session, TEXTS, near_question=SENDING)
    fused = await retrieve(
        session, QUESTION, embedder=FakeEmbedder(), reranker=None, config=RetrievalConfig(rerank=False, top_k=20)
    )
    config = RetrievalConfig()
    reranked = await retrieve(session, QUESTION, embedder=FakeEmbedder(), reranker=Reversing(), config=config)
    assert [hit.chunk_id for hit in reranked.hits] == [hit.chunk_id for hit in reversed(fused.hits)][:5]
    scores = [hit.rerank_score for hit in reranked.hits]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.anyio
async def test_keyword_search_finds_a_passage_with_only_some_of_the_questions_words(session):
    """websearch_to_tsquery alone joins the words with AND, so no passage here holds them all."""
    ids = await add_passages(session, TEXTS)
    question = "please change the font size for me"
    strict = await session.scalar(
        select(func.count())
        .select_from(Chunk)
        .where(Chunk.id.in_(ids.values()), text("tsv @@ websearch_to_tsquery('english', :q)"))
        .params(q=question)
    )
    assert strict == 0
    config = RetrievalConfig(rerank=False)
    result = await retrieve(session, question, embedder=FakeEmbedder(), reranker=None, config=config)
    font = next(hit for hit in result.hits if hit.chunk_id == ids[FONT])
    assert font.keyword_score > 0


@pytest.mark.anyio
async def test_with_reranking_off_the_fused_order_is_kept_and_cut_to_top_k(session):
    ids = await add_passages(session, TEXTS, near_question=SENDING)
    reranker = FakeReranker()
    config = RetrievalConfig(rerank=False, top_k=2)
    result = await retrieve(session, QUESTION, embedder=FakeEmbedder(), reranker=reranker, config=config)
    assert [hit.rank for hit in result.hits] == [1, 2]
    assert result.hits[0].chunk_id == ids[SENDING]
    assert result.hits[0].fused_score >= result.hits[1].fused_score
    assert all(hit.rerank_score is None for hit in result.hits)
    assert reranker.calls == [] and result.rerank_tokens == 0


@pytest.mark.anyio
async def test_retired_passages_are_never_found(session):
    ids = await add_passages(session, TEXTS, near_question=SENDING)
    await session.execute(update(Chunk).where(Chunk.id == ids[SENDING]).values(retired_at=func.now()))
    result = await retrieve(
        session, QUESTION, embedder=FakeEmbedder(), reranker=FakeReranker(), config=RetrievalConfig(top_k=20)
    )
    assert ids[SENDING] not in {hit.chunk_id for hit in result.hits}
    assert ids[SEEING] in {hit.chunk_id for hit in result.hits}


@pytest.mark.anyio
async def test_an_empty_question_searches_nothing(session):
    embedder = FakeEmbedder()
    result = await retrieve(session, "   ", embedder=embedder, reranker=FakeReranker(), config=RetrievalConfig())
    assert result.hits == [] and embedder.calls == 0


@pytest.mark.anyio
async def test_the_retrieval_setting_changes_the_search_and_a_bad_one_is_named(session):
    assert await load_config(session) == RetrievalConfig()
    session.add(Setting(key="retrieval", value={"top_k": 3, "rerank": False}))
    await session.flush()
    assert await load_config(session) == RetrievalConfig(top_k=3, rerank=False)
    await session.execute(update(Setting).where(Setting.key == "retrieval").values(value={"top_k": 0}))
    with pytest.raises(RetrievalError, match='"retrieval" setting isn\'t valid: top_k'):
        await load_config(session)


@pytest.mark.anyio
async def test_a_reranker_other_than_the_configured_one_is_refused(session):
    """Every test run stores its configuration, so it has to be the one that ran."""
    with pytest.raises(RetrievalError, match=r"reranking with rerank-3, but the reranker is rerank-2\.5"):
        await retrieve(
            session, QUESTION, embedder=FakeEmbedder(), reranker=FakeReranker("rerank-2.5"), config=RetrievalConfig()
        )


@pytest.mark.anyio
async def test_hits_are_saved_with_their_three_scores(session):
    await add_passages(session, TEXTS, near_question=SENDING)
    search = {"embedder": FakeEmbedder(), "reranker": FakeReranker(), "config": RetrievalConfig()}
    result = await retrieve(session, QUESTION, **search)
    conversation = Conversation(model="claude-haiku-5-5", prompt_version="answer.v1")
    session.add(conversation)
    await session.flush()
    message = Message(conversation_id=conversation.id, role="assistant", content="...", kind="answer")
    session.add(message)
    await session.flush()
    save_hits(session, message.id, result.hits)
    await session.flush()
    saved = (await session.scalars(select(RetrievalHit).where(RetrievalHit.message_id == message.id))).all()
    by_rank = {hit.rank: hit for hit in saved}
    assert sorted(by_rank) == [hit.rank for hit in result.hits]
    first = result.hits[0]
    assert (by_rank[1].chunk_id, by_rank[1].vector_score, by_rank[1].keyword_score, by_rank[1].rerank_score) == (
        first.chunk_id,
        pytest.approx(first.vector_score),
        pytest.approx(first.keyword_score),
        pytest.approx(first.rerank_score),
    )


@pytest.mark.anyio
async def test_full_context_holds_every_live_passage_grouped_by_article_in_page_order(session):
    ids = await add_passages(session, TEXTS)
    await session.execute(update(Chunk).where(Chunk.id == ids[SHORTCUTS]).values(retired_at=func.now()))
    articles = await full_context(session)
    assert [article.title for article in articles] == ["Font size", "Typing notifications"]  # by address
    typing = articles[1]
    assert [passage.chunk_id for passage in typing.passages] == [ids[SENDING], ids[SEEING]]
    assert typing.passages[0].blocks == [TEXTS[SENDING]]


# --- The real steps on a few Zulip articles, with recorded Voyage replies ---

SUBSET = [  # none of them used by the frozen test set
    "typing-notifications",
    "font-size",
    "change-your-language",
    "custom-emoji",
    "email-notifications",
    "topic-notifications",
    "keyboard-shortcuts",
]
KNOWN = [
    ("can I stop people from seeing that I'm in the middle of writing something?", SENDING),
    ("the words on my screen are too small to read comfortably", FONT),
]


def zulip(raw: Path):
    def handle(request: httpx2.Request) -> httpx2.Response:
        slug = request.url.path.removeprefix("/help/").strip("/") or "index"
        page = raw / f"{slug}.html"
        if not request.url.path.startswith("/help/") or not page.is_file():
            return httpx2.Response(404)
        return httpx2.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=page.read_bytes())

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handle))


async def no_wait(seconds: float) -> None:
    pass


@pytest.mark.anyio
async def test_a_known_question_finds_its_section_in_the_top_5(sessions, zulip_raw, recorded_transport, recording):
    from citemark.settings import get_settings

    key = get_settings().voyage_api_key.get_secret_value() if recording else "replayed"
    async with sessions.begin() as session:
        source = Source(
            kind="start_page",
            url="https://zulip.com/help/",
            content_selector=".sl-markdown-content",
            include=["/help/", *(f"/help/{slug}" for slug in SUBSET)],
        )
        session.add(source)
        await session.flush()
    async with zulip(zulip_raw) as http, httpx2.AsyncClient(transport=recorded_transport) as api:
        embedder, reranker = VoyageEmbedder(key, api), VoyageReranker(key, api)
        indexed = await index_source(
            source.id,
            sessions=sessions,
            http=http,
            embedder=embedder,
            agent="CitemarkBot (+test)",
            interval=0,
            sleep=no_wait,
        )
        assert indexed.added == len(SUBSET) + 1  # and the help center's index page
        async with sessions() as session:
            for question, section in KNOWN:
                config = RetrievalConfig()
                result = await retrieve(session, question, embedder=embedder, reranker=reranker, config=config)
                assert path(section) in [hit.heading_path for hit in result.hits], question
