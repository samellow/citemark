"""The strings test (QA promise 9): every visible string comes from content/en/*.json.

The first strings file, widget.json, arrived with the answering rules (T8). This checks each
file's shape, how slots are filled, and that every locked string a file holds is word for word
the content spec's. The spec isn't in this repository, so its locked rows are copied into
tests/fixtures/locked-strings.json (T13).
"""

import json
from pathlib import Path

import pytest

from citemark import strings

CONTENT = Path(__file__).parents[2] / "content" / "en"
LOCKED = json.loads((Path(__file__).parents[1] / "fixtures" / "locked-strings.json").read_text(encoding="utf-8"))


def icu_balanced(text: str) -> bool:
    depth = 0
    for char in text:
        depth += {"{": 1, "}": -1}.get(char, 0)
        if depth < 0:
            return False
    return depth == 0


@pytest.mark.parametrize("path", sorted(CONTENT.glob("*.json")), ids=lambda p: p.name)
def test_each_strings_file_is_flat_text_with_balanced_slots(path):
    strings = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(strings, dict) and strings, f"{path.name} should be one object of key: text"
    for key, text in strings.items():
        assert isinstance(text, str) and text.strip(), f"{path.name}: {key} has no text"
        assert icu_balanced(text), f"{path.name}: {key} has unbalanced braces"


@pytest.mark.parametrize(
    ("text", "ok"),
    [("Fixed by {builder_name}", True), ("{hours, plural, one {# hour} other {# hours}}", True), ("{oops", False)],
)
def test_the_brace_check(text, ok):
    assert icu_balanced(text) is ok


def test_a_strings_slots_are_filled():
    assert strings.text("widget", "decline.off_topic", company="Zulip") == (
        "I can only answer questions about Zulip's product."
    )


def test_a_missing_slot_is_an_error_not_a_gap():
    with pytest.raises(KeyError, match=r"needs a value for \{company\}"):
        strings.text("widget", "decline.off_topic")


def test_a_value_is_used_as_written_even_with_braces():
    """A gap phrase is the model's words, so braces in it aren't slots."""
    assert strings.text("widget", "partial.gap", gap="the {x} option") == "The help center doesn't say the {x} option."


def test_every_locked_string_a_file_holds_is_word_for_word():
    """A locked string (content spec 3) may be missing until its component is built, never changed."""
    checked, changed = [], []
    for file, locked in LOCKED["strings"].items():
        held = strings.load(file)
        for key, text in locked.items():
            if key in held:
                checked.append(key)
                if held[key] != text:
                    changed.append(f"{file}:{key}")
    assert changed == []
    assert len(checked) >= 7  # widget.json holds 7 of the 20 so far: they can't go unchecked


# --- Plurals (content spec 2.3): "1 question" and "2 questions", never "question(s)" ---


@pytest.mark.parametrize("path", sorted(CONTENT.glob("*.json")), ids=lambda p: p.name)
def test_every_string_reads_as_a_message(path):
    for key, text in json.loads(path.read_text(encoding="utf-8")).items():
        try:
            strings.parse(text)
        except strings.StringError as exc:
            pytest.fail(f"{path.name}: {key}: {exc}")


@pytest.mark.parametrize(
    ("count", "said"),
    [
        (0, "0 questions passed. Show them."),
        (1, "1 question passed. Show them."),
        (2, "2 questions passed. Show them."),
    ],
)
def test_a_plural_takes_one_or_other(count, said):
    assert strings.text("report", "questions.folded_passes", count=count) == said


def test_an_exact_case_wins_and_a_big_number_has_separators():
    text = "flagged {n, plural, =0 {none} one {# question} other {# questions}}"
    parts = strings.parse(text)
    assert strings._filled("k", parts, {"n": 0}, None) == "flagged none"
    assert strings._filled("k", parts, {"n": 1}, None) == "flagged 1 question"
    assert strings._filled("k", parts, {"n": 1200}, None) == "flagged 1,200 questions"


def test_the_demo_authorship_line_says_none_rather_than_zero():
    found = strings.text("report", "method.authorship.demo", builder_name="B", edited=18, total=50, flagged=0)
    assert "flagged none." in found and "changed 18 of 50" in found
    found = strings.text("report", "method.authorship.demo", builder_name="B", edited=18, total=50, flagged=1)
    assert "flagged 1, which was rewritten before the freeze." in found


def test_a_slot_inside_a_plural_case_is_filled():
    parts = strings.parse("{hours, plural, one {# hour for {who}} other {# hours for {who}}}")
    assert strings._filled("k", parts, {"hours": 3, "who": "Sam"}, None) == "3 hours for Sam"


def test_a_plural_needs_a_whole_number():
    with pytest.raises(TypeError, match="whole number"):
        strings.text("report", "fix.count", count="3")
    with pytest.raises(TypeError, match="whole number"):
        strings.text("report", "fix.count", count=True)


@pytest.mark.parametrize(
    "text",
    [
        "{gender, select, female {she} other {they}}",  # select isn't supported
        "{gender, select, other {they}}",  # not even with only the case a plural has
        "{n, plural, one {# thing}}",  # no other case
        "{n, plural, few {# things} other {# things}}",  # not an English category
        "{n, plural, one {# thing} other {# things}",  # not closed
        "{ }",  # no slot name
        "stray } brace",
    ],
)
def test_a_pattern_it_cant_read_is_refused(text):
    with pytest.raises(strings.StringError):
        strings.parse(text)


def test_an_apostrophe_is_a_letter():
    assert strings.parse("doesn't {x}") == ("doesn't ", strings.Slot("x"))
