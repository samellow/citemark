"""Answering (PRD 5.3): what the visitor sees, decided by the server from what the model did.

`rules.decide` turns the model layer's events into a `Reply`. `pipeline.respond` answers a whole
question: the follow-up rewrite, the search, the model, the rules and the cost.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from citemark import strings
from citemark.models import Turn, UsageEvent


@dataclass(frozen=True)
class Source:
    """A numbered source under the answer."""

    marker: int  # 1 to 3, in order of first appearance
    passage: int  # its index among the passages the model was sent
    chunk_id: uuid.UUID
    url: str
    title: str  # the heading path
    cited_text: str  # copied by the API from the passage, never written by the model
    start_block: int
    end_block: int  # exclusive


@dataclass(frozen=True)
class Segment:
    """A stretch of the answer, with the markers of the sources that support it."""

    text: str
    markers: tuple[int, ...] = ()


@dataclass(frozen=True)
class Reply:
    kind: str  # one of db.models.MESSAGE_KINDS
    text: str  # what the visitor reads: the answer, or a decision's fixed sentence
    segments: tuple[Segment, ...] = ()  # the answer with its markers; empty for a decision
    sources: tuple[Source, ...] = ()
    clarify_options: tuple[str, ...] | None = None
    gap: str | None = None  # completes "The help center doesn't say …" (partial answers only)
    swapped: bool = False  # text was shown, then swapped out for a decline or a question (PRD Q11)
    calls: tuple[UsageEvent, ...] = ()  # one per model call
    problems: tuple[str, ...] = ()  # where the model broke the rules: logged, and counted in test runs

    @property
    def stored_segments(self) -> list[dict[str, object]] | None:
        """The answer's stretches as the database keeps them, or None when it isn't an answer."""
        if self.kind not in ("answer", "partial"):
            return None
        return [{"text": segment.text, "markers": list(segment.markers)} for segment in self.segments]

    @property
    def gap_line(self) -> str | None:
        return strings.text("widget", "partial.gap", gap=self.gap) if self.gap else None

    def as_turn(self) -> Turn:
        """This reply as the next question's history: what the visitor saw, and its kind."""
        shown = self.text
        if self.gap_line:
            shown = f"{shown}\n\n{self.gap_line}"
        if self.clarify_options:
            shown = f"{shown} " + " / ".join(self.clarify_options)
        return Turn("assistant", shown, self.kind)
