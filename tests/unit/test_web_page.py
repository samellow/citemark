"""The demo page's words and markup (PRD 8.2; content spec 6; UI kit 5.4), from the made-up sample:
what shows before and after a run, every link, and no word written into a template."""

import json
import re
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import pytest

from citemark import strings
from citemark.design import manifest
from citemark.report import sample as report_sample
from citemark.web import page, published, sample
from citemark.web.limits import QUESTIONS_AN_HOUR
from citemark.web.view import Turn

TEMPLATES = Path(page.__file__).parent / "templates"
COMPONENTS = manifest.load()  # by name


class Parsed(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        found = dict(attrs)
        if "id" in found:
            self.ids.append(found["id"])
        if tag == "a":
            self.links.append(found.get("href") or "")


def demo(**given) -> str:
    return page.render(sample.demo(**given))


def test_before_a_run_nothing_claims_a_test():
    """Not even the offer: it sells "this report", which isn't there yet."""
    built = sample.demo(run=False)
    hero, slot = built.hero, built.slot
    assert (hero.subhead, hero.verdict, hero.verdict_state, hero.measures, hero.report) == (None, None, None, (), None)
    assert (slot.recorded, slot.suggestions, hero.cta, hero.cta_note, built.offer) == ((), (), None, None, None)
    assert built.title == "A support bot that shows its source · Citemark demo"
    assert "test" not in built.title + built.description
    assert hero.headline == page.t("hero.headline")
    html = page.render(built)
    assert "/go/audit" not in html and "$300" not in html and "test report" not in html


def test_with_a_run_the_first_screen_says_what_it_found():
    hero = sample.demo().hero
    assert hero.subhead == (
        "I tested it on 50 questions before launch. Try it on 257 real help-center articles, "
        "then read the full test report."
    )
    assert hero.verdict == "50 test questions · Not pass" and hero.verdict_state == "fail"
    assert [m.name for m in hero.measures] == [
        "Correct answers",
        "Right source",
        'Correctly "not covered"',
        'Wrongly "not covered"',
        "Right place",
    ]
    assert hero.report.href == "/reports/sample"


def test_without_the_listing_there_is_no_button_but_the_price_is_still_said():
    built = page.page(
        builder_name="Casey Morgan",
        audit_url=None,
        audit_price="$400",
        article_count=257,
        published=sample.results(),
        ask=page.ask_box(company="Zulip"),
    )
    assert built.hero.cta is None and built.hero.cta_note is None and built.offer.cta is None
    assert "It's $400 as an Upwork project" in built.offer.body


def test_every_link_keeps_the_pitch():
    built = sample.demo(ask=page.ask_box(company="Acme Chat", variant="build"))
    assert built.hero.cta.href == built.offer.cta.href == "/go/audit?v=build"
    assert built.hero.report.href == "/reports/sample?v=build"
    assert 'name="v" value="build"' in page.render(built)


def test_the_notices_say_how_long_to_wait_and_what_is_still_on_the_page():
    assert f"allows {QUESTIONS_AN_HOUR} questions an hour" in page.rate_limited(1)  # the words and the limiter agree
    assert page.rate_limited(1).endswith("You can ask again in 1 minute.")
    assert page.rate_limited(12).endswith("You can ask again in 12 minutes.")
    assert "recorded example" in page.spend_capped(sample.results())
    assert page.spend_capped(None) == "The demo has reached today's limit. You can ask again tomorrow."


def test_the_page_is_one_document_whose_ids_are_unique_and_whose_links_all_land():
    html = page.render(sample.demo(ask=sample.asked()))
    parsed = Parsed(html)
    assert len(parsed.ids) == len(set(parsed.ids))
    for href in parsed.links:
        assert href.startswith(("#", "/go/audit", "/reports/", "https://", "http://")), href
        if href.startswith("#"):
            assert href[1:] in parsed.ids, href
    assert html.count("<main") == 1 and html.count("<h1") == 1 and '<html lang="en">' in html


def test_the_label_comes_first_and_the_page_runs_no_inline_code():
    html = demo()
    assert html.index("cm-topbar-label") < html.index("<main")
    assert re.findall(r"\sstyle=|<script>|\son[a-z]+=", html) == []
    assert '<script src="/static/demo.js" defer></script>' in html


def test_a_live_answer_shows_steps_2_to_4_and_its_options_ask_again():
    html = page.render_ask(sample.asked())
    assert html.count('<li class="cm-step') == 3 * 2  # the clarifying turn and the answer; the error has none
    assert "5 · The result" not in html and "Went wrong" not in html
    assert 'name="option" value="Weekly digest" form="ask-form" formnovalidate' in html
    assert html.startswith('<div class="cm-ask" data-ask-box>') and "<html" not in html


def test_a_question_is_shown_as_text():
    turn = Turn('<script>alert("x")</script>', None, page.t("demo.error"))
    html = page.render_ask(page.ask_box(company="Acme Chat", turns=(turn,), draft="<b>kept</b>"))
    assert "<script>alert" not in html and "&lt;script&gt;alert(&#34;x&#34;)&lt;/script&gt;" in html
    assert "&lt;b&gt;kept&lt;/b&gt;</textarea>" in html


def test_the_question_box_is_labeled_required_and_held_to_1000_characters():
    html = demo()
    assert '<label class="cm-field-label" for="question">Your question</label>' in html
    assert (
        '<textarea class="cm-input" id="question" name="question" required placeholder="Ask about Acme Chat" '
        'maxlength="1000">' in html
    )


@pytest.mark.parametrize("name", ["demo.html", "demo_parts.html", "ask.html"])
def test_the_demo_templates_hold_no_words(name):
    """Every word comes from the strings files (UI kit 2, rule 6; QA promise 9)."""
    source = (TEMPLATES / name).read_text(encoding="utf-8")
    attributes = re.findall(r'\b(?:aria-label|title|alt|placeholder|data-searching|data-failed)="([^"]*)"', source)
    assert [value for value in attributes if not re.fullmatch(r"\{\{[^}]*\}\}", value)] == []
    for pattern in (r"\{#.*?#\}", r"\{%.*?%\}", r"\{\{.*?\}\}", r"<[^>]*>"):
        source = re.sub(pattern, " ", source, flags=re.S)
    assert re.findall(r"[A-Za-z]+", source) == []


def test_the_demo_components_list_every_demo_string_and_only_real_ones():
    listed = set()
    for component in COMPONENTS.values():
        if component.layer != "demo":
            continue
        for key in component.strings:
            file, _, name = key.partition(":")
            assert name in strings.load(file), f"{component.name} lists {key}, which isn't in {file}.json"
            if file == "demo":
                listed.add(name)
    assert set(strings.load("demo")) - listed == set()


def test_the_published_results_round_trip_and_refuse_what_the_demo_cant_show(tmp_path):
    report = report_sample.report()
    path = tmp_path / "results.json"
    published.dump(sample.results(), path)
    assert published.load(path) == sample.results()
    both = {"recorded": ("Q004", "Q041"), "suggestions": ("Q030", "Q004", "Q041")}
    with pytest.raises(published.PublishedError, match="Q017 failed in the test run"):
        published.from_report(report, report_id="x", **{**both, "recorded": ("Q017", "Q041")})
    with pytest.raises(published.PublishedError, match="Q099 isn't one of the report's questions"):
        published.from_report(report, report_id="x", **{**both, "suggestions": ("Q030", "Q004", "Q099")})
    missing = replace(report, measures=tuple(m for m in report.measures if m.key != "right_place"))
    with pytest.raises(published.PublishedError, match="no count for right_place"):
        published.from_report(missing, report_id="x", **both)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["suggestions"] = data["suggestions"][:2]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(published.PublishedError, match="3 suggested questions"):
        published.load(path)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(published.PublishedError, match="isn't a results file"):
        published.load(path)
    with pytest.raises(published.PublishedError, match="no results file"):
        published.load(tmp_path / "missing.json")
