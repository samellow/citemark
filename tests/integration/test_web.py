"""The demo page and its ask box, end to end in the app, with scripted answers on the Zulip subset
(PRD 8.2; QA promises 18, 23 and 27). The questions are scripted_run's, written for tests only.
Addresses are from the ranges set aside for documentation."""

import datetime as dt
import re
from contextlib import asynccontextmanager
from decimal import Decimal

import httpx2
import pytest
from scripted_run import QUESTIONS, SCRIPT, SCRIPTED, Scripted, failing_client
from sqlalchemy import select, text
from zulip_subset import add_zulip

from citemark import strings
from citemark.db.models import Conversation, DailyCount, Message, Price
from citemark.settings import Settings
from citemark.testing.fakes import FakeEmbedder, FakeReranker
from citemark.web import conversation, sample
from citemark.web.app import SetupError, create_app, preflight
from citemark.web.conversation import Services
from citemark.web.limits import RateLimiter, set_spend_cap
from citemark.web.published import dump

BROWSER = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
PROXY = "10.0.0.9"  # the host's proxy: every request arrives from it
VISITOR, OTHER = "203.0.113.7", "203.0.113.8"
AUDIT = "https://www.upwork.com/services/product/example"
ANSWERED, CLARIFIED, DECLINED = QUESTIONS[0]["question"], QUESTIONS[2]["question"], QUESTIONS[3]["question"]
SITE = {"origin": "http://demo.test"}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\+?\d[\d ().-]{7,}\d")


def settings(**changed) -> Settings:
    given = {
        "database_url": "postgresql://unused/unused",
        "builder_name": "Casey Morgan",
        "demo_company": "Zulip",
        "demo_audit_url": AUDIT,
        "demo_audit_price": None,
        "demo_results": None,
        "client_ip_header": "CF-Connecting-IP",
        "anthropic_api_key": None,
        "voyage_api_key": None,
    }
    return Settings(_env_file=None, **{**given, **changed})


def t(key: str, **slots) -> str:
    return strings.text("demo", key, **slots)


def escaped(words: str) -> str:
    return words.replace("'", "&#39;")


@pytest.fixture
async def zulip(session):
    await add_zulip(session)
    session.add(Price(model=SCRIPTED, input_per_mtok=1, output_per_mtok=10, effective_from=dt.date(2026, 1, 1)))
    await session.commit()


@asynccontextmanager
async def served(sessions, *, given=None, limiter=None, failing=frozenset(), published_dir=None, script=None):
    answerer = Scripted(script or SCRIPT, failing=failing)
    services = Services(answerer, failing_client(), FakeEmbedder(), lambda config: FakeReranker())
    app = create_app(
        settings=given or settings(),
        sessions=sessions,
        services=services,
        limiter=limiter,
        **({"published_dir": published_dir} if published_dir else {}),
    )
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app, client=(PROXY, 4321))
        async with httpx2.AsyncClient(
            transport=transport, base_url="http://demo.test", headers={"user-agent": BROWSER}
        ) as client:
            client.answerer = answerer
            yield client


async def asked(client, question, *, visitor=VISITOR, fragment=False, **fields):
    headers = {**SITE, "CF-Connecting-IP": visitor, **({"X-Citemark-Fragment": "ask"} if fragment else {})}
    return await client.post("/ask", data={"question": question, **fields}, headers=headers)


async def counted(session, event: str) -> dict[str, int]:
    rows = await session.execute(select(DailyCount.variant, DailyCount.count).where(DailyCount.event == event))
    return dict(rows.all())


@pytest.mark.anyio
async def test_before_a_run_the_page_shows_the_label_the_ask_box_and_the_offer_and_claims_no_test(sessions, zulip):
    async with served(sessions) as client:
        page = await client.get("/")
    html = page.text
    assert page.status_code == 200
    assert html.index(escaped(t("top.label"))) < html.index("<main")
    assert 'action="/ask"' in html and 'placeholder="Ask about Zulip"' in html
    assert "<title>A support bot that shows its source · Citemark demo</title>" in html
    for claim in (
        "I tested it on",
        "cm-hero-verdict",
        "cm-recorded",
        "cm-suggestions",
        "/reports/",
        "/go/audit",
        "$300",
    ):
        assert claim not in html
    assert "set-cookie" not in page.headers
    assert "default-src 'self'" in page.headers["content-security-policy"]


