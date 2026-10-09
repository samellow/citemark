"""Answering against the database (PRD 5.3, 5.12): prices, saved exchanges, and whole questions
answered from search and from the full help center, with recorded replies.

The passages are 7 Zulip articles the frozen test set doesn't use, chunked as ingestion chunks
them, with stand-in vectors. Re-record with: uv run pytest tests/integration/test_answer.py --record
"""

import datetime as dt
import uuid
from decimal import Decimal
from pathlib import Path

import anthropic
import httpx2
import pytest
from sqlalchemy import select

from citemark.answer import Reply, Source
from citemark.answer.pipeline import Answered, respond, save_exchange
from citemark.costs import PriceMissing, price
from citemark.db.models import Chunk, Citation, Conversation, Document, Message, Price, RetrievalHit
from citemark.db.models import Source as SourceRow
from citemark.embed.voyage import RERANK_MODEL, VoyageEmbedder
from citemark.ingest.chunk import PATH_SEPARATOR, chunk_document
from citemark.models.claude import SETTINGS, ClaudeAnswerer
from citemark.retrieve import RetrievalConfig
from citemark.retrieve.context import full_context
from citemark.retrieve.rewrite import MODEL as REWRITE_MODEL
from citemark.retrieve.rewrite import Rewritten
from citemark.testing.fakes import FakeEmbedder, FakeReranker, fake_vector

ZULIP = Path(__file__).parents[2] / "fixtures" / "zulip" / "text"
SUBSET = {  # none of them used by the frozen test set
    "typing-notifications": "Typing notifications",
    "font-size": "Font size",
    "change-your-language": "Change your language",
    "custom-emoji": "Custom emoji",
    "email-notifications": "Email notifications",
    "topic-notifications": "Topic notifications",
    "keyboard-shortcuts": "Keyboard shortcuts",
}
CHECKED = dt.date(2026, 10, 9)  # the seeded prices' date (migration 0003)
HAIKU = "claude-haiku-5-5"


async def add_zulip(session) -> dict[str, uuid.UUID]:
    """The subset's passages as live chunks, by heading path."""
    source = SourceRow(kind="url", url="https://zulip.com/help/")
    session.add(source)
    await session.flush()
    ids = {}
    for slug, title in SUBSET.items():
        url = f"https://zulip.com/help/{slug}"
        document = Document(source_id=source.id, url=url, title=title, content_hash=slug)
        session.add(document)
        await session.flush()
        for passage in chunk_document(title, (ZULIP / f"{slug}.md").read_text(encoding="utf-8"), url):
            chunk = Chunk(
                document_id=document.id,
                position=passage.position,
                heading_path=passage.heading_path,
                anchor_url=passage.anchor_url,
                blocks=list(passage.blocks),
                text=passage.text,
                token_count=passage.token_count,
                embedding=fake_vector(passage.text),
            )
            session.add(chunk)
            await session.flush()
            ids[passage.heading_path] = chunk.id
    session.add(Price(model=FakeEmbedder.model, input_per_mtok=Decimal(0), effective_from=dt.date(2026, 1, 1)))
    await session.flush()
    return ids


def bot(client) -> ClaudeAnswerer:
    return ClaudeAnswerer(client, HAIKU, company="Zulip")


async def ask(session, client, question: str, **options) -> Answered:
    return await respond(
        session,
        question,
        model=bot(client),
        rewriter=client,
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        config=RetrievalConfig(),
        **options,
    )


# --- Prices (PRD 5.12) ---


@pytest.mark.anyio
async def test_a_call_is_priced_from_the_price_table(session):
    cost = await price(session, HAIKU, on=CHECKED, input_tokens=2_000, output_tokens=300, cache_read_tokens=2_286)
    assert cost == (2_000 * Decimal("0.10") + 300 * Decimal("0.50") + 2_286 * Decimal("0.01")) / 1_000_000


@pytest.mark.anyio
async def test_haiku_5_5_costs_more_over_100k_tokens_counting_cached_tokens(session):
    at_limit = await price(session, HAIKU, on=CHECKED, input_tokens=50_000, cache_read_tokens=50_000)
    over = await price(session, HAIKU, on=CHECKED, input_tokens=50_001, cache_read_tokens=50_000)
    assert at_limit == (50_000 * Decimal("0.10") + 50_000 * Decimal("0.01")) / 1_000_000
    assert over == (50_001 * Decimal("0.50") + 50_000 * Decimal("0.05")) / 1_000_000


