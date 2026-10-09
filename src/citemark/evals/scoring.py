"""Mechanical scoring (PRD 5.4): whether the bot looked in the right place, showed the right
source and declined what it should. No AI is involved, so re-scoring a stored run gives the
same scores every time (QA plan 4.1). Answer correctness is the judge's (`evals.judge`).

A passage matches an expected source when it's from the same article and either is the
expected section, by its own heading, or holds the expected quote. The section above an
article's first heading is the article's title (the frozen set's convention).

Every function here reads what a test result stores, so `citemark test rescore` recomputes
the scores from the database alone.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from citemark.evals.snapshot import normalize
from citemark.ingest.chunk import PATH_SEPARATOR

DECLINES = ("decline_not_covered", "decline_off_topic")
SHOULD_DECLINE = ("decline", "off_topic")
ANSWER_EXPECTED = ("answerable", "partial", "ambiguous")
COVERED = ("answerable", "partial")  # the over-decline measure's questions (PRD 5.4)
JUDGED = ("answer", "partial")  # the reply kinds the judge grades

Row = Mapping[str, Any]


def _url(url: str) -> str:
    return url.rstrip("/")


def matches(passage: Row, source: Row) -> bool:
    """Whether a retrieved or cited passage is an expected source."""
    if _url(passage["url"]) != _url(source["url"]):
        return False
    own_heading = passage["heading_path"].split(PATH_SEPARATOR)[-1]
    if normalize(own_heading) == normalize(source["section"]):
        return True
    return normalize(source["quote"]) in normalize(" ".join(passage["blocks"]))


def retrieval_hit(qtype: str, retrieved: Sequence[Row], expected: Sequence[Row], mode: str) -> bool | None:
    """An expected source is among the passages search gave the model. None in full-context
    mode, where the model reads everything, and for questions with no expected source."""
    if mode == "full_context" or qtype not in ANSWER_EXPECTED or not expected:
        return None
    return any(matches(passage, source) for passage in retrieved for source in expected)


def citation_correct(qtype: str, kind: str | None, citations: Sequence[Row], expected: Sequence[Row]) -> bool | None:
    """At least one citation is an expected source, and none is from an unrelated article. None
    when the reply isn't an answer: a decline or a question has no source to get wrong."""
    if qtype not in ANSWER_EXPECTED or not expected or kind not in JUDGED:
        return None
    articles = {_url(source["url"]) for source in expected}
    return any(matches(cited, source) for cited in citations for source in expected) and all(
        _url(cited["url"]) in articles for cited in citations
    )


def decline_correct(qtype: str, kind: str | None) -> bool | None:
    """A question the help center doesn't cover, or that isn't about the product, ended in a decline."""
    if qtype not in SHOULD_DECLINE:
        return None
    return kind in DECLINES


def chosen_option(options: Sequence[str] | None, expected: Sequence[str]) -> str | None:
    """The first option the bot offered that holds one of the accepted phrasings, as whole words.

    "Your password" holds "password", but a vague "Notifications" doesn't hold "desktop
    notifications", so a bot that offers only vague options doesn't pass."""
    for option in options or ():
        offered = normalize(option)
        for phrase in filter(str.strip, expected):  # a blank phrasing would match anything
            if re.search(rf"(?<!\w){re.escape(normalize(phrase))}(?!\w)", offered):
                return option
    return None


def failure_type(
    qtype: str,
    kind: str | None,
    *,
    clarified: bool | None,
    retrieval_hit: bool | None,
    citation_correct: bool | None,
    judge_verdict: str | None,
) -> str | None:
    """The first failure in PRD 5.4's order, or None if the question passed.

    An ambiguous question passes only if the bot asked which meaning, with the expected one
    among its options, and then answered the follow-up correctly."""
    if qtype in SHOULD_DECLINE:
        return None if kind in DECLINES else "answered_should_decline"
    if kind in DECLINES:
        return "declined_answerable"
    if retrieval_hit is False:
        return "retrieval_miss"
    if citation_correct is False:
        return "wrong_citation"
    if judge_verdict != "correct" or clarified is False:
        return "wrong_answer"
    return None


@dataclass(frozen=True)
class Scores:
    retrieval_hit: bool | None
    citation_correct: bool | None
    decline_correct: bool | None
    clarified: bool | None  # ambiguous questions only
    failure_type: str | None


def score(
    question: Row,
    *,
    mode: str,
    kind: str | None,
    retrieved: Sequence[Row],
    citations: Sequence[Row],
    clarify_options: Sequence[str] | None,
    judge_verdict: str | None,
) -> Scores:
    """All the mechanical scores of one result. `question` holds the test question's fields."""
    qtype, expected = question["type"], question["expected_sources"]
    clarified = None
    if qtype == "ambiguous":
        clarified = chosen_option(clarify_options, question["expected_option"]) is not None
    hit = retrieval_hit(qtype, retrieved, expected, mode)
    cited = citation_correct(qtype, kind, citations, expected)
    return Scores(
        retrieval_hit=hit,
        citation_correct=cited,
        decline_correct=decline_correct(qtype, kind),
        clarified=clarified,
        failure_type=failure_type(
            qtype, kind, clarified=clarified, retrieval_hit=hit, citation_correct=cited, judge_verdict=judge_verdict
        ),
    )


@dataclass(frozen=True)
class Measure:
    passed: int
    total: int


@dataclass(frozen=True)
class Summary:
    """A run's measures (content spec 5.2), as counts. Rounding is the report's job."""

    correct_answers: Measure
    right_source: Measure
    correct_declines: Measure
    wrongly_declined: Measure  # lower is better
    right_place: Measure | None  # None in full-context mode
    failures: dict[str, int]
    swapped: int


def _count(rows: Sequence[Row], among: Callable[[Row], bool], passed: Callable[[Row], bool]) -> Measure:
    chosen = [row for row in rows if among(row)]
    return Measure(sum(1 for row in chosen if passed(row)), len(chosen))


def summarize(rows: Sequence[Row], *, mode: str) -> Summary:
    """Each row holds a result's question type, kind, judge verdict and stored scores."""

    def expected(row: Row) -> bool:
        return row["type"] in ANSWER_EXPECTED

    return Summary(
        correct_answers=_count(
            rows, expected, lambda row: row["judge_verdict"] == "correct" and row["clarified"] is not False
        ),
        right_source=_count(rows, expected, lambda row: row["citation_correct"] is True),
        correct_declines=_count(
            rows, lambda row: row["type"] in SHOULD_DECLINE, lambda row: row["decline_correct"] is True
        ),
        wrongly_declined=_count(rows, lambda row: row["type"] in COVERED, lambda row: row["kind"] in DECLINES),
        right_place=(
            None if mode == "full_context" else _count(rows, expected, lambda row: row["retrieval_hit"] is True)
        ),
        failures=dict(Counter(row["failure_type"] for row in rows if row["failure_type"])),
        swapped=sum(1 for row in rows if row["swapped"]),
    )