@pytest.mark.anyio
async def test_with_results_published_the_first_screen_shows_the_counts_the_exchange_and_the_report(
    sessions, zulip, tmp_path
):
    dump(sample.results(), tmp_path / "results.json")
    async with served(sessions, given=settings(demo_results=str(tmp_path / "results.json"))) as client:
        html = (await client.get("/?v=accuracy")).text
    assert "I tested it on 50 questions before launch. Try it on" in html
    assert "50 test questions · Not pass" in html and "35 of 40 (87%)" in html
    assert "cm-recorded" in html and 'name="suggestion"' in html
    assert 'href="/reports/sample?v=accuracy"' in html and 'href="/go/audit?v=accuracy"' in html


@pytest.mark.anyio
async def test_the_page_has_no_email_address_or_phone_number(sessions, zulip, tmp_path):
    """QA promise 27, on the page as served: before and after a run, and with an answer on it."""
    dump(sample.results(), tmp_path / "results.json")
    for given in (settings(), settings(demo_results=str(tmp_path / "results.json"))):
        async with served(sessions, given=given) as client:
            answered = await asked(client, ANSWERED)
            html = (await client.get(answered.headers["location"])).text
            for found in (EMAIL.findall(html), PHONE.findall(re.sub(r"<[^>]+>", " ", html))):
                assert found == []


@pytest.mark.anyio
async def test_a_question_without_javascript_is_answered_on_the_page_it_returns_to(sessions, zulip):
    async with served(sessions) as client:
        response = await asked(client, ANSWERED)
        assert response.status_code == 303
        location = response.headers["location"]
        assert re.fullmatch(r"/\?c=[0-9a-f-]{36}#turn-1", location)
        html = (await client.get(location)).text
    assert escaped(ANSWERED) in html
    assert "Turn it off in your settings." in html and 'class="cm-quote"' in html
    assert 'href="#t1-q1"' in html  # the answer's marker links to its quote
    assert "4 · What it answered" in html and "5 · The result" not in html  # live answers aren't graded


@pytest.mark.anyio
async def test_demo_js_gets_the_ask_box_alone_and_the_answer_is_saved_with_its_cost(sessions, zulip, session):
    async with served(sessions) as client:
        response = await asked(client, ANSWERED, fragment=True)
    assert response.status_code == 200
    assert response.text.startswith('<div class="cm-ask" data-ask-box>')
    assert "Turn it off in your settings." in response.text and "<html" not in response.text
    reply = (await session.scalars(select(Message).where(Message.role == "assistant"))).one()
    assert reply.kind == "answer" and reply.cost_usd > 0
    assert reply.segments == [{"text": "Turn it off in your settings.", "markers": [1]}]
    stored = await session.get(Conversation, reply.conversation_id)
    assert (stored.page_url, stored.model) == ("/", SCRIPTED)


@pytest.mark.anyio
async def test_a_chosen_option_is_asked_in_the_same_conversation(sessions, zulip, session):
    async with served(sessions) as client:
        first = await asked(client, CLARIFIED, fragment=True)
        assert 'name="option" value="New login emails" form="ask-form" formnovalidate' in first.text
        kept = re.search(r'name="conversation" value="([0-9a-f-]{36})"', first.text).group(1)
        # The box's half-typed words go too, but the option chosen is the question asked
        second = await asked(client, "half-typed", fragment=True, option="New login emails", conversation=kept)
    assert second.status_code == 200 and second.text.count('class="cm-turn"') == 2
    assert client.answerer.asked == [CLARIFIED, "New login emails"]
    history = await conversation.history(session, (await session.scalars(select(Conversation.id))).one())
    assert [turn.role for turn in history] == ["user", "assistant", "user", "assistant"]


@pytest.mark.anyio
async def test_a_failed_answer_shows_the_error_and_stays_out_of_the_history(sessions, zulip, session):
    async with served(sessions, failing=frozenset({ANSWERED})) as client:
        response = await asked(client, ANSWERED, fragment=True)
    assert t("demo.error") in response.text and 'class="cm-turn-error"' in response.text
    assert await conversation.history(session, (await session.scalars(select(Conversation.id))).one()) == []


