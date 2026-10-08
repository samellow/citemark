"""Fetching pages politely (PRD 5.1): the source's host and path prefix only, robots.txt
respected, at most 2 requests a second, and the user agent `CitemarkBot (+<deployment URL>)`.

Redirects are followed here, one hop at a time, so each hop is checked against the source's
scope and robots.txt. The client should use `guard.PublicOnlyTransport`, which checks each
connection's address, so every hop is checked for internal addresses too.
"""

from __future__ import annotations

import datetime as dt
import email.utils
import fnmatch
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import anyio
import httpx2

from citemark.ingest import IngestError

BOT_NAME = "CitemarkBot"
PROJECT_URL = "https://github.com/samellow/citemark"
MIN_INTERVAL = 0.5  # seconds between requests: at most 2 a second
MAX_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 10
TIMEOUT = 30.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
RETRY_WAIT = 2.0  # seconds before the one retry, unless the site asks for longer
MAX_RETRY_WAIT = 60.0
REDIRECTS = frozenset({301, 302, 303, 307, 308})
DEFAULT_PORTS = {"http": 80, "https": 443}
ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

Sleep = Callable[[float], Awaitable[None]]


class FetchError(IngestError):
    def __init__(self, url: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.url, self.status = url, status


class PageGone(FetchError):
    """404 or 410: the page was taken down."""


class OutOfScope(FetchError):
    """A redirect leads outside the source's host or path prefix."""


class Disallowed(FetchError):
    """robots.txt asks crawlers to stay away."""


def user_agent(base_url: str | None) -> str:
    return f"{BOT_NAME} (+{base_url or PROJECT_URL})"


def _host_port(url: str) -> tuple[str, int] | None:
    parts = urlsplit(url)
    if parts.scheme not in DEFAULT_PORTS or not parts.hostname:
        return None
    try:
        return parts.hostname.lower(), parts.port or DEFAULT_PORTS[parts.scheme]
    except ValueError:  # a port that isn't a number
        return None


@dataclass(frozen=True)
class Scope:
    """Which addresses belong to a source: its host, under its path prefix, matching its include
    patterns if it has any, and none of its exclude patterns. Patterns are globs on the path."""

    origin: str  # "https://zulip.com"
    path_prefix: str = "/"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    @classmethod
    def of(
        cls,
        url: str,
        path_prefix: str | None = None,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> Scope:
        if _host_port(url) is None:
            raise IngestError(f"{url} isn't a web address Citemark can crawl. It needs to start with https://.")
        parts = urlsplit(url)
        return cls(f"{parts.scheme}://{parts.netloc}", path_prefix or "/", tuple(include or ()), tuple(exclude or ()))

    def same_host(self, url: str) -> bool:
        return _host_port(url) == _host_port(self.origin)

    def allows(self, url: str) -> bool:
        if not self.same_host(url):
            return False
        path = urlsplit(url).path or "/"
        if not (path.startswith(self.path_prefix) or path == self.path_prefix.rstrip("/")):
            return False
        if self.include and not any(fnmatch.fnmatchcase(path, pattern) for pattern in self.include):
            return False
        return not any(fnmatch.fnmatchcase(path, pattern) for pattern in self.exclude)


@dataclass(frozen=True)
class Response:
    url: str  # where the content came from, after any redirects
    status: int
    media_type: str  # "text/html", without parameters
    charset: str | None
    body: bytes
    last_modified: dt.datetime | None = None
    location: str | None = None  # a redirect's target
    retry_after: float | None = None

    @property
    def text(self) -> str:
        try:
            return self.body.decode(self.charset or "utf-8", errors="replace")
        except LookupError:  # a charset Python doesn't know
            return self.body.decode("utf-8", errors="replace")

    @property
    def is_html(self) -> bool:
        return self.media_type in ("text/html", "application/xhtml+xml")


def _date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


def _retry_after(value: str | None) -> float | None:
    try:
        return min(MAX_RETRY_WAIT, max(0.0, float(value))) if value else None
    except ValueError:  # an HTTP date: the usual wait will do
        return None


def _charset(content_type: str) -> str | None:
    for param in content_type.split(";")[1:]:
        key, _, value = param.partition("=")
        if key.strip().lower() == "charset":
            return value.strip(" \"'") or None
    return None


class Fetcher:
    def __init__(
        self,
        client: httpx2.AsyncClient,
        scope: Scope,
        *,
        agent: str,
        interval: float = MIN_INTERVAL,
        max_bytes: int = MAX_BYTES,
        sleep: Sleep = anyio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client, self.scope, self.agent = client, scope, agent
        self.interval, self.max_bytes = interval, max_bytes
        self.sleep, self.clock = sleep, clock
        self.robots: RobotFileParser | None = None
        self.requests = 0
        self._last: float | None = None

    async def read_robots(self) -> None:
        """Read the host's robots.txt (RFC 9309). If there isn't one (any 4xx), every page is
        allowed. If it can't be read (5xx, or no answer), nothing is crawled, as the RFC says."""
        url = urljoin(self.scope.origin, "/robots.txt")
        try:
            response = await self._follow(url, self.scope.same_host)
        except FetchError as exc:
            raise IngestError(f"{url} couldn't be read, so nothing was crawled. {exc}") from exc
        if response.status >= 500:
            raise IngestError(f"{url} answered with status {response.status}, so nothing was crawled.")
        self.robots = RobotFileParser(url)
        self.robots.parse(response.text.splitlines() if response.status < 400 else [])
        delay = self.robots.crawl_delay(BOT_NAME)
        if delay:
            self.interval = max(self.interval, float(delay))

    async def get(self, url: str, allowed: Callable[[str], bool] | None = None) -> Response:
        """A page, after following its redirects within `allowed` (the source's scope unless
        given). Raises `PageGone` for 404 and 410, and `FetchError` for any other status that
        isn't a success."""
        response = await self._follow(url, allowed or self.scope.allows)
        if response.status in (404, 410):
            raise PageGone(url, f"{url} is gone (status {response.status}).", response.status)
        if not 200 <= response.status < 300:
            raise FetchError(url, f"{url} answered with status {response.status}.", response.status)
        return response

    async def _follow(self, url: str, allowed: Callable[[str], bool]) -> Response:
        start = url
        for _ in range(MAX_REDIRECTS + 1):
            if self.robots is not None and not self.robots.can_fetch(BOT_NAME, url):
                raise Disallowed(url, f"robots.txt asks crawlers not to read {url}.")
            response = await self._fetch(url)
            if response.location is None:
                return response
            target = urldefrag(urljoin(url, response.location))[0]
            if not allowed(target):
                raise OutOfScope(start, f"{start} redirects to {target}, which is outside this source.")
            url = target
        raise FetchError(start, f"{start} redirects more than {MAX_REDIRECTS} times.")

    async def _fetch(self, url: str) -> Response:
        """One request, with one retry if the site is busy or doesn't answer."""
        for attempt in (1, 2):
            await self._wait_turn()
            try:
                response = await self._request(url)
            except httpx2.TransportError as exc:
                if attempt == 2:
                    raise FetchError(url, f"{url} couldn't be fetched ({type(exc).__name__}).") from exc
                await self.sleep(RETRY_WAIT)
                continue
            if response.status in RETRY_STATUSES and attempt == 1:
                await self.sleep(response.retry_after or RETRY_WAIT)
                continue
            return response
        raise AssertionError("unreachable")

    async def _wait_turn(self) -> None:
        if self._last is not None:
            wait = self.interval - (self.clock() - self._last)
            if wait > 0:
                await self.sleep(wait)
        self._last = self.clock()
        self.requests += 1

    async def _request(self, url: str) -> Response:
        too_large = f"{url} is larger than {self.max_bytes // 2**20} MB, so it wasn't read."
        headers = {"User-Agent": self.agent, "Accept": ACCEPT}
        async with self.client.stream("GET", url, headers=headers, follow_redirects=False, timeout=TIMEOUT) as live:
            declared = live.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > self.max_bytes:
                raise FetchError(url, too_large)
            body = bytearray()
            async for piece in live.aiter_bytes():
                body += piece
                if len(body) > self.max_bytes:
                    raise FetchError(url, too_large)
            content_type = live.headers.get("content-type", "")
            status = live.status_code
            return Response(
                url=url,
                status=status,
                media_type=content_type.split(";")[0].strip().lower(),
                charset=_charset(content_type),
                body=bytes(body),
                last_modified=_date(live.headers.get("last-modified")),
                location=live.headers.get("location") if status in REDIRECTS else None,
                retry_after=_retry_after(live.headers.get("retry-after")) if status in RETRY_STATUSES else None,
            )
