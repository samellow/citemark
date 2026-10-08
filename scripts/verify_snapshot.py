"""Check a snapshot's extracted text against its raw HTML (implementation plan P0.4, G9).

Counts what a reader sees on the page that the extracted text lost: section
headings, tab labels, tab panel text, and Note and Tip callouts. The kit's
crawler (Phase 1, T6) has to match the counts this reports.

    uv run --with lxml python scripts/verify_snapshot.py fixtures/zulip
"""

import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

import lxml.html

PROBE_WORDS = 5
CONTENT = '//*[contains(concat(" ", normalize-space(@class), " "), " sl-markdown-content ")]'


def norm(text: str) -> str:
    text = re.sub(r"(?m)^\s*\d+\.\s+", "", text)  # list numbering
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.lower().split())


def own_text(block: lxml.html.HtmlElement) -> str:
    """An element's text without the lists nested in it, which are probed on their own."""
    clone = copy.deepcopy(block)
    for nested in clone.xpath(".//ul | .//ol | .//figcaption"):  # a code block's hidden "Terminal window"
        nested.drop_tree()
    for line in clone.xpath('.//*[contains(@class, "ec-line")]'):  # one <div> per line of code
        line.tail = "\n" + (line.tail or "")
    return clone.text_content()


def probe(text: str) -> str:
    """A few words from the middle of an element's text, to look for in the extracted text."""
    words = norm(text).split()
    middle = len(words) // 2
    return " ".join(words[middle : middle + PROBE_WORDS] if len(words) >= PROBE_WORDS else words)


def check_page(raw: str, markdown: str, counts: Counter, problems: list[str]) -> None:
    doc = lxml.html.fromstring(raw)
    flat = norm(markdown)
    headings = {norm(h) for h in re.findall(r"(?m)^#{1,4}\s+(.+)$", markdown)}

    for heading in doc.xpath("//main//h2 | //main//h3"):
        text = norm(heading.text_content())
        if text and text != "related articles":  # link lists, dropped on purpose
            counts["headings"] += 1
            if text not in headings:
                counts["headings missing"] += 1
                problems.append(f"heading: {text[:50]}")

    labels = {tab.get("id"): " ".join(tab.text_content().split()) for tab in doc.xpath('//*[@role="tab"]')}
    for panel in doc.xpath('//*[@role="tabpanel"]'):
        counts["tab panels"] += 1
        if f"**{labels.get(panel.get('aria-labelledby'))}:**" not in markdown:
            counts["tab labels missing"] += 1
            problems.append("tab label")
        words = probe(panel.text_content())
        if words and words not in flat:
            counts["tab panel text missing"] += 1
            problems.append(f"tab panel: {words}")

    for callout in doc.xpath('//main//aside[contains(@class, "starlight-aside")]'):
        counts["callouts"] += 1
        if probe(callout.text_content()) not in flat:
            counts["callouts missing"] += 1
            problems.append(f"callout: {norm(callout.text_content())[:50]}")

    # Every paragraph and list item. Lists under "Related articles" link to
    # other pages, and are dropped on purpose.
    related = set(doc.xpath(f'{CONTENT}/*[h2[@id="related-articles"]]/following-sibling::*[1]//li'))
    for block in doc.xpath(f'{CONTENT}//p | {CONTENT}//li[not(ancestor::*[@role="tablist"])]'):
        if block in related or block.xpath("ancestor::pre"):
            continue
        words = probe(own_text(block))
        if words:
            counts["paragraphs and list items"] += 1
            if words not in flat:
                counts["paragraphs and list items missing"] += 1
                problems.append(f"{block.tag}: {norm(own_text(block))[:60]}")

    if "help center home" in flat:
        counts["pages with navigation text"] += 1
        problems.append("navigation text")


def main(snapshot: Path) -> None:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    counts: Counter = Counter()
    by_page: dict[str, list[str]] = {}
    for page in manifest["pages"]:
        raw = (snapshot / "raw" / f"{page['slug']}.html").read_text(encoding="utf-8")
        markdown = (snapshot / "text" / f"{page['slug']}.md").read_text(encoding="utf-8")
        problems: list[str] = []
        check_page(raw, markdown, counts, problems)
        if problems:
            by_page[page["slug"]] = problems

    print(f"pages {manifest['page_count']}")
    for name in ("headings", "tab panels", "callouts"):
        print(f"  {name}: {counts[name]}, missing {counts[name + ' missing']}")
    print(f"  paragraphs and list items: {counts['paragraphs and list items']}, "
          f"missing {counts['paragraphs and list items missing']}")
    print(f"  tab labels missing: {counts['tab labels missing']}")
    print(f"  tab panel text missing (spot check, code blocks included): {counts['tab panel text missing']}")
    print(f"  pages with navigation text: {counts['pages with navigation text']}")
    for slug, problems in list(by_page.items())[:15]:
        print(f"    {slug}: {'; '.join(problems[:3])}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
