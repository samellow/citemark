"""Extraction (PRD 5.1, implementation plan G9): a page's main text as Markdown, keeping what a
reader sees.

`trafilatura` finds a page's main text, but on its own it lost a lot of Zulip's help center:
the label on every tab panel, so mobile steps read as desktop steps; nearly every Note and Tip
callout; steps whose class mentions navigation; lists made only of links; the commands inside
install steps; and on short pages, the article itself. So a preparation step runs first. With
the source's content selector, every step below runs; without one, the page keeps its links,
classes and callouts, and the extractor decides what's content. On the Zulip snapshot this
gives the text `scripts/verify_snapshot.py` checked, byte for byte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from urllib.parse import urljoin

import lxml.etree
import lxml.html
import trafilatura
from cssselect import SelectorError

from citemark.ingest import IngestError

HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
RELATED = frozenset({"related articles"})  # lists of links to other pages, not content
REFRESH_URL = re.compile(r"""url\s*=\s*['"]?([^'"]+)""", re.I)


class ExtractError(IngestError):
    pass


@dataclass(frozen=True)
class Extracted:
    title: str
    markdown: str
    anchors: tuple[tuple[str, str], ...] = ()  # each heading's text and id, in page order


def _words(text: str) -> str:
    return " ".join(text.split())


def _label(text: str) -> lxml.html.HtmlElement:
    return lxml.html.fragment_fromstring(f"<p><strong>{escape(text)}:</strong></p>")


def redirect_target(doc: lxml.html.HtmlElement, url: str) -> str | None:
    """Where a page that only redirects with <meta http-equiv="refresh"> points (G8)."""
    for content in doc.xpath('//meta[translate(@http-equiv, "REFSH", "refsh") = "refresh"]/@content'):
        match = REFRESH_URL.search(content)
        if match:
            return urljoin(url, match.group(1).strip())
    return None


def canonical_url(doc: lxml.html.HtmlElement, url: str) -> str | None:
    found = doc.xpath('//link[translate(@rel, "CANOICL", "canoicl") = "canonical"]/@href')
    return urljoin(url, found[0].strip()) if found and found[0].strip() else None


def _title(doc: lxml.html.HtmlElement) -> str:
    h1 = doc.xpath("//h1")
    if h1:
        return _words(h1[0].text_content())
    title = doc.xpath("//title")
    return _words(title[0].text_content()) if title else ""


def _select(doc: lxml.html.HtmlElement, selector: str) -> lxml.html.HtmlElement:
    try:
        found = doc.cssselect(selector)
    except SelectorError as exc:
        raise ExtractError(f'The content selector "{selector}" isn\'t a valid CSS selector.') from exc
    if len(found) != 1:
        raise ExtractError(f'The content selector "{selector}" matched {len(found)} elements on this page, not 1.')
    return found[0]


def _show_tabs(doc: lxml.html.HtmlElement) -> None:
    """Each tab panel starts with its tab's label ("Desktop/Web:", "Mobile:"), and hidden
    panels are shown, so mobile steps don't read as desktop steps."""
    labels = {tab.get("id"): _words(tab.text_content()) for tab in doc.xpath('//*[@role="tab"]')}
    for panel in doc.xpath('//*[@role="tabpanel"]'):
        panel.attrib.pop("hidden", None)
        label = labels.get(panel.get("aria-labelledby", ""))
        if label:
            panel.insert(0, _label(label))


def _keep_callouts(content: lxml.html.HtmlElement) -> None:
    """Note and Tip callouts are <aside>, which the extractor drops as page clutter. They hold
    caveats like "only available to organization owners and administrators"."""
    for aside in list(content.iter("aside")):
        aside.tag = "div"
        label = aside.get("aria-label", "")
        if label and not _words(aside.text_content()).lower().startswith(label.lower()):
            aside.insert(0, _label(label))


