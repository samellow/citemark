"""The strings test (QA promise 9): every visible string comes from content/en/*.json.

The first strings file, widget.json, arrived with the answering rules (T8).
For now it checks each file's shape and how slots are filled; the check of locked strings
against the content spec joins it with the design foundations (T13).
"""

import json
from pathlib import Path

import pytest

from citemark import strings

CONTENT = Path(__file__).parents[2] / "content" / "en"


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
