"""Decision runs (PRD 5.4; QA plan 4.1 and 4.2): three runs sharing a group, their medians and
ranges, the grading queue, and the refusals that keep a decision honest.

The scripted answerer and judge from the runner's tests make each case exact and free. A judge
that changes its verdict from run to run stands in for the real one's variation.
"""

from decimal import Decimal

import pytest
from scripted_run import (
    QUESTIONS,
    SCRIPT,
    SHA,
    Scripted,
    Varying,
    finished,
    frozen_set,
    grouped,
    no_wait,
    results,
    services,
)
from sqlalchemy import func, update

from citemark.db.models import HumanGrade, TestResult, TestRun
from citemark.evals.decision import (
    DecisionError,
    Spread,
    decision,
    find_group,
    finish_group,
    group_runs,
    mismatched,
)
from citemark.evals.runner import RunError, run_tests

NOWHERE = "postgresql://nobody@localhost:1/none"  # a closed port


async def grade(session, run: TestRun, question: str, verdict: str, *, locked: bool = True) -> None:
    """Your grade, locked as completing its sheet would lock it (PRD Q18)."""
    found = (await results(session, run.id))[question]
    session.add(HumanGrade(test_result_id=found.id, verdict=verdict, locked_at=func.now() if locked else None))
    await session.commit()


# --- Starting ---


@pytest.mark.anyio
async def test_a_decision_run_is_three_runs_with_identical_settings_and_a_third_of_the_budget_each(session, tmp_path):
    runs = await grouped(session, frozen_set(tmp_path), budget="6")
    assert len(runs) == 3 and len({run.decision_group for run in runs}) == 1
    assert runs[0].decision_group is not None
    assert mismatched(runs) == []
    assert [run.budget_usd for run in runs] == [Decimal(2)] * 3
    assert [run.status for run in runs] == ["queued"] * 3
    assert [run.id for run in await group_runs(session, runs[0].decision_group)] == [run.id for run in runs]


@pytest.mark.anyio
async def test_a_decision_run_wont_start_from_uncommitted_changes(session, tmp_path):
    with pytest.raises(DecisionError, match="uncommitted changes"):
        await grouped(session, frozen_set(tmp_path), sha=f"{SHA}-dirty")


@pytest.mark.anyio
async def test_a_decision_run_is_found_from_its_group_or_any_of_its_runs(session, tmp_path):
    runs = await grouped(session, frozen_set(tmp_path))
    group = runs[0].decision_group
    assert await find_group(session, group) == group
    assert await find_group(session, runs[2].id) == group


@pytest.mark.anyio
async def test_a_run_goes_on_only_from_the_commit_it_started_on(session, sessions, tmp_path):
    runs = await grouped(session, frozen_set(tmp_path))
    with pytest.raises(RunError, match=f"started from commit {SHA}, and this is 9e8d7c6"):
        await run_tests(runs[0].id, sessions=sessions, services=services(Scripted(SCRIPT)), sha="9e8d7c6", parallel=1)


# --- The medians, the ranges and the queue ---


@pytest.mark.anyio
async def test_each_measure_gets_its_median_and_range_and_a_disagreement_goes_to_the_queue(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({"Q001": {2}}))
    found = await decision(session, runs[0].decision_group)
    assert [run.status for run in found.runs] == ["done"] * 3
    assert found.measures["correct_answers"] == Spread(median=3, low=2, high=3, total=3)
    assert found.measures["right_source"] == Spread(3, 3, 3, 3)
    assert found.measures["correct_declines"] == Spread(2, 2, 2, 2)
    assert found.measures["wrongly_declined"] == Spread(0, 0, 0, 2)
    assert found.measures["right_place"] == Spread(3, 3, 3, 3)
    assert [(entry.question, entry.run, entry.grade) for entry in found.queue] == [
        ("Q001", 1, None),
        ("Q001", 2, None),
        ("Q001", 3, None),
    ]
    assert found.provisional


@pytest.mark.anyio
async def test_a_judge_that_agrees_with_itself_leaves_nothing_to_grade(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({}))
    found = await decision(session, runs[0].decision_group)
    assert found.queue == [] and not found.provisional
    assert found.measures["correct_answers"].same