def _flatten_code(root: lxml.html.HtmlElement) -> None:
    """Code blocks become plain <pre>. Starlight's code blocks put each line in a <div>, with a
    copy button and a hidden caption, and in a list step the extractor dropped the whole block,
    and with it the commands the step is about."""
    for block in root.xpath('.//div[contains(@class, "expressive-code")]'):
        lines = "\n".join(line.text_content() for line in block.xpath('.//*[contains(@class, "ec-line")]'))
        _replace_with_pre(block, lines)
    for pre in list(root.iter("pre")):
        plain = len(pre) == 1 and pre[0].tag == "code" and len(pre[0]) == 0 and not (pre.text or "").strip()
        if not plain:
            _replace_with_pre(pre, pre.text_content())


def _replace_with_pre(element: lxml.html.HtmlElement, text: str) -> None:
    pre = lxml.html.fragment_fromstring(f"<pre><code>{escape(text)}</code></pre>")
    pre.tail = element.tail
    element.getparent().replace(element, pre)


def _drop_heading_anchors(root: lxml.html.HtmlElement) -> None:
    """The "#" link beside or inside each heading. Its text is for screen readers ("Section
    titled ..."), and in extracted text it repeats the heading. A heading wrapped in its own
    link keeps the text."""
    for heading in root.xpath(" | ".join(f".//{h}[@id]" for h in HEADINGS)):
        target = "#" + heading.get("id")
        nearby = [*heading.iter("a"), heading.getprevious(), heading.getnext()]
        for link in nearby:
            if link is None or link.tag != "a" or link.get("href") != target:
                continue
            if _words(link.text_content()) == _words(heading.text_content()):
                link.drop_tag()
            else:
                link.drop_tree()  # drop_tree keeps the text that follows; a plain remove() loses it


def _drop_related(content: lxml.html.HtmlElement) -> None:
    for heading in content.xpath(" | ".join(f".//{h}" for h in HEADINGS)):
        if _words(heading.text_content()).lower() not in RELATED:
            continue
        node = heading
        while node.getparent() is not content and _words(node.getparent().text_content()) == _words(
            heading.text_content()
        ):
            node = node.getparent()
        following = node.getnext()
        if following is not None and following.tag in ("ul", "ol"):
            following.drop_tree()
        node.drop_tree()


def _anchors(content: lxml.html.HtmlElement) -> tuple[tuple[str, str], ...]:
    return tuple(
        (_words(heading.text_content()), heading.get("id"))
        for heading in content.xpath(" | ".join(f".//{h}[@id]" for h in HEADINGS))
    )


def prepare_html(html: str, selector: str | None = None) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """The page as the extractor should see it: its title, the HTML and the heading anchors."""
    try:
        doc = lxml.html.fromstring(html)
    except (lxml.etree.ParserError, ValueError) as exc:
        raise ExtractError("This page is empty, or isn't HTML that can be read.") from exc
    _show_tabs(doc)
    for tablist in doc.xpath('//*[@role="tablist"]'):
        tablist.drop_tree()
    title = _title(doc)
    if selector is None:
        _flatten_code(doc)
        _drop_heading_anchors(doc)
        return title, lxml.html.tostring(doc, encoding="unicode"), _anchors(doc)

    # The per-source content selector (PRD 5.1): on short pages the extractor otherwise falls
    # back to the whole page, navigation sidebar included.
    content = _select(doc, selector)
    _keep_callouts(content)
    _flatten_code(content)
    _drop_heading_anchors(content)
    _drop_related(content)
    anchors = _anchors(content)
    # The extractor drops what looks like navigation: lists made of links (the supported call
    # providers) and elements whose class says "navigation" (every "Select Billing" step).
    # Links become plain text, and classes and ids are cleared, so only the page's structure
    # decides what's kept.
    for link in list(content.iter("a")):
        link.drop_tag()
    for element in content.iter(lxml.etree.Element):
        element.attrib.pop("class", None)
        element.attrib.pop("id", None)
    body = lxml.html.tostring(content, encoding="unicode")
    return title, f"<html><body><article><h1>{escape(title)}</h1>{body}</article></body></html>", anchors


def extract_html(html: str, selector: str | None = None) -> Extracted:
    title, prepared, anchors = prepare_html(html, selector)
    markdown = trafilatura.extract(
        prepared,
        output_format="markdown",
        include_formatting=True,
        include_tables=True,
        include_links=False,
        favor_recall=True,
    )
    if not markdown or not markdown.strip():
        raise ExtractError("No text was found on this page.")
    return Extracted(title, markdown, anchors)
