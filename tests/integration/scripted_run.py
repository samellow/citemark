"""A scripted answerer and judge, and the test set they answer, for tests of the runner and of
decision runs: each case is exact and free. The questions are written for these tests only, on
Zulip articles the frozen test set doesn't use."""

import datetime as dt
from collections import Counter
from decimal import Decimal
from pathlib import Path

import anthropic
import httpx2
import yaml
from sqlalchemy import select
from zulip_subset import add_zulip

from citemark.db.models import Price, TestQuestion, TestResult, TestRun, TestSet
from citemark.evals import judge as judging
from citemark.evals import testset
from citemark.evals.decision import create_group, finish_group
from citemark.evals.runner import Services, create_run, load_test_set
from citemark.models import CitationEvent, DecisionEvent, ModelCallFailed, TextEvent, UsageEvent
from citemark.retrieve import RetrievalConfig
from citemark.testing.fakes import FakeEmbedder, FakeReranker

TYPING = "https://zulip.com/help/typing-notifications"
EMAILS = "https://zulip.com/help/email-notifications"
SENDING = "Disable sending typing notifications"
TYPING_SOURCE = {"url": TYPING, "section": SENDING, "quote": "you can configure Zulip to not send typing notifications"}
QUESTIONS = [
    {
        "id": "Q001",
        "type": "answerable",
        "question": "Is there a way to stop people from seeing when I'm typing?",  # unlike test_answer's question
        "expected_answer": [
            "Yes: turn off sending typing notifications",
            "Desktop/Web: gear icon, then Personal settings, then Account & privacy",
            "Under Privacy, toggle the settings that let recipients see when you're typing",
        ],
        "expected_sources": [TYPING_SOURCE],
    },
    {
        "id": "Q002",
        "type": "partial",
        "question": "How do I stop people seeing that I'm typing? And can I hide it from just one person?",
        "expected_answer": [
            "Turn off sending typing notifications: gear icon, Personal settings, Account & privacy",
            "Under Privacy, toggle the settings that let recipients see when you're typing",
        ],
        "expected_sources": [TYPING_SOURCE],
        "uncovered_part": "whether typing can be hidden from one specific person",
    },
    {
        "id": "Q003",
        "type": "ambiguous",
        "question": "How do I stop getting emails?",
        "expected_answer": [
            "Gear icon, then Personal settings, then Notifications",
            "Under Other emails, turn off Send email notifications for new logins to my account",
        ],
        "expected_sources": [
            {
                "url": EMAILS,
                "section": "Disable new login emails",
                "quote": "Send email notifications for new logins to my account",
            }
        ],
        "expected_option": ["new login emails", "login emails"],
    },
    {"id": "Q004", "type": "decline", "question": "How do I change my profile picture?"},
    {"id": "Q005", "type": "off_topic", "question": "What's the capital of Australia?"},
]
OPTIONS = ["Message notification emails", "New login emails", "Newsletter"]
SCRIPT = {
    QUESTIONS[0]["question"]: ("answer", SENDING),
    QUESTIONS[1]["question"]: ("partial", SENDING),
    QUESTIONS[2]["question"]: ("clarify", OPTIONS),
    "New login emails": ("answer", "Disable new login emails"),
    QUESTIONS[3]["question"]: ("decline", "not_covered"),
    QUESTIONS[4]["question"]: ("decline", "off_topic"),
}
SCRIPTED = "fake-answer"
SHA = "test"  # the commit every scripted run starts from


def frozen_set(folder: Path, questions=QUESTIONS, *, name: str = "runner-test") -> Path:
    path = folder / f"{name}-v1.yaml"
    path.write_text(yaml.safe_dump({"name": name, "version": 1, "questions": questions}, sort_keys=False))
    testset.freeze(path, testset.load(path), None)
    return path


