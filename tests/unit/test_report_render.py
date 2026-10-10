"""The report's one file (PRD 8.1; QA promises 9 and 12): drawn from its content alone, readable
offline and without JavaScript, and printable in light. Checked on the sample report, whose
content is made up; `test_report.py` builds one from runs."""

import re
from collections import Counter
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import pytest
from markupsafe import escape

from citemark.report import build, sample
from citemark.report.data import t
from citemark.report.render import RenderError, bold_part, rich

TEMPLATES = Path(build.__file__).parent / "templates"


class Page(HTMLParser):
    """What a check needs from a page: its elements, ids, links and visible text."""

    def __init__(self, html: str):
        super().__init__()
        self.tags: Counter[str] = Counter()
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.attributes: list[tuple[str, dict]] = []
        self.text: list[str] = []
        self._raw = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        found = dict(attrs)
        self.tags[tag] += 1
        self.attributes.append((tag, found))
        if "id" in found:
            self.ids.append(found["id"])
        if "href" in found:
            self.hrefs.append(found["href"])
        if tag in ("style", "script"):
            self._raw += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self._raw -= 1

    def handle_data(self, data):
        if not self._raw and data.strip():
            self.text.append(data.strip())


@pytest.fixture(scope="module")
def html() -> str:
    return build.render(sample.report())


@pytest.fixture(scope="module")
def page(html) -> Page:
    return Page(html)


def body(html: str) -> str:
    """The page without its inlined styles, whose class names would match anything."""
    return html[html.index("<body") :]


def part(html: str, start: str, end: str) -> str:
    found = body(html)
    at = found.index(start)
    return found[at : found.index(end, at)]


def test_a_script_in_a_question_is_shown_as_text(html, page):
    assert page.tags["script"] == 1  # the report's own filter, and nothing a question brought
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert any("<script>alert(1)</script>" in text for text in page.text)


def test_it_is_one_document_with_a_language_and_a_main_landmark(page):
    assert page.tags["html"] == 1 and page.tags["main"] == 1 and page.tags["h1"] == 1
    assert ("html", {"lang": "en"}) in page.attributes


def test_it_fetches_nothing(html, page):
    """It opens offline: no linked file, and every font is inlined (QA promise 12)."""
    assert page.tags["link"] == 0 and page.tags["img"] == 0 and page.tags["iframe"] == 0
    assert not [attrs for _tag, attrs in page.attributes if "src" in attrs]
    assert "@import" not in html
    urls = re.findall(r"url\(\s*['\"]?([^'\")]*)", html)
    assert urls and all(url.startswith("data:font/woff2;base64,") for url in urls)
    assert len(urls) == len(build.FACES) == 5


def test_every_id_is_unique_and_every_link_on_the_page_has_its_target(page):
    assert [name for name, count in Counter(page.ids).items() if count > 1] == []
    internal = [href[1:] for href in page.hrefs if href.startswith("#")]
    assert internal and set(internal) <= set(page.ids)
    assert all(href.startswith(("#", "https://")) for href in page.hrefs)


def test_each_marker_links_to_its_quote(page):
    markers = [attrs for tag, attrs in page.attributes if tag == "a" and "cm-cite" in attrs.get("class", "")]
    assert markers
    for marker in markers:
        assert re.fullmatch(r"#[\w-]+-q\d", marker["href"]) and marker["aria-label"].startswith("Source ")


def test_failures_are_open_and_passes_are_folded(html):
    passes = html.index('<details class="cm-passes">')
    assert html.index('id="Q017"') < passes and html.index('id="Q023"') < passes  # the failed ones
    assert html.index('id="Q004"') > passes and html.index('id="Q041"') > passes  # the passed ones
    assert "<details open" not in html
    assert f"<summary>{t('questions.folded_passes', count=3)}</summary>" in html


def test_it_reads_without_javascript(page):
    """The filter needs the script, so it starts hidden; the rest needs nothing."""
    (attrs,) = [attrs for _tag, attrs in page.attributes if "data-filter" in attrs]
    assert "hidden" in attrs


def test_the_traced_question_shows_five_steps_and_the_list_four(html):
    trace = part(html, '<section class="cm-trace"', "</section>")
    assert trace.count('<li class="cm-step') == 5 and "cm-record-full" in trace
    entry = part(html, 'id="Q017"', "</article>")
    assert entry.count('<li class="cm-step') == 4 and 'value="1"' not in entry


