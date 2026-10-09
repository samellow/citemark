"""Your grading (PRD 5.4; QA plan 4.2) against the database: what a sheet holds, recording and
locking grades, agreement once a sheet is complete, and a decision run's queue.

The runs come from the scripted answerer and judge, so the judge's verdicts are known: free,
and exact.
"""

import uuid

import pytest
from scripted_run import SCRIPT, SHA, Scripted, Varying, finished, frozen_set, results, services, started
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError

from citemark.db.models import HumanGrade, TestRun
from citemark.evals.decision import DecisionError, decision
from citemark.evals.grading import GradingError, agreement, lock, record, sheet
from citemark.evals.runner import run_tests


async def done_run(session, sessions, tmp_path, judge=None) -> TestRun:
    run = await started(session, frozen_set(tmp_path), Scripted(SCRIPT))
    given = services(Scripted(SCRIPT), judge=judge) if judge else services(Scripted(SCRIPT))
    await run_tests(run.id, sessions=sessions, services=given, parallel=1, sha=SHA)
    await session.refresh(run)
    return run


async def grade_all(session, graded, verdicts: dict[str, str]) -> None:
    for item in graded.items:
        await record(session, item.result_id, verdicts[item.question])
    await session.commit()


# --- What a sheet holds ---


@pytest.mark.anyio
async def test_a_runs_sheet_holds_its_judged_answers_with_what_the_judge_read(session, sessions, tmp_path):
    run = await done_run(session, sessions, tmp_path)
    graded = await sheet(session, run.id)
    assert graded.kind == "run" and graded.rubric == "judge.v1"
    assert [item.question for item in graded.items] == ["Q001", "Q002", "Q003"]  # Q004 and Q005 were declined
    q002, q003 = graded.items[1], graded.items[2]
    assert q002.uncovered_part == "whether typing can be hidden from one specific person"
    assert q003.option == "New login emails" and q003.expected_answer[0].startswith("Gear icon")
    assert q003.answer == (await results(session, run.id))["Q003"].answer
    assert not hasattr(q003, "judge_verdict") and graded.graded == 0


@pytest.mark.anyio
async def test_a_sample_is_the_same_every_time_and_drawn_from_the_judged_answers(
    session, sessions, tmp_path, monkeypatch
):
    monkeypatch.setattr("citemark.evals.grading.SAMPLE", 2)  # 10 in use; the scripted run has 3 judged answers
    run = await done_run(session, sessions, tmp_path)
    first = await sheet(session, run.id, sample=True)
    again = await sheet(session, run.id, sample=True)
    assert first.kind == "sample" and len(first.items) == 2
    assert [item.result_id for item in first.items] == [item.result_id for item in again.items]
    assert {item.question for item in first.items} <= {"Q001", "Q002", "Q003"}


@pytest.mark.anyio
async def test_an_unfinished_run_isnt_graded(session, tmp_path):
    run = await started(session, frozen_set(tmp_path), Scripted(SCRIPT))
    with pytest.raises(GradingError, match="hasn't finished"):
        await sheet(session, run.id)


@pytest.mark.anyio
async def test_an_id_thats_neither_a_run_nor_a_decision_run_is_refused(session, tmp_path):
    with pytest.raises(DecisionError, match="There's no decision run"):
        await sheet(session, uuid.uuid4())


# --- Recording, locking and agreement ---


@pytest.mark.anyio
async def test_agreement_is_counted_once_the_sheet_is_complete(session, sessions, tmp_path):
    run = await done_run(session, sessions, tmp_path, judge=Varying({"Q002": {1}}))  # the judge fails Q002
    graded = await sheet(session, run.id)
    await grade_all(session, graded, {"Q001": "correct", "Q002": "correct", "Q003": "incorrect"})
    await lock(session, await sheet(session, run.id))
    found = await agreement(session, await sheet(session, run.id))
    assert (found.agreed, found.graded, found.percent, found.meets_target) == (1, 3, 33, False)
    assert [(item.question, item.yours, item.judges) for item in found.disagreements] == [
        ("Q002", "correct", "incorrect"),
        ("Q003", "incorrect", "correct"),
    ]
    assert found.disagreements[0].reason == "Scripted."


@pytest.mark.anyio
async def test_the_judges_verdicts_stay_hidden_until_the_sheet_is_complete_and_locked(session, sessions, tmp_path):
    run = await done_run(session, sessions, tmp_path)
    graded = await sheet(session, run.id)
    await record(session, graded.items[0].result_id, "correct")
    with pytest.raises(GradingError, match="once every answer"):
        await agreement(session, await sheet(session, run.id))
    with pytest.raises(GradingError, match="locks only once every answer"):
        await lock(session, await sheet(session, run.id))
    await grade_all(session, graded, {"Q001": "correct", "Q002": "correct", "Q003": "correct"})
    with pytest.raises(GradingError, match="graded and locked"):  # complete, but not yet locked
        await agreement(session, await sheet(session, run.id))


@pytest.mark.anyio
async def test_a_grade_can_change_until_the_sheet_is_complete(session, sessions, tmp_path):
    run = await done_run(session, sessions, tmp_path)
    first = (await sheet(session, run.id)).items[0]
    await record(session, first.result_id, "correct", "has the steps")
    await record(session, first.result_id, "incorrect", "the second step is wrong")
    changed = (await sheet(session, run.id)).items[0]
    assert (changed.grade, changed.note, changed.locked) == ("incorrect", "the second step is wrong", False)


