"""Extraction keeps what a reader sees (PRD 5.1, implementation plan G9)."""

import json
from pathlib import Path

import lxml.html
import pytest

from citemark.ingest.extract import ExtractError, canonical_url, extract_html, redirect_target

ZULIP = Path(__file__).parents[2] / "fixtures" / "zulip"
ARTICLE = """<html><head><title>Star a message | Help</title></head><body>
<nav class="sidebar"><a href="/help/">Help center home</a></nav>
<h1>Star a message</h1>
<div class="content">
  <p>Starring messages is a good way to keep track of important messages you need to go back to.</p>
  <div class="heading-wrapper"><h2 id="star-a-message">Star a message</h2>
    <a class="anchor" href="#star-a-message">Section titled “Star a message”</a></div>
  <div role="tablist">
    <button role="tab" id="tab-1">Desktop/Web</button><button role="tab" id="tab-2">Mobile</button></div>
  <div role="tabpanel" aria-labelledby="tab-1"><ol>
    <li>Hover over a message to reveal three icons on the right.</li>
    <li class="navigation-step">Select <strong>Billing</strong> in the menu.</li></ol></div>
  <div role="tabpanel" aria-labelledby="tab-2" hidden><ol>
    <li>Press and hold a message until the long-press menu appears.</li></ol></div>
  <aside aria-label="Note" class="callout">
    <p>Only organization administrators can star messages for everyone.</p></aside>
  <p>Supported providers:</p>
  <ul><li><a href="/help/zoom">Zoom</a></li><li><a href="/help/jitsi">Jitsi Meet</a></li></ul>
  <div class="heading-wrapper"><h2 id="related-articles">Related articles</h2></div>
  <ul><li><a href="/help/other">An unrelated article title</a></li></ul>
</div></body></html>"""


def test_the_kit_extracts_the_zulip_snapshot_exactly_as_it_was_checked(zulip_raw):
    """The frozen text is what scripts/verify_snapshot.py counted: all 567 tab labels, all 566
    callouts, and every paragraph and list item but 3 its probe misreads. Matching it byte for
    byte means the kit keeps all of them too."""
    manifest = json.loads((ZULIP / "manifest.json").read_text(encoding="utf-8"))
    different = []
    for page in manifest["pages"]:
        raw = (zulip_raw / f"{page['slug']}.html").read_text(encoding="utf-8")
        frozen = (ZULIP / "text" / f"{page['slug']}.md").read_text(encoding="utf-8")
        if extract_html(raw, ".sl-markdown-content").markdown != frozen:
            different.append(page["slug"])
    assert len(manifest["pages"]) == 257
    assert different == []


def test_tabs_callouts_steps_and_link_lists_are_kept_and_clutter_dropped():
    extracted = extract_html(ARTICLE, ".content")
    text = extracted.markdown
    assert extracted.title == "Star a message"
    assert "**Desktop/Web:**" in text and "**Mobile:**" in text
    assert "Press and hold a message" in text  # the hidden tab
    assert "Select **Billing**" in text  # a step whose class says navigation
    assert "**Note:**" in text and "Only organization administrators" in text
    assert "Zoom" in text and "Jitsi Meet" in text  # a list made only of links
    for dropped in ("Section titled", "Related articles", "An unrelated article title", "Help center home"):
        assert dropped not in text
    assert extracted.anchors == (("Star a message", "star-a-message"),)


def test_a_content_selector_must_match_one_element():
    with pytest.raises(ExtractError, match="matched 0 elements"):
        extract_html(ARTICLE, ".missing")
    with pytest.raises(ExtractError, match="isn't a valid CSS selector"):
        extract_html(ARTICLE, "div[")


def test_without_a_selector_the_extractor_finds_the_article():
    text = extract_html(ARTICLE).markdown
    assert "Hover over a message to reveal three icons" in text
    assert "**Mobile:**" in text


def test_a_page_with_no_text_is_an_error():
    with pytest.raises(ExtractError, match="No text"):
        extract_html("<html><body><div class='content'></div></body></html>", ".content")


def test_meta_refresh_and_canonical_addresses_are_read():
    stub = lxml.html.fromstring(
        '<html><head><meta http-equiv="Refresh" content="0; URL=\'/help/user-roles\'">'
        '<link rel="canonical" href="/help/user-roles"></head><body></body></html>'
    )
    url = "https://zulip.com/help/roles-and-permissions"
    assert redirect_target(stub, url) == "https://zulip.com/help/user-roles"
    assert canonical_url(stub, url) == "https://zulip.com/help/user-roles"
    plain = lxml.html.fromstring('<html><head><meta http-equiv="refresh" content="300"></head></html>')
    assert redirect_target(plain, url) is None  # reloads itself; not a redirect
