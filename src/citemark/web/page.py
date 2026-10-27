"""The demo page's words (PRD 8.2, content spec 6), decided before anything is drawn.

- **Before the decision runs are published,** the page shows what's true without them: the label,
  the headline, the ask box. What would claim a test is left out: the subhead, the verdict, the
  counts, the recorded exchange, the suggested questions, the report link, and the offer and its
  button, which sell "this report". The title and description have their own words for it.
- **The headline's two promises** are each shown by a recorded turn: the answer with its sources
  under the first half, the decline under the second.
- **The audit button** appears only once the run is published and the listing's address is set,
  and goes through the counting redirect, carrying the pitch variant.
- **Every link keeps `?v=`,** so a click is counted under the pitch that brought the visitor.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from functools import cache
from pathlib import Path
from urllib.parse import urlencode

from citemark import strings
from citemark.report.render import environment
from citemark.web.published import Published
from citemark.web.view import (
    AskBox,
    DemoPage,
    Hero,
    Link,
    Offer,
    Panel,
    Results,
    Slot,
    Suggestion,
    Turn,
    record_kind,
)

STATIC = Path(__file__).resolve().parents[3] / "static"
ASSETS = ("tokens.css", "citemark.css", "demo.css", "demo.js")  # what the page links, in that order
LANG = "en"
AUDIT_PRICE = "$300"  # the slot dictionary's default (content spec 10)
FORM = "ask-form"  # the ask box's form, which the suggestions and options submit
MAX_QUESTION = 1_000  # characters (PRD 5.6)
RECORD_LABELS = (  # the evidence record's fixed labels, from the report's strings
    "trace.step1",
    "trace.step2",
    "trace.step3",
    "trace.step4",
    "trace.step5",
    "trace.gap_step2",
    "evidence.expected_answer",
    "evidence.expected_source",
    "evidence.shown_source",
    "state.pass",
    "state.fail",
)
TURN_LABELS = ("turn.looked", "turn.trace", "turn.quoted", "turn.retry")  # the demo's own, for every turn
STATUS = {
    "answer": "turn.answered",
    "partial": "turn.partial",
    "decline": "turn.declined",
}  # a clarifying turn asks for itself


def t(key: str, **slots: str | int) -> str:
    return strings.text("demo", key, **slots)


def _with_variant(path: str, variant: str) -> str:
    return f"{path}?{urlencode({'v': variant})}" if variant else path


def halves(headline: str) -> tuple[str, str]:
    """The claim split after its first comma, where "shows its source" meets "says it doesn't know"."""
    first, comma, second = headline.partition(", ")
    return (first + comma.strip(), second) if comma else (headline, "")


def shown(turn: Turn) -> Turn:
    """A turn with the words drawn around it: what it did, and what it read."""
    if turn.record is None:
        return turn
    kind = turn.kind or record_kind(turn.record)
    status = STATUS.get(kind)
    looked = len(turn.record.looked)
    return replace(
        turn,
        kind=kind,
        status=t(status, sources=len(turn.record.quotes)) if status else None,
        trace_line=t("turn.trace_line", passages=looked) if looked else None,
    )


def panels(recorded: tuple[Turn, ...]) -> tuple[Panel, ...]:
    """The recorded answer under "shows its source", then the recorded decline."""
    turns = [shown(turn) for turn in recorded]
    answer = next((turn for turn in turns if turn.kind in ("answer", "partial")), None)
    decline = next((turn for turn in turns if turn.kind == "decline"), None)
    found = [Panel(t("panel.source"), "pass", answer)] if answer else []
    return tuple(found + ([Panel(t("panel.decline"), "declined", decline)] if decline else []))


def ask_box(
    *,
    company: str,
    turns: tuple[Turn, ...] = (),
    notice: str | None = None,
    conversation: str | None = None,
    variant: str = "",
    draft: str | None = None,
    closed: bool = False,
    wait: int | None = None,
) -> AskBox:
    return AskBox(
        label=strings.text("widget", "composer.label"),
        placeholder=strings.text("widget", "composer.placeholder", company=company),
        send=strings.text("widget", "composer.send"),
        searching=strings.text("widget", "answer.searching"),
        failed=t("demo.error"),
        turns=tuple(shown(turn) for turn in turns),
        notice=notice,
        conversation=conversation,
        variant=variant,
        draft=draft,
        closed=closed,
        wait=wait,
    )


def rate_limited(minutes: int) -> str:
    return t("demo.rate_limit", minutes=minutes)


def spend_capped(published: Published | None) -> str:
    return t("demo.spend_cap" if published else "demo.spend_cap_no_run")


def page(
    *,
    company: str,
    builder_name: str,
    audit_url: str | None,
    audit_price: str | None,
    article_count: int,
    published: Published | None,
    ask: AskBox,
) -> DemoPage:
    variant = ask.variant
    audit = Link(t("hero.cta"), _with_variant("/go/audit", variant)) if audit_url and published else None
    price = audit_price or AUDIT_PRICE
    hero = Hero(
        headline=t("hero.headline"),
        headline_halves=halves(t("hero.headline")),
        subhead=t("hero.subhead", total=published.total, article_count=article_count) if published else None,
        verdict=t("hero.verdict", total=published.total, verdict_word=published.verdict_word) if published else None,
        verdict_state=("pass" if published.verdict_state == "pass" else "fail") if published else None,
        measures=published.measures if published else (),
        cta=audit,
        cta_note=t("hero.cta_note", audit_price=price) if audit else None,
        report=Link(t("hero.cta_secondary"), _with_variant(f"/reports/{published.report}", variant))
        if published
        else None,
    )
    slot = Slot(
        recorded_label=strings.text("widget", "inline.recorded_label"),
        panels=panels(published.recorded) if published else (),
        heading=t("ask.heading", company=company),
        lede=t("ask.lede"),
        suggestions_label=strings.text("widget", "inline.suggestions_label"),
        suggestions=tuple(
            Suggestion(found.question, found.kind, t(f"suggest.{found.kind}")) for found in published.suggestions
        )
        if published
        else (),
        ask=ask,
    )
    return DemoPage(
        lang=LANG,
        title=t("meta.title" if published else "meta.title_no_run"),
        description=t("meta.description" if published else "meta.description_no_run"),
        label=t("top.label"),
        prepared_by=t("top.prepared_by", builder_name=builder_name),
        hero=hero,
        slot=slot,
        results=Results(t("results.heading", total=published.total), published.verdict_word, t("results.note"))
        if published
        else None,
        offer=Offer(
            heading=t("offer.heading"),
            body=t("offer.body", audit_price=price),
            data=t("offer.data"),
            cta=Link(t("offer.cta"), audit.href) if audit else None,
        )
        if published
        else None,
        footer_label=t("footer.label"),
        footer_license=t("footer.license"),
        labels=record_labels(),
    )


def record_labels() -> dict[str, str]:
    return {key: strings.text("report", key) for key in RECORD_LABELS} | {key: t(key) for key in TURN_LABELS}


@cache
def assets_version(directory: Path = STATIC) -> str:
    """A fingerprint of the files the page links. It goes in their addresses, so a browser that
    kept an older copy fetches the new one after a deploy instead of styling the new page with it.
    The files don't change while the app runs, so it's worked out once."""
    digest = hashlib.sha256()
    for name in ASSETS:
        digest.update((directory / name).read_bytes())
    return digest.hexdigest()[:12]


def render(
    demo: DemoPage,
    *,
    static: str = "/static/",
    version: str | None = None,
    theme: str | None = None,
    banner: str | None = None,
) -> str:
    """The whole page. `theme` forces light or dark, as the gallery shows it; served, it follows the visitor's.
    `version` is the files' fingerprint, by default today's; the gallery, opened from disk, passes ""."""
    version = assets_version() if version is None else version
    return (
        environment()
        .get_template("demo.html")
        .render(
            page=demo,
            static=static,
            version=version,
            theme=theme,
            banner=banner,
            form=FORM,
            max_question=MAX_QUESTION,
        )
    )


def render_ask(ask: AskBox) -> str:
    """The ask box alone, which demo.js swaps in after a question."""
    return (
        environment()
        .get_template("ask.html")
        .render(ask=ask, labels=record_labels(), form=FORM, max_question=MAX_QUESTION)
    )
