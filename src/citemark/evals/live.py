"""The nightly live run (QA plan 3.2): five known questions through the real APIs, which no
commit's CI calls. It catches a change in the APIs or the model that recorded replies would hide
(QA plan 8). Accuracy is the frozen test set's job, not this one's.

Four questions and the seven Zulip articles they're asked over are the recorded tests' own, so a
live reply can be set beside its recording. The fifth is a question none of the seven articles
has a word on, which a test checks: the recorded tests' own not-covered question names something
one of the seven articles mentions in passing. The frozen test set uses none of this. The articles
are embedded live into an empty database, which takes a call or two where the whole help center
would take half an hour on a low rate limit.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import anthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from citemark.answer import Reply
from citemark.answer.pipeline import respond
from citemark.db.models import Source
from citemark.embed import Embedder, Reranker
from citemark.ingest.pipeline import IndexResult, index_files
from citemark.models import AnswerModel
from citemark.retrieve import RetrievalConfig

TEXT = Path(__file__).resolve().parents[3] / "fixtures" / "zulip" / "text"
COMPANY = "Zulip"
ARTICLES = (
    "typing-notifications",
    "font-size",
    "change-your-language",
    "custom-emoji",
    "email-notifications",
    "topic-notifications",
    "keyboard-shortcuts",
)
ANSWERS = ("answer", "partial")
DECLINES = ("decline_not_covered", "decline_off_topic")
QUOTE = 200  # characters of a source's quote shown


class LiveRunError(RuntimeError):
    """The run can't start as asked. The message is one plain sentence."""


@dataclass(frozen=True)
class Known:
    question: str
    expected: str  # the reply's kind: as recorded, or a decline for a question the articles don't cover
    absent: tuple[str, ...] = ()  # what it asks about, in words none of the seven articles holds


QUESTIONS = (
    Known("Can I stop people from seeing when I'm typing?", "answer"),
    Known("How do I make the text bigger?", "answer"),
    Known("How do I stop getting emails?", "clarify"),
    Known("How do I add a spoiler to my message?", "decline_not_covered", absent=("spoiler",)),
    Known("What's the capital of Australia?", "decline_off_topic"),
)


@dataclass(frozen=True)
class Asked:
    known: Known
    kind: str
    sources: int
    cost_usd: Decimal
    problems: tuple[str, ...] = ()
    said: tuple[str, ...] = ()  # the reply as a visitor reads it, so a change from a recording can be read
    calls: int = 1  # model calls: a second follows a gap reported before anything was cited

    def line(self) -> str:
        counted = f"{self.kind}, {self.sources} source{'' if self.sources == 1 else 's'}" if self.sources else self.kind
        if self.calls > 1:
            counted += f", {self.calls} model calls"
        differs = "" if self.kind == self.known.expected else f" (expected: {self.known.expected})"
        return f"[{counted}]{differs} {self.known.question}"


def shown(reply: Reply) -> tuple[str, ...]:
    """A reply as a visitor reads it, a line each: its words with their source markers, a
    clarifying question's options, a partial answer's gap, then what each source quoted."""
    words = "".join(part.text + "".join(f"[{marker}]" for marker in part.markers) for part in reply.segments)
    lines = [line.strip() for line in (words or reply.text).splitlines() if line.strip()]
    if reply.clarify_options:
        lines.append("Options: " + " / ".join(reply.clarify_options))
    if reply.gap_line:
        lines.append(reply.gap_line)
    for source in reply.sources:
        quote = " ".join(source.cited_text.split())
        lines.append(f'[{source.marker}] {source.title}: "{quote[:QUOTE]}{"…" if len(quote) > QUOTE else ""}"')
    return tuple(lines)


async def load(sessions: async_sessionmaker[AsyncSession], embedder: Embedder) -> IndexResult:
    """The seven articles, embedded into an upload source. Only into an empty database, so the
    run never mixes them into a real help center, or answers from one."""
    async with sessions.begin() as session:
        if await session.scalar(select(func.count()).select_from(Source)):
            raise LiveRunError("The live run needs an empty database: it loads seven articles of its own.")
        source = Source(kind="upload")
        session.add(source)
        await session.flush()
        source_id: uuid.UUID = source.id
    files = [(f"{slug}.md", (TEXT / f"{slug}.md").read_bytes()) for slug in ARTICLES]
    loaded = await index_files(source_id, files, sessions=sessions, embedder=embedder)
    if loaded.failed:
        raise LiveRunError(f"{loaded.failed} of the seven articles couldn't be indexed.")
    return loaded


async def ask(
    session: AsyncSession,
    *,
    model: AnswerModel,
    rewriter: anthropic.AsyncAnthropic,
    embedder: Embedder,
    reranker: Reranker | None,
    config: RetrievalConfig,
) -> list[Asked]:
    """Each question in turn, as a new conversation. A search that fails is an error, like a
    model call that does (which `respond` makes an error reply)."""
    asked = []
    for known in QUESTIONS:
        try:
            result = await respond(
                session,
                known.question,
                model=model,
                rewriter=rewriter,
                embedder=embedder,
                reranker=reranker,
                config=config,
            )
        except Exception as exc:  # the error's type only: its text can hold a request's details
            asked.append(Asked(known, "error", 0, Decimal(0), (f"It stopped with {type(exc).__name__}.",)))
            continue
        reply = result.reply
        said, calls = shown(reply), len(reply.calls)
        asked.append(Asked(known, reply.kind, len(reply.sources), result.cost_usd, reply.problems, said, calls))
    return asked


def failures(asked: Sequence[Asked]) -> list[str]:
    """What fails the run (QA plan 3.2): a call that errors, no answer arriving with its
    sources, or a known decline answered. Any other change from what's expected is shown, not
    failed: one question answered differently on one night is the model's variance, not an API change."""
    found = []
    for each in asked:
        if each.kind == "error":
            found.append(f"{each.known.question} The call failed: {' '.join(each.problems) or 'no detail'}")
        elif each.known.expected in DECLINES and each.kind in ANSWERS:
            found.append(f"{each.known.question} It's a known decline, and it was answered.")
    answerable = [each for each in asked if each.known.expected in ANSWERS]
    if not any(each.kind in ANSWERS and each.sources for each in answerable):
        found.append("No answer arrived with its sources.")
    return found
