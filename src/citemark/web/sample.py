"""A made-up demo page for the gallery, built from the sample report's made-up Acme Chat content,
so every state the page and its ask box can be in is drawn and checked before a real run exists.
The gallery labels each page as made up."""

from __future__ import annotations

from dataclasses import replace

from citemark.report import sample
from citemark.report.view import Record, Stretch
from citemark.web import page, published
from citemark.web.view import AskBox, DemoPage, Suggestion, Turn

BUILDER = "Casey Morgan"  # the sample report's made-up builder
AUDIT = "https://www.upwork.com/"  # made up: the button's target is set per deployment
COMPANY = "Acme Chat"
EXTRA_SUGGESTIONS = (  # made up: what the bot did with each is said, not tested
    Suggestion("How do I pin a channel to the top?", "answer"),
    Suggestion("Can I record a voice message?", "decline"),
)


def results() -> published.Published:
    """The sample report's passing questions: an answer and a correct decline recorded, and one
    suggestion of each kind, its clarifying question among them."""
    found = published.from_report(
        sample.report(), report_id="sample", recorded=("Q004", "Q041"), suggestions=("Q030", "Q004", "Q041")
    )
    # Its counts are of 50 questions (40 the help center answers, 10 it doesn't), though the sample
    # report lists only five of them
    return replace(found, total=50, suggestions=(*EXTRA_SUGGESTIONS, found.suggestions[0]))


def _live(record: Record, prefix: str) -> Record:
    """A record as the ask box shows it: its own ids, and nothing the test decided."""
    quotes = {quote.marker: replace(quote, id=f"{prefix}-q{quote.marker}") for quote in record.quotes}
    return replace(
        record,
        id=prefix,
        looked=tuple(replace(passage, expected=False) for passage in record.looked),
        quotes=tuple(quotes.values()),
        answer=tuple(Stretch(part.text, tuple(quotes[q.marker] for q in part.markers)) for part in record.answer),
        chosen=None,
        expected_answer=(),
        expected_sources=(),
    )


def conversation() -> tuple[Turn, ...]:
    """A clarifying question, the answer once an option is chosen, and a failed call."""
    entries = {entry.record.question_id: entry.record for entry in sample.report().passed}
    clarify, answer = entries["Q030"], entries["Q004"]
    # Live, a clarifying question stops at its options: what the test then chose and answered isn't there
    no_quote = page.strings.text("report", "trace.no_quote")
    asking = replace(_live(clarify, "t1"), quotes=(), quote_note=no_quote, answer=())
    return (
        Turn(clarify.question, asking),
        Turn(answer.question, _live(answer, "t2")),
        Turn(EXTRA_SUGGESTIONS[1].question, None, page.t("turn.failed")),
    )


def demo(*, run: bool = True, ask: AskBox | None = None) -> DemoPage:
    return page.page(
        company=COMPANY,
        builder_name=BUILDER,
        audit_url=AUDIT,
        audit_price=None,
        article_count=257,
        published=results() if run else None,
        ask=ask or page.ask_box(company=COMPANY),
    )


def asked() -> AskBox:
    """The ask box mid-conversation."""
    return page.ask_box(company=COMPANY, turns=conversation(), conversation="sample", variant="accuracy")


def refused() -> AskBox:
    """The same, refused by the hour's limit: everything that sends rests for its minutes."""
    return replace(asked(), notice=page.rate_limited(12), wait=12)
