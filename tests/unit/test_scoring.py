"""Mechanical scoring (PRD 5.4) on constructed results: no AI, so the same data always scores
the same (QA plan 4.1)."""

import pytest

from citemark.evals.scoring import (
    chosen_option,
    citation_correct,
    decline_correct,
    failure_type,
    matches,
    retrieval_hit,
    score,
    summarize,
)
from citemark.ingest.chunk import PATH_SEPARATOR

URL = "https://zulip.com/help/typing-notifications"
SENDING = {
    "url": URL,
    "heading_path": f"Typing notifications{PATH_SEPARATOR}Disable sending typing notifications",
    "blocks": ["If you'd prefer that others not know whether you're typing, turn it off.", "1. Click the gear."],
}
INTRO = {
    "url": URL + "/",
    "heading_path": "Typing notifications",
    "blocks": ["The Zulip web app displays typing notifications."],
}
OTHER = {"url": "https://zulip.com/help/font-size", "heading_path": "Font size", "blocks": ["Change the font size."]}
EXPECTED = [{"url": URL, "section": "Disable sending typing notifications", "quote": "turn it off"}]


def test_a_passage_matches_its_own_section_and_article():
    assert matches(SENDING, EXPECTED[0])
    assert not matches(OTHER, EXPECTED[0])


def test_the_article_title_is_the_section_above_the_first_heading():
    """The frozen set names the text above an article's first heading by the article's title."""
    assert matches(INTRO, {"url": URL, "section": "Typing notifications", "quote": "nothing here"})
    assert not matches(SENDING, {"url": URL, "section": "Typing notifications", "quote": "nothing here"})


def test_a_passage_also_matches_when_it_holds_the_quote():
    split_off = {**SENDING, "heading_path": "Typing notifications"}  # say, a long section split in two
    assert matches(split_off, {"url": URL, "section": "Somewhere else", "quote": "**Turn it off**"})


def test_retrieval_hit_is_an_expected_source_among_the_passages_searched():
    assert retrieval_hit("answerable", [OTHER, SENDING], EXPECTED, "retrieval") is True
    assert retrieval_hit("answerable", [OTHER, INTRO], EXPECTED, "retrieval") is False
    assert retrieval_hit("answerable", [], EXPECTED, "full_context") is None  # the model read everything
    assert retrieval_hit("decline", [OTHER], [], "retrieval") is None


def test_a_citation_is_right_when_one_is_expected_and_none_is_from_another_article():
    assert citation_correct("answerable", "answer", [SENDING, INTRO], EXPECTED) is True  # same article, other section
    assert citation_correct("answerable", "answer", [SENDING, OTHER], EXPECTED) is False  # an unrelated article
    assert citation_correct("answerable", "partial", [INTRO], EXPECTED) is False  # right article, wrong section
    assert citation_correct("answerable", "answer", [], EXPECTED) is False
    assert citation_correct("off_topic", "answer", [], []) is None


def test_a_reply_that_isnt_an_answer_has_no_source_to_get_wrong():
    """So a clarifying question on an answerable question fails as a wrong answer, not a wrong citation."""
    assert citation_correct("answerable", "clarify", [], EXPECTED) is None
    assert citation_correct("answerable", "decline_not_covered", [], EXPECTED) is None
    question = {"type": "answerable", "expected_sources": EXPECTED, "expected_option": []}
    scores = score(
        question, mode="retrieval", kind="clarify", retrieved=[SENDING], citations=[], clarify_options=["A", "B"],
        judge_verdict=None,
    )  # fmt: skip
    assert scores.failure_type == "wrong_answer"


@pytest.mark.parametrize(
    ("qtype", "kind", "correct"),
    [
        ("decline", "decline_not_covered", True),
        ("decline", "decline_off_topic", True),
        ("off_topic", "answer", False),
        ("off_topic", "clarify", False),
        ("answerable", "answer", None),
    ],
)
def test_a_decline_is_correct_for_a_question_the_help_center_doesnt_cover(qtype, kind, correct):
    assert decline_correct(qtype, kind) is correct


