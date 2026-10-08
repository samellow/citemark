"""Snapshot a help center by crawling from its index page (Phase 0, P0.4).

Saves the raw HTML of every page under the start path, a tarball of it, each
page's main text as Markdown (trafilatura), and a manifest with hashes.
At most 2 requests a second. Used once to freeze the demo test set; the
kit's real crawler (Phase 1, T6) replaces it.
"""

import datetime as dt
import hashlib
import json
import re
import sys
import tarfile
import time
from collections import deque
from html import escape
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
import lxml.etree
import lxml.html
import trafilatura

START = "https://zulip.com/help/"
USER_AGENT = "CitemarkBot/0.1 (+https://github.com/samellow/citemark)"
MIN_INTERVAL = 0.5  # seconds between requests: at most 2 a second
CONTENT_XPATH = '//*[contains(concat(" ", normalize-space(@class), " "), " sl-markdown-content ")]'
SKIP = re.compile(r"(/_astro/|/static/|\.\.|\.(png|jpe?g|gif|svg|webp|css|js|ico|pdf|zip)$)", re.I)


def normalize(url: str) -> str | None:
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.netloc != "zulip.com":
        return None
    path = parsed.path
    if not path.startswith("/help/") or SKIP.search(path):
        return None
    if path != "/help/":
        path = path.rstrip("/")
    return f"https://zulip.com{path}"


def slug_for(url: str) -> str:
    path = urlparse(url).path
    return "index" if path == "/help/" else path.removeprefix("/help/").replace("/", "__")


def redirect_target(html: str) -> str | None:
    """A page that only redirects with <meta http-equiv="refresh"> isn't an article."""
    match = re.search(r'<meta[^>]+http-equiv="refresh"[^>]+content="[^"]*url=([^"]+)"', html, re.I)
    return match.group(1) if match else None


def prepare_html(html: str) -> str:
    """Keep what a reader sees, in the order they'd see it, before extraction.

    Tabbed instructions (Desktop/Web, Mobile) lose their labels in extraction,
    which makes mobile steps read as desktop steps. Each panel gets its tab's
    label as a first line, hidden panels are unhidden, and screen-reader-only
    heading anchors ("Section titled ...") are dropped.
    """
    doc = lxml.html.fromstring(html)
    labels = {el.get("id"): " ".join(el.text_content().split()) for el in doc.xpath('//*[@role="tab"]')}
    for panel in doc.xpath('//*[@role="tabpanel"]'):
        panel.attrib.pop("hidden", None)
        label = labels.get(panel.get("aria-labelledby", ""))
        if label:
            marker = lxml.html.fragment_fromstring(f"<p><strong>{escape(label)}:</strong></p>")
            panel.insert(0, marker)
    # Note and Tip callouts are <aside>, which the extractor drops as page
    # clutter. They hold caveats like "only available to administrators".
    for aside in doc.xpath('//aside[contains(@class, "starlight-aside")]'):
        aside.tag = "div"
        label = aside.get("aria-label", "")
        if label and not " ".join(aside.text_content().split()).lower().startswith(label.lower()):
            aside.insert(0, lxml.html.fragment_fromstring(f"<p><strong>{escape(label)}:</strong></p>"))
    # Code blocks put each line in a <div> inside <pre>, with a copy button and
    # a hidden "Terminal window" caption. In a list step the extractor drops
    # the whole block, and with it the commands the step is about.
    for block in doc.xpath('//div[contains(@class, "expressive-code")]'):
        lines = "\n".join(line.text_content() for line in block.xpath('.//*[contains(@class, "ec-line")]'))
        pre = lxml.html.fragment_fromstring(f"<pre><code>{escape(lines)}</code></pre>")
        pre.tail = block.tail
        block.getparent().replace(block, pre)
    # drop_tree keeps the text that follows an element; a plain remove() loses it
    for el in doc.xpath('//*[@role="tablist"] | //a[contains(@class, "sl-anchor-link")]'):
        el.drop_tree()
    # The per-source content selector (PRD 5.1): on short pages the extractor
    # otherwise falls back to the whole page, navigation sidebar included.
    content = doc.xpath(CONTENT_XPATH)
    if len(content) != 1:
        raise ValueError(f"expected one content container, found {len(content)}")
    # "Related articles" lists are links to other pages, not content.
    for heading in content[0].xpath('*[h2[@id="related-articles"]]'):
        for el in (*heading.xpath("following-sibling::*[1][self::ul]"), heading):
            el.drop_tree()
    # The extractor drops what looks like navigation: lists made of links (the
    # supported call providers) and elements whose class says "navigation"
    # (every "Select Billing" step). Links become plain text, and classes and
    # ids are cleared, so only the page's structure decides what's kept.
    for link in list(content[0].iter("a")):
        link.drop_tag()
    for el in content[0].iter(lxml.etree.Element):
        el.attrib.pop("class", None)
        el.attrib.pop("id", None)
    h1 = doc.xpath("//h1")
    title = escape(" ".join(h1[0].text_content().split())) if h1 else ""
    body = lxml.html.tostring(content[0], encoding="unicode")
    return f"<html><body><article><h1>{title}</h1>{body}</article></body></html>"


