"""The test-set checks and the freeze lock (implementation plan P0.5)."""

import copy
import hashlib
import json

import pytest
import yaml
from typer.testing import CliRunner

from citemark.cli import app
from citemark.evals import checks, testset
from citemark.evals.snapshot import HelpCenterSnapshot, split_sections

EDIT = "https://zulip.com/help/edit-a-message"
DARK = "https://zulip.com/help/dark-theme"

ARTICLES = {
    "edit-a-message": (
        "Edit a message | Zulip help center",
        "# Edit a message\n\n"
        "Zulip makes it possible to edit the content of your messages.\n\n"
        "## Edit a message\n\n"
        "**Desktop/Web:**\n\n"
        "1. Hover over a message to reveal three icons on the right.\n"
        "2. Click **Save**.\n\n"
        "**Note:** Administrators can configure who can edit messages.\n\n"
        "### Edit a message on mobile\n\n"
        "Press and hold a message until the menu appears.\n\n"
        "## Message notifications\n\n"
        "Newly mentioned users are notified.\n",
    ),
    "dark-theme": (
        "Dark theme | Zulip help center",
        "# Dark theme\n\nZulip provides both a light theme and a dark theme.\n\n"
        "## Manage color theme\n\nYou can switch between themes from the personal menu.\n",
    ),
}

GOOD = {
    "name": "demo",
    "version": 1,
    "drafting": {"method": "drafted with AI help, then reviewed"},
    "questions": [
        {
            "id": "Q001",
            "type": "answerable",
            "question": "can i fix a typo after sending",
            "expected_answer": ["Hover over the message and use the pencil", "Admins decide who can edit"],
            "expected_sources": [
                {"url": EDIT, "section": "Edit a message", "quote": "Hover over a message to reveal three icons"}
            ],
        },
        {
            "id": "Q002",
            "type": "decline",
            "question": "can I set an out of office reply",
            "not_covered_terms": ["out of office", "auto-reply", "vacation"],
        },
        {"id": "Q003", "type": "off_topic", "question": "what's the weather like in Nairobi"},
    ],
}


@pytest.fixture
def snapshot_dir(tmp_path):
    directory = tmp_path / "snapshot"
    (directory / "text").mkdir(parents=True)
    pages = []
    for slug, (title, text) in ARTICLES.items():
        (directory / "text" / f"{slug}.md").write_text(text, encoding="utf-8")
        pages.append({"url": f"https://zulip.com/help/{slug}", "slug": slug, "title": title})
    (directory / "manifest.json").write_text(json.dumps({"page_count": len(pages), "pages": pages}))
    return directory


