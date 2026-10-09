"""Decision runs (PRD 5.4; QA plan 4.1 and 4.2): the three runs a decision is made on.

A model and its judge don't answer exactly the same way twice, so a decision (the baseline that
sets the pass mark, an acceptance run, a monthly or published report) is made on three runs of
one frozen test set with identical settings, sharing a `decision_group`. Each measure counts its
median, the middle of the three, and shows its range.

- **Settings:** every recorded setting that could change a score must match across the three,
  or the group is refused. A decision run starts only from committed code, and a run goes on
  only from the commit it started on (PRD Q17), so the recorded commit reproduces every answer.
- **The grading queue:** a question the judge graded differently across the three runs goes to
  you. You grade each of its answers, since each run's answer is different text, and your grade
  replaces the judge's on those answers only (PRD Q16). A grade counts once it's locked, which
  happens when its grading sheet is completed (PRD Q18), so a result can't be seen and then
  graded toward. Until then the decision is provisional: it counts the judge's verdicts on the
  answers still waiting, and the command holds back the correct-answers line, whose range would
  hint at them.
- **The budget** covers all three runs, a third each, so one run can't spend another's share.
  The runs go one after another, each 4 questions at a time.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Any

import anyio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from citemark.db.models import HumanGrade, TestQuestion, TestResult, TestRun, TestSet
from citemark.evals.runner import (
    ATTEMPTS,
    DIRTY,
    PARALLEL,
    STORED_PLACES,
    UNKNOWN_COMMIT,
    OnResult,
    Outcome,
    RunError,
    Services,
    Sleep,
    create_run,
    run_tests,
    summary_row,
)
from citemark.evals.scoring import Measure, summarize
from citemark.models import AnswerModel
from citemark.retrieve import RetrievalConfig

RUNS = 3
# Every recorded setting that could change a score (PRD 4.3). The budget isn't one.
SETTINGS = (
    "test_set_id",
    "mode",
    "model",
    "company",
    "prompt_version",
    "retrieval_config",
    "git_sha",
    "judge_model",
    "rubric_version",
)
MEASURES = ("correct_answers", "right_source", "correct_declines", "wrongly_declined", "right_place")

OnRun = Callable[[int, TestRun], None]


class DecisionError(RunError):
    """The group can't give a decision. The message is one plain sentence."""


# --- Starting and finishing the three runs ---


def committed(sha: str) -> str:
    """The commit a decision run starts from. Uncommitted changes are refused, since no commit
    could reproduce the numbers (PRD Q17)."""
    if sha.endswith(DIRTY):
        raise DecisionError(
            "A decision run can't start from uncommitted changes, since no commit could reproduce its numbers. "
            "Commit them first."
        )
    if sha == UNKNOWN_COMMIT:
        raise DecisionError(
            "A decision run needs to know which commit it runs from. Run it from the repository, "
            "or set CITEMARK_GIT_SHA."
        )
    return sha


def split(budget: Decimal, runs: int = RUNS) -> Decimal:
    """Each run's share of the budget, rounded down, so together they never pass it."""
    return (budget / runs).quantize(STORED_PLACES, rounding=ROUND_FLOOR)


async def create_group(
    session: AsyncSession,
    test_set: TestSet,
    *,
    mode: str,
    answerer: AnswerModel,
    config: RetrievalConfig,
    budget_usd: Decimal,
    sha: str,
) -> list[TestRun]:
    """Three runs with identical settings, sharing a decision group and a third of the budget each."""
    sha = committed(sha)
    group, share = uuid.uuid4(), split(budget_usd)
    runs = [
        await create_run(
            session,
            test_set,
            mode=mode,
            answerer=answerer,
            config=config,
            budget_usd=share,
            sha=sha,
            decision_group=group,
        )
        for _ in range(RUNS)
    ]
    return sorted(runs, key=lambda run: run.id)  # the order `group_runs` numbers them in


async def group_runs(session: AsyncSession, group: uuid.UUID) -> list[TestRun]:
    """A group's runs, numbered by ID: they're created together, so no other order is stable.
    They're read as they are now, even if this session loaded them before a run changed them."""
    query = select(TestRun).where(TestRun.decision_group == group).order_by(TestRun.id)
    runs = list(await session.scalars(query.execution_options(populate_existing=True)))
    if not runs:
        raise DecisionError(f"There's no decision run {group}.")
    return runs