def extract(html: str) -> str:
    return trafilatura.extract(
        prepare_html(html), output_format="markdown", include_formatting=True,
        include_tables=True, include_links=False, favor_recall=True,
    ) or ""


def reextract(out_dir: Path) -> None:
    """Rebuild text/ and the manifest's text counts from the saved raw HTML."""
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kept = []
    for page in manifest["pages"]:
        html = (out_dir / "raw" / f"{page['slug']}.html").read_text(encoding="utf-8")
        target = redirect_target(html)
        if target:
            manifest.setdefault("redirects", []).append({"url": page["url"], "to": urljoin(page["url"], target)})
            (out_dir / "text" / f"{page['slug']}.md").unlink(missing_ok=True)
            continue
        text = extract(html)
        (out_dir / "text" / f"{page['slug']}.md").write_text(text, encoding="utf-8")
        page["text_chars"] = len(text)
        kept.append(page)
    manifest["pages"] = kept
    manifest["page_count"] = len(kept)
    manifest["extracted_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"pages {len(kept)}  redirects {len(manifest.get('redirects', []))}")


def main(out_dir: Path) -> None:
    raw_dir = out_dir / "raw"
    text_dir = out_dir / "text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    queue: deque[str] = deque([START])
    seen: set[str] = {START}
    pages, errors = [], []
    last = 0.0

    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30) as client:
        while queue:
            url = queue.popleft()
            wait = MIN_INTERVAL - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
            last = time.monotonic()
            try:
                resp = client.get(url)
            except httpx.HTTPError as exc:
                errors.append({"url": url, "error": repr(exc)})
                continue
            final = normalize(str(resp.url))
            if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", "") or final is None:
                errors.append({"url": url, "status": resp.status_code, "final": str(resp.url)})
                continue
            if final != url and final in {p["url"] for p in pages}:
                continue  # a redirect to a page already saved

            html = resp.text
            for href in re.findall(r'href="([^"]+)"', html):
                nxt = normalize(urljoin(final, href))
                if nxt and nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)

            slug = slug_for(final)
            (raw_dir / f"{slug}.html").write_text(html, encoding="utf-8")
            if redirect_target(html):
                continue  # its target is linked from the index, so it's crawled anyway
            text = extract(html)
            (text_dir / f"{slug}.md").write_text(text, encoding="utf-8")
            title = re.search(r"<title>(.*?)</title>", html, re.S)
            pages.append({
                "url": final,
                "requested": url,
                "slug": slug,
                "title": title.group(1).strip() if title else "",
                "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
                "html_bytes": len(html.encode("utf-8")),
                "text_chars": len(text),
                "fetched_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            })
            print(f"{len(pages):4d}  {slug}", flush=True)

    tar_path = out_dir / "raw.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(raw_dir, arcname="raw")
    manifest = {
        "start": START,
        "user_agent": USER_AGENT,
        "crawled_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "page_count": len(pages),
        "raw_tarball_sha256": hashlib.sha256(tar_path.read_bytes()).hexdigest(),
        "pages": sorted(pages, key=lambda p: p["slug"]),
        "errors": errors,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"pages {len(pages)}  errors {len(errors)}  tarball {tar_path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    if sys.argv[1] == "--reextract":
        reextract(Path(sys.argv[2]))
    else:
        main(Path(sys.argv[1]))
