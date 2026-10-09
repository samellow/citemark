"""The design tokens (UI kit 3): the 25 contrast pairs held to WCAG AA in both themes, references
resolved per theme, and static/tokens.css written from design/tokens.json and kept in step."""

import copy
import json

import pytest
from typer.testing import CliRunner

from citemark.cli import app
from citemark.design import tokens

DESIGN = tokens.load()


@pytest.mark.parametrize("pair", tokens.pairs(DESIGN), ids=lambda p: f"{p.theme}: {p.foreground} on {p.background}")
def test_each_pair_holds_wcag_aa(pair):
    assert pair.passes, f"{pair.ratio:.2f}:1 is below {pair.minimum}:1"


def test_the_25_pairs_are_the_artifacts_checked_once_per_theme():
    assert len(tokens.PAIRS) == 25 == len({(fg, bg) for fg, bg, _ in tokens.PAIRS})
    assert len(tokens.pairs(DESIGN)) == 50


def test_contrast_is_wcags():
    assert tokens.contrast("#000000", "#ffffff") == pytest.approx(21)
    assert tokens.contrast("#2f4bd8", "#ffffff") == pytest.approx(6.7, abs=0.05)  # design system 3.1
    assert tokens.contrast("#ffffff", "#2f4bd8") == tokens.contrast("#2f4bd8", "#ffffff")


def with_color(name: str, theme: str, value: str) -> dict:
    changed = copy.deepcopy(DESIGN)
    token = next(t for t in changed["color"]["tokens"] if t["name"] == name)
    token["value"] = {**token["value"], theme: value}
    return changed


def test_a_color_too_faint_for_its_pairs_is_caught_in_every_pair_it_makes():
    """#707886 holds 3.5 to 4.35:1 on the dark grounds: over the 3:1 for borders, under the 4.5:1 for text."""
    found = [p for p in tokens.pairs(with_color("text-muted", "dark", "#707886")) if not p.passes]
    assert {(p.theme, p.foreground) for p in found} == {("dark", "text-muted"), ("dark", "declined")}


def test_a_reference_takes_each_themes_own_value():
    colors = tokens.colors(DESIGN)
    assert colors["declined"] == colors["text-muted"]
    assert colors["widget-accent"] == colors["ink"] and colors["focus-ring"] == colors["ink"]
    assert colors["declined"]["light"] != colors["declined"]["dark"]


@pytest.mark.parametrize(
    ("value", "message"),
    [("{nowhere}", "isn't a color token"), ("{declined}", "point at each other in a loop"), ("blue", "not a #rrggbb")],
)
def test_a_reference_to_nothing_a_loop_or_a_non_color_is_refused(value, message):
    changed = copy.deepcopy(DESIGN)
    next(t for t in changed["color"]["tokens"] if t["name"] == "text-muted")["value"] = value
    with pytest.raises(tokens.TokenError, match=message):
        tokens.colors(changed)


def test_dark_is_for_screens_only_so_every_page_prints_in_light():
    css = tokens.css(DESIGN)
    dark_ground = tokens.colors(DESIGN)["ground"]["dark"]
    assert dark_ground not in css[: css.index("@media screen and (prefers-color-scheme: dark)")]
    blocks = css.split("\n}\n")
    assert all("@media screen" in block for block in blocks if dark_ground in block)
    assert '[data-theme="light"] {' in css and "@media print" not in css


def test_a_theme_set_on_an_element_brings_its_own_text_and_ground():
    """A dark panel inside a light page gets dark text on a dark ground, not just dark variables."""
    css = tokens.css(DESIGN)
    for theme in ("dark", "light"):
        block = css[css.index(f'[data-theme="{theme}"] {{') :]
        block = block[: block.index("}")]
        assert "color: var(--text);" in block and "background-color: var(--ground);" in block


def test_reduced_motion_stops_every_duration():
    css = tokens.css(DESIGN)
    reduced = css[css.index("@media (prefers-reduced-motion: reduce)") :]
    assert "--duration-state: 0ms;" in reduced and "--duration-panel: 0ms;" in reduced


def test_each_type_style_gets_variables_and_a_role_class():
    css = tokens.css(DESIGN)
    assert "--type-label-tracking: 0.06em;" in css and "--type-data-lg-family: var(--font-mono);" in css
    assert ".cm-type-label { font-family: var(--type-label-family);" in css


def test_the_committed_css_matches_the_tokens():
    assert not tokens.stale(), "static/tokens.css is out of date: run citemark design build"


def test_the_build_writes_the_css_and_says_when_nothing_changed(tmp_path):
    target = tmp_path / "tokens.css"
    assert tokens.build(target=target) is True
    assert tokens.build(target=target) is False
    assert not tokens.stale(target=target)


def test_the_command_checks_the_pairs_and_refuses_stale_css(tmp_path, monkeypatch):
    stale = tmp_path / "tokens.css"
    stale.write_text("/* old */\n", encoding="utf-8")
    monkeypatch.setattr(tokens, "CSS", stale)
    found = CliRunner().invoke(app, ["design", "build", "--check"])
    assert found.exit_code == 1 and "doesn't match design/tokens.json" in found.output
    assert stale.read_text(encoding="utf-8") == "/* old */\n"  # --check writes nothing
    found = CliRunner().invoke(app, ["design", "build"])
    assert found.exit_code == 0 and "Wrote static/tokens.css." in found.output and not tokens.stale(target=stale)


def test_the_command_refuses_a_pair_below_aa(tmp_path, monkeypatch):
    source = tmp_path / "tokens.json"
    source.write_text(json.dumps(with_color("ink", "light", "#8ea2ff")), encoding="utf-8")
    monkeypatch.setattr(tokens, "SOURCE", source)
    monkeypatch.setattr(tokens, "CSS", tmp_path / "tokens.css")
    found = CliRunner().invoke(app, ["design", "build"])
    assert found.exit_code == 1 and "light: ink on surface is" in found.output
    assert not (tmp_path / "tokens.css").exists()