@pytest.mark.anyio
async def test_your_grade_replaces_the_judges_on_a_question_it_graded_differently(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({"Q001": {2}}))  # judge: 3, 2, 3
    await grade(session, runs[0], "Q001", "incorrect")  # the judge said correct
    await grade(session, runs[1], "Q001", "correct")  # the judge said incorrect
    await grade(session, runs[2], "Q001", "incorrect")
    found = await decision(session, runs[0].decision_group)
    assert found.measures["correct_answers"] == Spread(median=2, low=2, high=3, total=3)  # yours: 2, 3, 2
    assert not found.provisional


@pytest.mark.anyio
async def test_until_its_graded_the_judges_verdict_counts(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({"Q001": {2}}))
    await grade(session, runs[0], "Q001", "incorrect")  # run 2's judge said incorrect, run 3's correct
    found = await decision(session, runs[0].decision_group)
    assert found.measures["correct_answers"] == Spread(median=2, low=2, high=3, total=3)
    assert [entry.run for entry in found.waiting] == [2, 3]


@pytest.mark.anyio
async def test_a_grade_counts_only_once_its_locked(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({"Q001": {2}}))
    for run in runs:  # every answer graded, but the sheet never completed and locked
        await grade(session, run, "Q001", "incorrect", locked=False)
    found = await decision(session, runs[0].decision_group)
    assert found.measures["correct_answers"] == Spread(median=3, low=2, high=3, total=3)  # still the judge's
    assert [entry.run for entry in found.waiting] == [1, 2, 3] and found.provisional


@pytest.mark.anyio
async def test_your_grade_elsewhere_doesnt_replace_the_judges(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({}))
    await grade(session, runs[0], "Q002", "incorrect")  # the judge said correct in all three (PRD Q16)
    found = await decision(session, runs[0].decision_group)
    assert found.measures["correct_answers"] == Spread(3, 3, 3, 3)


@pytest.mark.anyio
async def test_a_decision_reads_results_as_they_are_now(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({}))
    loaded = await results(session, runs[1].id)  # this session now holds them
    async with sessions() as other, other.begin():  # re-judged elsewhere, as a judge.v2 would (plan 5.3)
        changed = update(TestResult).where(TestResult.id == loaded["Q001"].id).values(judge_verdict="incorrect")
        await other.execute(changed)
    found = await decision(session, runs[0].decision_group)
    assert found.measures["correct_answers"] == Spread(3, 2, 3, 3)


# --- Refusals ---


@pytest.mark.parametrize(
    ("setting", "value"),
    [("prompt_version", "answer.v2+tools.v1"), ("git_sha", "9e8d7c6"), ("retrieval_config", {"rerank": False})],
)
@pytest.mark.anyio
async def test_a_group_whose_settings_differ_is_refused(session, sessions, tmp_path, setting, value):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({}))
    await session.execute(update(TestRun).where(TestRun.id == runs[1].id).values({setting: value}))
    with pytest.raises(DecisionError, match=f"differ in {setting}"):
        await decision(session, runs[0].decision_group)


@pytest.mark.anyio
async def test_a_group_with_an_unfinished_run_gives_no_decision_and_says_how_to_finish_it(session, tmp_path):
    runs = await grouped(session, frozen_set(tmp_path))
    with pytest.raises(DecisionError, match=f"Run 1 of 3 hasn't finished.*citemark test resume {runs[0].id}"):
        await decision(session, runs[0].decision_group)


@pytest.mark.anyio
async def test_a_group_without_three_runs_is_refused(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({}))
    await session.execute(update(TestRun).where(TestRun.id == runs[2].id).values(decision_group=None))
    with pytest.raises(DecisionError, match="has 2 runs, not 3"):
        await decision(session, runs[0].decision_group)


# --- Finishing ---