@pytest.mark.anyio
async def test_ten_questions_an_hour_then_the_wait_in_minutes(sessions, zulip):
    clock = [1000.0]
    limiter = RateLimiter(clock=lambda: clock[0])
    async with served(sessions, limiter=limiter) as client:
        for _ in range(10):
            assert (await asked(client, DECLINED, fragment=True)).status_code == 200
        refused = await asked(client, "Is there a dark theme?", fragment=True)
        assert refused.status_code == 429
        assert escaped(t("demo.rate_limit", minutes=60)) in refused.text
        assert ">Is there a dark theme?</textarea>" in refused.text  # kept, to send again
        clock[0] += 59 * 60
        later = await asked(client, DECLINED)  # without JavaScript: the whole page
        assert later.status_code == 429 and "<html" in later.text and "again in 1 minute." in later.text
        clock[0] += 61
        assert (await asked(client, DECLINED, fragment=True)).status_code == 200


@pytest.mark.anyio
async def test_two_visitors_behind_the_same_proxy_are_counted_apart(sessions, zulip):
    """PRD 7, phase 1: every request comes from the host's proxy, so the visitor is read from the
    proxy's header. A visitor's own X-Forwarded-For changes nothing."""
    async with served(sessions) as client:
        for _ in range(10):
            await asked(client, DECLINED, fragment=True)
        forged = await client.post(
            "/ask",
            data={"question": DECLINED},
            headers={
                **SITE,
                "CF-Connecting-IP": VISITOR,
                "X-Forwarded-For": "198.51.100.1",
                "X-Citemark-Fragment": "ask",
            },
        )
        assert forged.status_code == 429
        assert (await asked(client, DECLINED, visitor=OTHER, fragment=True)).status_code == 200
    # Without the proxy's header everyone is the proxy, sharing one limit: why CLIENT_IP_HEADER is set
    async with served(sessions, given=settings(client_ip_header=None)) as client:
        for _ in range(10):
            await asked(client, DECLINED, fragment=True)
        assert (await asked(client, DECLINED, visitor=OTHER, fragment=True)).status_code == 429


@pytest.mark.anyio
async def test_the_spend_cap_stops_questions_in_its_own_words(sessions, zulip, session, tmp_path):
    now = dt.datetime.now(dt.UTC)
    spent = Conversation(page_url="/", model=SCRIPTED, prompt_version="scripted.v1")
    session.add(spent)
    await session.flush()
    for when, cost in ((now - dt.timedelta(days=1), "5.00"), (now, "0.999999")):
        reply = Message(
            conversation_id=spent.id, role="assistant", content="x", kind="small_talk", cost_usd=Decimal(cost)
        )
        reply.created_at = when
        session.add(reply)
    await session.commit()
    async with served(sessions) as client:
        assert (await asked(client, DECLINED, fragment=True)).status_code == 200  # yesterday's $5 doesn't count
        capped = await asked(client, DECLINED, fragment=True)  # today's spend is now past $1
        assert capped.status_code == 503 and escaped(t("demo.spend_cap_no_run")) in capped.text
    dump(sample.results(), tmp_path / "results.json")
    async with served(sessions, given=settings(demo_results=str(tmp_path / "results.json"))) as client:
        capped = await asked(client, DECLINED, fragment=True)
        assert capped.status_code == 503 and "The recorded example and the full test report" in capped.text
        await set_spend_cap(session, Decimal("2"), by="test")
        await session.commit()
        assert (await asked(client, DECLINED, fragment=True)).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize(
    "headers",
    [{"origin": "https://elsewhere.example"}, {"origin": "null"}, {"sec-fetch-site": "cross-site"}],
)
async def test_a_question_from_another_sites_page_is_refused(sessions, zulip, session, headers):
    async with served(sessions) as client:
        response = await client.post(
            "/ask", data={"question": ANSWERED}, headers={"CF-Connecting-IP": VISITOR, **headers}
        )
    assert response.status_code == 403
    assert (await session.scalars(select(Message))).all() == []