def write_set(tmp_path, data, name="demo-v1.yaml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def blocking_checks(data, snapshot_dir, tmp_path, **kwargs):
    test_set = testset.load(write_set(tmp_path, data))
    findings = checks.run_checks(test_set, HelpCenterSnapshot(snapshot_dir), **kwargs)
    return {f.check for f in findings if f.blocking}


def test_a_good_set_has_nothing_to_fix(snapshot_dir, tmp_path):
    assert blocking_checks(GOOD, snapshot_dir, tmp_path) == set()


def _set_q(index, **changes):
    def mutate(data):
        data["questions"][index].update(changes)

    return mutate


def _set_source(**changes):
    def mutate(data):
        data["questions"][0]["expected_sources"][0].update(changes)

    return mutate


@pytest.mark.parametrize(
    ("mutate", "check"),
    [
        pytest.param(_set_source(quote="Hover over a reply to reveal the icons"), "source", id="quote-not-in-section"),
        pytest.param(_set_source(section="Delete a message"), "source", id="no-such-section"),
        pytest.param(_set_source(url="https://zulip.com/help/nope"), "source", id="no-such-article"),
        pytest.param(_set_q(0, question="hover over the message to see icons"), "wording", id="copies-the-article"),
        pytest.param(_set_q(1, not_covered_terms=["light theme", "auto-reply", "vacation"]), "not_covered",
                     id="decline-term-is-covered"),
        pytest.param(_set_q(1, type="partial"), "fields", id="partial-without-its-fields"),
        pytest.param(_set_q(1, not_covered_terms=["vacation"]), "fields", id="too-few-decline-terms"),
        pytest.param(_set_q(2, question="email me at someone@example.com"), "personal_data", id="email-in-question"),
        pytest.param(_set_q(2, id="Q001"), "duplicate", id="duplicate-id"),
    ],
)
def test_each_problem_is_caught(snapshot_dir, tmp_path, mutate, check):
    data = copy.deepcopy(GOOD)
    mutate(data)
    assert check in blocking_checks(data, snapshot_dir, tmp_path)


def test_locked_wording_is_noted_but_not_blocking(snapshot_dir, tmp_path):
    data = copy.deepcopy(GOOD)
    data["questions"][0].update(question="hover over the message to see icons", locked=True)
    test_set = testset.load(write_set(tmp_path, data))
    findings = checks.run_checks(test_set, HelpCenterSnapshot(snapshot_dir))
    assert [(f.check, f.blocking) for f in findings] == [("wording", False)]


def test_composition_and_spread_are_enforced_when_asked(snapshot_dir, tmp_path):
    data = copy.deepcopy(GOOD)
    data["questions"].append(copy.deepcopy(data["questions"][0]) | {"id": "Q004", "question": "where is the pencil"})
    expect = {"answerable": 1, "decline": 1, "off_topic": 1}
    assert blocking_checks(data, snapshot_dir, tmp_path, expect=expect, max_per_article=1) == {
        "composition",
        "spread",
    }


def test_sections_follow_heading_levels():
    _title, text = ARTICLES["edit-a-message"]
    sections = {s.heading: s for s in split_sections("Edit a message", text)}
    # the title section stops at the first section heading, and a section includes its subsections
    assert sections["Edit a message"].level == 2
    assert "Press and hold" in sections["Edit a message"].text
    assert "Newly mentioned" not in sections["Edit a message"].text
    assert sections["Edit a message"].first_paragraph.startswith("1. Hover")
    intro = split_sections("Edit a message", text)[0]
    assert intro.level == 1 and intro.text == "Zulip makes it possible to edit the content of your messages."


def test_a_page_without_headings_is_one_section_named_after_its_title():
    (section,) = split_sections("View the exact time a message was sent", "Hover over the timestamp.")
    assert (section.heading, section.text) == ("View the exact time a message was sent", "Hover over the timestamp.")


def test_freezing_locks_the_file_bytes(tmp_path):
    path = write_set(tmp_path, GOOD)
    lock = testset.freeze(path, testset.load(path), "abc123")
    assert lock["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert lock["by_type"] == {"answerable": 1, "decline": 1, "off_topic": 1}
    assert testset.verify_unchanged(path) == lock

    path.write_text(path.read_text(encoding="utf-8").replace("weather", "weathr"), encoding="utf-8")
    with pytest.raises(testset.TestSetChanged):
        testset.verify_unchanged(path)
    with pytest.raises(testset.AlreadyFrozen):
        testset.freeze(path, testset.load(path), "abc123")


def test_a_malformed_file_is_refused_with_a_readable_message(tmp_path):
    data = copy.deepcopy(GOOD)
    data["questions"][0]["type"] = "easy"
    with pytest.raises(testset.TestSetError, match=r"questions\.0\.type"):
        testset.load(write_set(tmp_path, data))


def test_review_counts_what_the_wording_check_flagged_and_what_changed(snapshot_dir, tmp_path):
    help_center = HelpCenterSnapshot(snapshot_dir)
    draft = copy.deepcopy(GOOD)
    draft["drafting"] = {"method": "drafted", "rewritten": None}  # an older drafting block is ignored
    draft["questions"][0]["question"] = "hover over the message to see icons"
    draft_set = testset.load_draft(write_set(tmp_path, draft, "draft.yaml"))
    final = copy.deepcopy(GOOD)
    final["questions"][1]["notes"] = "checked against the help center"  # notes don't count as a change
    assert checks.review_counts(draft_set, testset.load(write_set(tmp_path, final)), help_center) == (1, 1)

    # a locked question's wording isn't the draft's, so it isn't flagged, and locking it isn't a change
    final["questions"][0].update(question=draft["questions"][0]["question"], locked=True)
    assert checks.review_counts(draft_set, testset.load(write_set(tmp_path, final)), help_center) == (0, 0)


def test_cli_checks_then_freezes_and_refuses_an_edit(snapshot_dir, tmp_path):
    runner = CliRunner()
    path = write_set(tmp_path, GOOD)
    draft = write_set(tmp_path, GOOD, "demo-v1.draft.yaml")
    args = [str(path), "--snapshot", str(snapshot_dir)]

    result = runner.invoke(app, ["test", "check", *args])
    assert result.exit_code == 0, result.output

    result = runner.invoke(app, ["test", "freeze", *args])
    assert result.exit_code == 1, "a set with a drafting block needs its draft to freeze"

    result = runner.invoke(app, ["test", "freeze", *args, "--draft", str(draft)])
    assert result.exit_code == 0, result.output
    assert "fingerprint" in result.output
    assert "0 of 3 changed in review" in result.output
    lock = testset.read_lock(path)
    assert (lock["flagged"], lock["edited"]) == (0, 0)
    assert lock["draft_sha256"] == hashlib.sha256(draft.read_bytes()).hexdigest()

    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert runner.invoke(app, ["test", "check", *args]).exit_code == 1
