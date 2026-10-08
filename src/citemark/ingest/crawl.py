"""Finding a source's pages (PRD 5.1): from a sitemap, from a start page, or one address.

A start page is for help centers without a sitemap, Zulip's among them (implementation plan
G8): the crawl follows its links under the same path prefix. A page that only redirects with
<meta http-equiv="refresh"> is followed like a redirect, not kept as an article. A page that
names a canonical address within the source is kept under that address, so the same article
reached by two addresses is kept once.
"""

from __future__ import annotations

import datetime as dt
import re
import zlib
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlsplit

import lxml.etree
import lxml.html

from citemark.ingest import IngestError
from citemark.ingest.extract import Extracted, ExtractError, canonical_url, extract_html, redirect_target
from citemark.ingest.fetch import Disallowed, Fetcher, FetchError, OutOfScope, PageGone, Response, Scope
from citemark.ingest.files import extract_pdf

MAX_PAGES = 5000  # a guard against crawling a calendar or search results forever
MAX_SITEMAPS = 50
MAX_SITEMAP_BYTES = 50 * 1024 * 1024  # unzipped
NOT_PAGES = re.compile(
    r"\.(png|jpe?g|gif|svg|webp|ico|css|js|mjs|json|txt|xml|gz|zip|pdf|mp3|mp4|webm|woff2?|ttf|eot)$", re.I
)


@dataclass(frozen=True)
class SourceSpec:
    kind: str  # sitemap · start_page · url
    url: str
    path_prefix: str | None = None
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    content_selector: str | None = None

    def scope(self) -> Scope:
        prefix = self.path_prefix
        if not prefix:
            path = urlsplit(self.url).path or "/"
            if self.kind == "start_page":
                prefix = path[: path.rfind("/") + 1]  # the start page's folder: /help/ for /help/
            elif self.kind == "url":
                prefix = path
            else:
                prefix = "/"
        return Scope.of(self.url, prefix, self.include, self.exclude)


@dataclass(frozen=True)
class Page:
    url: str
    extracted: Extracted
    last_modified: dt.datetime | None = None


@dataclass(frozen=True)
class Failed:
    url: str
    error: str
    gone: bool = False  # 404 or 410: the page was taken down, which isn't a failure to fetch


def _parse_date(value: str | None) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.strip()) if value else None
    except ValueError:
        return None
    return parsed.replace(tzinfo=dt.UTC) if parsed and parsed.tzinfo is None else parsed


def read_sitemap(response: Response) -> tuple[list[str], list[tuple[str, dt.datetime | None]]]:
    """A sitemap's nested sitemaps, and its pages with their last-modified dates. Gzipped
    sitemaps are unzipped, and entities aren't expanded, so a hostile file can't read local
    files or blow up in memory."""
    body = response.body
    if body[:2] == b"\x1f\x8b":
        unzip = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
        body = unzip.decompress(body, MAX_SITEMAP_BYTES)
        if unzip.unconsumed_tail:
            raise IngestError(f"The sitemap {response.url} is larger than {MAX_SITEMAP_BYTES // 2**20} MB unzipped.")
    parser = lxml.etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    try:
        root = lxml.etree.fromstring(body, parser)
    except lxml.etree.XMLSyntaxError as exc:
        raise IngestError(f"{response.url} isn't a sitemap: it isn't valid XML.") from exc
    if root is None:
        raise IngestError(f"{response.url} is empty, so it isn't a sitemap.")
    nested = [loc.strip() for loc in root.xpath("//*[local-name()='sitemap']/*[local-name()='loc']/text()")]
    pages = []
    for entry in root.xpath("//*[local-name()='url']"):
        loc = entry.xpath("string(*[local-name()='loc'])").strip()
        if loc:
            pages.append((loc, _parse_date(entry.xpath("string(*[local-name()='lastmod'])"))))
    return nested, pages


def _links(doc: lxml.html.HtmlElement, url: str) -> list[str]:
    base = doc.xpath("//base/@href")
    base_url = urljoin(url, base[0].strip()) if base else url
    links = []
    for href in doc.xpath("//a/@href"):
        href = href.strip()
        if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
            links.append(urldefrag(urljoin(base_url, href))[0])
    return links


