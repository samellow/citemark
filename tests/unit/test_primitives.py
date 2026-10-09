"""The shared primitives as Jinja renders them (UI kit 5.2): their markup, the rules each one
enforces, autoescape, and the glyphs' drawing rule. No text lives in a macro: every word comes
from its caller."""

import re
from pathlib import Path

import pytest
from jinja2 import UndefinedError
from lxml import html

from citemark.report.render import GLYPHS, RenderError, glyph, primitives

UI = primitives()
SCRIPT = "<script>alert(1)</script>"


def tree(markup):
    return html.fragment_fromstring(str(markup), create_parent="div")


def visible_text(node) -> list[str]:
    """Text a sighted reader sees: everything outside aria-hidden parts."""
    texts = []
    for element in node.iter():
        if any(a.get("aria-hidden") == "true" for a in (element, *element.iterancestors())):
            continue
        for text in (element.text, *(child.tail for child in element)):
            if text and text.strip():
                texts.append(text.strip())
    return texts


def test_a_state_mark_has_its_glyph_and_its_word():
    node = tree(UI.state_mark(state="warn", label="Warn"))
    mark = node.find("span")
    assert mark.get("class") == "cm-state cm-state-warn"
    svg = mark.find("svg")
    assert svg is not None and svg.get("aria-hidden") == "true" and svg.get("focusable") == "false"
    assert visible_text(node) == ["Warn"]


def test_a_citation_marker_is_a_link_named_for_screen_readers():
    marker = tree(UI.cite(n=2, label="Source 2", href="#source-2")).find("a")
    assert (marker.get("href"), marker.get("aria-label"), marker.text) == ("#source-2", "Source 2", "2")
    assert marker.get("class") == "cm-cite"
    assert tree(UI.cite(n=2, label="Source 2", href="#s", active=True)).find("a").get("class") == "cm-cite is-active"


def test_the_wordmark_is_one_image_named_citemark():
    mark = tree(UI.wordmark(size="sm")).find("span")
    assert (mark.get("role"), mark.get("aria-label")) == ("img", "Citemark")
    assert mark.get("class") == "cm-wordmark cm-wordmark-sm"
    assert visible_text(mark) == []  # its letters are hidden from screen readers, which read the label


def test_a_button_says_its_variant_and_is_never_a_submit_by_accident():
    button = tree(UI.button(label="Send")).find("button")
    assert (button.get("type"), button.get("class"), button.get("disabled")) == ("button", "cm-btn cm-btn-quiet", None)
    disabled = tree(UI.button(label="Send", variant="primary", disabled=True)).find("button")
    assert disabled.get("class") == "cm-btn cm-btn-primary" and disabled.get("disabled") is not None


def test_a_field_reads_its_help_and_its_error_with_the_control():
    node = tree(UI.field(id="email", label="Your email", kind="email", help="Help", error="Error", value="jo@"))
    label, control = node.find(".//label"), node.find(".//input")
    assert label.get("for") == control.get("id") == "email"
    described = control.get("aria-describedby").split()
    assert described == ["email-help", "email-error"]
    assert all(node.find(f".//*[@id='{each}']") is not None for each in described)
    assert control.get("aria-invalid") == "true" and control.get("type") == "email" and control.get("value") == "jo@"


def test_a_field_without_an_error_isnt_marked_invalid_or_described_by_nothing():
    control = tree(UI.field(id="q", label="Your question")).find(".//input")
    assert control.get("aria-invalid") is None and control.get("aria-describedby") is None


def test_long_text_is_a_text_area():
    node = tree(UI.field(id="q", label="Your question", kind="long_text", value="How do I?"))
    area = node.find(".//textarea")
    assert area is not None and area.text == "How do I?" and node.find(".//input") is None


@pytest.mark.parametrize(
    ("macro", "arguments", "message"),
    [
        ("wordmark", {"size": "xl"}, "sm, md or lg"),
        ("state_mark", {"state": "pending", "label": "x"}, "pass, fail, warn or declined"),
        ("button", {"label": "x", "variant": "danger"}, "primary, quiet or accent"),
        ("field", {"id": "x", "label": "x", "kind": "date"}, "text, email, password or long_text"),
    ],
)
def test_a_value_a_primitive_doesnt_have_is_refused(macro, arguments, message):
    with pytest.raises(RenderError, match=message):
        getattr(UI, macro)(**arguments)


