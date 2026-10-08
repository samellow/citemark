"""Finding a source's pages (PRD 5.1, implementation plan G8): start pages, sitemaps, one address."""

import gzip

import httpx2
import pytest

from citemark.ingest import IngestError
from citemark.ingest.crawl import Crawl, Failed, Page, SourceSpec
from citemark.ingest.fetch import Fetcher

SITE = "https://docs.example.com"


def page(title: str, links: tuple[str, ...] = (), canonical: str | None = None, refresh: str | None = None) -> str:
    head = f"<title>{title}</title>"
    head += f'<link rel="canonical" href="{canonical}">' if canonical else ""
    head += f'<meta http-equiv="refresh" content="0;url={refresh}">' if refresh else ""
    nav = "".join(f'<a href="{link}">{link}</a>' for link in links)
    body = f"<p>{title} explains how this part of the product works, one step at a time, for every plan.</p>"
    content = f"<h1>{title}</h1><div class='content'>{body}</div>"
    return f"<html><head>{head}</head><body><nav>{nav}</nav>{content}</body></html>"


INDEX_LINKS = (
    "a",
    "/help/b",
    "/help/b/",
    f"{SITE}/help/c-old",
    "/help/missing",
    "/help/broken",
    "/blog/news",
    "https://other.example.com/help/x",
    "/help/logo.png",
    "mailto:support@example.com",
    "#top",
)
HELP = {
    "/help/": page("Help center", INDEX_LINKS),
    "/help/a": page("Article A", ("/help/",)),
    "/help/b": page("Article B", canonical="/help/b"),
    "/help/b/": page("Article B", canonical="/help/b"),
    "/help/c-old": page("Moved", refresh="/help/c"),
    "/help/c": page("Article C"),
}
START_PAGE = SourceSpec("start_page", f"{SITE}/help/", content_selector=".content")


def serve(pages: dict, requested: list[str], broken: tuple[str, ...] = ("/help/broken",)):
    def handle(request: httpx2.Request) -> httpx2.Response:
        requested.append(request.url.path)
        if request.url.path in broken:
            return httpx2.Response(500)
        body = pages.get(request.url.path)
        if body is None:
            return httpx2.Response(404)
        if isinstance(body, httpx2.Response):
            return body
        return httpx2.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=body)

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handle))


async def no_wait(seconds: float) -> None:
    pass


async def crawl_all(spec: SourceSpec, client, **kwargs) -> tuple[Crawl, list]:
    fetcher = Fetcher(client, spec.scope(), agent="CitemarkBot (+test)", interval=0, sleep=no_wait)
    crawl = Crawl(spec, fetcher, **kwargs)
    return crawl, [item async for item in crawl.pages()]


@pytest.mark.anyio
async def test_a_start_page_crawl_follows_links_under_its_prefix_only():
    requested: list[str] = []
    async with serve(HELP, requested) as client:
        _, items = await crawl_all(START_PAGE, client)
    pages = {item.url: item for item in items if isinstance(item, Page)}
    assert sorted(pages) == [f"{SITE}/help/", f"{SITE}/help/a", f"{SITE}/help/b", f"{SITE}/help/c"]
    assert pages[f"{SITE}/help/a"].extracted.title == "Article A"
    for never in ("/blog/news", "/help/logo.png", "/help/x"):
        assert never not in requested
    assert requested.count("/help/c") == 1


@pytest.mark.anyio
async def test_gone_pages_and_failing_pages_are_told_apart_and_a_failure_leaves_the_crawl_incomplete():
    async with serve(HELP, []) as client:
        crawl, items = await crawl_all(START_PAGE, client)
    failed = {item.url: item for item in items if isinstance(item, Failed)}
    assert failed[f"{SITE}/help/missing"].gone
    assert not failed[f"{SITE}/help/broken"].gone
    assert not crawl.complete  # the broken page may have linked to pages this crawl never saw


@pytest.mark.anyio
async def test_a_crawl_that_reached_every_page_is_complete():
    async with serve(HELP, [], broken=()) as client:
        crawl, _ = await crawl_all(START_PAGE, client)
    assert crawl.complete
    assert crawl.found == crawl.done


@pytest.mark.anyio
async def test_a_start_page_that_cant_be_fetched_stops_the_crawl():
    async with serve(HELP, [], broken=("/help/",)) as client:
        with pytest.raises(IngestError, match="status 500"):
            await crawl_all(START_PAGE, client)


@pytest.mark.anyio
async def test_a_crawl_stops_finding_pages_at_its_cap_and_is_then_incomplete():
    async with serve(HELP, [], broken=()) as client:
        crawl, items = await crawl_all(START_PAGE, client, max_pages=2)
    assert len(items) == 2
    assert crawl.capped and not crawl.complete


SITEMAP_INDEX = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>{SITE}/sitemaps/help.xml.gz</loc></sitemap>
  <sitemap><loc>https://other.example.com/sitemap.xml</loc></sitemap>
</sitemapindex>"""
HELP_SITEMAP = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{SITE}/help/a</loc><lastmod>2026-10-01</lastmod></url>
  <url><loc>{SITE}/help/b</loc></url>
  <url><loc>{SITE}/blog/news</loc></url>
</urlset>"""


@pytest.mark.anyio
async def test_a_sitemap_and_its_nested_gzipped_sitemaps_are_read():
    requested: list[str] = []
    pages = {
        **HELP,
        "/sitemap.xml": httpx2.Response(200, headers={"content-type": "application/xml"}, text=SITEMAP_INDEX),
        "/sitemaps/help.xml.gz": httpx2.Response(200, content=gzip.compress(HELP_SITEMAP.encode())),
    }
    spec = SourceSpec("sitemap", f"{SITE}/sitemap.xml", path_prefix="/help/", content_selector=".content")
    async with serve(pages, requested) as client:
        crawl, items = await crawl_all(spec, client)
    assert [item.url for item in items] == [f"{SITE}/help/a", f"{SITE}/help/b"]
    assert items[0].last_modified.isoformat() == "2026-10-01T00:00:00+00:00"
    assert "/blog/news" not in requested and crawl.complete


@pytest.mark.anyio
async def test_a_sitemap_cant_read_local_files(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    hostile = f"""<?xml version="1.0"?>
<!DOCTYPE urlset [<!ENTITY secret SYSTEM "file://{secret}">]>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{SITE}/help/&secret;</loc></url></urlset>"""
    requested: list[str] = []
    async with serve({"/sitemap.xml": httpx2.Response(200, text=hostile)}, requested) as client:
        await crawl_all(SourceSpec("sitemap", f"{SITE}/sitemap.xml"), client)
    assert not any("TOPSECRET" in path for path in requested)


@pytest.mark.anyio
async def test_a_sitemap_that_isnt_xml_stops_the_crawl():
    pages = {"/sitemap.xml": httpx2.Response(200, text="<html>Not found</html")}
    async with serve(pages, []) as client:
        with pytest.raises(IngestError, match="isn't a sitemap"):
            await crawl_all(SourceSpec("sitemap", f"{SITE}/sitemap.xml"), client)
