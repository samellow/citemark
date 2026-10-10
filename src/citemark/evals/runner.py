"""The test runner (PRD 5.4): a frozen test set asked of the bot, then scored and judged.

- **Loading:** the YAML must be frozen and still match its lock (QA promise 13). The first run
  copies it into the database; later runs check that the copy has the same fingerprint.
- **Running:** 4 questions at a time, each retried with backoff. A finished question is saved
  with what it cost in one transaction, so a run that stops resumes where it left off.
- **The budget** (QA promise 17): each question reserves its estimated cost before it starts,
  and none starts once spent plus reserved would pass the cap. The run then ends
  `over_budget`, and its results cover only the questions that ran. Money spent on failed
  attempts counts too.
- **Ambiguous questions:** when the bot asks which meaning, the runner picks the option holding
  an expected phrasing and sends it as the follow-up, which is scored like any answer.
- **Full-context mode:** the window is checked on a measured count first (PRD 5.2), and the
  first question runs alone, so the others read the help center from the cache instead of
  each paying to write it.

The judge grades answers only (`evals.judge`). Everything else is scored mechanically
(`evals.scoring`) from what each result stores, so `rescore` gives the same scores every time.
The abuse set isn't judged at all: its rules are mechanical (`evals.abuse`).
"""

from __future__ import annotations

import datetime as dt
import os
import statistics
import subprocess
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

import anthropic
import anyio
import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from citemark.answer import Reply
from citemark.answer.pipeline import Answered, passages_from_articles, respond
from citemark.costs import price
from citemark.db.models import Document, TestQuestion, TestResult, TestRun, TestSet
from citemark.embed import Embedder, EmbedError, Reranker
from citemark.evals import judge as judging
from citemark.evals import testset
from citemark.evals.scoring import (
    ANSWER_EXPECTED,
    JUDGED,
    Scores,
    Summary,
    chosen_option,
    failure_type,
    score,
    summarize,
)
from citemark.evals.voice import voice_problems
from citemark.ingest.files import extract_file
from citemark.ingest.pipeline import UPLOAD_PREFIX, content_hash
from citemark.models import AnswerModel, AnswerRequest, Turn
from citemark.models.claude import MAX_TOKENS
from citemark.models.registry import require_fit
from citemark.retrieve import RetrievalConfig
from citemark.retrieve.context import Article, full_context
from citemark.retrieve.rewrite import MODEL as REWRITE_MODEL

log = structlog.get_logger()

KIT = Path(__file__).resolve().parents[3]
PARALLEL = 4
ATTEMPTS = 3
BACKOFF = 2.0  # seconds before the second attempt, doubled before each one after
STORED_PLACES = Decimal("0.000001")
UNKNOWN_COMMIT = "unknown"
DIRTY = "-dirty"  # marks a commit with uncommitted changes on top

# The estimate shown before a run, per call, in tokens, kept a little above what was measured.
# T8's recordings: an answer read about 1,500 new tokens and 2,300 cached ones, and wrote about
# 300. T9's: the judge read about 800 and wrote 93 to 224, thinking included, at high effort.
ANSWER_INPUT, ANSWER_CACHED, ANSWER_OUTPUT = 1_500, 2_300, 400
JUDGE_INPUT, JUDGE_OUTPUT = 900, 500
REWRITE_INPUT, REWRITE_OUTPUT = 200, 20
EMBED_TOKENS, RERANK_TOKENS = 20, 7_000

JudgeFn = Callable[..., Awaitable[judging.Verdict]]
OnResult = Callable[[str, TestResult], None]
Sleep = Callable[[float], Awaitable[None]]


class RunError(Exception):
    """The run can't go ahead. The message is one plain sentence."""


class QuestionFailed(Exception):
    """A question that failed every attempt. The run stops, and can be resumed."""


@dataclass(frozen=True)
class Services:
    """What a run calls. The CLI passes the real ones; tests can pass stand-ins."""

    answerer: AnswerModel
    client: anthropic.AsyncAnthropic  # rewrites the follow-up of an ambiguous question
    embedder: Embedder
    reranker: Reranker | None
    judge: JudgeFn  # `evals.judge.judge`, with its client bound


