"""One question answered (PRD 5.2, 5.3, 5.12): rewrite, search, answer, decide, price.

1. A follow-up is rewritten to stand alone. The rewrite is only for searching: the model reads
   the visitor's own words, with the conversation before them.
2. Search mode finds the top passages. Full-context mode sends every live passage instead.
3. The model streams its reply, and the rules decide what the visitor sees.
4. Every call is priced from the price table, at the day's prices.

Time to first word runs from the question to the first thing a visitor would see: text, or a
decline, clarifying question or small talk. The log never holds what was asked (PRD 5.11).
"""

from __future__ import annotations

import datetime as dt
import time
import uuid
from collections.abc import Callable, Sequence
from contextlib import aclosing
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

import anthropic
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.answer import Reply
from citemark.answer.rules import REPLACING, decide
from citemark.costs import price
from citemark.db.models import Citation, Message
from citemark.embed import Embedder, Reranker
from citemark.models import (
    DECISION_TOOLS,
    AnswerModel,
    AnswerRequest,
    DecisionEvent,
    Event,
    ModelCallFailed,
    Passage,
    TextEvent,
    Turn,
    UsageEvent,
)
from citemark.retrieve import RetrievalConfig
from citemark.retrieve.context import Article
from citemark.retrieve.rewrite import MODEL as REWRITE_MODEL
from citemark.retrieve.rewrite import Rewritten, rewrite
from citemark.retrieve.search import Hit, retrieve, save_hits

log = structlog.get_logger()

STORED_PLACES = Decimal("0.000001")  # message.cost_usd keeps 6 decimal places


@dataclass(frozen=True)
class Answered:
    reply: Reply
    searched: str  # the question as searched: rewritten when it was a follow-up
    rewritten: Rewritten
    passages: tuple[Passage, ...]  # what the model was sent
    hits: tuple[Hit, ...]  # what search found, with its scores; empty in full-context mode
    embed_tokens: int
    rerank_tokens: int
    cost_usd: Decimal  # every call for this question, unrounded
    asked_at: dt.datetime
    answered_at: dt.datetime
    ttfw_ms: int | None  # None when nothing was shown, as for an error
    total_ms: int


def offered_tools(history: Sequence[Turn]) -> tuple[str, ...]:
    """The decision tools for the next reply: no clarifying question right after one (PRD 5.3)."""
    last = next((turn for turn in reversed(history) if turn.role == "assistant"), None)
    if last is not None and last.kind == "clarify":
        return tuple(tool for tool in DECISION_TOOLS if tool != "ask_clarifying_question")
    return DECISION_TOOLS


def passages_from_hits(hits: Sequence[Hit]) -> tuple[Passage, ...]:
    return tuple(Passage(hit.chunk_id, hit.url, hit.heading_path, tuple(hit.blocks)) for hit in hits)


def passages_from_articles(articles: Sequence[Article]) -> tuple[Passage, ...]:
    return tuple(
        Passage(passage.chunk_id, article.url, passage.heading_path, tuple(passage.blocks))
        for article in articles
        for passage in article.passages
    )


def _visible(event: Event) -> bool:
    if isinstance(event, TextEvent):
        return bool(event.text.strip())
    return isinstance(event, DecisionEvent) and event.tool in REPLACING  # a gap line waits for the answer


async def _cost(
    session: AsyncSession,
    reply: Reply,
    rewritten: Rewritten,
    *,
    embedder: Embedder,
    embed_tokens: int,
    reranker: Reranker | None,
    rerank_tokens: int,
    on: dt.date,
) -> Decimal:
    total = Decimal(0)
    for call in reply.calls:
        total += await price(
            session,
            call.model,
            on=on,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            cache_read_tokens=call.cache_read_tokens,
            cache_write_tokens=call.cache_write_tokens,
        )
    if rewritten.called:
        total += await price(
            session, REWRITE_MODEL, on=on, input_tokens=rewritten.input_tokens, output_tokens=rewritten.output_tokens
        )
    if embed_tokens:
        total += await price(session, embedder.model, on=on, input_tokens=embed_tokens)
    if rerank_tokens and reranker is not None:
        total += await price(session, reranker.model, on=on, input_tokens=rerank_tokens)
    return total


