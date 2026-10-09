"""The test runner (PRD 5.4; QA promises 13 and 17): loading a frozen set, running it within
its budget, resuming, re-scoring and the summary.

Most tests use a scripted answerer and judge, so each case is exact and free. The last runs the
real bot and judge on recorded replies. The questions are written for these tests only, on
Zulip articles the frozen test set doesn't use. Re-record with:
uv run pytest tests/integration/test_runner.py --record

These tests run one question at a time: they share one rolled-back connection, and two
questions can't use it at once.
"""

import datetime as dt
import functools
from decimal import Decimal

import pytest
import yaml
from scripted_run import (
    OPTIONS,
    QUESTIONS,
    SCRIPT,
    SHA,
    Scripted,
    correct,
    failing_client,
    frozen_set,
    no_wait,
    results,
    services,
    started,
)
from sqlalchemy import func, select
from zulip_subset import add_zulip

from citemark.db.models import TestQuestion
from citemark.embed import EmbedError
from citemark.evals import judge as judging
from citemark.evals import testset
from citemark.evals.runner import RunError, Services, load_test_set, prepare, rescore, run_tests, summary
from citemark.models.claude import ClaudeAnswerer
from citemark.models.registry import ContextTooLarge
from citemark.testing.fakes import FakeEmbedder, FakeReranker

# --- Loading (QA promise 13) ---


@pytest.mark.anyio
async def test_a_frozen_set_is_copied_into_the_database_once(session, tmp_path):
    path = frozen_set(tmp_path)
    first = await load_test_set(session, path)
    again = await load_test_set(session, path)
    count = await session.scalar(select(func.count()).where(TestQuestion.test_set_id == first.id))
    assert again.id == first.id and count == 5 and first.frozen_at is not None
    assert first.content_hash == testset.fingerprint(path)


@pytest.mark.anyio
async def test_an_edited_file_is_refused(session, tmp_path):
    """Promise 13: the runner refuses an edited file under the same version."""
    path = frozen_set(tmp_path)
    path.write_text(path.read_text().replace("profile picture", "avatar"))
    with pytest.raises(testset.TestSetChanged, match="changed after it was frozen"):
        await load_test_set(session, path)


@pytest.mark.anyio
async def test_a_file_that_differs_from_the_version_first_run_is_refused(session, tmp_path):
    (tmp_path / "a").mkdir()
    await load_test_set(session, frozen_set(tmp_path / "a"))
    (tmp_path / "b").mkdir()
    other = frozen_set(tmp_path / "b", QUESTIONS[:4])  # same name and version, frozen again elsewhere
    with pytest.raises(testset.TestSetChanged, match="doesn't match runner-test version 1 as first run"):
        await load_test_set(session, other)


@pytest.mark.anyio
async def test_a_set_that_isnt_frozen_is_refused(session, tmp_path):
    path = tmp_path / "draft-v1.yaml"
    path.write_text(yaml.safe_dump({"name": "draft", "version": 1, "questions": QUESTIONS}))
    with pytest.raises(RunError, match="isn't frozen"):
        await load_test_set(session, path)


# --- Running ---


@pytest.mark.anyio
async def test_a_run_asks_every_question_then_scores_and_judges_the_answers(session, sessions, tmp_path):
    answerer = Scripted(SCRIPT)
    run = await started(session, frozen_set(tmp_path), answerer)
    judged = []

    async def judge(**asked):
        judged.append(asked["question"])
        return await correct(**asked)

    outcome = await run_tests(run.id, sessions=sessions, services=services(answerer, judge=judge), parallel=1, sha=SHA)
    assert (outcome.status, outcome.finished, outcome.total) == ("done", 5, 5)

    found = await results(session, run.id)
    assert {ext_id: (r.kind, r.failure_type) for ext_id, r in found.items()} == {
        "Q001": ("answer", None),
        "Q002": ("partial", None),
        "Q003": ("answer", None),  # the follow-up's reply, after the bot asked which emails
        "Q004": ("decline_not_covered", None),
        "Q005": ("decline_off_topic", None),
    }
    assert found["Q001"].retrieval_hit and found["Q001"].citation_correct
    assert found["Q002"].answer.endswith("The help center doesn't say whether you can hide it from one person.")
    assert found["Q003"].clarify_options == OPTIONS and found["Q003"].retrieved
    assert found["Q004"].decline_correct and found["Q004"].judge_verdict is None  # declines aren't judged
    assert answerer.asked == [q["question"] for q in QUESTIONS[:3]] + ["New login emails"] + [
        q["question"] for q in QUESTIONS[3:]
    ]
    assert (
        judged[2] == "How do I stop getting emails?\n(Asked which one they meant, the customer chose: New login emails)"
    )
    assert len(judged) == 3

    await session.refresh(run)
    costs = sum(r.cost_usd for r in found.values())
    judging_cost = 3 * (100 * Decimal("4") + 50 * Decimal("20")) / 1_000_000  # Opus 5.5's prices
    assert run.status == "done" and run.finished_at and run.cost_usd == costs + judging_cost
    measures = (await summary(session, run.id)).measures
    assert (measures.correct_answers.passed, measures.correct_answers.total) == (3, 3)
    assert (measures.correct_declines.passed, measures.correct_declines.total) == (2, 2)