@pytest.mark.anyio
async def test_a_question_must_be_1_to_1000_characters(sessions, zulip):
    async with served(sessions) as client:
        assert (await asked(client, "   ")).status_code == 422
        assert (await asked(client, "x" * 1_001)).status_code == 422


@pytest.mark.anyio
async def test_views_taps_clicks_and_report_opens_are_counted_per_day_and_pitch(sessions, zulip, session, tmp_path):
    """Onboarding plan 7: counts only, split by ?v=, and never a link preview's or a script's."""
    dump(sample.results(), tmp_path / "results.json")
    (tmp_path / "sample.html").write_text("<!doctype html><title>r</title><script>1</script>", encoding="utf-8")
    given = settings(demo_results=str(tmp_path / "results.json"))
    async with served(sessions, given=given, published_dir=tmp_path) as client:
        await client.get("/?v=accuracy")
        await client.get("/?v=accuracy")
        await client.get("/?v=made-up")
        await client.get("/", headers={"user-agent": "Mozilla/5.0 (compatible; Upwork-LinkPreview/1.0; bot)"})
        await client.get("/", headers={"user-agent": "python-httpx/0.28"})
        click = await client.get("/go/audit?v=build")
        await asked(client, "", fragment=True, suggestion=sample.results().suggestions[0], v="build")
        await asked(client, "", fragment=True, suggestion="A question that isn't one of them?")
        opened = await client.get("/reports/sample?v=accuracy")
    assert await counted(session, "page_view") == {"accuracy": 2, "": 1}
    assert await counted(session, "audit_click") == {"build": 1}
    assert await counted(session, "suggestion_tap") == {"build": 1}
    assert await counted(session, "report_open") == {"accuracy": 1}
    assert click.status_code == 303 and click.headers["location"] == AUDIT
    assert click.headers["cache-control"] == "no-store"
    assert "script-src 'sha256-" in opened.headers["content-security-policy"]


@pytest.mark.anyio
async def test_a_cap_reached_exactly_is_reached(sessions, zulip, session):
    """Nothing spent today, and a cap of nothing: the first question is already over it."""
    await set_spend_cap(session, Decimal("0"), by="test")
    await session.commit()
    async with served(sessions) as client:
        assert (await asked(client, DECLINED, fragment=True)).status_code == 503


@pytest.mark.anyio
@pytest.mark.parametrize("report_id", ["missing", "..%2Fsecrets", "UPPER", ".hidden", "a" * 65])
async def test_only_a_published_report_is_served(sessions, zulip, tmp_path, report_id):
    """Each name is a file that exists, so only the report's own rule for names keeps it out."""
    published = tmp_path / "published"
    published.mkdir()
    for name in ("UPPER", ".hidden", "a" * 65):
        (published / f"{name}.html").write_text("not a published report", encoding="utf-8")
    (tmp_path / "secrets.html").write_text("no", encoding="utf-8")
    async with served(sessions, published_dir=published) as client:
        assert (await client.get(f"/reports/{report_id}")).status_code == 404


@pytest.mark.anyio
async def test_the_audit_redirect_waits_for_the_listing(sessions, zulip, tmp_path):
    dump(sample.results(), tmp_path / "results.json")
    given = settings(demo_audit_url=None, demo_results=str(tmp_path / "results.json"))
    async with served(sessions, given=given) as client:
        assert (await client.get("/go/audit")).status_code == 404
        html = (await client.get("/")).text
    assert "/go/audit" not in html and "$300" in html  # the offer still says what it costs


@pytest.mark.anyio
async def test_no_visitor_address_is_stored(sessions, zulip, session):
    """QA promise 18: the limiter keeps a salted hash in memory, and nothing else keeps the address."""
    async with served(sessions) as client:
        await asked(client, ANSWERED)
        await asked(client, CLARIFIED)
    for table in ("conversation", "message", "citation", "retrieval_hit", "daily_count", "setting"):
        rows = (await session.execute(text(f"SELECT CAST({table} AS text) FROM {table}"))).scalars().all()
        assert not any(VISITOR in row or PROXY in row for row in rows), table