@pytest.mark.parametrize(
    ("options", "chosen"),
    [
        (["Your password", "Your email"], "Your password"),
        (["Change the color of a channel"], "Change the color of a channel"),
        (["Notifications", "Email"], None),  # too vague to hold "desktop notifications"
        (["Passwords"], None),  # whole words only
        (["Anything at all"], None),  # a blank accepted phrasing matches nothing
        (None, None),
    ],
)
def test_the_option_chosen_is_the_first_holding_an_expected_phrasing(options, chosen):
    expected = ["password", "the color of a channel", "desktop notifications", " "]
    assert chosen_option(options, expected) == chosen


def failure(qtype="answerable", kind="answer", *, clarified=None, hit=True, cited=True, verdict="correct"):
    return failure_type(
        qtype, kind, clarified=clarified, retrieval_hit=hit, citation_correct=cited, judge_verdict=verdict
    )


def test_failure_types_come_in_the_prds_order():
    assert failure("decline", "answer", hit=False, cited=False, verdict=None) == "answered_should_decline"
    assert failure(kind="decline_not_covered", hit=False, cited=False, verdict=None) == "declined_answerable"
    assert failure(hit=False, cited=False, verdict="incorrect") == "retrieval_miss"
    assert failure(cited=False, verdict="incorrect") == "wrong_citation"
    assert failure(verdict="incorrect") == "wrong_answer"
    assert failure(verdict=None) == "wrong_answer"  # an answer the judge never saw isn't correct
    assert failure() is None
    assert failure("off_topic", "decline_off_topic") is None


def test_an_ambiguous_question_fails_unless_the_bot_asked_with_the_expected_meaning():
    assert failure("ambiguous", clarified=False) == "wrong_answer"
    assert failure("ambiguous", clarified=True) is None


def test_full_context_mode_has_no_retrieval_miss():
    assert failure(hit=None) is None


def test_score_gathers_every_mechanical_score():
    question = {"type": "ambiguous", "expected_sources": EXPECTED, "expected_option": ["sending"]}
    scores = score(
        question,
        mode="retrieval",
        kind="answer",
        retrieved=[SENDING],
        citations=[SENDING],
        clarify_options=["Sending them", "Seeing them"],
        judge_verdict="correct",
    )
    assert (scores.retrieval_hit, scores.citation_correct, scores.decline_correct) == (True, True, None)
    assert scores.clarified is True and scores.failure_type is None


def row(qtype, kind, **scores):
    base = {
        "type": qtype,
        "kind": kind,
        "judge_verdict": None,
        "clarified": None,
        "retrieval_hit": None,
        "citation_correct": None,
        "decline_correct": None,
        "failure_type": None,
        "swapped": False,
    }
    return {**base, **scores}


def test_the_summary_counts_each_measure_over_its_own_questions():
    rows = [
        row("answerable", "answer", judge_verdict="correct", retrieval_hit=True, citation_correct=True),
        row("answerable", "decline_not_covered", retrieval_hit=True, citation_correct=False,
            failure_type="declined_answerable", swapped=True),
        row("partial", "partial", judge_verdict="incorrect", retrieval_hit=False, citation_correct=True,
            failure_type="retrieval_miss"),
        row("ambiguous", "answer", judge_verdict="correct", clarified=False, retrieval_hit=True,
            citation_correct=True, failure_type="wrong_answer"),
        row("decline", "decline_not_covered", decline_correct=True),
        row("off_topic", "answer", decline_correct=False, failure_type="answered_should_decline"),
    ]  # fmt: skip
    found = summarize(rows, mode="retrieval")
    assert (found.correct_answers.passed, found.correct_answers.total) == (1, 4)
    assert (found.right_source.passed, found.right_source.total) == (3, 4)
    assert (found.correct_declines.passed, found.correct_declines.total) == (1, 2)
    assert (found.wrongly_declined.passed, found.wrongly_declined.total) == (1, 3)  # ambiguous isn't counted
    assert (found.right_place.passed, found.right_place.total) == (3, 4)
    assert found.failures == {"declined_answerable": 1, "retrieval_miss": 1, "wrong_answer": 1,
                              "answered_should_decline": 1}  # fmt: skip
    assert found.swapped == 1
    assert summarize(rows, mode="full_context").right_place is None
