"""Decision runs (PRD 5.4; QA plan 4.1): the median and range of each measure, the settings
check, the grading queue and the rules for starting one."""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from citemark.evals.decision import (
    SETTINGS,
    Decision,
    DecisionError,
    QueueEntry,
    Spread,
    committed,
    judged_differently,
    mismatched,
    split,
    spread,
    unfinished,
)
from citemark.evals.scoring import Measure


def measures(*passed: int, total: int = 40) -> list[Measure]:
    return [Measure(count, total) for count in passed]


# --- The median and the range ---


def test_the_median_is_the_middle_run_and_the_range_its_lowest_and_highest():
    found = spread(measures(35, 37, 36))
    assert found == Spread(median=36, low=35, high=37, total=40)
    assert not found.same


def test_three_equal_runs_are_the_same_in_all_three():
    found = spread(measures(36, 36, 36))
    assert found == Spread(36, 36, 36, 40)
    assert found.same


def test_two_equal_runs_set_the_median():
    assert spread(measures(37, 35, 35)) == Spread(35, 35, 37, 40)


def test_a_measure_no_run_measured_has_no_median():
    assert spread([None, None, None]) is None  # retrieval in full-context mode


@pytest.mark.parametrize(
    "found",
    [
        [Measure(35, 40), Measure(36, 41), Measure(36, 40)],
        [Measure(35, 40), None, Measure(36, 40)],
        measures(35, 36),
    ],
    ids=["different totals", "one run unmeasured", "even count"],
)
def test_runs_that_cant_share_a_median_are_refused(found):
    with pytest.raises(DecisionError):
        spread(found)


# --- The settings ---


def run(**changed):
    settings = {name: f"same {name}" for name in SETTINGS}
    settings["retrieval_config"] = {"top_k": 5, "rerank": True}
    return SimpleNamespace(**(settings | changed))


def test_identical_settings_match():
    assert mismatched([run(), run(), run()]) == []


def test_each_differing_setting_is_named():
    assert mismatched([run(), run(model="other"), run(git_sha="other")]) == ["model", "git_sha"]


def test_retrieval_settings_compare_by_value():
    same = {"rerank": True, "top_k": 5}  # keys in another order
    assert mismatched([run(), run(retrieval_config=same), run()]) == []
    assert mismatched([run(), run(retrieval_config={"top_k": 5, "rerank": False}), run()]) == ["retrieval_config"]


# --- The grading queue ---


def test_only_questions_the_judge_graded_differently_go_to_the_queue():
    verdicts = {
        "Q001": ["correct", "incorrect", "correct"],
        "Q002": ["correct", "correct", "correct"],
        "Q003": [None, "correct", "correct"],  # declined once: scored mechanically, not a different verdict
        "Q004": [None, None, None],
        "Q005": [None, "incorrect", "correct"],
    }
    assert judged_differently(verdicts) == {"Q001", "Q005"}


def test_a_decision_is_provisional_until_every_answer_in_the_queue_is_graded():
    queue = [QueueEntry("Q001", 1, uuid.uuid4(), "correct"), QueueEntry("Q001", 2, uuid.uuid4(), None)]
    found = Decision(uuid.uuid4(), [], {}, queue, Decimal(0), Decimal(0))
    assert found.provisional and found.waiting == queue[1:]
    graded = Decision(uuid.uuid4(), [], {}, queue[:1], Decimal(0), Decimal(0))
    assert not graded.provisional


# --- Starting and finishing ---


def test_a_decision_run_starts_only_from_a_known_commit_with_no_uncommitted_changes():
    assert committed("4f2a9c1") == "4f2a9c1"
    with pytest.raises(DecisionError, match="uncommitted changes"):
        committed("4f2a9c1-dirty")
    with pytest.raises(DecisionError, match="which commit"):
        committed("unknown")


def test_each_run_gets_a_third_of_the_budget_rounded_down():
    assert split(Decimal("6")) == Decimal("2")
    assert split(Decimal("5")) == Decimal("1.666666")
    assert split(Decimal("5")) * 3 <= Decimal("5")
    assert split(Decimal("0.01")) == Decimal("0.003333")


