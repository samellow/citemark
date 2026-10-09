"""Your grading (PRD 5.4; QA plan 4.2): the judge checked against you.

- **What you grade:** the answers the judge graded, since its agreement with you is measured on
  answers alone. A run's sheet holds all of them, or a sample picked the same way every time:
  the 10-answer re-check each answer model gets (PRD Q19). A decision run's sheet is its
  grading queue, and those grades count in its result (PRD Q16).
- **Blind:** a sheet holds what the judge read (the question and its type, the option chosen,
  the expected answer, the expected sources' quotes and the bot's answer as shown), never the
  judge's verdict. The verdicts come out only once every answer on the sheet is graded.
- **Locked once complete** (PRD Q18): until then any grade can change. Completing the sheet
  locks its grades, and the database refuses to change them, since a grade changed after
  seeing the judge's reasons would lean toward it.
- **Agreement** is counted on a run's sheet. A queue holds only answers the judge graded
  inconsistently, so agreement on it would say nothing about the judge in general.
- **The abuse set** isn't graded: the judge doesn't grade it, and its rules are mechanical.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import HumanGrade, TestQuestion, TestResult, TestRun
from citemark.evals.abuse import is_abuse
from citemark.evals.decision import decision, group_runs
from citemark.evals.runner import RunError
from citemark.evals.scoring import chosen_option

SAMPLE = 10  # answers in a re-check (roadmap 6.1)
TARGET = (9, 10)  # agreement of at least 90% (roadmap 6.1), compared exactly


class GradingError(RunError):
    """The sheet can't be graded as asked. The message is one plain sentence."""


@dataclass(frozen=True)
class Item:
    """One answer to grade, with what the judge read and nothing it said."""

    result_id: uuid.UUID
    question: str  # the test question's ID
    run: int | None  # 1 to 3 on a decision run's queue
    qtype: str
    asked: str
    option: str | None  # what the customer chose, when an ambiguous question was clarified
    expected_answer: list[str]
    sources: list[dict[str, str]]  # the expected sources: url, section and quote
    uncovered_part: str | None
    answer: str  # as the visitor saw it, gap line included
    grade: str | None  # yours, once given
    note: str
    locked: bool


@dataclass(frozen=True)
class Sheet:
    target: uuid.UUID  # the run, or the decision run whose queue this is
    kind: str  # run, sample or queue
    rubric: str
    items: list[Item]

    @property
    def graded(self) -> int:
        return sum(1 for item in self.items if item.grade is not None)

    @property
    def complete(self) -> bool:
        return self.graded == len(self.items)

    @property
    def locked(self) -> bool:
        return all(item.locked for item in self.items)


def sampled(run_id: uuid.UUID, result_ids: Sequence[uuid.UUID], size: int) -> set[uuid.UUID]:
    """A sample of a run's answers that's the same every time it's asked for, so it can't be
    picked to suit: each answer's place comes from a hash of the run and the answer."""

    def place(result_id: uuid.UUID) -> str:
        return hashlib.sha256(f"{run_id}:{result_id}".encode()).hexdigest()

    return set(sorted(result_ids, key=place)[:size])


async def _items(session: AsyncSession, chosen: dict[uuid.UUID, int | None]) -> list[Item]:
    rows = await session.execute(
        select(TestResult, TestQuestion, HumanGrade)
        .join(TestQuestion, TestResult.test_question_id == TestQuestion.id)
        .outerjoin(HumanGrade, HumanGrade.test_result_id == TestResult.id)
        .where(TestResult.id.in_(chosen))
        .execution_options(populate_existing=True)
    )
    items = []
    for result, question, grade in rows:
        option = None
        if question.type == "ambiguous":
            option = chosen_option(result.clarify_options, question.expected_option)
        items.append(
            Item(
                result_id=result.id,
                question=question.ext_id,
                run=chosen[result.id],
                qtype=question.type,
                asked=question.question,
                option=option,
                expected_answer=list(question.expected_answer),
                sources=list(question.expected_sources),
                uncovered_part=question.uncovered_part,
                answer=result.answer or "",
                grade=grade.verdict if grade else None,
                note=grade.note if grade else "",
                locked=bool(grade and grade.locked_at),
            )
        )
    return sorted(items, key=lambda item: (item.question, item.run or 0))