@pytest.mark.anyio
async def test_a_run_stops_at_its_budget_and_covers_only_what_ran(session, sessions, tmp_path):
    """Promise 17: at fake prices of $100 per million input tokens, a question costs about
    $0.10 and is estimated at about $0.15. With $0.40, the third would pass the cap."""
    answerer = Scripted(SCRIPT)
    run = await started(session, frozen_set(tmp_path), answerer, budget="0.40", price_per_mtok="100")
    outcome = await run_tests(run.id, sessions=sessions, services=services(answerer), parallel=1, sha=SHA)
    assert outcome.status == "over_budget" and outcome.finished == 2
    assert answerer.asked == [QUESTIONS[0]["question"], QUESTIONS[1]["question"]]
    await session.refresh(run)
    assert run.status == "over_budget" and run.cost_usd <= run.budget_usd
    assert sorted(await results(session, run.id)) == ["Q001", "Q002"]
    assert (await summary(session, run.id)).finished == 2


@pytest.mark.anyio
async def test_a_stopped_run_resumes_without_asking_finished_questions_again(session, sessions, tmp_path):
    stuck = QUESTIONS[2]["question"]
    first = Scripted(SCRIPT, failing=frozenset({stuck}))
    run = await started(session, frozen_set(tmp_path), first)
    outcome = await run_tests(run.id, sessions=sessions, services=services(first), parallel=1, sleep=no_wait, sha=SHA)
    assert outcome.status == "failed" and first.asked.count(stuck) == 3  # each attempt, then it gave up
    assert sorted(await results(session, run.id)) == ["Q001", "Q002"]
    await session.refresh(run)
    assert run.finished_at is None
    stored = sum(r.cost_usd for r in (await results(session, run.id)).values())
    judged = 2 * (100 * Decimal("4") + 50 * Decimal("20")) / 1_000_000  # Q001 and Q002, at Opus 5.5's prices
    attempt = (1_000 * Decimal("1") + 10 * Decimal("10")) / 1_000_000  # what each failed call was billed
    assert run.cost_usd - stored - judged >= 3 * attempt  # the failed attempts count

    second = Scripted(SCRIPT)
    outcome = await run_tests(run.id, sessions=sessions, services=services(second), parallel=1, sha=SHA)
    assert (outcome.status, outcome.finished) == ("done", 5)
    assert second.asked == [stuck, "New login emails", QUESTIONS[3]["question"], QUESTIONS[4]["question"]]


@pytest.mark.anyio
async def test_a_declined_answerable_question_isnt_judged_and_fails_as_a_wrong_decline(session, sessions, tmp_path):
    answerer = Scripted({**SCRIPT, QUESTIONS[0]["question"]: ("decline", "not_covered")})
    run = await started(session, frozen_set(tmp_path, QUESTIONS[:1]), answerer)
    judged = []

    async def judge(**asked):
        judged.append(asked)
        return await correct(**asked)

    await run_tests(run.id, sessions=sessions, services=services(answerer, judge=judge), parallel=1, sha=SHA)
    result = (await results(session, run.id))["Q001"]
    assert not judged and result.judge_verdict is None and result.failure_type == "declined_answerable"