def statuses(*given: str) -> list[SimpleNamespace]:
    return [SimpleNamespace(id=uuid.uuid4(), status=status) for status in given]


def test_the_runs_left_to_finish_are_those_not_done():
    runs = statuses("done", "failed", "queued")
    assert unfinished(runs) == runs[1:]
    assert unfinished(statuses("done", "done", "done")) == []


@pytest.mark.parametrize(
    ("status", "message"), [("over_budget", "stopped at its budget"), ("cancelled", "was cancelled")]
)
def test_a_group_with_a_run_that_cant_be_finished_cant_be_completed(status, message):
    with pytest.raises(DecisionError, match=f"Run 2 of 3 {message}"):
        unfinished(statuses("done", status, "queued"))


# --- What the command prints ---


def printed(capsys, queue, measures_found) -> str:
    from citemark.cli import _print_decision

    runs = [SimpleNamespace(model="claude-haiku-5-5", mode="retrieval", git_sha="4f2a9c1e8b7d6a5f")] * 3
    _print_decision(Decision(uuid.uuid4(), runs, measures_found, queue, Decimal("1.2"), Decimal("6")))
    return capsys.readouterr().out


MEASURED = {
    "correct_answers": Spread(36, 35, 37, 40),
    "right_source": Spread(38, 38, 38, 40),
    "correct_declines": Spread(9, 9, 10, 10),
    "wrongly_declined": Spread(1, 0, 1, 37),
    "right_place": None,
}


def test_the_command_shows_each_median_with_its_range(capsys):
    out = printed(capsys, [], MEASURED)
    assert "Correct answers: 36 of 40 (median) \u00b7 3 runs: 35\u201337" in out
    assert "Right source shown: 38 of 40 (median) \u00b7 Same in all 3 runs" in out
    assert "Looked in the right place: n/a" in out
    assert "commit 4f2a9c1e8b7d." in out
    assert "nothing waits for your grade" in out


def test_the_command_lists_the_answers_waiting_without_the_judges_verdicts(capsys):
    queue = [
        QueueEntry("Q001", 1, uuid.uuid4(), None),
        QueueEntry("Q001", 2, uuid.uuid4(), None),
        QueueEntry("Q001", 3, uuid.uuid4(), None),
        QueueEntry("Q007", 1, uuid.uuid4(), "correct"),
        QueueEntry("Q007", 3, uuid.uuid4(), None),
    ]
    out = printed(capsys, queue, MEASURED)
    assert "Waiting for your grade: Q001 (runs 1, 2 and 3), Q007 (run 3)." in out
    assert "Grade them with: citemark grade " in out
    assert "provisional" in out
    assert "incorrect" not in out
    # the correct-answers range would hint at how the judge split, so it waits too
    assert "Correct answers: shown once you've graded" in out and "36 of 40" not in out
    assert "Right source shown: 38 of 40" in out


def test_the_command_says_when_the_queue_is_graded(capsys):
    out = printed(capsys, [QueueEntry("Q001", 1, uuid.uuid4(), "correct")], MEASURED)
    assert "Every answer in the queue is graded" in out and "provisional" not in out
    assert "Correct answers: 36 of 40 (median)" in out


def test_your_grade_assigns_the_failure_type_again():
    from citemark.evals.runner import summary_row

    question = SimpleNamespace(type="answerable", expected_option=None)
    scores = {"retrieval_hit": True, "citation_correct": True, "decline_correct": None, "swapped": False}
    judged_wrong = SimpleNamespace(
        kind="answer", judge_verdict="incorrect", failure_type="wrong_answer", clarify_options=None, **scores
    )
    row = summary_row(judged_wrong, question, verdict="correct")
    assert (row["judge_verdict"], row["failure_type"]) == ("correct", None)
    judged_right = SimpleNamespace(
        kind="answer", judge_verdict="correct", failure_type=None, clarify_options=None, **scores
    )
    row = summary_row(judged_right, question, verdict="incorrect")
    assert (row["judge_verdict"], row["failure_type"]) == ("incorrect", "wrong_answer")
