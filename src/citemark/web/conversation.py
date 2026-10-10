"""The ask box's conversations (PRD 8.2, D1): a question asked, and the turns shown back.

- **A question** is answered by the same pipeline as the widget and the test runs, with the
  conversation so far, so a follow-up or a chosen option is read in context. The exchange is saved
  with its sources, what search found, and what it cost (PRD 5.12).
- **The turns** are built back from the database, each as an evidence record without its result:
  where it looked, what it quoted, what it answered. A turn whose model call failed shows the error
  instead, and isn't sent back to the model as history.
- **Kept 90 days,** like every conversation (PRD 5.11): the worker's daily purge deletes them.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

import anthropic
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citemark import strings
from citemark.answer import Reply
from citemark.answer.pipeline import respond, save_exchange
from citemark.db.models import Chunk, Citation, Conversation, Document, Message, RetrievalHit
from citemark.embed import Embedder, Reranker
from citemark.models import AnswerModel, Turn
from citemark.report.view import Looked, Quote, Record, Stretch
from citemark.retrieve import RetrievalConfig, load_config
from citemark.web import view

log = structlog.get_logger()

PAGE = "/"  # where a conversation was had: the demo page


@dataclass(frozen=True)
class Services:
    """What answering needs: the model, the follow-up rewriter, and search."""

    answerer: AnswerModel
    rewriter: anthropic.AsyncAnthropic
    embedder: Embedder
    reranker: Callable[[RetrievalConfig], Reranker | None]  # by the stored retrieval settings


def _link(url: str | None) -> str | None:
    return url if url and url.startswith(("https://", "http://")) else None


async def _own(session: AsyncSession, conversation_id: uuid.UUID | None) -> Conversation | None:
    """The conversation, if it's one of this page's: another surface's (the widget's, later) is
    never shown or continued here."""
    found = await session.get(Conversation, conversation_id) if conversation_id else None
    return found if found is not None and found.page_url == PAGE else None


async def ask(session: AsyncSession, services: Services, question: str, conversation_id: uuid.UUID | None) -> uuid.UUID:
    """Answer `question` in the conversation, or in a new one, and save the exchange."""
    conversation = await _own(session, conversation_id)
    if conversation is None:
        conversation = Conversation(
            page_url=PAGE, model=services.answerer.model, prompt_version=services.answerer.prompt_version
        )
        session.add(conversation)
        await session.flush()
    config = await load_config(session)
    answered = await respond(
        session,
        question,
        model=services.answerer,
        rewriter=services.rewriter,
        embedder=services.embedder,
        reranker=services.reranker(config),
        config=config,
        history=await history(session, conversation.id),
    )
    await save_exchange(session, conversation.id, question, answered)
    await session.commit()
    return conversation.id


async def _messages(session: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    found = await session.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at, Message.id)
    )
    return list(found)


def _exchanges(messages: list[Message]) -> list[tuple[Message, Message]]:
    """Each question with the reply that names it, in the order they were asked. Two questions
    asked at once in two tabs still each get their own reply."""
    questions = {message.id: message for message in messages if message.role == "user"}
    pairs = [
        (questions[message.reply_to], message)
        for message in messages
        if message.role == "assistant" and message.reply_to in questions
    ]
    return sorted(pairs, key=lambda pair: (pair[0].created_at, pair[0].id))


async def history(session: AsyncSession, conversation_id: uuid.UUID) -> list[Turn]:
    """The conversation as the model reads it, without the questions a failed call left unanswered."""
    turns: list[Turn] = []
    for asked, reply in _exchanges(await _messages(session, conversation_id)):
        if reply.kind in ("error", "stopped"):
            continue
        shown = Reply(
            reply.kind or "answer",
            reply.content,
            clarify_options=tuple(reply.clarify_options) if reply.clarify_options else None,
            gap=reply.gap_text,
        )
        turns += [Turn("user", asked.content), shown.as_turn()]
    return turns


async def turns(session: AsyncSession, conversation_id: uuid.UUID) -> tuple[view.Turn, ...]:
    """The conversation as the ask box shows it: nothing, if it isn't one of this page's."""
    if await _own(session, conversation_id) is None:
        return ()
    exchanges = _exchanges(await _messages(session, conversation_id))
    replies = [reply.id for _, reply in exchanges]
    place = (Chunk.heading_path, Chunk.anchor_url, Document.url)
    cited = defaultdict(list)
    for message_id, citation, *where in await session.execute(
        select(Citation.message_id, Citation, *place)
        .join(Chunk, Chunk.id == Citation.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .where(Citation.message_id.in_(replies))
        .order_by(Citation.marker)
    ):
        cited[message_id].append((citation, *where))
    looked = defaultdict(list)
    for message_id, heading_path, anchor_url, url in await session.execute(
        select(RetrievalHit.message_id, *place)
        .join(Chunk, Chunk.id == RetrievalHit.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .where(RetrievalHit.message_id.in_(replies))
        .order_by(RetrievalHit.rank)
    ):
        looked[message_id].append(Looked(heading_path, _link(anchor_url or url), False))
    shown = []
    for number, (asked, reply) in enumerate(exchanges, start=1):
        if reply.kind in ("error", "stopped"):
            shown.append(view.Turn(asked.content, None, strings.text("demo", "demo.error")))
            continue
        prefix = f"t{number}"
        quotes = tuple(
            Quote(
                citation.marker,
                f"{prefix}-q{citation.marker}",
                strings.text("report", "evidence.marker_a11y", n=citation.marker),
                citation.cited_text,
                heading_path,
                _link(anchor_url or url),
            )
            for citation, heading_path, anchor_url, url in cited[reply.id]
        )
        shown.append(view.Turn(asked.content, _record(prefix, asked, reply, quotes, tuple(looked[reply.id]))))
    return tuple(shown)


def _record(
    prefix: str, asked: Message, reply: Message, quotes: tuple[Quote, ...], looked: tuple[Looked, ...]
) -> Record:
    by_marker = {quote.marker: quote for quote in quotes}
    if reply.segments is not None:
        stretches = []
        for part in reply.segments:
            if unknown := [n for n in part["markers"] if n not in by_marker]:
                log.warning("marker_without_quote", message=str(reply.id), markers=unknown)
            stretches.append(Stretch(part["text"], tuple(by_marker[n] for n in part["markers"] if n in by_marker)))
        answer = tuple(stretches)
    elif reply.kind == "clarify":
        answer = ()  # the question and its options are shown instead
    else:
        answer = (Stretch(reply.content, ()),)
    options = tuple(reply.clarify_options or ())
    return Record(
        id=prefix,
        question_id="",
        run=0,
        question=asked.content,
        full_context=False,
        looked=looked,
        missed=False,
        looked_note=None,
        quotes=quotes,
        quote_note=None if quotes else strings.text("report", "trace.no_quote"),
        clarify_question=strings.text("widget", "clarify.question") if options else None,
        options=options,
        chosen=None,
        answer=answer,
        gap_line=strings.text("widget", "partial.gap", gap=reply.gap_text) if reply.gap_text else None,
        passed=True,  # not shown: a live answer isn't graded
        went_wrong=None,
        step=None,
        expected_answer=(),
        expected_sources=(),
    )