class DownFor(FakeEmbedder):
    """An embedding service that stays down for one question, through every retry."""

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    async def embed_query(self, text: str):
        if text == self.question:
            raise EmbedError("The embedding service is down (a test outage).")
        return await super().embed_query(text)


@pytest.mark.anyio
async def test_an_outage_stops_the_run_as_resumable_and_keeps_what_finished(session, sessions, tmp_path):
    answerer = Scripted(SCRIPT)
    run = await started(session, frozen_set(tmp_path), answerer)
    down = Services(answerer, failing_client(), DownFor(QUESTIONS[1]["question"]), FakeReranker(), correct)
    outcome = await run_tests(run.id, sessions=sessions, services=down, parallel=1, sleep=no_wait, sha=SHA)
    assert outcome.status == "failed" and sorted(await results(session, run.id)) == ["Q001"]
    await session.refresh(run)
    assert run.status == "failed" and run.finished_at is None


@pytest.mark.anyio
async def test_an_unexpected_error_ends_the_run_as_failed_not_stuck_running(session, sessions, tmp_path):
    class Broken(Scripted):
        async def stream(self, request):
            raise RuntimeError("a bug")
            yield  # an async generator, like the real one

    answerer = Broken(SCRIPT)
    run = await started(session, frozen_set(tmp_path), answerer)
    outcome = await run_tests(run.id, sessions=sessions, services=services(answerer), parallel=1, sha=SHA)
    await session.refresh(run)
    assert outcome.status == run.status == "failed" and not await results(session, run.id)


@pytest.mark.anyio
async def test_a_run_marked_running_is_resumed_only_with_force(session, sessions, tmp_path):
    """Either another process is running it, or its process was killed before marking how it ended."""
    answerer = Scripted(SCRIPT)
    run = await started(session, frozen_set(tmp_path, QUESTIONS[3:]), answerer)
    run.status = "running"
    await session.commit()
    with pytest.raises(RunError, match="resume it with --force"):
        await run_tests(run.id, sessions=sessions, services=services(answerer), parallel=1, sha=SHA)
    outcome = await run_tests(run.id, sessions=sessions, services=services(answerer), parallel=1, force=True, sha=SHA)
    assert outcome.status == "done"


@pytest.mark.anyio
async def test_a_judge_reply_with_no_verdict_still_counts_what_it_cost(session, sessions, tmp_path):
    answerer = Scripted(SCRIPT)
    run = await started(session, frozen_set(tmp_path, QUESTIONS[:1]), answerer)
    tries = []

    async def unusable_once(**asked):
        tries.append(asked)
        if len(tries) == 1:
            raise judging.JudgeError("The judge stopped early (max_tokens).", 1_000, 16_000)
        return await correct(**asked)

    flaky = services(answerer, judge=unusable_once)
    await run_tests(run.id, sessions=sessions, services=flaky, parallel=1, sleep=no_wait, sha=SHA)
    await session.refresh(run)
    [result] = (await results(session, run.id)).values()
    wasted = (1_000 * Decimal("4") + 16_000 * Decimal("20")) / 1_000_000  # Opus 5.5's prices
    judged = (100 * Decimal("4") + 50 * Decimal("20")) / 1_000_000
    assert len(tries) == 2 and run.cost_usd == result.cost_usd + judged + wasted


@pytest.mark.anyio
async def test_a_run_is_resumed_only_with_its_own_settings(session, sessions, tmp_path):
    run = await started(session, frozen_set(tmp_path), Scripted(SCRIPT))
    with pytest.raises(RunError, match="Resume it with the same settings"):
        await run_tests(
            run.id, sessions=sessions, services=services(Scripted(SCRIPT, model="claude-haiku-5-5")), sha=SHA
        )


@pytest.mark.anyio
async def test_rescoring_a_stored_run_twice_gives_identical_scores(session, sessions, tmp_path):
    answerer = Scripted(SCRIPT)
    run = await started(session, frozen_set(tmp_path), answerer)
    await run_tests(run.id, sessions=sessions, services=services(answerer), parallel=1, sha=SHA)
    stored = {k: (r.retrieval_hit, r.citation_correct, r.decline_correct, r.failure_type)
              for k, r in (await results(session, run.id)).items()}  # fmt: skip
    once = await rescore(session, run.id)
    twice = await rescore(session, run.id)
    assert once == twice
    assert {
        k: (s.retrieval_hit, s.citation_correct, s.decline_correct, s.failure_type) for k, s in once.items()
    } == stored