def git_sha(root: Path = KIT) -> str:
    """The commit the kit runs from, marked `-dirty` when it has uncommitted changes, since the
    commit alone couldn't reproduce that run. `CITEMARK_GIT_SHA` wins where there's no repository."""
    if from_env := os.environ.get("CITEMARK_GIT_SHA"):
        return from_env
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return UNKNOWN_COMMIT
    return sha.stdout.strip() + (DIRTY if dirty.stdout.strip() else "")


# --- Loading ---


async def load_test_set(session: AsyncSession, path: Path) -> TestSet:
    """The frozen test set at `path`, copied into the database by its first run."""
    loaded = testset.load(path)
    lock = testset.verify_unchanged(path)
    if lock is None:
        raise RunError(f"{path.name} isn't frozen, so its results couldn't be compared. Freeze it first.")
    found = await session.scalar(select(TestSet).where(TestSet.name == loaded.name, TestSet.version == loaded.version))
    if found is not None:
        if found.content_hash != lock["sha256"]:
            raise testset.TestSetChanged(
                f"{path.name} doesn't match {loaded.name} version {loaded.version} as first run, which has the "
                f"fingerprint {(found.content_hash or '')[:8]}. Put changes in version {loaded.version + 1} instead."
            )
        return found
    test_set = TestSet(name=loaded.name, version=loaded.version, kind=loaded.kind.value, content_hash=lock["sha256"])
    session.add(test_set)
    await session.flush()
    session.add_all(
        TestQuestion(
            test_set_id=test_set.id,
            ext_id=question.id,
            type=question.type.value,
            question=question.question,
            expected_answer=question.expected_answer,
            expected_sources=[source.model_dump() for source in question.expected_sources],
            expected_option=question.expected_option,
            uncovered_part=question.uncovered_part,
            not_covered_terms=question.not_covered_terms,
            doc_gap=question.doc_gap,
            locked=question.locked,
            abuse_kind=question.abuse_kind.value if question.abuse_kind else None,
            must_not_contain=question.must_not_contain,
            planted_article=question.planted_article,
            planted_hash=planted_hash(path, question.planted_article) if question.planted_article else None,
            notes=question.notes,
        )
        for question in loaded.questions
    )
    await session.flush()
    test_set.frozen_at = dt.datetime.fromisoformat(lock["frozen_at"])  # from here the database refuses changes
    await session.flush()
    return test_set


def planted_hash(path: Path, name: str) -> str:
    """The content hash a planted article next to the set at `path` is indexed under."""
    return content_hash(extract_file(name, (path.parent / name).read_bytes()))


async def check_index(session: AsyncSession, test_set_id: uuid.UUID) -> None:
    """Refuse a database whose index would skew the set (QA plan 4.3). Checked as every run starts
    or resumes, before anything is called.

    An abuse set's planted articles must be indexed there as they were frozen, and no other
    planted article may be, or the attack wouldn't be the frozen one. An accuracy set must never
    meet a planted article, so they live in a separate database, built from the same help center."""
    kind = await session.scalar(select(TestSet.kind).where(TestSet.id == test_set_id))
    rows = await session.execute(
        select(Document.url, Document.content_hash).where(
            Document.status == "active", Document.url.like(f"{UPLOAD_PREFIX}%{testset.PLANTED_SUFFIX}")
        )
    )
    indexed: dict[str, set[str | None]] = {}
    for url, digest in rows:
        indexed.setdefault(url.removeprefix(UPLOAD_PREFIX), set()).add(digest)
    if kind != testset.SetKind.ABUSE:
        if indexed:
            raise RunError(
                f"This database holds {min(indexed)}, an article planted for the abuse set, so search could give "
                "it to the bot. Run accuracy sets against a database without it."
            )
        return
    planted = await session.execute(
        select(TestQuestion.planted_article, TestQuestion.planted_hash)
        .where(TestQuestion.test_set_id == test_set_id, TestQuestion.planted_article.is_not(None))
        .distinct()
    )
    wanted: dict[str, str | None] = {name: digest for name, digest in planted}
    for name, digest in sorted(wanted.items()):
        if name not in indexed:
            raise RunError(
                f"{name} isn't indexed in this database, so the questions it plants instructions for would never "
                f"meet them. Upload it, from beside the set's file, to the abuse set's own database: "
                f"citemark sources upload {name}"
            )
        if indexed[name] != {digest}:  # search finds every active copy
            raise RunError(
                f"The copy of {name} indexed here isn't the one the set was frozen with. Upload it again, from "
                f"beside the set's file: citemark sources upload {name}"
            )
    if others := sorted(set(indexed) - set(wanted)):
        raise RunError(
            f"This database also holds {others[0]}, planted for another set, so search could give it to the bot. "
            "Build this set's database again from the accuracy one, with only its own planted articles."
        )


