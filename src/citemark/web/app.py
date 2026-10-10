"""The web app (PRD 3, 8.2): one FastAPI process, with the job worker running inside it (PRD Q1).

Phase 1 serves the public demo page:

- `GET /`: the page. With `?c=`, the conversation it's showing.
- `POST /ask`: one question from the ask box. Without JavaScript the browser is sent back to the
  page, which shows the answer; demo.js asks for the ask box alone and swaps it in. A refused
  question (the hour's limit, the day's spend cap) is answered with the box and its notice. A
  model call that fails is saved as an error turn, shown in its place; anything else that stops an
  answer is answered with the box and the error notice.
- **At most four answers at once,** each checking the day's cap again when its turn comes, so many
  questions sent together can't run far past it.
- `GET /go/audit`: counts the click, then goes on to the audit listing.
- `GET /reports/<id>`: a published report from `demo/published/`.
- `GET /healthz`: for the host.

What it promises the visitor (PRD 5.11): no cookies, nothing fetched from anywhere else, and no
address stored or logged. A question from another site's page is refused, so another page can't
spend the demo's cap.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import datetime as dt
import hashlib
import re
import traceback
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from citemark.db.models import Document, Message
from citemark.settings import Settings, get_settings
from citemark.web import conversation, counts, page
from citemark.web.limits import RateLimiter, client_address, over_spend_cap, utc_today
from citemark.web.published import Published, PublishedError, load
from citemark.web.view import AskBox

log = structlog.get_logger()

KIT = Path(__file__).resolve().parents[3]
STATIC = KIT / "static"
PUBLISHED = KIT / "demo" / "published"
FRAGMENT = "X-Citemark-Fragment"  # demo.js asks for the ask box alone
MAX_BODY = 16_384  # bytes: a question is at most 1,000 characters
ANSWERING = 4  # questions answered at once
REPORT_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
PAGE_POLICY = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)


class SetupError(RuntimeError):
    """The demo can't start as configured. The message is one plain sentence."""


@dataclass
class Demo:
    """What the demo's requests share."""

    settings: Settings
    sessions: async_sessionmaker[AsyncSession]
    services: conversation.Services
    limiter: RateLimiter
    published: Published | None
    today: Callable[[], dt.date]
    answering: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(ANSWERING))


def _check(settings: Settings) -> None:
    if not settings.builder_name:
        raise SetupError("BUILDER_NAME isn't set, and the demo page's top bar names who built it. Set it first.")


def _published(settings: Settings) -> Published | None:
    if not settings.demo_results:
        return None
    path = Path(settings.demo_results)
    try:
        return load(path if path.is_absolute() else KIT / path)
    except PublishedError as exc:
        raise SetupError(str(exc)) from exc


def preflight(settings: Settings) -> None:
    """What `citemark serve` checks before it starts, so a demo that can't run says why in one
    sentence: who built it, the results file, and the two API keys."""
    if settings.demo_company is None:
        return
    _check(settings)
    _published(settings)
    if settings.anthropic_api_key is None or settings.voyage_api_key is None:
        raise SetupError(
            "The demo answers with Claude and searches with Voyage: set ANTHROPIC_API_KEY and VOYAGE_API_KEY."
        )


def _uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


def _same_origin(request: Request) -> bool:
    """A question sent from this site's own page: another page can't spend the demo's cap."""
    site = request.headers.get("sec-fetch-site")
    if site and site not in ("same-origin", "none"):
        return False
    origin = request.headers.get("origin")
    if origin is None:
        return True  # an older browser's own form; the limits still hold
    return origin != "null" and urlsplit(origin).netloc == request.headers.get("host")


def _first(form: dict[str, list[str]], name: str) -> str | None:
    values = form.get(name)
    return values[0] if values else None