@pytest.mark.anyio
async def test_full_context_mode_is_refused_for_a_model_whose_window_cant_hold_the_help_center(session, tmp_path):
    """Measured, not estimated (PRD 5.2): Haiku 4.5 counted Zulip's help center at about 265K."""
    answerer = Scripted(SCRIPT, model="claude-haiku-4-5", window=265_000)
    test_set = await load_test_set(session, frozen_set(tmp_path))
    await add_zulip(session)
    with pytest.raises(ContextTooLarge, match="doesn't fit the model's 200,000-token window"):
        await prepare(
            session, test_set.id, mode="full_context", answerer=answerer, embedder=FakeEmbedder(),
            reranker=None, on=dt.date(2026, 10, 9),
        )  # fmt: skip


@pytest.mark.anyio
async def test_full_context_mode_scores_no_retrieval_and_pays_once_to_cache_the_help_center(
    session, sessions, tmp_path
):
    answerer = Scripted(SCRIPT, model="claude-sonnet-5-5", window=20_000)  # the window check needs a real model
    run = await started(session, frozen_set(tmp_path), answerer, mode="full_context")
    prepared = await prepare(
        session, run.test_set_id, mode="full_context", answerer=answerer, embedder=FakeEmbedder(), reranker=None,
        on=dt.date(2026, 10, 9),
    )  # fmt: skip
    first, *rest = prepared.questions
    assert prepared.docs_tokens == 20_000 and prepared.estimates[first.id] > prepared.estimates[rest[0].id]
    outcome = await run_tests(run.id, sessions=sessions, services=services(answerer), parallel=1, sha=SHA)
    assert outcome.status == "done"
    found = await results(session, run.id)
    assert found["Q001"].retrieval_hit is None and not found["Q001"].retrieved and found["Q001"].citation_correct
    assert (await summary(session, run.id)).measures.right_place is None


# --- The real bot and judge, on recorded replies ---


@pytest.mark.anyio
async def test_the_real_bot_and_judge_run_a_test_set(session, sessions, tmp_path, anthropic_client):
    path = frozen_set(tmp_path)
    answerer = ClaudeAnswerer(anthropic_client, "claude-haiku-5-5", company="Zulip")
    run = await started(session, path, answerer)
    real = Services(
        answerer, anthropic_client, FakeEmbedder(), FakeReranker(), functools.partial(judging.judge, anthropic_client)
    )
    outcome = await run_tests(run.id, sessions=sessions, services=real, parallel=1, sleep=no_wait, sha=SHA)
    assert (outcome.status, outcome.finished) == ("done", 5)
    found = await results(session, run.id)
    assert found["Q005"].decline_correct is True
    for result in found.values():
        judged = result.kind in ("answer", "partial") and result.judge_verdict is not None
        assert judged == (result.judge_output is not None)
    stored = {k: r.failure_type for k, r in found.items()}
    assert {k: s.failure_type for k, s in (await rescore(session, run.id)).items()} == stored
    await session.refresh(run)
    assert run.cost_usd > 0 and run.git_sha == "test"


# --- The command line ---


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (
            lambda path: path.write_text(path.read_text().replace("profile picture", "avatar")),
            "changed after it was frozen",
        ),
        (lambda path: testset.lock_path(path).unlink(), "isn't frozen"),
    ],
    ids=["edited", "not frozen"],
)
def test_the_command_refuses_an_edited_or_unfrozen_set_before_calling_anything(tmp_path, monkeypatch, edit, message):
    from typer.testing import CliRunner

    from citemark.cli import app
    from citemark.settings import get_settings

    monkeypatch.setenv("ANTHROPIC_API_KEY", "unused")
    monkeypatch.setenv("VOYAGE_API_KEY", "unused")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://nobody@localhost:1/none"
    )  # if a check were missed, the command still couldn't write anywhere
    get_settings.cache_clear()
    try:
        path = frozen_set(tmp_path)
        edit(path)
        result = CliRunner().invoke(app, ["test", "run", str(path), "--company", "Zulip", "--budget", "1", "--yes"])
    finally:
        get_settings.cache_clear()
    assert result.exit_code == 1 and message in result.output