# --- Preparing: the passages, the window check and the estimate ---


@dataclass(frozen=True)
class Prepared:
    questions: list[TestQuestion]
    articles: list[Article] | None  # full-context mode only
    docs_tokens: int  # the whole help center as the model counts it; 0 in search mode
    estimates: dict[uuid.UUID, Decimal]  # each question's estimated cost, reserved before it starts

    @property
    def estimate(self) -> Decimal:
        return sum(self.estimates.values(), Decimal(0))


async def prepare(
    session: AsyncSession,
    test_set_id: uuid.UUID,
    *,
    mode: str,
    answerer: AnswerModel,
    embedder: Embedder,
    reranker: Reranker | None,
    on: dt.date,
) -> Prepared:
    questions = list(
        await session.scalars(
            select(TestQuestion).where(TestQuestion.test_set_id == test_set_id).order_by(TestQuestion.ext_id)
        )
    )
    articles: list[Article] | None = None
    docs_tokens = 0
    if mode == "full_context":
        articles = await full_context(session)
        sample = questions[0].question if questions else "?"  # the API refuses an empty question
        docs_tokens = await answerer.count_tokens(
            AnswerRequest(sample, passages_from_articles(articles), full_context=True)
        )
        require_fit(answerer.model, docs_tokens, MAX_TOKENS)

    async def cost(model: str, **tokens: int) -> Decimal:
        return await price(session, model, on=on, **tokens)

    if articles is None:
        answer = await cost(
            answerer.model, input_tokens=ANSWER_INPUT, output_tokens=ANSWER_OUTPUT, cache_read_tokens=ANSWER_CACHED
        )
        answer += await cost(embedder.model, input_tokens=EMBED_TOKENS)
        if reranker is not None:
            answer += await cost(reranker.model, input_tokens=RERANK_TOKENS)
    else:
        answer = await cost(
            answerer.model, input_tokens=ANSWER_INPUT, output_tokens=ANSWER_OUTPUT, cache_read_tokens=docs_tokens
        )
    judged = await cost(judging.MODEL, input_tokens=JUDGE_INPUT, output_tokens=JUDGE_OUTPUT)
    follow_up = answer + await cost(REWRITE_MODEL, input_tokens=REWRITE_INPUT, output_tokens=REWRITE_OUTPUT)

    estimates = {}
    for question in questions:
        estimate = answer
        if question.type == "ambiguous":
            estimate += follow_up
        if question.type in ANSWER_EXPECTED and question.abuse_kind is None:
            estimate += judged
        estimates[question.id] = estimate
    if articles is not None and questions:  # the first question writes the help center to the cache
        estimates[questions[0].id] += await cost(answerer.model, cache_write_tokens=docs_tokens)
    return Prepared(questions, articles, docs_tokens, estimates)


async def create_run(
    session: AsyncSession,
    test_set: TestSet,
    *,
    mode: str,
    answerer: AnswerModel,
    config: RetrievalConfig,
    budget_usd: Decimal,
    sha: str,
    decision_group: uuid.UUID | None = None,
) -> TestRun:
    run = TestRun(
        test_set_id=test_set.id,
        decision_group=decision_group,
        mode=mode,
        model=answerer.model,
        company=answerer.company,
        prompt_version=answerer.prompt_version,
        retrieval_config=config.model_dump() if mode == "retrieval" else None,
        git_sha=sha,
        judge_model=judging.MODEL,
        rubric_version=judging.RUBRIC,
        budget_usd=budget_usd,
    )
    session.add(run)
    await session.flush()
    return run


# --- Running ---


@dataclass
class _Budget:
    """Money spent and reserved, changed only while holding the run's condition, so two
    questions can't both take the last of the budget."""

    budget: Decimal
    spent: Decimal
    reserved: Decimal = Decimal(0)
    stopped: str | None = None  # over_budget or failed


