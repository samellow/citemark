"""What the demo page's templates lay out (PRD 8.2): every word already decided, as the report's
view is. Parts that need a test run are None or empty until one is published, so the templates
leave them out rather than fill them (PRD 8.2: "Sections whose run hasn't happened yet are left
out, not filled with placeholders")."""

from __future__ import annotations

from dataclasses import dataclass

from citemark.report.view import Record


@dataclass(frozen=True)
class Link:
    text: str
    href: str


@dataclass(frozen=True)
class HeroMeasure:
    key: str
    name: str  # the short form: "Right source"
    count: str  # "37 of 40 (92%)"
    state: str  # pass, warn or fail
    state_label: str
    target: str | None = None  # "target 90%", as the report states it


KINDS = ("answer", "partial", "clarify", "decline", "small_talk")


def record_kind(record: Record) -> str:
    """What a recorded reply did, read from its evidence when the reply's own kind isn't kept."""
    if record.clarify_question:
        return "clarify"
    if record.gap_line:
        return "partial"
    return "answer" if record.quotes else "decline"


@dataclass(frozen=True)
class Turn:
    """A question and what the bot did with it: its evidence record without the result (step 5),
    or the error that stopped it. `status` and `trace_line` are the words drawn above and in its
    fold, filled in by `web.page`."""

    question: str
    record: Record | None
    error: str | None = None
    kind: str | None = None  # one of KINDS; None for an error
    status: str | None = None  # "Answered · 2 sources"
    trace_line: str | None = None  # what it read, above the list in "How it found this"


@dataclass(frozen=True)
class Suggestion:
    question: str
    kind: str  # one of KINDS, what the bot did with it in the test run
    label: str | None = None  # what to expect, filled in by `web.page`


@dataclass(frozen=True)
class Hero:
    headline: str
    headline_halves: tuple[str, str]  # the claim, split where its two promises meet
    subhead: str | None  # says the bot was tested, so it waits for the run
    verdict: str | None
    verdict_state: str | None  # pass or fail, for its mark
    measures: tuple[HeroMeasure, ...]
    cta: Link | None  # left out until the audit listing's address is set
    cta_note: str | None
    report: Link | None


@dataclass(frozen=True)
class AskBox:
    label: str
    placeholder: str
    send: str
    searching: str  # shown while an answer is on its way
    failed: str  # shown when the page can't reach the server
    turns: tuple[Turn, ...]
    notice: str | None  # the rate limit or the spend cap
    conversation: str | None  # the conversation the next question continues
    variant: str
    draft: str | None = None  # a refused question, kept in the box to send again
    closed: bool = False  # the day's cap is reached: nothing can be sent until tomorrow
    wait: int | None = None  # minutes until the hour's limit lets a question through

    @property
    def resting(self) -> bool:
        """Nothing can be sent now: Send, the suggestions and the options rest with the box."""
        return self.closed or bool(self.wait)


@dataclass(frozen=True)
class Panel:
    """One of the headline's two promises, shown by a recorded turn."""

    heading: str  # "Shows its source"
    state: str  # pass or declined, for its mark
    turn: Turn


@dataclass(frozen=True)
class Slot:
    recorded_label: str
    panels: tuple[Panel, ...]  # the recorded answer, then the recorded decline; empty until published
    heading: str  # "Ask it about Zulip"
    lede: str
    suggestions_label: str
    suggestions: tuple[Suggestion, ...]  # each passed in the test run; empty until it's published
    ask: AskBox


@dataclass(frozen=True)
class Results:
    heading: str  # "How it did on 50 test questions"
    verdict: str  # "Not pass", the verdict's word
    note: str


@dataclass(frozen=True)
class Offer:
    heading: str
    body: str
    data: str
    cta: Link | None


@dataclass(frozen=True)
class DemoPage:
    lang: str
    title: str
    description: str
    label: str  # the unofficial-demo label, always visible
    prepared_by: str
    hero: Hero
    slot: Slot
    results: Results | None  # the counts, which wait for the run
    offer: Offer | None  # it sells "this report", so it waits for the run
    footer_label: str
    footer_license: str
    labels: dict[str, str]  # the evidence record's fixed labels