@pytest.mark.anyio
async def test_a_new_price_applies_from_its_date_and_earlier_calls_keep_theirs(session):
    later = dt.date(2026, 11, 1)
    session.add(Price(model="rerank-3", input_per_mtok=Decimal("0.10"), effective_from=later))
    await session.flush()
    assert await price(session, "rerank-3", on=later - dt.timedelta(days=1), input_tokens=1_000_000) == Decimal("0.05")
    assert await price(session, "rerank-3", on=later, input_tokens=1_000_000) == Decimal("0.10")


@pytest.mark.anyio
@pytest.mark.parametrize("model", [*SETTINGS, REWRITE_MODEL, VoyageEmbedder.model, RERANK_MODEL])
async def test_every_model_the_bot_calls_has_a_price(session, model):
    """A missing price stops an answer after it's written, so each model is checked here instead."""
    assert await price(session, model, on=CHECKED, input_tokens=1_000_000) > 0


@pytest.mark.anyio
@pytest.mark.parametrize(("model", "on"), [("claude-unknown", CHECKED), (HAIKU, dt.date(2026, 1, 1))])
async def test_a_call_with_no_price_is_an_error_not_free(session, model, on):
    with pytest.raises(PriceMissing, match=f"There's no price for {model} on {on.isoformat()}"):
        await price(session, model, on=on, input_tokens=1)


# --- Saving (PRD 4.2) ---


def answered(reply: Reply, **changes) -> Answered:
    now = dt.datetime(2026, 10, 9, 12, tzinfo=dt.UTC)
    fields = {
        "reply": reply,
        "searched": "q",
        "rewritten": Rewritten("q", called=False),
        "passages": (),
        "hits": (),
        "embed_tokens": 0,
        "rerank_tokens": 0,
        "cost_usd": Decimal("0.0000004"),
        "asked_at": now,
        "answered_at": now + dt.timedelta(seconds=1),
        "ttfw_ms": 800,
        "total_ms": 1000,
    }
    return Answered(**{**fields, **changes})


async def conversation(session) -> uuid.UUID:
    row = Conversation(model=HAIKU, prompt_version="answer.v1+tools.v1")
    session.add(row)
    await session.flush()
    return row.id


@pytest.mark.anyio
@pytest.mark.parametrize(
    "reply",
    [
        Reply("clarify", "Which one do you mean?", clarify_options=("Login emails", "Newsletter"), swapped=True),
        Reply("decline_off_topic", "I can only answer questions about Zulip's product."),
        Reply("small_talk", "You're welcome. Ask another question any time."),
        Reply("error", ""),
    ],
    ids=lambda reply: reply.kind,
)
async def test_each_kind_of_reply_is_saved_as_the_database_allows(session, reply):
    saved = await save_exchange(session, await conversation(session), "q", answered(reply))
    assert (saved.kind, saved.content, saved.swapped) == (reply.kind, reply.text, reply.swapped)
    assert saved.clarify_options == (list(reply.clarify_options) if reply.clarify_options else None)
    assert saved.cost_usd == Decimal("0.000001")  # rounded up, never down


@pytest.mark.anyio
async def test_a_partial_answer_is_saved_with_its_gap_and_sources(session):
    ids = await add_zulip(session)
    chunk_id = ids[f"Typing notifications{PATH_SEPARATOR}Disable sending typing notifications"]
    source = Source(1, 0, chunk_id, "https://zulip.com/help/typing-notifications", "t", "If you", 0, 1)
    reply = Reply("partial", "Turn it off.", sources=(source,), gap="whether it works per person")
    saved = await save_exchange(session, await conversation(session), "q", answered(reply))
    assert saved.gap_text == "whether it works per person"
    [citation] = (await session.scalars(select(Citation).where(Citation.message_id == saved.id))).all()
    assert (citation.marker, citation.chunk_id, citation.start_block, citation.end_block) == (1, chunk_id, 0, 1)


