"""Your grading (PRD 5.4; QA plan 4.2): agreement with the judge, the re-check sample, and the
answer card, which shows what the judge read and nothing it said."""

import uuid

import pytest

from citemark.evals.grading import GradingError, Item, Sheet, agree, sampled, to_grade

# --- Agreement ---


def test_agreement_counts_the_answers_you_and_the_judge_graded_the_same():
    found = agree(
        [
            ("Q001", None, "correct", "correct", "It has every key fact."),
            ("Q002", None, "correct", "incorrect", "It misses the second step."),
            ("Q003", None, "incorrect", "correct", "It has every key fact."),
            ("Q004", None, "incorrect", "incorrect", "It contradicts the help center."),
        ]
    )
    assert (found.agreed, found.graded) == (2, 4)
    assert [(item.question, item.yours, item.judges) for item in found.disagreements] == [
        ("Q002", "correct", "incorrect"),
        ("Q003", "incorrect", "correct"),
    ]
    assert found.disagreements[0].reason == "It misses the second step."


def rows(agreed: int, graded: int) -> list[tuple]:
    return [(f"Q{n:03}", None, "correct", "correct" if n < agreed else "incorrect", "") for n in range(graded)]


@pytest.mark.parametrize(
    ("agreed", "graded", "percent", "met"),
    [(40, 40, 100, True), (36, 40, 90, True), (9, 10, 90, True), (37, 40, 92, True), (35, 39, 89, False)],
)
def test_the_percent_rounds_down_and_the_target_is_compared_exactly(agreed, graded, percent, met):
    found = agree(rows(agreed, graded))
    assert (found.percent, found.meets_target) == (percent, met)


def test_just_under_90_percent_misses_the_target_though_it_would_round_to_90():
    found = agree(rows(899, 1000))  # 89.9%
    assert found.percent == 89 and not found.meets_target


def test_no_graded_answers_give_no_agreement():
    with pytest.raises(GradingError):
        agree([])


# --- The re-check sample ---


def test_a_sample_is_the_same_every_time_whatever_order_the_answers_come_in():
    run = uuid.uuid4()
    answers = [uuid.uuid4() for _ in range(40)]
    first = sampled(run, answers, 10)
    assert len(first) == 10 and first <= set(answers)
    assert sampled(run, list(reversed(answers)), 10) == first


def test_another_run_gets_another_sample():
    answers = [uuid.uuid4() for _ in range(40)]
    assert sampled(uuid.uuid4(), answers, 10) != sampled(uuid.uuid4(), answers, 10)


def test_a_sample_bigger_than_the_run_is_the_whole_run():
    answers = [uuid.uuid4() for _ in range(4)]
    assert sampled(uuid.uuid4(), answers, 10) == set(answers)


# --- A sheet ---


def item(question="Q001", *, grade=None, locked=False, **changed) -> Item:
    fields = {
        "result_id": uuid.uuid4(),
        "question": question,
        "run": None,
        "qtype": "answerable",
        "asked": "How do I stop people seeing that I'm typing?",
        "option": None,
        "expected_answer": ["Turn off typing notifications", "Gear icon, then Personal settings"],
        "sources": [{"url": "https://zulip.com/help/typing", "section": "Disable", "quote": "you can configure"}],
        "uncovered_part": None,
        "answer": "Turn it off in your settings.\n\nGo to Personal settings.",
        "grade": grade,
        "note": "",
        "locked": locked,
    }
    return Item(**(fields | changed))


def test_a_sheet_is_complete_once_every_answer_is_graded_and_locked_once_every_grade_is():
    sheet = Sheet(uuid.uuid4(), "run", "judge.v1", [item(grade="correct"), item("Q002")])
    assert sheet.graded == 1 and not sheet.complete and not sheet.locked
    sheet = Sheet(uuid.uuid4(), "run", "judge.v1", [item(grade="correct"), item("Q002", grade="incorrect")])
    assert sheet.complete and not sheet.locked
    sheet = Sheet(uuid.uuid4(), "run", "judge.v1", [item(grade="correct", locked=True)])
    assert sheet.complete and sheet.locked


# --- What you type and what you see ---


@pytest.mark.parametrize(
    ("typed", "choice"),
    [
        ("c", "correct"),
        (" Correct ", "correct"),
        ("I", "incorrect"),
        ("s", "skip"),
        ("q", "quit"),
        ("x", None),
        ("", None),
    ],
)
def test_a_grade_is_typed_as_a_letter_or_a_word(typed, choice):
    from citemark.cli import _choice

    assert _choice(typed) == choice


def test_the_card_shows_what_the_judge_read():
    from citemark.cli import _card

    shown = _card(
        item("Q014", qtype="partial", uncovered_part="hiding it from one person", option="New login emails", run=2),
        3,
        40,
    )
    assert "Answer 3 of 40: Q014, run 2 (partial)" in shown
    assert "Question: How do I stop people seeing that I'm typing?" in shown
    assert "the customer chose: New login emails" in shown
    assert "    - Turn off typing notifications" in shown
    assert "Not covered by the help center: hiding it from one person" in shown
    assert '"you can configure" (https://zulip.com/help/typing, Disable)' in shown
    assert "    Turn it off in your settings.\n\n    Go to Personal settings." in shown
    assert "judge" not in shown.lower() and "grade so far" not in shown


def test_the_card_shows_your_own_grade_when_you_look_again():
    from citemark.cli import _card

    shown = _card(item(grade="incorrect", note="misses the mobile steps"), 1, 1)
    assert "Your grade so far: incorrect (misses the mobile steps)" in shown


def test_the_answers_to_grade_are_those_without_a_grade_or_with_again_those_not_locked():
    ungraded, graded = item("Q001"), item("Q002", grade="correct")
    sheet = Sheet(uuid.uuid4(), "run", "judge.v1", [ungraded, graded])
    assert to_grade(sheet) == [ungraded]
    assert to_grade(sheet, again=True) == [ungraded, graded]
    locked = Sheet(uuid.uuid4(), "run", "judge.v1", [item(grade="correct", locked=True)])
    assert to_grade(locked) == []
    with pytest.raises(GradingError, match="locked"):
        to_grade(locked, again=True)


# --- What the command prints once the sheet is complete ---


def printed_agreement(capsys, found, kind="run") -> str:
    from citemark.cli import _print_agreement

    _print_agreement(found, Sheet(uuid.uuid4(), kind, "judge.v1", []))
    return capsys.readouterr().out


def test_the_command_shows_the_agreement_and_each_disagreement_with_the_judges_reason(capsys):
    found = agree([*rows(36, 40)[:-1], ("Q039", None, "correct", "incorrect", "It misses the mobile steps.")])
    out = printed_agreement(capsys, found)
    assert "You and the judge agreed on 36 of 40 answers (90%, rounded down). The 90% target is met." in out
    assert "Q039: you said correct, the judge said incorrect. Its reason: It misses the mobile steps." in out
    assert "isn't trusted yet" not in out


def test_under_the_target_the_command_says_to_fix_the_rubric_and_measure_on_fresh_answers(capsys):
    out = printed_agreement(capsys, agree(rows(8, 10)), kind="sample")
    assert "agreed on 8 of 10 sampled answers (80%, rounded down). The 90% target is not met." in out
    assert "isn't trusted yet" in out and "fresh run's answers" in out


def test_the_command_refuses_an_id_that_isnt_one():
    from typer.testing import CliRunner

    from citemark.cli import app

    found = CliRunner().invoke(app, ["grade", "Q012"])
    assert found.exit_code == 1 and "Q012 isn't a run ID" in found.output