async def respond(
    session: AsyncSession,
    question: str,
    *,
    model: AnswerModel,
    rewriter: anthropic.AsyncAnthropic,
    embedder: Embedder,
    reranker: Reranker | None,
    config: RetrievalConfig,
    history: Sequence[Turn] = (),
    articles: Sequence[Article] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Answered:
    """Answer one question. `articles` switches to full-context mode (test runs only)."""
    asked_at = dt.datetime.now(dt.UTC)
    started = clock()
    rewritten = await rewrite(rewriter, history, question)
    hits: tuple[Hit, ...] = ()
    embed_tokens = rerank_tokens = 0
    if articles is None:
        found = await retrieve(session, rewritten.question, embedder=embedder, reranker=reranker, config=config)
        hits, embed_tokens, rerank_tokens = tuple(found.hits), found.embed_tokens, found.rerank_tokens
        passages = passages_from_hits(hits)
    else:
        passages = passages_from_articles(articles)

    request = AnswerRequest(question, passages, tuple(history), offered_tools(history), articles is not None)
    events: list[Event] = []
    first: float | None = None
    try:
        async with aclosing(model.stream(request)) as stream:  # the HTTP stream is closed even on an error
            async for event in stream:
                if first is None and _visible(event):
                    first = clock()
                events.append(event)
    except ModelCallFailed as exc:
        calls = tuple(event for event in events if isinstance(event, UsageEvent))
        reply = Reply("error", "", calls=calls, problems=(str(exc),))
        first = None
    else:
        reply = decide(events, passages=passages, offered=request.tools, company=model.company)
    finished = clock()

    cost = await _cost(
        session,
        reply,
        rewritten,
        embedder=embedder,
        embed_tokens=embed_tokens,
        reranker=reranker,
        rerank_tokens=rerank_tokens,
        on=asked_at.date(),
    )
    log.info(
        "answered",
        model=model.model,
        kind=reply.kind,
        swapped=reply.swapped,
        sources=len(reply.sources),
        calls=len(reply.calls),
        problems=list(reply.problems),
    )
    return Answered(
        reply=reply,
        searched=rewritten.question,
        rewritten=rewritten,
        passages=passages,
        hits=hits,
        embed_tokens=embed_tokens,
        rerank_tokens=rerank_tokens,
        cost_usd=cost,
        asked_at=asked_at,
        answered_at=asked_at + dt.timedelta(seconds=finished - started),
        ttfw_ms=round((first - started) * 1000) if first is not None else None,
        total_ms=round((finished - started) * 1000),
    )


async def save_exchange(
    session: AsyncSession, conversation_id: uuid.UUID, question: str, answered: Answered
) -> Message:
    """The visitor's message and the bot's reply, with its sources, what search found and what
    it all cost. Each keeps its own time, and the reply names the question it answers."""
    reply = answered.reply
    calls = reply.calls
    rewritten = answered.rewritten
    asked = Message(conversation_id=conversation_id, role="user", content=question, created_at=answered.asked_at)
    session.add(asked)
    await session.flush()  # the question's ID, for the reply to name
    answer = Message(
        conversation_id=conversation_id,
        reply_to=asked.id,
        role="assistant",
        content=reply.text,
        kind=reply.kind,
        clarify_options=list(reply.clarify_options) if reply.clarify_options else None,
        gap_text=reply.gap,
        segments=reply.stored_segments,
        swapped=reply.swapped,
        input_tokens=sum(call.input_tokens for call in calls) + rewritten.input_tokens,
        output_tokens=sum(call.output_tokens for call in calls) + rewritten.output_tokens,
        cache_read_tokens=sum(call.cache_read_tokens for call in calls),
        cache_write_tokens=sum(call.cache_write_tokens for call in calls),
        embed_tokens=answered.embed_tokens,
        rerank_tokens=answered.rerank_tokens,
        cost_usd=answered.cost_usd.quantize(STORED_PLACES, rounding=ROUND_CEILING),
        ttfw_ms=answered.ttfw_ms,
        total_ms=answered.total_ms,
        created_at=answered.answered_at,
    )
    session.add(answer)
    await session.flush()  # the reply's ID, for its sources and hits
    session.add_all(
        Citation(
            message_id=answer.id,
            marker=source.marker,
            chunk_id=source.chunk_id,
            cited_text=source.cited_text,
            start_block=source.start_block,
            end_block=source.end_block,
        )
        for source in reply.sources
    )
    save_hits(session, answer.id, answered.hits)
    await session.flush()
    return answer