@pytest.mark.anyio
async def test_without_a_demo_the_page_isnt_served_and_a_demo_needs_its_builder(sessions, zulip):
    async with served(sessions, given=settings(demo_company=None)) as client:
        assert (await client.get("/")).status_code == 404
        assert (await client.get("/healthz")).text == "ok"
    with pytest.raises(SetupError, match="BUILDER_NAME"):
        preflight(settings(builder_name=None))
    with pytest.raises(SetupError, match="ANTHROPIC_API_KEY and VOYAGE_API_KEY"):
        preflight(settings())
    with pytest.raises(SetupError, match="no results file"):
        preflight(settings(demo_results="demo/published/missing.json"))


@pytest.mark.anyio
async def test_a_line_break_counts_once_as_the_browser_counted_it(sessions, zulip):
    """A browser holds a textarea to 1,000 characters counting a line break as one, then sends it as two."""
    typed = "Is there a way to stop people from seeing when I'm typing?\n" + "x\n" * 470
    assert len(typed) <= 1_000 < len(typed.replace("\n", "\r\n"))
    async with served(sessions, script={**SCRIPT, typed.strip(): ("decline", "not_covered")}) as client:
        response = await asked(client, typed.replace("\n", "\r\n"), fragment=True)
    assert response.status_code == 200 and client.answerer.asked == [typed.strip()]


@pytest.mark.anyio
async def test_a_body_past_its_size_is_refused_before_its_read(sessions, zulip, session):
    async with served(sessions) as client:
        declared = await client.post(
            "/ask",
            content=b"question=x",
            headers={**SITE, "content-length": "999999", "content-type": "application/x-www-form-urlencoded"},
        )
        sent = await client.post("/ask", data={"question": "x" * 20_000}, headers=SITE)
    assert declared.status_code == sent.status_code == 413
    assert (await session.scalars(select(Message))).all() == []


@pytest.mark.anyio
async def test_another_surfaces_conversation_is_never_shown_or_continued(sessions, zulip, session):
    widget = Conversation(page_url="https://acme.example/pricing", model=SCRIPTED, prompt_version="scripted.v1")
    session.add(widget)
    await session.flush()
    question = Message(conversation_id=widget.id, role="user", content="A widget visitor's question")
    session.add(question)
    await session.flush()
    session.add(
        Message(conversation_id=widget.id, role="assistant", kind="small_talk", content="hi", reply_to=question.id)
    )
    await session.commit()
    async with served(sessions) as client:
        shown = (await client.get(f"/?c={widget.id}")).text
        continued = await asked(client, DECLINED, fragment=True, conversation=str(widget.id))
    assert "A widget visitor" not in shown and str(widget.id) not in shown
    assert continued.status_code == 200 and str(widget.id) not in continued.text
    assert len((await session.scalars(select(Message).where(Message.conversation_id == widget.id))).all()) == 2


@pytest.mark.anyio
async def test_two_questions_answered_at_once_each_keep_their_own_reply(sessions, zulip, session):
    """Two tabs on one conversation: B is asked before A's answer is saved, so by time alone the
    messages read question A, question B, answer A, answer B."""
    talk = Conversation(page_url="/", model=SCRIPTED, prompt_version="scripted.v1")
    session.add(talk)
    await session.flush()
    start = dt.datetime.now(dt.UTC)
    first = Message(conversation_id=talk.id, role="user", content="Question A", created_at=start)
    second = Message(
        conversation_id=talk.id, role="user", content="Question B", created_at=start + dt.timedelta(seconds=1)
    )
    session.add_all([first, second])
    await session.flush()
    for asked_, words, seconds in ((first, "Answer A", 2), (second, "Answer B", 3)):
        session.add(
            Message(
                conversation_id=talk.id,
                role="assistant",
                kind="small_talk",
                content=words,
                reply_to=asked_.id,
                created_at=start + dt.timedelta(seconds=seconds),
            )
        )
    await session.commit()
    shown = await conversation.turns(session, talk.id)
    assert [(turn.question, turn.record.answer[0].text) for turn in shown] == [
        ("Question A", "Answer A"),
        ("Question B", "Answer B"),
    ]
    history = await conversation.history(session, talk.id)
    assert [turn.text for turn in history] == ["Question A", "Answer A", "Question B", "Answer B"]