@dataclass(frozen=True)
class Asked:
    first: Answered
    final: Answered  # the follow-up's reply when an ambiguous question was clarified, else `first`
    option: str | None  # the option sent as the follow-up
    verdict: judging.Verdict | None
    judge_cost: Decimal

    @property
    def bot_cost(self) -> Decimal:
        return self.first.cost_usd + (self.final.cost_usd if self.final is not self.first else Decimal(0))


@dataclass(frozen=True)
class Outcome:
    status: str  # done, over_budget or failed
    finished: int  # questions with a result, including those from before a resume
    total: int
    spent: Decimal


def _fields(question: TestQuestion) -> dict[str, Any]:
    return {
        "type": question.type,
        "expected_sources": question.expected_sources,
        "expected_option": question.expected_option,
    }


def _shown(reply: Reply) -> str:
    """The reply as the visitor saw it, gap line and options included: what the judge reads."""
    return reply.as_turn().text


def _retrieved(answered: Answered) -> list[dict[str, Any]]:
    return [
        {
            "rank": hit.rank,
            "chunk_id": str(hit.chunk_id),
            "url": hit.url,
            "heading_path": hit.heading_path,
            "blocks": hit.blocks,
            "vector_score": hit.vector_score,
            "keyword_score": hit.keyword_score,
            "rerank_score": hit.rerank_score,
        }
        for hit in answered.hits
    ]


def _citations(answered: Answered) -> list[dict[str, Any]]:
    return [
        {
            "marker": source.marker,
            "chunk_id": str(source.chunk_id),
            "url": source.url,
            "heading_path": source.title,
            "cited_text": source.cited_text,
            "start_block": source.start_block,
            "end_block": source.end_block,
            "blocks": list(answered.passages[source.passage].blocks),
        }
        for source in answered.reply.sources
    ]


def _segments(reply: Reply) -> list[dict[str, Any]] | None:
    if reply.kind not in JUDGED:
        return None
    return [{"text": segment.text, "markers": list(segment.markers)} for segment in reply.segments]


def _stored(cost: Decimal) -> Decimal:
    return cost.quantize(STORED_PLACES, rounding=ROUND_CEILING)


async def _spend(sessions: async_sessionmaker[AsyncSession], run_id: uuid.UUID, budget: _Budget, cost: Decimal) -> None:
    """Money spent on an attempt that failed still counts against the budget."""
    if cost <= 0:
        return
    cost = _stored(cost)
    budget.spent += cost
    async with sessions() as session, session.begin():
        await session.execute(update(TestRun).where(TestRun.id == run_id).values(cost_usd=TestRun.cost_usd + cost))


async def _retrying[T](attempt: Callable[[], Awaitable[T]], *, attempts: int, sleep: Sleep, what: str) -> T:
    """Retry what an outage can cause: a failed model call, a judge with no verdict, an
    embedding service that stayed down through its own retries."""
    wait = BACKOFF
    for number in range(1, attempts + 1):
        try:
            return await attempt()
        except (QuestionFailed, judging.JudgeError, EmbedError) as exc:
            log.warning("test_attempt_failed", what=what, attempt=number, error=str(exc))
            if number == attempts:
                raise QuestionFailed(f"{what} failed {attempts} times: {exc}") from exc
            await sleep(wait)
            wait *= 2
    raise AssertionError("attempts must be at least 1")


