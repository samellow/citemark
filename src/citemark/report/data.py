"""The report's content (PRD 8.1), worked out from the database before anything is drawn.

Everything the report says is decided here, as text from `report.json` and numbers from
`report.numbers`, so the templates only lay it out and every refusal happens before a file is
written (QA plan 7.4). A report won't build without:

- **Decision runs** (QA plan Q1): three runs each, finished, with identical settings and no answer
  still waiting for your grade. Your grades from a run's queue count instead of the judge's.
- **The frozen test set,** unchanged since its freeze, with the fingerprint the runs used.
- **The five measures,** your name, the client's (except on a demo), the judge's agreement with
  your grading, and an estimate for every fix-plan group that has failures.
- **A pass mark with who agreed it and when,** or none at all, which makes the report a baseline.

**Three answers per question** (decided in T14): a question that failed in any of the three runs
counts as failed. Its record shows the first answer that failed the way it's grouped in the fix
plan, and says how many runs it failed in. A question that passed in all three shows run 1's.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from citemark import strings
from citemark.db.models import FAILURE_TYPES, HumanGrade, Price, TestQuestion, TestResult, TestRun, TestSet
from citemark.evals import testset
from citemark.evals.abuse import abuse_decision
from citemark.evals.decision import Decision, decision, find_group
from citemark.evals.grading import SAMPLE, sampled
from citemark.evals.runner import RunError, summary_row
from citemark.evals.scoring import DECLINES, JUDGED, LOWER_IS_BETTER, MEASURES, SHOULD_DECLINE, chosen_option, counted
from citemark.evals.scoring import matches as source_matches
from citemark.models.registry import ModelError
from citemark.models.registry import model as registered
from citemark.report import numbers
from citemark.report.inputs import DOC_GAP, GROUPS, ReportFile
from citemark.report.view import (
    Column,
    Comparison,
    Entry,
    Expected,
    FixGroup,
    FixPlan,
    Header,
    Looked,
    MeasureRow,
    Method,
    Quote,
    Record,
    Report,
    Stretch,
    Verdict,
)

TOP_K = 5  # "among the 5 the bot read" (content spec 5.2)
STEPS = {"retrieval_miss": 2, "wrong_citation": 3}  # where each failure went wrong; every other one, at step 4
OWNERS = {  # content spec 5.4
    "answered_should_decline": "builder",
    "declined_answerable": "either",
    "retrieval_miss": "builder",
    "wrong_citation": "builder",
    "wrong_answer": "builder",
    DOC_GAP: "client",
}
LABELS = (  # the fixed words the templates place, each from report.json
    "title",
    "trace.heading",
    "trace.intro",
    "trace.step1",
    "trace.step2",
    "trace.step3",
    "trace.step4",
    "trace.step5",
    "trace.gap_step2",
    "evidence.expected_answer",
    "evidence.bot_answer",
    "evidence.expected_source",
    "evidence.shown_source",
    "questions.heading",
    "questions.filter.label",
    "questions.filter.all",
    "questions.filter.failed",
    "compare.heading",
    "method.heading",
    "state.pass",
    "state.fail",
    "state.warn",
    "state.warn_help",
)
PAGE, PAGES = "\x00page\x00", "\x00pages\x00"  # where the print footer's page numbers go


class ReportError(Exception):
    """The report can't be built as asked. The message is one plain sentence."""


def t(key: str, **slots: str | int) -> str:
    return strings.text("report", key, **slots)


def _and(items: Sequence[str]) -> str:
    """A, B and C."""
    if len(items) == 1:
        return items[0]
    return t("list.and", first=", ".join(items[:-1]), last=items[-1])


# --- Reading the runs ---


@dataclass(frozen=True)
class _Answer:
    run: int
    result: TestResult
    outcomes: dict[str, bool]  # each measure it counts in, and whether it went the bot's way
    failure: str | None