@pytest.mark.anyio
async def test_a_stopped_group_finishes_its_runs_in_turn_without_asking_anything_twice(session, sessions, tmp_path):
    runs = await grouped(session, frozen_set(tmp_path))
    group = runs[0].decision_group
    down = Scripted(SCRIPT, failing=frozenset({QUESTIONS[3]["question"]}))
    ended = await finish_group(group, sessions=sessions, services=services(down), sha=SHA, parallel=1, sleep=no_wait)
    assert [(run.id, outcome.status) for run, outcome in ended] == [(runs[0].id, "failed")]  # runs 2 and 3 wait
    answered_before = len(await results(session, runs[0].id))

    answerer = Scripted(SCRIPT)
    ended = await finish_group(group, sessions=sessions, services=services(answerer), sha=SHA, parallel=1)
    assert [(run.id, outcome.status) for run, outcome in ended] == [(run.id, "done") for run in runs]
    follow_ups = 2  # the ambiguous question's, in runs 2 and 3; run 1 asked it before it stopped
    assert len(answerer.asked) == len(QUESTIONS) - answered_before + 2 * len(QUESTIONS) + follow_ups
    assert len((await decision(session, group)).runs) == 3


@pytest.mark.anyio
async def test_a_finished_group_has_nothing_left_to_run(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({}))
    answerer = Scripted(SCRIPT)
    ended = await finish_group(runs[0].decision_group, sessions=sessions, services=services(answerer), sha=SHA)
    assert ended == [] and answerer.asked == []


@pytest.mark.anyio
async def test_a_group_with_a_run_stopped_at_its_budget_cant_be_finished(session, sessions, tmp_path):
    runs = await grouped(session, frozen_set(tmp_path))
    await session.execute(update(TestRun).where(TestRun.id == runs[1].id).values(status="over_budget"))
    await session.commit()
    answerer = Scripted(SCRIPT)
    with pytest.raises(DecisionError, match="Run 2 of 3 stopped at its budget"):
        await finish_group(runs[0].decision_group, sessions=sessions, services=services(answerer), sha=SHA)
    assert answerer.asked == []


@pytest.mark.anyio
async def test_only_the_named_run_is_resumed_although_marked_running(session, sessions, tmp_path):
    runs = await grouped(session, frozen_set(tmp_path))
    await session.execute(update(TestRun).where(TestRun.id.in_([runs[0].id, runs[1].id])).values(status="running"))
    await session.commit()
    group = runs[0].decision_group
    with pytest.raises(RunError, match=f"Run {runs[1].id} is marked as running"):
        await finish_group(
            group, sessions=sessions, services=services(Scripted(SCRIPT)), sha=SHA, force=runs[0].id, parallel=1
        )
    assert [run.status for run in await group_runs(session, group)] == ["done", "running", "queued"]


@pytest.mark.anyio
async def test_a_group_whose_settings_differ_is_refused_before_anything_is_asked(session, sessions, tmp_path):
    runs = await grouped(session, frozen_set(tmp_path))
    await session.execute(update(TestRun).where(TestRun.id == runs[2].id).values(retrieval_config={"rerank": False}))
    await session.commit()
    answerer = Scripted(SCRIPT)
    with pytest.raises(DecisionError, match="differ in retrieval_config"):
        await finish_group(runs[0].decision_group, sessions=sessions, services=services(answerer), sha=SHA)
    assert answerer.asked == []


# --- The command line ---


def invoke(tmp_path, monkeypatch, *args: str):
    from typer.testing import CliRunner

    from citemark.cli import app
    from citemark.settings import get_settings

    monkeypatch.setenv("ANTHROPIC_API_KEY", "unused")
    monkeypatch.setenv("VOYAGE_API_KEY", "unused")
    monkeypatch.setenv("DATABASE_URL", NOWHERE)  # if a check were missed, the command still couldn't write anywhere
    get_settings.cache_clear()
    try:
        path = frozen_set(tmp_path)
        return CliRunner().invoke(app, ["test", "run", str(path), "--company", "Zulip", "--budget", "1", *args])
    finally:
        get_settings.cache_clear()


def test_the_command_takes_one_run_or_three(tmp_path, monkeypatch):
    found = invoke(tmp_path, monkeypatch, "--runs", "2", "--yes")
    assert found.exit_code == 1 and "--runs takes 1 for a single run, or 3 for a decision run" in found.output


def test_the_command_refuses_a_decision_run_from_uncommitted_changes_before_calling_anything(tmp_path, monkeypatch):
    monkeypatch.setenv("CITEMARK_GIT_SHA", "4f2a9c1-dirty")
    found = invoke(tmp_path, monkeypatch, "--runs", "3", "--yes")
    assert found.exit_code == 1 and "can't start from uncommitted changes" in found.output