async def _ask(
    question: TestQuestion,
    *,
    run_id: uuid.UUID,
    sessions: async_sessionmaker[AsyncSession],
    services: Services,
    config: RetrievalConfig,
    articles: list[Article] | None,
    budget: _Budget,
    attempts: int,
    sleep: Sleep,
) -> Asked:
    async def answer(message: str, history: Sequence[Turn] = ()) -> Answered:
        async with sessions() as session:
            answered = await respond(
                session,
                message,
                model=services.answerer,
                rewriter=services.client,
                embedder=services.embedder,
                reranker=services.reranker,
                config=config,
                history=history,
                articles=articles,
            )
        if answered.reply.kind == "error":
            await _spend(sessions, run_id, budget, answered.cost_usd)
            raise QuestionFailed("; ".join(answered.reply.problems) or "the model call failed")
        return answered

    async def answers() -> tuple[Answered, Answered, str | None]:
        first = await answer(question.question)
        option = None
        if question.type == "ambiguous" and first.reply.kind == "clarify":
            option = chosen_option(first.reply.clarify_options, question.expected_option)
        if option is None:
            return first, first, None
        try:
            follow_up = await answer(option, (Turn("user", question.question), first.reply.as_turn()))
        except BaseException:
            with anyio.CancelScope(shield=True):  # the first reply was paid for, whatever happens next
                await _spend(sessions, run_id, budget, first.cost_usd)
            raise
        return first, follow_up, option

    first, final, option = await _retrying(answers, attempts=attempts, sleep=sleep, what=f"{question.ext_id}'s answer")
    answered = Asked(first, final, option, None, Decimal(0))
    if question.abuse_kind is not None or question.type not in ANSWER_EXPECTED or final.reply.kind not in JUDGED:
        return answered  # the abuse set is scored mechanically
    if question.type == "ambiguous" and option is None:
        return answered  # it answered without asking which meaning: wrong, whatever it said

    asked = question.question
    if option is not None:
        asked += f"\n(Asked which one they meant, the customer chose: {option})"
    today = dt.datetime.now(dt.UTC).date()

    async def judge_cost(input_tokens: int, output_tokens: int) -> Decimal:
        async with sessions() as session:
            return await price(session, judging.MODEL, on=today, input_tokens=input_tokens, output_tokens=output_tokens)

    async def grade() -> judging.Verdict:
        try:
            return await services.judge(
                question=asked,
                qtype=question.type,
                expected_answer=question.expected_answer,
                sources=question.expected_sources,
                answer=_shown(final.reply),
                uncovered_part=question.uncovered_part,
            )
        except judging.JudgeError as exc:  # a reply with no usable verdict was still billed
            await _spend(sessions, run_id, budget, await judge_cost(exc.input_tokens, exc.output_tokens))
            raise

    try:
        verdict = await _retrying(grade, attempts=attempts, sleep=sleep, what=f"{question.ext_id}'s judging")
    except BaseException:
        with anyio.CancelScope(shield=True):  # the answers were paid for, though the question won't be saved
            await _spend(sessions, run_id, budget, answered.bot_cost)
        raise
    return Asked(first, final, option, verdict, await judge_cost(verdict.input_tokens, verdict.output_tokens))


def _failure(question: TestQuestion, scores: Scores) -> str | None:
    """The failure type, which is an accuracy measure: an abuse question's result has none."""
    return None if question.abuse_kind is not None else scores.failure_type


def _result(run_id: uuid.UUID, mode: str, question: TestQuestion, asked: Asked) -> TestResult:
    """The question's stored result. Its cost is the bot's alone, which is what a conversation
    costs a client; the judge's is added to the run's total, with money spent on failed attempts."""
    first, final = asked.first.reply, asked.final.reply
    retrieved, citations = _retrieved(asked.final), _citations(asked.final)
    options = list(first.clarify_options) if first.kind == "clarify" and first.clarify_options else None
    verdict = asked.verdict
    scores = score(
        _fields(question),
        mode=mode,
        kind=final.kind,
        retrieved=retrieved,
        citations=citations,
        clarify_options=options,
        judge_verdict=verdict.verdict if verdict else None,
    )
    return TestResult(
        test_run_id=run_id,
        test_question_id=question.id,
        answer=_shown(final),
        kind=final.kind,
        segments=_segments(final),
        gap_text=final.gap if final.kind == "partial" else None,
        swapped=first.swapped or final.swapped,
        citations=citations,
        clarify_options=options,
        retrieved=retrieved,
        retrieval_hit=scores.retrieval_hit,
        citation_correct=scores.citation_correct,
        decline_correct=scores.decline_correct,
        judge_verdict=verdict.verdict if verdict else None,
        judge_reason=verdict.reason if verdict else None,
        judge_output=verdict.output if verdict else None,
        failure_type=_failure(question, scores),
        ttfw_ms=asked.first.ttfw_ms,
        cost_usd=_stored(asked.bot_cost),
    )