async def sheet(session: AsyncSession, target: uuid.UUID, *, sample: bool = False) -> Sheet:
    """A run's judged answers, or a sample of 10 of them, or a decision run's queue when
    `target` is a decision run's ID. A run of a decision run waits until its queue is graded."""
    run = await session.get(TestRun, target, populate_existing=True)
    first = run if run is not None else (await group_runs(session, target))[0]  # refuses an unknown ID
    if await is_abuse(session, first):
        raise GradingError(
            f"{target} is a run of the abuse set, which is scored mechanically without the judge, so there's "
            "nothing to grade."
        )
    if run is None:
        if sample:
            raise GradingError("A decision run's queue is graded whole, so --sample is for a single run.")
        found = await decision(session, target)  # refuses an unfinished group
        if not found.queue:
            raise GradingError(
                f"The judge graded every question of decision run {target} the same way in all three runs, "
                "so nothing waits for your grade."
            )
        chosen: dict[uuid.UUID, int | None] = {entry.result_id: entry.run for entry in found.queue}
        return Sheet(target, "queue", found.runs[0].rubric_version, await _items(session, chosen))

    if run.status != "done":
        raise GradingError(
            f"Run {target} hasn't finished (it's {run.status.replace('_', ' ')}), so its answers can't all be graded."
        )
    if run.decision_group is not None and (await decision(session, run.decision_group)).waiting:
        raise GradingError(  # completing this sheet would show verdicts on answers the queue holds
            f"Grade decision run {run.decision_group}'s queue first: once this run's sheet is complete, the "
            "judge's verdicts on it are shown, and some may be on questions in that queue."
        )
    judged = list(
        await session.scalars(
            select(TestResult.id).where(TestResult.test_run_id == target, TestResult.judge_verdict.is_not(None))
        )
    )
    if not judged:
        raise GradingError(f"The judge graded no answers in run {target}, so there's nothing to grade.")
    if sample:
        judged = sorted(sampled(target, judged, SAMPLE))
    items = await _items(session, dict.fromkeys(judged))
    return Sheet(target, "sample" if sample else "run", run.rubric_version, items)


def to_grade(graded: Sheet, *, again: bool = False) -> list[Item]:
    """The answers still to grade, or with `again`, every answer whose grade can still change."""
    if again and graded.locked:
        raise GradingError("This sheet is complete, so its grades are locked.")
    return [item for item in graded.items if item.grade is None or (again and not item.locked)]


async def record(session: AsyncSession, result_id: uuid.UUID, verdict: str, note: str = "") -> None:
    """Give or change your grade on one answer, until its sheet is complete."""
    locked = "That grade was locked when its grading sheet was completed, so it can't change."
    found = await session.scalar(select(HumanGrade).where(HumanGrade.test_result_id == result_id))
    if found is None:
        session.add(HumanGrade(test_result_id=result_id, verdict=verdict, note=note))
    elif found.locked_at is not None:
        raise GradingError(locked)
    else:
        found.verdict, found.note, found.graded_at = verdict, note, func.now()
    try:
        await session.flush()
    except IntegrityError as exc:  # another grading process got there first, or locked it meanwhile
        raise GradingError(f"{locked} It may have been graded elsewhere meanwhile.") from exc


async def lock(session: AsyncSession, graded: Sheet) -> None:
    """Lock a completed sheet's grades, before the judge's verdicts are shown."""
    if not graded.complete:
        raise GradingError("A sheet locks only once every answer on it is graded.")
    await session.execute(
        update(HumanGrade)
        .where(HumanGrade.test_result_id.in_([item.result_id for item in graded.items]))
        .where(HumanGrade.locked_at.is_(None))
        .values(locked_at=func.now())
    )


@dataclass(frozen=True)
class Disagreement:
    question: str
    run: int | None
    yours: str
    judges: str
    reason: str | None


@dataclass(frozen=True)
class Agreement:
    graded: int
    agreed: int
    disagreements: list[Disagreement]

    @property
    def percent(self) -> int:
        """Rounded down, so it never looks better than it is (content spec Q2)."""
        return self.agreed * 100 // self.graded

    @property
    def meets_target(self) -> bool:
        wanted, of = TARGET
        return self.agreed * of >= self.graded * wanted


def agree(rows: Sequence[tuple[Any, ...]]) -> Agreement:
    """Each row: question, run, your grade, the judge's verdict, the judge's reason."""
    if not rows:
        raise GradingError("There are no graded answers to compare.")
    disagreements = [Disagreement(*row) for row in rows if row[2] != row[3]]
    return Agreement(len(rows), len(rows) - len(disagreements), disagreements)


async def agreement(session: AsyncSession, graded: Sheet) -> Agreement:
    """You against the judge on a completed, locked sheet: its verdicts aren't shown before."""
    if not (graded.complete and graded.locked):
        raise GradingError("The judge's verdicts are shown only once every answer on the sheet is graded and locked.")
    verdicts = {
        result_id: (verdict, reason)
        for result_id, verdict, reason in await session.execute(
            select(TestResult.id, TestResult.judge_verdict, TestResult.judge_reason).where(
                TestResult.id.in_([item.result_id for item in graded.items])
            )
        )
    }
    return agree([(item.question, item.run, item.grade, *verdicts[item.result_id]) for item in graded.items])