# --- Whole questions, on recorded replies ---


@pytest.mark.anyio
async def test_a_question_is_searched_answered_saved_and_priced(session, anthropic_client):
    await add_zulip(session)
    question = "Can I stop people from seeing when I'm typing?"
    result = await ask(session, anthropic_client, question)
    reply = result.reply
    assert reply.kind == "answer" and reply.sources and len(result.hits) == 5
    assert {source.chunk_id for source in reply.sources} <= {hit.chunk_id for hit in result.hits}
    assert result.ttfw_ms is not None and result.total_ms >= result.ttfw_ms

    [call] = reply.calls
    expected = (
        call.input_tokens * Decimal("0.10")
        + call.output_tokens * Decimal("0.50")
        + call.cache_read_tokens * Decimal("0.01")
        + call.cache_write_tokens * Decimal("0.125")
        + result.rerank_tokens * Decimal("0.05")
    ) / 1_000_000
    assert result.cost_usd == expected and result.rerank_tokens > 0

    conversation_id = await conversation(session)
    saved = await save_exchange(session, conversation_id, question, result)
    messages = (
        await session.scalars(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
        )
    ).all()
    assert [(m.role, m.content) for m in messages] == [("user", question), ("assistant", reply.text)]
    assert saved.input_tokens == call.input_tokens and saved.rerank_tokens == result.rerank_tokens
    citations = (await session.scalars(select(Citation).where(Citation.message_id == saved.id))).all()
    assert sorted(c.marker for c in citations) == list(range(1, len(reply.sources) + 1))
    hits = (await session.scalars(select(RetrievalHit).where(RetrievalHit.message_id == saved.id))).all()
    assert len(hits) == 5


@pytest.mark.anyio
async def test_full_context_mode_reads_the_help_center_from_the_cache_on_the_next_question(session, anthropic_client):
    """The docs block is cached (PRD 5.3), so a second question reads it rather than paying for it.

    In this recording the API also cited paragraphs 3-4 of a 2-paragraph passage, with no cited
    text. The rules dropped that citation and logged it, so every source shown is a real range."""
    await add_zulip(session)
    articles = await full_context(session)
    first = await ask(session, anthropic_client, "Can I stop people from seeing when I'm typing?", articles=articles)
    second = await ask(session, anthropic_client, "How do I make the text bigger?", articles=articles)
    assert len(first.passages) == sum(len(article.passages) for article in articles) and not first.hits
    assert first.reply.kind == "answer" and first.reply.sources
    for source in first.reply.sources:
        assert source.end_block <= len(first.passages[source.passage].blocks) and source.cited_text
    written, read = first.reply.calls[0], second.reply.calls[0]
    assert written.cache_write_tokens > 0 and read.cache_read_tokens >= written.cache_write_tokens


FAILS_PARTWAY = """event: message_start
data: {"type": "message_start", "message": {"id": "msg_x", "type": "message", "role": "assistant", \
"model": "claude-haiku-5-5", "content": [], "stop_reason": null, "stop_sequence": null, "usage": \
{"input_tokens": 1000, "output_tokens": 1, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 2000}}}

event: error
data: {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}

"""


@pytest.mark.anyio
async def test_a_failed_call_is_an_error_reply_that_still_counts_what_was_billed(session):
    """CONSTRUCTED: the API accepted the question, then failed mid-stream, as an overload can."""
    await add_zulip(session)
    transport = httpx2.MockTransport(
        lambda request: httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=FAILS_PARTWAY)
    )
    http_client = anthropic.DefaultAsyncHttpxClient(transport=transport)
    async with anthropic.AsyncAnthropic(api_key="unused", max_retries=0, http_client=http_client) as client:
        result = await ask(
            session, client, "Can I stop people from seeing when I'm typing?", articles=await full_context(session)
        )
    assert result.reply.kind == "error" and result.reply.text == "" and result.ttfw_ms is None
    assert result.reply.problems == ("The call to claude-haiku-5-5 failed (APIStatusError).",)
    assert result.cost_usd == (1000 * Decimal("0.10") + 1 * Decimal("0.50") + 2000 * Decimal("0.01")) / 1_000_000