def test_a_retrieval_miss_is_a_visible_break_and_the_step_is_marked(html):
    entry = part(html, 'id="Q017"', "</article>")
    assert str(escape(t("trace.gap_step2"))) in entry and 'class="cm-break"' in entry
    assert 'class="cm-step is-wrong" value="2"' in entry and t("trace.went_wrong", step=2) in entry


def test_it_prints_in_light_with_the_long_parts_on_new_pages(html):
    css = html[html.index("<style>") : html.index("</style>")]
    assert re.search(r"@media print \{.*\.cm-fix, \.cm-questions \{ break-before: page; \}", css, re.S)
    assert "counter(page)" in css and "counter(pages)" in css
    assert '"Citemark accuracy report · Acme Chat · Oct 30, 2026 · page " counter(page) " of " counter(pages)' in css
    # Dark only ever applies on screen (tokens.css), so a print is light whatever the reader's setting
    assert "@media screen and (prefers-color-scheme: dark)" in css
    assert not re.search(r"@media \(prefers-color-scheme: dark\)", css)


def test_a_client_name_cant_break_out_of_the_stylesheet():
    found = sample.report()
    hostile = (*found.footer[:2], ' · </style><script>alert(2)</script> "quoted"')
    html = build.render(replace(found, footer=hostile))
    assert Page(html).tags["script"] == 1 and html.count("</style>") == 1
    assert "\\3C /style\\3E \\3C script\\3E alert(2)" in html and '\\"quoted\\"' in html


def test_a_passing_report_with_one_setup_has_no_fold_no_fix_and_no_comparison():
    found = sample.report()
    passing = replace(
        found,
        failed=(),
        comparison=None,
        fix_plan=replace(found.fix_plan, heading=t("fix.heading.pass"), groups=(), none=t("fix.none")),
    )
    html = body(build.render(passing))
    assert t("fix.none") in html and "cm-fix-group" not in html and "cm-compare" not in html


def test_the_gallery_can_force_a_theme_and_label_it_a_sample():
    html = build.render(sample.report(), theme="dark", banner="Sample")
    assert '<html lang="en" data-theme="dark">' in html and '<p class="cm-report-banner">Sample</p>' in html
    assert "data-theme" not in build.render(sample.report())[:200]


@pytest.mark.parametrize("name", ["report.html", "parts.html", "record.html"])
def test_the_report_templates_hold_no_words(name):
    """Every word comes from report.json (UI kit 2, rule 6; QA promise 9): with Jinja and the
    markup taken out, only punctuation is left."""
    source = (TEMPLATES / name).read_text(encoding="utf-8")
    for pattern in (r"\{#.*?#\}", r"\{%.*?%\}", r"\{\{.*?\}\}", r"<[^>]*>"):
        source = re.sub(pattern, " ", source, flags=re.S)
    assert re.findall(r"[A-Za-z]+", source) == []


def test_bold_stretches_are_drawn_bold_and_everything_else_escaped():
    assert rich("**Pass.** The bot met <b>it</b>") == "<strong>Pass.</strong> The bot met &lt;b&gt;it&lt;/b&gt;"
    assert bold_part(t("trace.step2")) == "2 · Where it looked"
    with pytest.raises(RenderError):
        bold_part("no bold here")


def test_a_closing_tag_in_an_inlined_sheet_is_refused(monkeypatch):
    monkeypatch.setattr(build, "script", lambda: "if (a</script>) {}")
    with pytest.raises(ValueError, match="closing tag"):
        build.render(sample.report())


@pytest.mark.parametrize("name", ["report.html", "parts.html", "record.html", "primitives.html"])
def test_the_words_a_person_hears_in_an_attribute_come_from_the_strings_too(name):
    """The scan above drops whole tags, so this one reads the attributes a screen reader announces
    or a pointer shows: each is filled from a value, never written in."""
    source = re.sub(r"\{#.*?#\}", " ", (TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S)
    found = re.findall(r'\b(?:aria-label|title|alt|placeholder)="([^"]*)"', source)
    written = [value for value in found if not re.fullmatch(r"\{\{[^}]*\}\}", value)]
    assert written in ([], ["Citemark"] if name == "primitives.html" else [])  # the wordmark's name is the logo