@dataclass(frozen=True)
class _Setup:
    """One decision run, read whole."""

    decision: Decision
    questions: dict[str, TestQuestion]  # by ID, in order
    answers: dict[str, list[_Answer]]  # a question's answer in each run, in run order
    cost: Decimal  # the middle of the three runs' mean cost per question, like every other number

    @property
    def runs(self) -> list[TestRun]:
        return self.decision.runs

    @property
    def first(self) -> TestRun:
        return self.decision.runs[0]


async def _setup(session: AsyncSession, given: uuid.UUID) -> _Setup:
    try:
        group = await find_group(session, given)
        found = await decision(session, group)
    except RunError as exc:
        raise ReportError(str(exc)) from exc
    if found.provisional:
        raise ReportError(
            f"Decision run {group} has {len(found.waiting)} answers waiting for your grade, so its numbers aren't "
            f"final. Grade them first: citemark grade {group}"
        )
    grades = {entry.result_id: entry.grade for entry in found.queue}  # yours count instead of the judge's
    number = {run.id: position for position, run in enumerate(found.runs, 1)}
    rows = await session.execute(
        select(TestResult, TestQuestion)
        .join(TestQuestion, TestResult.test_question_id == TestQuestion.id)
        .where(TestResult.test_run_id.in_(number))
        .order_by(TestQuestion.ext_id)
        .execution_options(populate_existing=True)
    )
    questions: dict[str, TestQuestion] = {}
    answers: dict[str, list[_Answer]] = defaultdict(list)
    costs: dict[int, list[Decimal]] = defaultdict(list)
    for result, question in rows:
        row = summary_row(result, question, verdict=grades.get(result.id) or result.judge_verdict)
        answers[question.ext_id].append(
            _Answer(number[result.test_run_id], result, counted(row, mode=found.runs[0].mode), row["failure_type"])
        )
        questions[question.ext_id] = question
        costs[number[result.test_run_id]].append(result.cost_usd)
    for each in answers.values():
        each.sort(key=lambda answer: answer.run)
    means = sorted(sum(each, Decimal(0)) / len(each) for each in costs.values())
    return _Setup(found, questions, dict(answers), means[len(means) // 2])


def _model_name(model_id: str) -> str:
    try:
        return registered(model_id).name
    except ModelError as exc:
        raise ReportError(str(exc)) from exc


def _mode(run: TestRun) -> str:
    if run.mode == "full_context":
        return t("compare.mode.full_context")
    if (run.retrieval_config or {}).get("rerank", True):
        return t("compare.mode.retrieval")
    return t("compare.mode.retrieval_no_rerank")


def _check_together(setups: Sequence[_Setup]) -> None:
    """Refuse setups a reader couldn't compare: another test set, company, judge or rubric, or a
    search that didn't give the bot the 5 sections its measure's definition names."""
    first, seen = setups[0], set()
    for setup in setups:
        if setup.decision.group in seen:
            raise ReportError(f"Decision run {setup.decision.group} is named twice.")
        seen.add(setup.decision.group)
        run = setup.first
        for name in ("test_set_id", "company", "judge_model", "rubric_version"):
            if getattr(run, name) != getattr(first.first, name):
                raise ReportError(
                    f"Decision run {setup.decision.group} differs from {first.decision.group} in "
                    f"{name.replace('_', ' ')}, so they can't share a report."
                )
        top_k = (run.retrieval_config or {}).get("top_k")
        if run.mode == "retrieval" and top_k != TOP_K:
            raise ReportError(
                f"Decision run {setup.decision.group} gave the bot {top_k} sections per question, and the report says "
                f"{TOP_K}. Report runs made with {TOP_K}."
            )


# --- The numbers ---


def _count_text(name: str, passed: int, total: int) -> str:
    if name in LOWER_IS_BETTER:
        return t("count.rate", count=passed, total=total, percent=numbers.percent_up(passed, total))
    return t("count.score", passed=passed, total=total, percent=numbers.percent_down(passed, total))


def _spread_text(low: int, high: int) -> str:
    return t("measure.range_same") if low == high else t("measure.range", low=low, high=high)


def _targets(test_set: TestSet) -> dict[str, int] | None:
    if test_set.threshold is None:
        return None
    readable = set(test_set.threshold) == set(MEASURES) and all(
        isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100 for v in test_set.threshold.values()
    )
    if not readable:
        raise ReportError(
            f"The pass mark of {test_set.name} version {test_set.version} isn't one the report can read: it needs a "
            "whole-percent target for each of the five measures. Set it again with: citemark test threshold"
        )
    if not test_set.threshold_set_by or test_set.threshold_set_at is None:
        raise ReportError(
            f"The pass mark of {test_set.name} version {test_set.version} doesn't say who agreed it and when. "
            "Set it again with: citemark test threshold"
        )
    return dict(test_set.threshold)


def _cost_line(cost: Decimal) -> str:
    return t("measure.cost.definition", cost=numbers.money(cost), per_thousand=numbers.money(cost * 1000))


def _link(url: str) -> str | None:
    """A help-center address to link to. Anything else, such as an uploaded file's, is shown unlinked."""
    return url if url.startswith(("https://", "http://")) else None


def _unmeasured(name: str) -> MeasureRow:
    return MeasureRow(name, t(f"measure.{name}.name"), None, None, None, None, None, t("not_measured"), None)


def _measure_rows(
    setup: _Setup, targets: dict[str, int] | None, failed_by: dict[str, list[str]], kind: str
) -> tuple[list[MeasureRow], list[str]]:
    """The measure strip, and the state of each row that has a target."""
    rows, states = [], []
    for name in MEASURES:
        spread = setup.decision.measures[name]
        label, definition = t(f"measure.{name}.name"), t(f"measure.{name}.definition")
        if spread is None:  # retrieval, in full-context mode
            rows.append(MeasureRow(name, label, definition, None, None, None, None, t("compare.not_measured"), None))
            continue
        if spread.total == 0:  # the report won't build without the five measures (content spec 2.3)
            raise ReportError(
                f"The test set has no questions that count in {label}, so the report can't measure it. "
                "A report's test set needs questions of every type that measure counts."
            )
        target = state = None
        if targets is not None and name in targets:
            lower = name in LOWER_IS_BETTER
            target = t("target.at_most" if lower else "target.at_least", target=targets[name])
            state = numbers.state(spread.median, spread.total, targets[name], lower_is_better=lower)
            states.append(state)
        rows.append(
            MeasureRow(
                name,
                label,
                definition,
                _count_text(name, spread.median, spread.total),
                target,
                state,
                _spread_text(spread.low, spread.high),
                None,
                f"#show-{name}" if failed_by.get(name) else None,
            )
        )
    if kind == "build":  # handoff honesty is measured on a build (Phase 2)
        rows.append(_unmeasured("honest_tickets"))
    rows.append(_unmeasured("time_to_first_word"))  # the speed run needs the deployed bot (roadmap, Phase 1)
    rows.append(MeasureRow("cost", t("measure.cost.name"), None, _cost_line(setup.cost), None, None, None, None, None))
    return rows, states


# --- The evidence ---


def _record(prefix: str, question: TestQuestion, answer: _Answer, mode: str) -> Record:
    result = answer.result
    full_context = mode == "full_context"
    looked: tuple[Looked, ...] = ()
    if not full_context:
        looked = tuple(
            Looked(
                passage["heading_path"],
                _link(passage["url"]),
                any(source_matches(passage, source) for source in question.expected_sources),
            )
            for passage in sorted(result.retrieved, key=lambda passage: passage["rank"])
        )
    missed = result.retrieval_hit is False
    quotes = tuple(
        Quote(
            cited["marker"],
            f"{prefix}-q{cited['marker']}",
            t("evidence.marker_a11y", n=cited["marker"]),
            cited["cited_text"],
            cited["heading_path"],
            _link(cited["url"]),
        )
        for cited in sorted(result.citations, key=lambda cited: cited["marker"])
    )
    quote_note = None
    if not quotes:
        correctly = question.type in SHOULD_DECLINE and result.kind in DECLINES
        quote_note = t("trace.decline_step3" if correctly else "trace.no_quote")
    options = tuple(result.clarify_options or ())
    picked = chosen_option(options, question.expected_option) if options else None
    by_marker = {quote.marker: quote for quote in quotes}
    if result.kind in JUDGED:
        if result.segments is None:
            raise ReportError(
                f"Run {result.test_run_id} was saved before results kept where each source marker goes, so its "
                "answers can't show their markers. Build the report from runs made since."
            )
        if unknown := {n for part in result.segments for n in part["markers"]} - set(by_marker):
            raise ReportError(
                f"An answer in run {result.test_run_id} marks source {min(unknown)}, which it has no quote for, so "
                "the report can't show what it rests on."
            )
        stretches = tuple(
            Stretch(part["text"], tuple(by_marker[n] for n in part["markers"])) for part in result.segments
        )
    elif result.kind == "clarify":
        stretches = ()  # the question and its options are shown instead
    else:
        stretches = (Stretch(result.answer or "", ()),)
    step = None if answer.failure is None else STEPS.get(answer.failure, 4)  # where its fix-plan group says
    return Record(
        id=prefix,
        question_id=question.ext_id,
        run=answer.run,
        question=question.question,
        full_context=full_context,
        looked=looked,
        missed=missed,
        looked_note=t("compare.mode.full_context") if full_context else None,
        quotes=quotes,
        quote_note=quote_note,
        clarify_question=strings.text("widget", "clarify.question") if options else None,
        options=options,
        chosen=t("evidence.chosen", option=picked) if picked else None,
        answer=stretches,
        gap_line=strings.text("widget", "partial.gap", gap=result.gap_text) if result.gap_text else None,
        passed=answer.failure is None,
        went_wrong=t("trace.went_wrong", step=step) if step else None,
        step=step,
        expected_answer=tuple(question.expected_answer),
        expected_sources=tuple(
            Expected(source["section"], _link(source["url"]), source["quote"]) for source in question.expected_sources
        ),
    )


def _group_of(question: TestQuestion, failing: Sequence[_Answer]) -> tuple[str, _Answer]:
    """A failed question's fix-plan group, and the answer shown for it: the first that failed the
    way it's grouped. Of different failures across runs, the first in PRD 5.4's order counts."""
    first = min((answer.failure or "" for answer in failing), key=FAILURE_TYPES.index)
    shown = next(answer for answer in failing if answer.failure == first)
    return (DOC_GAP if question.doc_gap else first), shown


# --- The judge's agreement with you ---


@dataclass(frozen=True)
class _Agreement:
    graded: int
    agreed: int


async def _graded(session: AsyncSession, run: TestRun, result_ids: Sequence[uuid.UUID], what: str) -> _Agreement:
    rows = await session.execute(
        select(TestResult.judge_verdict, HumanGrade.verdict, HumanGrade.locked_at)
        .outerjoin(HumanGrade, HumanGrade.test_result_id == TestResult.id)
        .where(TestResult.id.in_(result_ids))
    )
    found = [(judge, yours) for judge, yours, locked in rows if yours is not None and locked is not None]
    if len(found) != len(result_ids):
        command = f"citemark grade {run.id}" + (" --sample" if what == "sample" else "")
        raise ReportError(
            f"Run {run.id}'s {what} isn't complete: {len(found)} of {len(result_ids)} answers are graded and locked. "
            f"Finish it with: {command}"
        )
    return _Agreement(len(found), sum(1 for judge, yours in found if judge == yours))


async def _judged(session: AsyncSession, run_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        await session.scalars(
            select(TestResult.id).where(TestResult.test_run_id == run_id, TestResult.judge_verdict.is_not(None))
        )
    )


async def _check_run(session: AsyncSession, run_id: uuid.UUID, like: TestRun) -> TestRun:
    run = await session.get(TestRun, run_id)
    if run is None:
        raise ReportError(f"There's no test run {run_id}.")
    for name in ("test_set_id", "judge_model", "rubric_version"):
        if getattr(run, name) != getattr(like, name):
            raise ReportError(
                f"Run {run_id} differs from the report's runs in {name.replace('_', ' ')}, so its grading doesn't "
                "check the judge they were graded by."
            )
    return run


async def _grading(
    session: AsyncSession, inputs: ReportFile, like: TestRun
) -> tuple[_Agreement, _Agreement | None, list[str]]:
    """The full check, the re-checks' total, and the re-checked models' names."""
    run = await _check_run(session, inputs.judge_check.run, like)
    judged = await _judged(session, run.id)
    if not judged:
        raise ReportError(f"The judge graded no answers in run {run.id}, so it can't check the judge.")
    full = await _graded(session, run, judged, "grading sheet")
    named = Counter([run.id, *inputs.judge_check.rechecks])
    if twice := [str(run_id) for run_id, count in named.items() if count > 1]:
        raise ReportError(f"Run {twice[0]} is named for the judge's check twice.")
    graded = agreed = 0
    models: list[str] = []
    for run_id in inputs.judge_check.rechecks:
        recheck = await _check_run(session, run_id, like)
        sample = sorted(sampled(recheck.id, await _judged(session, recheck.id), SAMPLE))
        found = await _graded(session, recheck, sample, "sample")
        graded, agreed = graded + found.graded, agreed + found.agreed
        if (name := _model_name(recheck.model)) not in models:
            models.append(name)
    return full, (_Agreement(graded, agreed) if inputs.judge_check.rechecks else None), models


# --- Building it ---


def _test_set_file(inputs: ReportFile, test_set: TestSet) -> dict[str, Any]:
    """The frozen file's lock, refused unless the file is unchanged and is the set the runs used."""
    path = inputs.test_set
    try:
        lock = testset.verify_unchanged(path)
    except (testset.TestSetChanged, OSError) as exc:
        raise ReportError(str(exc)) from exc
    if lock is None:
        raise ReportError(f"{path.name} isn't frozen, so it can't be the test set of a report.")
    if lock["sha256"] != test_set.content_hash:
        raise ReportError(
            f"{path.name} has the fingerprint {numbers.fingerprint(lock['sha256'])}, and the runs used "
            f"{numbers.fingerprint(test_set.content_hash or '')}, so it isn't their test set."
        )
    return lock


async def _price_date(session: AsyncSession, runs: Sequence[TestRun]) -> dt.date:
    """The day whose prices one setup's runs were charged at, refused if prices changed while they
    ran. Setups compared can be months apart, so each has its own (a monthly report)."""
    first = min(run.started_at for run in runs if run.started_at).date()
    last = max(run.finished_at for run in runs if run.finished_at).date()
    changed = await session.scalar(
        select(func.min(Price.effective_from)).where(Price.effective_from > first, Price.effective_from <= last)
    )
    if changed is not None:
        raise ReportError(
            f"Prices changed on {numbers.date(changed)}, while these runs ran, so no single price date describes "
            "their costs. Report runs made on one side of the change."
        )
    return first


async def _abuse_line(inputs: ReportFile, primary: _Setup, abuse_session: AsyncSession | None) -> str:
    """The abuse gate's line, read from the abuse set's own database, or "Not measured yet"."""
    if inputs.abuse is None:
        return t("method.abuse_not_measured")
    if abuse_session is None:
        raise ReportError(
            "The report names an abuse run, which lives in the abuse set's own database. Set ABUSE_DATABASE_URL."
        )
    try:
        found = await abuse_decision(abuse_session, await find_group(abuse_session, inputs.abuse))
    except RunError as exc:
        raise ReportError(str(exc)) from exc
    run, like = found.runs[0], primary.first
    differing = [
        name.replace("_", " ")
        for name in ("model", "company", "prompt_version", "mode", "retrieval_config", "git_sha")
        if getattr(run, name) != getattr(like, name)
    ]
    if differing:
        raise ReportError(
            f"The abuse run {found.group} differs from the reported bot in {', '.join(differing)}, so its result "
            "isn't this bot's. Run the abuse set on the same setup."
        )
    return t("method.abuse", **found.slots())


def _traced(inputs: ReportFile, primary: _Setup, test_set: TestSet) -> str:
    """Yours, or the first answerable question that passed in every run with a source."""
    if inputs.traced is not None:
        if inputs.traced not in primary.questions:
            raise ReportError(f"{inputs.traced} isn't a question of {test_set.name} version {test_set.version}.")
        if any(answer.failure for answer in primary.answers[inputs.traced]):
            raise ReportError(
                f"{inputs.traced} failed in at least one run. The traced question shows what passing looks like, "
                "so choose one that passed in all three."
            )
        return inputs.traced
    for question_id, question in primary.questions.items():
        answers = primary.answers[question_id]
        if (
            question.type == "answerable"
            and not any(answer.failure for answer in answers)
            and answers[0].result.kind == "answer"
            and answers[0].result.citations
        ):
            return question_id
    raise ReportError(
        "No answerable question passed in all three runs with a source, so none is traced by default. "
        "Name one under traced:."
    )


def _fix_plan(
    inputs: ReportFile, groups: dict[str, list[str]], verdict: Verdict, *, builder_name: str, client: str
) -> FixPlan:
    missing = [group for group in GROUPS if group in groups and group not in inputs.fix_plan]
    if missing:
        listing = "; ".join(
            f"{group} ({t(f'fix.group.{group}.title')}, {t('fix.count', count=len(groups[group]))})"
            for group in missing
        )
        raise ReportError(f"The fix plan needs your estimate for: {listing}. Add them under fix_plan:.")
    if extra := [group for group in inputs.fix_plan if group not in groups]:
        raise ReportError(
            f"fix_plan has an estimate for {extra[0]}, and no question failed that way in these runs. Take it out."
        )
    found = []
    for group in sorted(groups, key=lambda group: (-len(groups[group]), GROUPS.index(group))):
        estimate = inputs.fix_plan[group]  # type: ignore[index]
        if OWNERS[group] == "client":
            owner = t("fix.owner.client", client=client, count=estimate.articles or 0)
        else:
            key = "fix.owner.builder" if OWNERS[group] == "builder" else "fix.owner.either"
            owner = t(key, builder_name=builder_name, client=client, hours=estimate.hours or 0)
        found.append(
            FixGroup(
                group,
                t(f"fix.group.{group}.title"),
                t(f"fix.group.{group}.what", **({"client": client} if group == DOC_GAP else {})),
                t("fix.count", count=len(groups[group])),
                owner,
                tuple(groups[group]),
            )
        )
    heading = {"pass": "fix.heading.pass", "not_pass": "fix.heading.not_pass", "baseline": "fix.heading.baseline"}
    return FixPlan(t(heading[verdict.state]), tuple(found), None if found else t("fix.none"))


def _comparison(setups: Sequence[_Setup]) -> Comparison | None:
    if len(setups) < 2:
        return None
    columns, seen = [], set()
    for setup in setups:
        run = setup.first
        started = min(r.started_at for r in setup.runs if r.started_at)
        column = Column(_model_name(run.model), _mode(run), numbers.date(started.date()), {})
        if (column.model, column.mode, column.date) in seen:
            raise ReportError(
                f"Two setups compared would read the same ({column.model}, {column.mode}, {column.date}), so a "
                "reader couldn't tell them apart. Compare runs that differ in model, mode, reranking or date."
            )
        seen.add((column.model, column.mode, column.date))
        for name in MEASURES:
            spread = setup.decision.measures[name]
            column.cells[name] = (
                t("compare.not_measured")
                if spread is None
                else f"{_count_text(name, spread.median, spread.total)} · {_spread_text(spread.low, spread.high)}"
            )
        column.cells["cost"] = _cost_line(setup.cost)
        columns.append(column)
    rows = tuple((name, t(f"measure.{name}.name")) for name in (*MEASURES, "cost"))
    return Comparison(rows, tuple(columns))


async def gather(
    session: AsyncSession,
    inputs: ReportFile,
    *,
    builder_name: str | None,
    today: dt.date,
    abuse_session: AsyncSession | None = None,
) -> Report:
    """Everything the report says, or a ReportError naming what's missing."""
    if not builder_name:
        raise ReportError("A report is prepared and signed with your name. Set BUILDER_NAME first.")
    demo = inputs.kind == "demo"
    client = t("demo.client") if demo else (inputs.client or "")

    primary = await _setup(session, inputs.decision)
    setups = [primary] + [await _setup(session, given) for given in inputs.compare]
    _check_together(setups)
    first = primary.first
    test_set = await session.get(TestSet, first.test_set_id)
    if test_set is None or test_set.frozen_at is None:
        raise ReportError(f"Decision run {primary.decision.group}'s test set isn't frozen.")
    if test_set.kind != "accuracy":
        raise ReportError(f"Decision run {primary.decision.group} is of the abuse set. Name it under abuse: instead.")
    lock = _test_set_file(inputs, test_set)
    first_start = min(run.started_at for setup in setups for run in setup.runs if run.started_at)
    if test_set.frozen_at > first_start:
        raise ReportError(
            f"{test_set.name} version {test_set.version} was frozen after a run of it started, so the report "
            "couldn't say its questions were frozen before any tuning."
        )
    targets = _targets(test_set)
    threshold_date = numbers.date(test_set.threshold_set_at.date()) if test_set.threshold_set_at else ""
    report_date = numbers.date(today)
    total = len(primary.questions)

    # Every question, with the failed ones grouped for the fix plan
    failed, passed = [], []
    groups: dict[str, list[str]] = defaultdict(list)
    failed_by: dict[str, list[str]] = defaultdict(list)
    for question_id, question in primary.questions.items():
        answers = primary.answers[question_id]
        missed = tuple(name for name in MEASURES if any(answer.outcomes.get(name) is False for answer in answers))
        for name in missed:
            failed_by[name].append(question_id)
        failing = [answer for answer in answers if answer.failure is not None]
        if failing:
            group, shown = _group_of(question, failing)
            groups[group].append(question_id)
            line = t("questions.failed_runs", failed=len(failing), run=shown.run)
            failed.append(Entry(_record(question_id, question, shown, first.mode), line, missed))
        else:
            passed.append(Entry(_record(question_id, question, answers[0], first.mode), None, missed))

    measures, states = _measure_rows(primary, targets, failed_by, inputs.kind)
    if targets is None:
        verdict = Verdict("baseline", t("verdict.baseline"))
    else:
        met = sum(1 for found in states if found == "pass")
        slots = {"threshold_date": threshold_date, "builder_name": builder_name, "client": client}
        if met == len(states):
            verdict = Verdict("pass", t("verdict.pass_demo" if demo else "verdict.pass", **slots))
        else:
            key = "verdict.not_pass_demo" if demo else "verdict.not_pass"
            verdict = Verdict("not_pass", t(key, met=met, target_count=len(states), **slots))

    traced = _traced(inputs, primary, test_set)
    trace = _record("trace", primary.questions[traced], primary.answers[traced][0], first.mode)
    fix_plan = _fix_plan(inputs, groups, verdict, builder_name=builder_name, client=client)

    # How the test was done
    types = Counter(question.type for question in primary.questions.values())
    paragraphs = [
        t(
            "method.questions",
            total=total,
            answerable=types["answerable"],
            partial=types["partial"],
            ambiguous=types["ambiguous"],
            should_decline=types["decline"] + types["off_topic"],
            frozen_date=numbers.date(test_set.frozen_at.date()),
            version=test_set.version,
            fingerprint=numbers.fingerprint(test_set.content_hash or ""),
        )
    ]
    if demo:
        if lock.get("edited") is None or lock.get("flagged") is None:
            raise ReportError(
                f"{inputs.test_set.name}'s lock has no review counts, which the demo's method needs. "
                "They're written when a set is frozen with --draft."
            )
        paragraphs.append(
            t(
                "method.authorship.demo",
                builder_name=builder_name,
                edited=lock["edited"],
                total=total,
                flagged=lock["flagged"],
            )
        )
    else:  # you confirm it in the report's file, since nothing in the runs could
        paragraphs.append(t("method.authorship.client", client=client, builder_name=builder_name))
    full, recheck, models = await _grading(session, inputs, first)
    paragraphs.append(
        t(
            "method.grading",
            judge_model=_model_name(first.judge_model),
            builder_name=builder_name,
            graded=full.graded,
            agreed=full.agreed,
        )
    )
    if recheck is not None:
        paragraphs.append(
            t(
                "method.grading_recheck",
                builder_name=builder_name,
                rechecked=recheck.graded,
                recheck_models=_and(models),
                re_agreed=recheck.agreed,
            )
        )
    if queued := sum(len(setup.decision.queue) for setup in setups):
        paragraphs.append(t("method.grading_queue", builder_name=builder_name, queued=queued))
    paragraphs.append(t("method.quotes"))
    paragraphs.append(await _abuse_line(inputs, primary, abuse_session))
    paragraphs.append(t("method.runs"))
    all_runs = [run for setup in setups for run in setup.runs]
    priced = sorted({await _price_date(session, setup.runs) for setup in setups})
    paragraphs.append(t("method.cost", price_date=_and([numbers.date(day) for day in priced])))
    setups_text = tuple(
        t(
            "method.setup",
            setup=f"{_model_name(setup.first.model)} · {_mode(setup.first)}",
            prompt_version=setup.first.prompt_version,
            commit=setup.first.git_sha[:12],
            run_ids=_and([str(run.id) for run in setup.runs]),
        )
        for setup in setups
    )

    if targets is None:
        pass_mark = t("signed.none")
    elif demo:
        pass_mark = t("signed.set", builder_name=builder_name, threshold_date=threshold_date)
    else:
        pass_mark = t(
            "signed.agreed",
            threshold_agreed_by=test_set.threshold_set_by or "",
            builder_name=builder_name,
            threshold_date=threshold_date,
        )
    footer_key = "print.footer_demo" if demo else "print.footer"
    footer = t(footer_key, client=client, report_date=report_date, page=PAGE, pages=PAGES)
    before, rest = footer.split(PAGE)
    middle, after = rest.split(PAGES)

    return Report(
        kind=inputs.kind,
        lang="en",
        labels={key: t(key) for key in LABELS},
        header=Header(
            t("title"),
            t("header.prepared_by", builder_name=builder_name),
            t("header.demo") if demo else t("header.for", client=client),
            t("header.questions", total=total, version=test_set.version),
            t("header.date", report_date=report_date),
            t("header.model", model_name=_model_name(first.model)),
        ),
        verdict=verdict,
        measures=tuple(measures),
        trace=trace,
        fix_plan=fix_plan,
        failed=tuple(failed),
        passed=tuple(passed),
        folded=t("questions.folded_passes", count=len(passed)),
        filters=tuple((name, t(f"measure.{name}.name")) for name in MEASURES if failed_by.get(name)),
        comparison=_comparison(setups),
        method=Method(tuple(paragraphs), setups_text),
        pass_mark=pass_mark,
        prepared=t("signed.prepared", builder_name=builder_name, report_date=report_date),
        footer=(before, middle, after),
        run_ids=tuple(run.id for run in all_runs),
        fix_estimates={group: estimate.model_dump(exclude_none=True) for group, estimate in inputs.fix_plan.items()},
    )