async def find_group(session: AsyncSession, given: uuid.UUID) -> uuid.UUID:
    """A decision run's group, from its own ID or the ID of one of its runs."""
    run = await session.get(TestRun, given)
    if run is not None:
        if run.decision_group is None:
            raise DecisionError(f"Run {given} is a single run, not one of a decision run's three.")
        return run.decision_group
    if await session.scalar(select(func.count()).select_from(TestRun).where(TestRun.decision_group == given)):
        return given
    raise DecisionError(f"There's no decision run or test run {given}.")


def coherent(group: uuid.UUID, runs: Sequence[TestRun]) -> None:
    """Refuse a group that isn't three runs with identical settings, before it's run or combined."""
    if len(runs) != RUNS:
        raise DecisionError(f"Decision run {group} has {len(runs)} runs, not {RUNS}.")
    if differing := mismatched(runs):
        raise DecisionError(
            f"The runs of decision run {group} differ in {', '.join(differing)}, so their results can't be combined."
        )


def unfinished(runs: Sequence[TestRun]) -> list[TestRun]:
    """The group's runs still to finish. A run that stopped at its budget or was cancelled can't
    be finished, so neither can the group: a decision needs all three."""
    for number, run in enumerate(runs, 1):
        if run.status == "over_budget":
            raise DecisionError(
                f"Run {number} of {len(runs)} stopped at its budget, so this decision run can't be completed. "
                "Start a new one with a bigger budget."
            )
        if run.status == "cancelled":
            raise DecisionError(
                f"Run {number} of {len(runs)} was cancelled, so this decision run can't be completed. Start a new one."
            )
    return [run for run in runs if run.status != "done"]


async def finish_group(
    group: uuid.UUID,
    *,
    sessions: async_sessionmaker[AsyncSession],
    services: Services,
    sha: str,
    force: uuid.UUID | None = None,
    on_run: OnRun | None = None,
    on_result: OnResult | None = None,
    parallel: int = PARALLEL,
    attempts: int = ATTEMPTS,
    sleep: Sleep = anyio.sleep,
) -> list[tuple[TestRun, Outcome]]:
    """Run each of the group's unfinished runs in turn, stopping at the first that doesn't end
    done. `force` names the one run that may be resumed although it's marked running. A group
    that couldn't give a decision is refused before anything is spent."""
    async with sessions() as session:
        runs = await group_runs(session, group)
    coherent(group, runs)
    ended = []
    for run in unfinished(runs):
        if on_run is not None:
            on_run(runs.index(run) + 1, run)
        outcome = await run_tests(
            run.id,
            sessions=sessions,
            services=services,
            on_result=on_result,
            parallel=parallel,
            attempts=attempts,
            sleep=sleep,
            force=run.id == force,
            sha=sha,
        )
        ended.append((run, outcome))
        if outcome.status != "done":
            break
    return ended


# --- Combining them ---


@dataclass(frozen=True)
class Spread:
    """One measure across the runs: the median counts, and the range shows how far apart the
    runs were (content spec 5.2)."""

    median: int
    low: int
    high: int
    total: int

    @property
    def same(self) -> bool:
        return self.low == self.high


