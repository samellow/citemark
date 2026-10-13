"""The nightly live run (QA plan 3.2, T19), free: a scripted model and stand-in vectors take the
place of Claude and Voyage. What the real APIs say is the nightly run's own job."""

import datetime as dt
from pathlib import Path

import pytest
from scripted_run import SCRIPTED, Scripted, failing_client
from sqlalchemy import func, select
from zulip_subset import SUBSET

from citemark.db.models import Price, Source
from citemark.evals import live
from citemark.retrieve import RetrievalConfig
from citemark.testing.fakes import FakeEmbedder, FakeReranker

pytestmark = pytest.mark.anyio
RECORDINGS = Path(__file__).parents[1] / "recordings"
TYPING, BIGGER, EMAILS, PICTURE, AUSTRALIA = (known.question for known in live.QUESTIONS)
SCRIPT = {
    TYPING: ("answer", "Disable sending typing notifications"),
    BIGGER: ("answer", ""),  # stand-in vectors can't find font size by meaning, so the first passage
    EMAILS: ("clarify", ["New login emails", "Message notification emails"]),
    PICTURE: ("decline", "not_covered"),
    AUSTRALIA: ("decline", "off_topic"),
}


@pytest.fixture
async def priced(session):
    for model in (SCRIPTED, FakeEmbedder.model):
        session.add(Price(model=model, input_per_mtok=1, output_per_mtok=10, effective_from=dt.date(2026, 1, 1)))
    await session.commit()


async def ask(session, answerer, embedder=None):
    return await live.ask(
        session,
        model=answerer,
        rewriter=failing_client(),
        embedder=embedder or FakeEmbedder(),
        reranker=FakeReranker(),
        config=RetrievalConfig(),
    )


def test_the_questions_and_articles_are_the_recorded_tests_own():
    """So a live reply can be set beside its recording, and the frozen test set stays unseen."""
    assert set(live.ARTICLES) == set(SUBSET)
    recorded = [path.read_text(encoding="utf-8") for path in RECORDINGS.glob("v1-messages-*.json")]
    for known in live.QUESTIONS:
        assert any(known.question in text and '"claude-haiku-5-5"' in text for text in recorded), known.question


async def test_it_loads_the_seven_articles_and_asks_the_five_questions(sessions, session, priced):
    loaded = await live.load(sessions, FakeEmbedder())
    assert (loaded.added, loaded.failed, loaded.passages > 7) == (7, 0, True)
    asked = await ask(session, Scripted(SCRIPT))
    assert [each.kind for each in asked] == [known.expected for known in live.QUESTIONS]
    assert [each.sources for each in asked] == [1, 1, 0, 0, 0]
    assert all(each.cost_usd > 0 for each in asked) and live.failures(asked) == []
    assert asked[0].line() == f"[answer, 1 source] {TYPING}"


async def test_it_loads_only_into_an_empty_database(sessions, session):
    session.add(Source(kind="sitemap", url="https://zulip.com/sitemap.xml"))
    await session.commit()
    with pytest.raises(live.LiveRunError, match="needs an empty database"):
        await live.load(sessions, FakeEmbedder())
    assert await session.scalar(select(func.count()).select_from(Source)) == 1


async def test_a_failed_model_call_or_search_fails_the_run(sessions, session, priced):
    await live.load(sessions, FakeEmbedder())
    asked = await ask(session, Scripted(SCRIPT, failing=frozenset({TYPING})))
    assert asked[0].kind == "error" and asked[1].kind == "answer"
    assert live.failures(asked) == [f"{TYPING} The call failed: The call to {SCRIPTED} failed (APIStatusError)."]
    searched = await ask(session, Scripted(SCRIPT), FakeEmbedder(fail_on=1))
    assert searched[0].kind == "error" and searched[0].problems == ("It stopped with EmbedError.",)
    assert live.failures(searched)[0] == f"{TYPING} The call failed: It stopped with EmbedError."
