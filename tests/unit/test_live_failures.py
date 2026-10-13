"""What fails the nightly live run (QA plan 3.2): a call that errors, no answer arriving with its
sources, or a known decline answered. Another change from what's expected is shown, not failed."""

from decimal import Decimal

from citemark.evals.live import QUESTIONS, Asked, failures

TYPING, BIGGER, EMAILS, SPOILER, AUSTRALIA = QUESTIONS


def asked(*replies: tuple[str, int]) -> list[Asked]:
    """The five questions' replies, as (kind, sources), in QUESTIONS order."""
    return [
        Asked(known, kind, sources, Decimal("0.001")) for known, (kind, sources) in zip(QUESTIONS, replies, strict=True)
    ]


AS_RECORDED = (("answer", 2), ("answer", 1), ("clarify", 0), ("decline_not_covered", 0), ("decline_off_topic", 0))


def test_replies_as_recorded_pass():
    assert failures(asked(*AS_RECORDED)) == []


def test_a_known_decline_answered_fails():
    found = failures(asked(*AS_RECORDED[:3], ("answer", 1), ("partial", 1)))
    assert found == [
        f"{SPOILER.question} It's a known decline, and it was answered.",
        f"{AUSTRALIA.question} It's a known decline, and it was answered.",
    ]


def test_no_answer_with_its_sources_fails():
    """Citations stopped arriving: an answer without sources counts as none."""
    found = failures(asked(("decline_not_covered", 0), ("answer", 0), *AS_RECORDED[2:]))
    assert found == ["No answer arrived with its sources."]


def test_one_answer_declined_is_shown_beside_what_was_expected_but_doesnt_fail():
    replies = asked(("decline_not_covered", 0), *AS_RECORDED[1:])
    assert failures(replies) == []
    assert replies[0].line() == f"[decline_not_covered] (expected: answer) {TYPING.question}"
    assert replies[1].line() == f"[answer, 1 source] {BIGGER.question}"
    assert asked(*AS_RECORDED)[0].line() == f"[answer, 2 sources] {TYPING.question}"
    twice = Asked(TYPING, "partial", 1, Decimal("0.001"), calls=2)
    assert twice.line() == f"[partial, 1 source, 2 model calls] (expected: answer) {TYPING.question}"


def test_an_error_fails_with_what_went_wrong():
    failed = Asked(EMAILS, "error", 0, Decimal(0), ("The call to x failed (APIStatusError).",))
    replies = [*asked(*AS_RECORDED)[:2], failed]
    assert failures(replies) == [f"{EMAILS.question} The call failed: The call to x failed (APIStatusError)."]
