"""The model layer (PRD 5.3): one small interface between the answering rules and a model's API.

A question, the conversation so far and the passages go in. A stream of events comes out:
- `TextEvent`: text as it's written, in numbered text blocks
- `CitationEvent`: a range of a passage that supports a text block
- `DecisionEvent`: a decision tool the model called, with its input
- `UsageEvent`: one per model call, with its tokens and why it stopped

Thinking is never passed on, so the first event is the first block a visitor could see.

The adapter reports what the model did, and `citemark.answer.rules` decides what the visitor
sees. Only the Claude adapter is built (`models.claude`, roadmap Q7). One for OpenAI would check
markers like [P3] in the text against the passages sent, behind the same events (PRD 5.3).
Each model's window is in `models.registry`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from citemark.models.registry import ModelError

DECISION_TOOLS = ("decline", "ask_clarifying_question", "report_gap", "small_talk")  # prompts/tools.v1.json
HISTORY_TURNS = 6  # PRD 5.3: earlier passages aren't sent again, only the text


@dataclass(frozen=True)
class Turn:
    """One message of the conversation so far. The bot's messages keep their kind, so a
    clarifying question is never followed by another (PRD 5.3)."""

    role: Literal["user", "assistant"]
    text: str
    kind: str | None = None


@dataclass(frozen=True)
class Passage:
    """A passage the model may cite: one `search_result` block, for Claude."""

    chunk_id: uuid.UUID
    url: str  # the article's address
    title: str  # the heading path: the article title, then the section headings
    blocks: tuple[str, ...]  # its paragraphs: a citation names a range of them


@dataclass(frozen=True)
class AnswerRequest:
    question: str  # the visitor's own words: the rewritten question is only for searching
    passages: tuple[Passage, ...]
    history: tuple[Turn, ...] = ()
    tools: tuple[str, ...] = DECISION_TOOLS  # the decision tools offered this time
    full_context: bool = False  # the passages are the whole help center, cached between questions


@dataclass(frozen=True)
class TextEvent:
    block: int  # numbered across the whole reply, so the blocks of a continued call don't collide
    text: str


@dataclass(frozen=True)
class CitationEvent:
    block: int  # the text block it supports
    passage: int  # an index into the request's passages
    cited_text: str
    start_block: int
    end_block: int  # exclusive, as the API gives it


@dataclass(frozen=True)
class DecisionEvent:
    tool: str
    input: dict[str, Any]


@dataclass(frozen=True)
class UsageEvent:
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    stop_reason: str | None  # end_turn, tool_use, max_tokens or refusal


Event = TextEvent | CitationEvent | DecisionEvent | UsageEvent


class ModelCallFailed(ModelError):
    """The call failed before the model finished. The message is one plain sentence."""


class AnswerModel(Protocol):
    model: str
    company: str  # the product it answers for, named in the off-topic decline
    prompt_version: str  # recorded on every message and test run

    def stream(self, request: AnswerRequest) -> AsyncIterator[Event]: ...