async def run_tests(
    run_id: uuid.UUID,
    *,
    sessions: async_sessionmaker[AsyncSession],
    services: Services,
    on_result: OnResult | None = None,
    parallel: int = PARALLEL,
    attempts: int = ATTEMPTS,
    sleep: Sleep = anyio.sleep,
    force: bool = False,
    sha: str,
) -> Outcome:
    """Ask every question of the run that has no result yet, then mark how the run ended.

    A run marked `running` is refused unless `force` is given: either another process is
    running it, or its process was killed before it could mark how it ended. A run goes on only
    from the commit it started on (`sha`), so all its answers come from one version of the code
    (PRD Q17). Two different sets of uncommitted changes on one commit can't be told apart, which
    is why a decision run never starts from any."""
    async with sessions() as session, session.begin():
        run = await session.get(TestRun, run_id)
        if run is None:
            raise RunError(f"There's no test run {run_id}.")
        if run.status == "running" and not force:
            raise RunError(
                f"Run {run_id} is marked as running. If no other process is running it, because the last one "
                "stopped without finishing, resume it with --force."
            )
        if sha != run.git_sha:
            raise RunError(
                f"Run {run_id} started from commit {run.git_sha}, and this is {sha}. A run goes on only from the "
                "commit it started on, so all its answers come from one version of the code."
            )
        given = (services.answerer.model, services.answerer.company, services.answerer.prompt_version)
        if given != (run.model, run.company, run.prompt_version):
            raise RunError(
                f"Run {run_id} was started with {run.model}, for {run.company}, on prompt {run.prompt_version}. "
                "Resume it with the same settings."
            )
        await check_index(session, run.test_set_id)
        mode = run.mode
        config = RetrievalConfig.model_validate(run.retrieval_config or {})
        prepared = await prepare(
            session,
            run.test_set_id,
            mode=mode,
            answerer=services.answerer,
            embedder=services.embedder,
            reranker=services.reranker,
            on=dt.datetime.now(dt.UTC).date(),
        )
        finished = set(
            await session.scalars(select(TestResult.test_question_id).where(TestResult.test_run_id == run_id))
        )
        run.status = "running"
        run.started_at = run.started_at or dt.datetime.now(dt.UTC)
        run.finished_at = None  # a resumed run isn't finished, whatever ended it before
        budget = _Budget(run.budget_usd, run.cost_usd)
    pending = [question for question in prepared.questions if question.id not in finished]
    done = len(finished)
    changed = anyio.Condition()  # a question finished, so money that was reserved is now known

    async def reserve(estimate: Decimal) -> bool:
        """Reserve a question's estimated cost. While other questions hold reservations, wait for
        one to finish rather than stop: they usually cost less than their estimates."""
        async with changed:
            while not budget.stopped:
                if budget.spent + budget.reserved + estimate <= budget.budget:
                    budget.reserved += estimate
                    return True
                if budget.reserved <= 0:
                    budget.stopped = "over_budget"
                else:
                    await changed.wait()
            return False

    async def settle(estimate: Decimal, spent: Decimal) -> None:
        """Release a reservation and count what was spent, before anything else can await."""
        async with changed:
            budget.reserved -= estimate
            budget.spent += spent
            changed.notify_all()

    async def one(question: TestQuestion, limiter: anyio.CapacityLimiter) -> None:
        nonlocal done
        async with limiter:
            estimate = prepared.estimates[question.id]
            if not await reserve(estimate):
                return
            spent = Decimal(0)
            try:
                asked = await _ask(
                    question,
                    run_id=run_id,
                    sessions=sessions,
                    services=services,
                    config=config,
                    articles=prepared.articles,
                    budget=budget,
                    attempts=attempts,
                    sleep=sleep,
                )
                result = _result(run_id, mode, question, asked)
                spent = result.cost_usd + _stored(asked.judge_cost)
            except Exception as exc:  # one question's failure stops the run, but not the questions in flight
                log.error(
                    "test_question_failed", run_id=str(run_id), question=question.ext_id, error=str(exc) or repr(exc)
                )
                budget.stopped = budget.stopped or "failed"
                return
            finally:
                with anyio.CancelScope(shield=True):
                    await settle(estimate, spent)
            try:
                async with sessions() as session, session.begin():
                    session.add(result)
                    await session.execute(
                        update(TestRun).where(TestRun.id == run_id).values(cost_usd=TestRun.cost_usd + spent)
                    )
            except Exception as exc:
                log.error("test_result_not_saved", run_id=str(run_id), question=question.ext_id, error=str(exc))
                budget.stopped = budget.stopped or "failed"
                return
            done += 1
            if on_result is not None:
                on_result(question.ext_id, result)

    completed = False
    try:
        if prepared.articles is not None and pending:  # one question first, so the rest read the cache
            await one(pending[0], anyio.CapacityLimiter(1))
            pending = pending[1:]
        limiter = anyio.CapacityLimiter(parallel)
        async with anyio.create_task_group() as group:
            for question in pending:
                group.start_soon(one, question, limiter)
        completed = True
    finally:
        status = (budget.stopped or "done") if completed else "failed"  # interrupted, so it can be resumed
        with anyio.CancelScope(shield=True):
            async with sessions() as session, session.begin():
                values: dict[str, Any] = {"status": status}
                if status != "failed":  # a failed run can be resumed, so it isn't finished
                    values["finished_at"] = dt.datetime.now(dt.UTC)
                await session.execute(update(TestRun).where(TestRun.id == run_id).values(**values))
    log.info("test_run_ended", run_id=str(run_id), status=status, finished=done, total=len(prepared.questions))
    return Outcome(status, done, len(prepared.questions), budget.spent)