class Scripted:
    """An answer model that replies from a script, keyed by the message it's sent. Each reply
    cites the passage under the scripted heading, so its scores are known in advance. An answer's
    words can be scripted too, as a third item."""

    company = "Zulip"
    prompt_version = "scripted.v1"

    def __init__(self, script, *, model: str = SCRIPTED, window: int = 1_000, failing: frozenset = frozenset()):
        self.script, self.model, self.window, self.failing = script, model, window, failing
        self.asked: list[str] = []

    async def count_tokens(self, request) -> int:
        return self.window

    async def stream(self, request):
        self.asked.append(request.question)
        usage = UsageEvent(self.model, 1_000, 100, 0, 0, "end_turn")
        if request.question in self.failing:
            yield UsageEvent(self.model, 1_000, 10, 0, 0, None)  # billed, then the call failed
            raise ModelCallFailed(f"The call to {self.model} failed (APIStatusError).")
        kind, detail, *said = self.script[request.question]
        if kind in ("answer", "partial"):
            found = [n for n, p in enumerate(request.passages) if p.title.endswith(detail)]
            assert found, f"search didn't return the passage under {detail!r}"
            yield TextEvent(0, said[0] if said else "Turn it off in your settings.")
            yield CitationEvent(0, found[0], request.passages[found[0]].blocks[0], 0, 1)
            if kind == "partial":
                yield DecisionEvent("report_gap", {"missing": "whether you can hide it from one person"})
        elif kind == "clarify":
            yield DecisionEvent("ask_clarifying_question", {"options": detail})
        else:
            yield DecisionEvent("decline", {"reason": detail})
        yield usage


async def correct(**asked) -> judging.Verdict:
    return judging.Verdict("correct", [], [], "It has every key fact.", 100, 50, {"verdict": "correct"})


async def no_wait(seconds: float) -> None:
    pass


def failing_client() -> anthropic.AsyncAnthropic:
    """For the follow-up's rewrite: it fails, so the follow-up is searched as it is."""
    transport = httpx2.MockTransport(lambda request: httpx2.Response(500, json={"type": "error"}))
    http_client = anthropic.DefaultAsyncHttpxClient(transport=transport)
    return anthropic.AsyncAnthropic(api_key="unused", max_retries=0, http_client=http_client)


def services(answerer, *, judge=correct, client=None) -> Services:
    return Services(answerer, client or failing_client(), FakeEmbedder(), FakeReranker(), judge)


async def stocked(session, path: Path, *, price_per_mtok="1", model: str = SCRIPTED) -> TestSet:
    """The Zulip passages, a price for the scripted model, and the test set at `path`."""
    await add_zulip(session)
    session.add(
        Price(
            model=model,
            input_per_mtok=Decimal(price_per_mtok),
            output_per_mtok=Decimal("10"),
            effective_from=dt.date(2026, 1, 1),
        )
    )
    return await load_test_set(session, path)


async def started(session, path: Path, answerer, *, mode="retrieval", budget="5", price_per_mtok="1") -> TestRun:
    test_set = await stocked(session, path, price_per_mtok=price_per_mtok)
    run = await create_run(
        session,
        test_set,
        mode=mode,
        answerer=answerer,
        config=RetrievalConfig(),
        budget_usd=Decimal(budget),
        sha=SHA,
    )
    await session.commit()
    return run


async def results(session, run_id) -> dict[str, TestResult]:
    rows = await session.execute(
        select(TestQuestion.ext_id, TestResult)
        .join(TestResult, TestResult.test_question_id == TestQuestion.id)
        .where(TestResult.test_run_id == run_id)
    )
    return {ext_id: result for ext_id, result in rows}


class Varying:
    """A judge whose verdict on a question changes from run to run: `incorrect` maps a
    question's ID to the runs (1 to 3) in which its answer is graded incorrect."""

    def __init__(self, incorrect: dict[str, set[int]]):
        self.incorrect = {QUESTIONS[int(key[1:]) - 1]["question"]: runs for key, runs in incorrect.items()}
        self.calls: Counter[str] = Counter()

    async def __call__(self, **asked) -> judging.Verdict:
        question = asked["question"].split("\n")[0]  # an ambiguous question carries the option chosen
        self.calls[question] += 1
        verdict = "incorrect" if self.calls[question] in self.incorrect.get(question, ()) else "correct"
        return judging.Verdict(verdict, [], [], "Scripted.", 100, 50, {"verdict": verdict})


async def grouped(session, path, *, budget="6", sha=SHA, answerer=None, mode="retrieval") -> list[TestRun]:
    answerer = answerer or Scripted(SCRIPT)
    test_set = await stocked(session, path, model=answerer.model)
    runs = await create_group(
        session,
        test_set,
        mode=mode,
        answerer=answerer,
        config=RetrievalConfig(),
        budget_usd=Decimal(budget),
        sha=sha,
    )
    await session.commit()
    return runs


async def finished(session, sessions, path, judge) -> list[TestRun]:
    runs = await grouped(session, path)
    await finish_group(
        runs[0].decision_group, sessions=sessions, services=services(Scripted(SCRIPT), judge=judge), sha=SHA, parallel=1
    )
    return runs