def spread(measures: Sequence[Measure | None]) -> Spread | None:
    """The median and range of one measure. None when no run measured it, such as retrieval in
    full-context mode."""
    if all(measure is None for measure in measures):
        return None
    found = [measure for measure in measures if measure is not None]
    if len(found) != len(measures) or len({measure.total for measure in found}) != 1:
        raise DecisionError("The runs didn't measure the same questions, so they can't share a median.")
    if len(found) % 2 == 0:
        raise DecisionError("A median needs an odd number of runs.")
    counts = sorted(measure.passed for measure in found)
    return Spread(counts[len(counts) // 2], counts[0], counts[-1], found[0].total)


def mismatched(runs: Sequence[Any]) -> list[str]:
    """The settings that differ across the runs."""

    def key(value: Any) -> str:
        return json.dumps(value, sort_keys=True, default=str)

    return [name for name in SETTINGS if len({key(getattr(run, name)) for run in runs}) > 1]


def judged_differently(verdicts: dict[str, list[str | None]]) -> set[str]:
    """The questions whose judged answers didn't all get the same verdict. A run whose reply
    wasn't judged, such as a decline, isn't a different verdict: it's scored mechanically."""
    return {question for question, given in verdicts.items() if len({v for v in given if v is not None}) > 1}


@dataclass(frozen=True)
class QueueEntry:
    """One answer waiting for, or given, your grade. The judge's verdict isn't kept here, so
    nothing that lists the queue can show it to you before you grade (PRD 5.4)."""

    question: str  # the test question's ID
    run: int  # 1 to 3
    result_id: uuid.UUID
    grade: str | None  # yours, once locked: a grade still open to change doesn't count yet


@dataclass(frozen=True)
class Decision:
    group: uuid.UUID
    runs: list[TestRun]
    measures: dict[str, Spread | None]
    queue: list[QueueEntry]  # every judged answer to a question the judge graded differently
    spent: Decimal
    budget: Decimal

    @property
    def waiting(self) -> list[QueueEntry]:
        return [entry for entry in self.queue if entry.grade is None]

    @property
    def provisional(self) -> bool:
        """Some answers in the queue aren't graded yet, so their judge's verdicts still count."""
        return bool(self.waiting)


async def finished_runs(session: AsyncSession, group: uuid.UUID) -> list[TestRun]:
    """The group's runs, refused unless all three finished with identical settings."""
    runs = await group_runs(session, group)
    coherent(group, runs)
    if pending := unfinished(runs):
        raise DecisionError(
            f"Run {runs.index(pending[0]) + 1} of {RUNS} hasn't finished. Finish the decision run with: "
            f"citemark test resume {pending[0].id}"
        )
    return runs


async def decision(session: AsyncSession, group: uuid.UUID) -> Decision:
    """The group's medians and ranges, with your grades counted where the judge disagreed with
    itself. Refused unless all three runs finished with identical settings."""
    runs = await finished_runs(session, group)
    total = await session.scalar(
        select(func.count()).select_from(TestQuestion).where(TestQuestion.test_set_id == runs[0].test_set_id)
    )
    rows = await session.execute(
        select(TestResult, TestQuestion, HumanGrade.verdict, HumanGrade.locked_at)
        .join(TestQuestion, TestResult.test_question_id == TestQuestion.id)
        .outerjoin(HumanGrade, HumanGrade.test_result_id == TestResult.id)
        .where(TestResult.test_run_id.in_([run.id for run in runs]))
        .order_by(TestQuestion.ext_id)
        .execution_options(populate_existing=True)  # as they are now, if this session loaded them before
    )
    number = {run.id: position for position, run in enumerate(runs, 1)}
    by_run: dict[int, list[tuple[TestResult, TestQuestion, str | None]]] = defaultdict(list)
    verdicts: dict[str, list[str | None]] = defaultdict(list)
    for result, question, grade, locked_at in rows:
        locked = grade if locked_at is not None else None  # only a locked grade counts
        by_run[number[result.test_run_id]].append((result, question, locked))
        verdicts[question.ext_id].append(result.judge_verdict)
    for position in range(1, RUNS + 1):
        if len(by_run[position]) != total:
            raise DecisionError(f"Run {position} of {RUNS} has {len(by_run[position])} of {total} results.")

    queued = judged_differently(verdicts)
    queue, summaries = [], []
    for position in range(1, RUNS + 1):
        flat = []
        for result, question, grade in by_run[position]:
            verdict = result.judge_verdict
            if question.ext_id in queued and verdict is not None:
                queue.append(QueueEntry(question.ext_id, position, result.id, grade))
                verdict = grade or verdict  # your grade counts; until then, the judge's
            flat.append(summary_row(result, question, verdict=verdict))
        summaries.append(summarize(flat, mode=runs[0].mode))
    return Decision(
        group=group,
        runs=runs,
        measures={name: spread([getattr(found, name) for found in summaries]) for name in MEASURES},
        queue=sorted(queue, key=lambda entry: (entry.question, entry.run)),
        spent=sum((run.cost_usd for run in runs), Decimal(0)),
        budget=sum((run.budget_usd for run in runs), Decimal(0)),
    )