@pytest.mark.parametrize("href", ["javascript:alert(1)", "JavaScript:alert(1)", "data:text/html,x", " https://a"])
def test_a_marker_never_links_to_a_script(href):
    """Escaping can't stop a javascript: link, and a source's address could come from a help center."""
    with pytest.raises(RenderError, match="A marker links to"):
        UI.cite(n=1, label="Source 1", href=href)


@pytest.mark.parametrize(
    "href", ["#source-1", "https://zulip.com/help/typing-notifications", "http://acme.example/help"]
)
def test_a_marker_links_to_its_source_on_the_page_or_on_the_web(href):
    assert tree(UI.cite(n=1, label="Source 1", href=href)).find("a").get("href") == href


@pytest.mark.parametrize(
    ("macro", "arguments", "message"),
    [
        ("button", {"label": "x", "type": "reset"}, "button or submit"),
        ("field", {"id": "my email", "label": "x"}, "id is one word"),
        ("field", {"id": "", "label": "x"}, "id is one word"),
    ],
)
def test_a_button_type_or_a_field_id_that_would_break_it_is_refused(macro, arguments, message):
    with pytest.raises(RenderError, match=message):
        getattr(UI, macro)(**arguments)


@pytest.mark.parametrize(
    ("macro", "arguments"),
    [("state_mark", {"state": "pass"}), ("button", {}), ("field", {"id": "x"}), ("cite", {"n": 1, "href": "#"})],
)
def test_a_missing_label_fails_the_render_rather_than_leaving_a_gap(macro, arguments):
    with pytest.raises(UndefinedError):
        getattr(UI, macro)(**arguments)


@pytest.mark.parametrize(
    ("macro", "arguments"),
    [
        ("state_mark", {"state": "pass", "label": SCRIPT}),
        ("cite", {"n": 1, "label": SCRIPT, "href": "#" + SCRIPT}),
        ("button", {"label": SCRIPT}),
        ("field", {"id": "x", "label": SCRIPT, "help": SCRIPT, "error": SCRIPT, "value": SCRIPT}),
        ("field", {"id": "x", "label": "x", "kind": "long_text", "value": SCRIPT}),
    ],
)
def test_visitor_text_is_escaped_never_run(macro, arguments):
    rendered = str(getattr(UI, macro)(**arguments))
    assert "<script>" not in rendered and tree(rendered).find(".//script") is None


@pytest.mark.parametrize(
    ("macro", "arguments", "words"),
    [
        ("state_mark", {"state": "fail", "label": "ONE"}, ["ONE"]),
        ("cite", {"n": "7", "label": "ONE", "href": "#a"}, ["7"]),
        ("button", {"label": "ONE"}, ["ONE"]),
        ("field", {"id": "x", "label": "ONE", "help": "TWO", "error": "THREE"}, ["ONE", "TWO", "THREE"]),
    ],
)
def test_every_word_a_primitive_shows_comes_from_its_caller(macro, arguments, words):
    assert visible_text(tree(getattr(UI, macro)(**arguments))) == words


@pytest.mark.parametrize("path", sorted(GLYPHS.glob("*.svg")), ids=lambda p: p.stem)
def test_each_glyph_follows_the_drawing_rule(path: Path):
    """16px, a round stroke of 1.5 to 1.75px, in currentColor, hidden from screen readers (UI kit 7)."""
    svg = path.read_text(encoding="utf-8")
    assert 'viewBox="0 0 16 16"' in svg and 'width="16" height="16"' in svg
    assert 'aria-hidden="true"' in svg and 'focusable="false"' in svg
    assert set(re.findall(r'stroke="([^"]+)"', svg)) == {"currentColor"}
    assert set(re.findall(r'fill="([^"]+)"', svg)) <= {"none"}
    assert all(1.5 <= float(w) <= 1.75 for w in re.findall(r'stroke-width="([^"]+)"', svg))
    assert 'stroke-linecap="round"' in svg


def test_the_four_state_glyphs_are_drawn():
    assert {path.stem for path in GLYPHS.glob("*.svg")} == {"pass", "fail", "warn", "declined"}
    with pytest.raises(RenderError, match="no glyph minimize"):
        glyph("minimize")
