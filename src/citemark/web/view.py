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


@dataclass(frozen=True)
class Turn:
    """A question and what the bot did with it: its evidence record without the result (step 5),
    or the error that stopped it."""

    question: str
    record: Record | None
    error: str | None = None


@dataclass(frozen=True)
class Hero:
    headline: str
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


@dataclass(frozen=True)
class Slot:
    recorded_label: str
    recorded: tuple[Turn, ...]  # copied from the test run; empty until it's published
    suggestions_label: str
    suggestions: tuple[str, ...]  # each passed in the test run; empty until it's published
    ask: AskBox


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
    offer: Offer | None  # it sells "this report", so it waits for the run
    footer_label: str
    footer_license: str
    labels: dict[str, str]  # the evidence record's fixed labels