class Crawl:
    """One pass over a source. When it ends, `complete` says whether every page it found was
    fetched. Only then does a page it didn't find count as removed: a crawl that couldn't
    reach some pages may also have missed the links on them."""

    def __init__(self, source: SourceSpec, fetcher: Fetcher, *, max_pages: int = MAX_PAGES) -> None:
        if source.kind not in ("sitemap", "start_page", "url"):
            raise IngestError(f"A {source.kind} source isn't crawled.")
        self.source, self.fetcher, self.max_pages = source, fetcher, max_pages
        self.scope = fetcher.scope
        self.found = 0
        self.done = 0
        self.complete = False
        self.capped = False
        self._queue: deque[tuple[str, dt.datetime | None]] = deque()
        self._queued: set[str] = set()
        self._kept: set[str] = set()
        self._fetch_failed = False

    def _add(self, url: str, last_modified: dt.datetime | None = None, *, found: bool = True) -> None:
        """Queue a page. A link the crawl found is skipped if its name says it's an image, a
        stylesheet or a file; the source's own address is always fetched."""
        if url in self._queued or not self.scope.allows(url) or (found and NOT_PAGES.search(urlsplit(url).path)):
            return
        if len(self._queued) >= self.max_pages:
            self.capped = True
            return
        self._queued.add(url)
        self._queue.append((url, last_modified))
        self.found += 1

    async def pages(self) -> AsyncIterator[Page | Failed]:
        await self.fetcher.read_robots()
        if self.source.kind == "sitemap":
            for url, last_modified in await self._sitemap_pages():
                self._add(url, last_modified)
        elif not self.scope.allows(self.source.url):
            raise IngestError(f"{self.source.url} isn't under the source's path prefix, {self.scope.path_prefix}.")
        else:
            self._add(self.source.url, found=False)
        first = self.source.kind != "sitemap"
        while self._queue:
            url, last_modified = self._queue.popleft()
            result = await self._visit(url, last_modified, first=first)
            first = False
            self.done += 1
            if result is not None:
                yield result
        self.complete = not self._fetch_failed and not self.capped

    async def _sitemap_pages(self) -> list[tuple[str, dt.datetime | None]]:
        pending, read, pages = [self.source.url], set(), []
        while pending and len(read) < MAX_SITEMAPS:
            url = pending.pop(0)
            if url in read:
                continue
            read.add(url)
            try:
                response = await self.fetcher.get(url, self.scope.same_host)
            except FetchError as exc:
                raise IngestError(f"The sitemap couldn't be read, so nothing was crawled. {exc}") from exc
            nested, found = read_sitemap(response)
            pending += [loc for loc in nested if self.scope.same_host(loc)]
            pages += found
        if pending:
            self.capped = True
        return pages

    async def _visit(self, url: str, last_modified: dt.datetime | None, *, first: bool) -> Page | Failed | None:
        try:
            response = await self.fetcher.get(url)
        except (OutOfScope, Disallowed, PageGone) as exc:
            if first:
                raise IngestError(str(exc)) from exc
            return Failed(url, str(exc), gone=True) if isinstance(exc, PageGone) else None
        except FetchError as exc:
            if first:
                raise IngestError(str(exc)) from exc
            self._fetch_failed = True
            return Failed(url, str(exc))
        self._queued.add(response.url)  # reached by a redirect: no need to fetch it again
        last_modified = response.last_modified or last_modified

        if response.media_type == "application/pdf" and self.source.kind == "url":
            return self._keep(response.url, lambda: extract_pdf(response.body, response.url), last_modified)
        if not response.is_html:
            return None
        try:
            doc = lxml.html.fromstring(response.body)
        except (lxml.etree.ParserError, ValueError):
            return Failed(response.url, f"{response.url} isn't HTML that can be read.")
        if self.source.kind == "start_page":
            for link in _links(doc, response.url):
                self._add(link)
        target = redirect_target(doc, response.url)
        if target is not None:
            self._add(target)
            return None
        canonical = canonical_url(doc, response.url)
        address = canonical if canonical and self.scope.allows(canonical) else response.url
        html = response.text
        return self._keep(address, lambda: extract_html(html, self.source.content_selector), last_modified)

    def _keep(
        self, url: str, extract: Callable[[], Extracted], last_modified: dt.datetime | None
    ) -> Page | Failed | None:
        if url in self._kept:
            return None  # the same article, reached by another address
        self._kept.add(url)
        self._queued.add(url)
        try:
            return Page(url, extract(), last_modified)
        except ExtractError as exc:
            return Failed(url, str(exc))