async def _body(request: Request) -> bytes | None:
    """The request's body, or None once it's past MAX_BODY, read no further than that."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY:
        return None
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY:
            return None
    return body


def _failed(exc: BaseException) -> None:
    """Logs what kind of error stopped an answer, and where. Never its message: a database error
    lists the values it was saving, the question among them (PRD 5.11)."""
    frames = traceback.extract_tb(exc.__traceback__)
    where = f"{Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else "unknown"
    log.error("ask_failed", error=type(exc).__name__, at=where)


def _worker_stopped(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        log.error("worker_stopped", exc_info=task.exception())


def _peer(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _article_count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(Document).where(Document.status == "active")) or 0


async def _answers(session: AsyncSession, conversation_id: uuid.UUID) -> int:
    asked = select(func.count()).where(Message.conversation_id == conversation_id, Message.role == "assistant")
    return await session.scalar(asked) or 0


def _report_policy(html: str) -> str:
    """A published report inlines its styles, fonts and one script: only those may run."""
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    hashes = [f"'sha256-{base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()}'" for script in scripts]
    allowed = " ".join(hashes) or "'none'"
    return (
        f"default-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src data:; script-src {allowed}; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )


def create_app(
    *,
    settings: Settings | None = None,
    sessions: async_sessionmaker[AsyncSession] | None = None,
    services: conversation.Services | None = None,
    limiter: RateLimiter | None = None,
    today: Callable[[], dt.date] = utc_today,
    worker: bool = False,
    published_dir: Path = PUBLISHED,
) -> FastAPI:
    """The app. Tests pass their own sessions and services; served, they're made from settings."""
    settings = settings or get_settings()
    demo_on = settings.demo_company is not None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            made_sessions = sessions
            if made_sessions is None:
                from citemark.db.session import make_engine, make_sessionmaker

                engine = make_engine()
                stack.push_async_callback(engine.dispose)
                made_sessions = make_sessionmaker(engine)
            if demo_on:
                _check(settings)
                app.state.demo = Demo(
                    settings=settings,
                    sessions=made_sessions,
                    services=services or await _live_services(settings, stack),
                    limiter=limiter if limiter is not None else RateLimiter(),
                    published=_published(settings),
                    today=today,
                )
            running = None
            if worker:
                from citemark.jobs.worker import run_worker

                running = asyncio.create_task(run_worker())
                running.add_done_callback(_worker_stopped)
            try:
                yield
            finally:
                if running is not None:
                    running.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):  # a crash was logged as it happened
                        await running

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")  # ignored over plain http
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers.setdefault("Content-Security-Policy", PAGE_POLICY)
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    def demo(request: Request) -> Demo | None:
        return getattr(request.app.state, "demo", None)

    async def whole_page(found: Demo, session: AsyncSession, box: AskBox, status: int = 200) -> HTMLResponse:
        built = page.page(
            builder_name=found.settings.builder_name or "",
            audit_url=found.settings.demo_audit_url,
            audit_price=found.settings.demo_audit_price,
            article_count=await _article_count(session),
            published=found.published,
            ask=box,
        )
        return HTMLResponse(page.render(built), status_code=status)

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request, v: str | None = None, c: str | None = None) -> Response:
        found = demo(request)
        if found is None:
            return PlainTextResponse("Not found", status_code=404)
        pitch = counts.variant(v)
        shown = _uuid(c)
        async with found.sessions() as session:
            turns = await conversation.turns(session, shown) if shown else ()
            if shown is None and counts.is_person(request.headers.get("user-agent")):
                await counts.count(session, "page_view", pitch, day=found.today())
                await session.commit()
            box = page.ask_box(
                company=found.settings.demo_company or "",
                turns=turns,
                conversation=str(shown) if turns else None,
                variant=pitch,
            )
            return await whole_page(found, session, box)

    @app.post("/ask")
    async def ask(request: Request) -> Response:
        found = demo(request)
        if found is None:
            return PlainTextResponse("Not found", status_code=404)
        if not _same_origin(request):
            return PlainTextResponse("Questions are asked from the demo page itself.", status_code=403)
        body = await _body(request)
        if body is None:
            return PlainTextResponse("That question is too long.", status_code=413)
        form = parse_qs(body.decode("utf-8", "replace"))
        suggestion, option = _first(form, "suggestion"), _first(form, "option")
        # A browser counts a line break as one character and sends it as two
        question = (option or suggestion or _first(form, "question") or "").replace("\r\n", "\n").strip()
        pitch = counts.variant(_first(form, "v"))
        asked_in = _uuid(_first(form, "conversation"))
        fragment = request.headers.get(FRAGMENT) == "ask"
        person = counts.is_person(request.headers.get("user-agent"))
        if not question or len(question) > page.MAX_QUESTION:
            return PlainTextResponse("A question is 1 to 1,000 characters.", status_code=422)
        address = client_address(request.headers, _peer(request), found.settings.client_ip_header)
        async with found.sessions() as session:
            notice, status = None, 200
            if await over_spend_cap(session, found.today()):
                notice, status = page.spend_capped(found.published), 503
            elif (minutes := found.limiter.ask(address)) is not None:
                notice, status = page.rate_limited(minutes), 429
            else:
                tapped = suggestion and not option and found.published and suggestion in found.published.suggestions
                if person and tapped:
                    await counts.count(session, "suggestion_tap", pitch, day=found.today())
                await session.commit()  # no connection is held while waiting for a turn
                async with found.answering:
                    if await over_spend_cap(session, found.today()):
                        notice, status = page.spend_capped(found.published), 503
                    else:
                        try:
                            asked_in = await conversation.ask(session, found.services, question, asked_in)
                            number = await _answers(session, asked_in)
                        except Exception as exc:
                            await session.rollback()
                            _failed(exc)
                            notice, status = page.t("demo.error"), 502
                if status == 200 and not fragment:
                    query = urlencode({"c": str(asked_in), **({"v": pitch} if pitch else {})})
                    return RedirectResponse(f"/?{query}#turn-{number}", status_code=303)
            turns = await conversation.turns(session, asked_in) if asked_in else ()
            box = page.ask_box(
                company=found.settings.demo_company or "",
                turns=turns,
                notice=notice,
                conversation=str(asked_in) if turns else None,
                variant=pitch,
                draft=None if status == 200 or suggestion or option else question,
            )
            if fragment:
                return HTMLResponse(page.render_ask(box), status_code=status)
            return await whole_page(found, session, box, status)

    @app.get("/go/audit")
    async def go_audit(request: Request, v: str | None = None) -> Response:
        found = demo(request)
        if found is None or not found.settings.demo_audit_url:
            return PlainTextResponse("Not found", status_code=404)
        if counts.is_person(request.headers.get("user-agent")):
            async with found.sessions() as session:
                await counts.count(session, "audit_click", counts.variant(v), day=found.today())
                await session.commit()
        return RedirectResponse(found.settings.demo_audit_url, status_code=303, headers={"Cache-Control": "no-store"})

    @app.get("/reports/{report_id}")
    async def report(request: Request, report_id: str, v: str | None = None) -> Response:
        found = demo(request)
        path = published_dir / f"{report_id}.html"
        if found is None or not REPORT_ID.fullmatch(report_id) or not path.is_file():
            return PlainTextResponse("Not found", status_code=404)
        html = path.read_text(encoding="utf-8")
        if counts.is_person(request.headers.get("user-agent")):
            async with found.sessions() as session:
                await counts.count(session, "report_open", counts.variant(v), day=found.today())
                await session.commit()
        return HTMLResponse(html, headers={"Content-Security-Policy": _report_policy(html)})

    return app


async def _live_services(settings: Settings, stack: AsyncExitStack) -> conversation.Services:
    """Claude and Voyage, with the keys from settings. Both are needed before the page can answer."""
    import anthropic
    import httpx2

    from citemark.embed.voyage import VoyageEmbedder, VoyageReranker
    from citemark.models.claude import ClaudeAnswerer

    if settings.anthropic_api_key is None or settings.voyage_api_key is None:
        raise SetupError(
            "The demo answers with Claude and searches with Voyage: set ANTHROPIC_API_KEY and VOYAGE_API_KEY."
        )
    voyage = settings.voyage_api_key.get_secret_value()
    client = await stack.enter_async_context(
        anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    )
    api = await stack.enter_async_context(httpx2.AsyncClient())
    return conversation.Services(
        answerer=ClaudeAnswerer(client, settings.demo_model, company=settings.demo_company or ""),
        rewriter=client,
        embedder=VoyageEmbedder(voyage, api),
        reranker=lambda config: VoyageReranker(voyage, api, model=config.reranker) if config.rerank else None,
    )
