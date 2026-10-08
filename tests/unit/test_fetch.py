"""Fetching politely (PRD 5.1): scope, robots.txt, 2 requests a second, redirects, size and retries."""

from itertools import pairwise

import httpx2
import pytest

from citemark.ingest import IngestError
from citemark.ingest.fetch import (
    BOT_NAME,
    Disallowed,
    Fetcher,
    FetchError,
    OutOfScope,
    PageGone,
    Scope,
    user_agent,
)

SITE = "https://docs.example.com"
SCOPE = Scope.of(f"{SITE}/help/", "/help/")


class Clock:
    """Time that only moves when the fetcher sleeps, so waits can be counted exactly."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def site(pages: dict[str, httpx2.Response], log: list | None = None, clock: Clock | None = None):
    """A mock site: each path's response, and 404 for anything else."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        if log is not None:
            log.append((clock() if clock else 0.0, request.url.path, request.headers.get("user-agent")))
        return pages.get(request.url.path, httpx2.Response(404))

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handle))


def html(body: str = "<p>ok</p>", **headers) -> httpx2.Response:
    return httpx2.Response(200, headers={"content-type": "text/html; charset=utf-8", **headers}, text=body)


def fetcher(client, clock: Clock | None = None, **kwargs) -> Fetcher:
    clock = clock or Clock()
    return Fetcher(client, SCOPE, agent=user_agent(None), sleep=clock.sleep, clock=clock, **kwargs)


def test_the_scope_is_the_host_and_path_prefix_with_its_patterns():
    assert SCOPE.allows(f"{SITE}/help")  # the prefix itself, without its slash
    scope = Scope.of(f"{SITE}/help/", "/help/", include=["/help/*"], exclude=["/help/archive/*"])
    assert scope.allows(f"{SITE}/help/star-a-message")
    assert not scope.allows(f"{SITE}/help")  # not matched by the include pattern
    assert scope.allows("https://DOCS.example.com:443/help/x")
    assert not scope.allows(f"{SITE}/blog/post")
    assert not scope.allows("https://other.example.com/help/x")
    assert not scope.allows("https://docs.example.com:8443/help/x")
    assert not scope.allows(f"{SITE}/help/archive/old")
    assert not scope.allows("ftp://docs.example.com/help/x")
    with pytest.raises(IngestError, match="needs to start with https://"):
        Scope.of("docs.example.com/help/")


@pytest.mark.anyio
async def test_requests_are_at_least_half_a_second_apart_and_name_the_bot():
    clock, log = Clock(), []
    pages = {f"/help/{n}": html() for n in range(4)}
    async with site(pages, log, clock) as client:
        fetch = fetcher(client, clock)
        for n in range(4):
            await fetch.get(f"{SITE}/help/{n}")
    times = [at for at, _, _ in log]
    assert all(later - earlier >= 0.5 for earlier, later in pairwise(times))
    assert {agent for _, _, agent in log} == {f"{BOT_NAME} (+https://github.com/samellow/citemark)"}


@pytest.mark.anyio
async def test_robots_txt_is_respected_and_its_crawl_delay_slows_the_crawl():
    clock, log = Clock(), []
    robots = "User-agent: *\nDisallow: /help/private/\nCrawl-delay: 3\n"
    pages = {"/robots.txt": httpx2.Response(200, text=robots), "/help/a": html(), "/help/b": html()}
    async with site(pages, log, clock) as client:
        fetch = fetcher(client, clock)
        await fetch.read_robots()
        with pytest.raises(Disallowed):
            await fetch.get(f"{SITE}/help/private/x")
        await fetch.get(f"{SITE}/help/a")
        await fetch.get(f"{SITE}/help/b")
    assert [path for _, path, _ in log] == ["/robots.txt", "/help/a", "/help/b"]  # never asked for the private page
    assert log[2][0] - log[1][0] == 3


@pytest.mark.anyio
async def test_a_missing_robots_txt_allows_everything():
    async with site({"/help/a": html()}) as client:
        fetch = fetcher(client)
        await fetch.read_robots()
        assert (await fetch.get(f"{SITE}/help/a")).status == 200


@pytest.mark.anyio
async def test_an_unreadable_robots_txt_stops_the_crawl():
    async with site({"/robots.txt": httpx2.Response(503)}) as client:
        with pytest.raises(IngestError, match="status 503, so nothing was crawled"):
            await fetcher(client).read_robots()


@pytest.mark.anyio
async def test_redirects_are_followed_inside_the_source_and_refused_outside_it():
    pages = {
        "/help/old": httpx2.Response(301, headers={"location": "/help/new#section"}),
        "/help/new": html(),
        "/help/away": httpx2.Response(302, headers={"location": "https://elsewhere.example.com/help/x"}),
    }
    async with site(pages) as client:
        fetch = fetcher(client)
        response = await fetch.get(f"{SITE}/help/old")
        assert response.url == f"{SITE}/help/new"
        with pytest.raises(OutOfScope, match=r"redirects to https://elsewhere\.example\.com/help/x"):
            await fetch.get(f"{SITE}/help/away")


@pytest.mark.anyio
async def test_a_redirect_loop_stops():
    async with site({"/help/loop": httpx2.Response(302, headers={"location": "/help/loop"})}) as client:
        with pytest.raises(FetchError, match="redirects more than 10 times"):
            await fetcher(client).get(f"{SITE}/help/loop")


@pytest.mark.anyio
async def test_a_page_that_is_too_large_is_not_read():
    async def unannounced():
        for _ in range(4):
            yield b"x" * 512

    pages = {
        "/help/declared": html("x" * 2048),
        "/help/streamed": httpx2.Response(200, headers={"content-type": "text/html"}, content=unannounced()),
    }
    async with site(pages) as client:
        fetch = fetcher(client, max_bytes=1024)
        for path in pages:
            with pytest.raises(FetchError, match="larger than"):
                await fetch.get(f"{SITE}{path}")


@pytest.mark.anyio
async def test_a_busy_site_is_tried_once_more_after_the_wait_it_asks_for():
    clock, answers = Clock(), [httpx2.Response(503, headers={"retry-after": "7"}), html()]

    def handle(request):
        return answers.pop(0)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
        response = await fetcher(client, clock).get(f"{SITE}/help/a")
    assert response.status == 200
    assert 7 in clock.slept


@pytest.mark.anyio
async def test_gone_and_failing_pages_are_told_apart():
    pages = {"/help/gone": httpx2.Response(410), "/help/broken": httpx2.Response(500)}
    async with site(pages) as client:
        fetch = fetcher(client)
        with pytest.raises(PageGone):
            await fetch.get(f"{SITE}/help/gone")
        with pytest.raises(PageGone):
            await fetch.get(f"{SITE}/help/never-existed")
        with pytest.raises(FetchError, match="status 500") as failed:
            await fetch.get(f"{SITE}/help/broken")
        assert not isinstance(failed.value, PageGone)


@pytest.mark.anyio
async def test_the_charset_and_last_modified_date_are_read():
    page = html("<p>café</p>", **{"last-modified": "Tue, 06 Oct 2026 14:52:31 GMT"})
    async with site({"/help/a": page}) as client:
        response = await fetcher(client).get(f"{SITE}/help/a")
    assert response.is_html and "café" in response.text
    assert response.last_modified.isoformat() == "2026-10-06T14:52:31+00:00"