@pytest.mark.anyio
async def test_once_locked_a_grade_cant_change_and_the_database_refuses_it_too(session, sessions, tmp_path):
    run = await done_run(session, sessions, tmp_path)
    graded = await sheet(session, run.id)
    await grade_all(session, graded, {"Q001": "correct", "Q002": "correct", "Q003": "correct"})
    await lock(session, await sheet(session, run.id))
    await session.commit()
    first = graded.items[0].result_id
    with pytest.raises(GradingError, match="locked"):
        await record(session, first, "incorrect")
    for statement in (
        update(HumanGrade).where(HumanGrade.test_result_id == first).values(verdict="incorrect"),
        delete(HumanGrade).where(HumanGrade.test_result_id == first),
    ):
        with pytest.raises(IntegrityError, match="locked when its grading sheet was completed"):
            async with session.begin_nested():
                await session.execute(statement)


@pytest.mark.anyio
async def test_completing_a_sample_locks_only_the_sample(session, sessions, tmp_path, monkeypatch):
    monkeypatch.setattr("citemark.evals.grading.SAMPLE", 2)
    run = await done_run(session, sessions, tmp_path)
    await grade_all(session, await sheet(session, run.id), dict.fromkeys(("Q001", "Q002", "Q003"), "correct"))
    sample = await sheet(session, run.id, sample=True)
    await lock(session, sample)
    whole = await sheet(session, run.id)
    assert {item.result_id for item in whole.items if item.locked} == {item.result_id for item in sample.items}
    assert whole.complete and not whole.locked  # the third grade can still change


# --- Grading at the command line ---


@pytest.mark.anyio
async def test_grading_records_each_grade_as_its_given_and_a_stop_loses_nothing(session, sessions, tmp_path):
    from citemark.cli import _grade_items

    run = await done_run(session, sessions, tmp_path)
    graded = await sheet(session, run.id)
    typed = iter(["maybe", "c", "has every step", "s", "i", "", "q"])
    shown: list[str] = []
    given = await _grade_items(sessions, graded.items, ask=lambda prompt: next(typed), echo=shown.append)
    assert given == 2
    assert "  Type c, i, s or q." in shown
    after = {item.question: (item.grade, item.note) for item in (await sheet(session, run.id)).items}
    assert after == {"Q001": ("correct", "has every step"), "Q002": (None, ""), "Q003": ("incorrect", "")}
    assert all("judge" not in line.lower() for line in shown)


@pytest.mark.anyio
async def test_looking_again_keeps_a_note_on_enter_and_removes_it_on_a_dash(session, sessions, tmp_path):
    from citemark.cli import _grade_items

    run = await done_run(session, sessions, tmp_path)
    graded = await sheet(session, run.id)
    await record(session, graded.items[0].result_id, "correct", "has every step")
    await record(session, graded.items[1].result_id, "correct", "a slip")
    await session.commit()
    typed = iter(["c", "", "i", "-", "q"])
    await _grade_items(sessions, (await sheet(session, run.id)).items, ask=lambda prompt: next(typed), echo=print)
    after = {item.question: (item.grade, item.note) for item in (await sheet(session, run.id)).items}
    assert after["Q001"] == ("correct", "has every step") and after["Q002"] == ("incorrect", "")


@pytest.mark.anyio
async def test_quitting_stops_at_once(session, sessions, tmp_path):
    from citemark.cli import _grade_items

    run = await done_run(session, sessions, tmp_path)
    typed = iter(["q"])
    given = await _grade_items(sessions, (await sheet(session, run.id)).items, ask=lambda p: next(typed), echo=print)
    assert given == 0 and (await sheet(session, run.id)).graded == 0


# --- A decision run's queue ---


@pytest.mark.anyio
async def test_a_decision_runs_sheet_is_its_queue_and_grading_it_settles_the_decision(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({"Q001": {2}}))
    group = runs[0].decision_group
    graded = await sheet(session, group)
    assert graded.kind == "queue"
    assert [(item.question, item.run) for item in graded.items] == [("Q001", 1), ("Q001", 2), ("Q001", 3)]
    for item, verdict in zip(graded.items, ("correct", "incorrect", "incorrect"), strict=True):
        await record(session, item.result_id, verdict)
    await lock(session, await sheet(session, group))
    found = await decision(session, group)
    assert not found.provisional
    assert found.measures["correct_answers"].median == 2  # yours: 3, 2, 2


@pytest.mark.anyio
async def test_a_decision_runs_own_runs_wait_until_its_queue_is_graded(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({"Q001": {2}}))
    group = runs[0].decision_group
    with pytest.raises(GradingError, match=f"Grade decision run {group}'s queue first"):
        await sheet(session, runs[0].id, sample=True)
    queue = await sheet(session, group)
    for item in queue.items:
        await record(session, item.result_id, "correct")
    await lock(session, await sheet(session, group))
    reviewed = await sheet(session, runs[0].id)  # the queue's answers in it are graded and locked already
    assert [(item.question, item.locked) for item in reviewed.items] == [
        ("Q001", True),
        ("Q002", False),
        ("Q003", False),
    ]


@pytest.mark.anyio
async def test_a_decision_run_with_nothing_in_its_queue_has_no_sheet(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({}))
    with pytest.raises(GradingError, match="nothing waits for your grade"):
        await sheet(session, runs[0].decision_group)


@pytest.mark.anyio
async def test_a_queue_is_graded_whole(session, sessions, tmp_path):
    runs = await finished(session, sessions, frozen_set(tmp_path), Varying({"Q001": {2}}))
    with pytest.raises(GradingError, match="graded whole"):
        await sheet(session, runs[0].decision_group, sample=True)