# --- A stored run: its scores and summary ---


async def _results(session: AsyncSession, run_id: uuid.UUID) -> tuple[TestRun, list[tuple[TestResult, TestQuestion]]]:
    run = await session.get(TestRun, run_id)
    if run is None:
        raise RunError(f"There's no test run {run_id}.")
    rows = await session.execute(
        select(TestResult, TestQuestion)
        .join(TestQuestion, TestResult.test_question_id == TestQuestion.id)
        .where(TestResult.test_run_id == run_id)
        .order_by(TestQuestion.ext_id)
    )
    return run, [(result, question) for result, question in rows]


async def rescore(session: AsyncSession, run_id: uuid.UUID) -> dict[str, Scores]:
    """Recompute every mechanical score from what the results store (`citemark test rescore`).
    The judge isn't asked again: its stored verdict counts."""
    run, rows = await _results(session, run_id)
    scored = {}
    for result, question in rows:
        scores = score(
            _fields(question),
            mode=run.mode,
            kind=result.kind,
            retrieved=result.retrieved,
            citations=result.citations,
            clarify_options=result.clarify_options,
            judge_verdict=result.judge_verdict,
        )
        result.retrieval_hit = scores.retrieval_hit
        result.citation_correct = scores.citation_correct
        result.decline_correct = scores.decline_correct
        result.failure_type = _failure(question, scores)
        scored[question.ext_id] = scores
    await session.flush()
    return scored


def summary_row(result: TestResult, question: TestQuestion, *, verdict: str | None) -> dict[str, Any]:
    """What `summarize` reads from one result, with the verdict that counts: the judge's, or
    yours on a decision run's graded answer (`evals.decision`). A different verdict can change
    the failure type, so it's assigned again."""
    clarified = None
    if question.type == "ambiguous":
        clarified = chosen_option(result.clarify_options, question.expected_option) is not None
    failure = result.failure_type
    if verdict != result.judge_verdict:
        failure = failure_type(
            question.type,
            result.kind,
            clarified=clarified,
            retrieval_hit=result.retrieval_hit,
            citation_correct=result.citation_correct,
            judge_verdict=verdict,
        )
    return {
        "type": question.type,
        "kind": result.kind,
        "judge_verdict": verdict,
        "clarified": clarified,
        "retrieval_hit": result.retrieval_hit,
        "citation_correct": result.citation_correct,
        "decline_correct": result.decline_correct,
        "failure_type": failure,
        "swapped": result.swapped,
    }


@dataclass(frozen=True)
class RunSummary:
    run: TestRun
    measures: Summary
    voice: dict[str, list[str]]  # question ID: what its answer did against the voice rules
    finished: int
    total: int
    median_ttfw_ms: int | None


async def summary(session: AsyncSession, run_id: uuid.UUID) -> RunSummary:
    run, rows = await _results(session, run_id)
    total = await session.scalar(
        select(func.count()).select_from(TestQuestion).where(TestQuestion.test_set_id == run.test_set_id)
    )
    flat = []
    voice: dict[str, list[str]] = {}
    for result, question in rows:
        flat.append(summary_row(result, question, verdict=result.judge_verdict))
        if result.kind in JUDGED and (problems := voice_problems(result.answer or "")):
            voice[question.ext_id] = problems
    times = [result.ttfw_ms for result, _ in rows if result.ttfw_ms is not None]
    return RunSummary(
        run=run,
        measures=summarize(flat, mode=run.mode),
        voice=voice,
        finished=len(rows),
        total=total or 0,
        median_ttfw_ms=round(statistics.median(times)) if times else None,
    )
