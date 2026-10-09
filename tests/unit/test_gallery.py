"""The component manifest and the gallery (UI kit 4 and 5): 67 components as the inventory
lists them, and one page per component, state and theme, built from the fixtures with the real
strings. Also the fonts the pages load, and their license."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest
import yaml
from lxml import html
from typer.testing import CliRunner

from citemark import strings
from citemark.cli import app
from citemark.design import gallery, manifest

KIT = Path(__file__).parents[2]
FONTS = KIT / "static" / "fonts"
COMPONENTS = manifest.load()


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("gallery") / "site"
    return out, gallery.build(out)


# --- The manifest ---


def test_the_manifest_lists_the_67_components_by_phase_as_the_inventory_does():
    """UI kit 5: 25 in Phase 1, 2 across phases 1 and 2, 38 in Phase 2 and 2 in Phase 3."""
    assert len(COMPONENTS) == 67
    assert Counter(c.phase for c in COMPONENTS.values()) == {"1": 25, "1-2": 2, "2": 38, "3": 2}
    assert Counter(c.layer for c in COMPONENTS.values()) == {
        "foundation": 5,
        "primitive": 6,
        "report": 11,
        "demo": 7,
        "widget": 16,
        "admin": 22,
    }


def test_a_component_listed_twice_is_refused(tmp_path):
    entry = COMPONENTS["Button"].model_dump()
    (tmp_path / "components.yaml").write_text(yaml.safe_dump({"components": [entry, entry]}), encoding="utf-8")
    with pytest.raises(manifest.ManifestError, match=r"Button is in components\.yaml twice"):
        manifest.load(tmp_path / "components.yaml")


def test_every_string_a_built_component_shows_is_in_its_file(built):
    _, pages = built
    for name in {page.component for page in pages}:
        for key in COMPONENTS[name].strings:
            file, _, name_in_file = key.partition(":")
            assert name_in_file in strings.load(file), f"{name} shows {key}, which isn't in {file}.json"


# --- The gallery ---


def test_every_fixture_state_gets_a_page_in_each_theme_unless_it_is_a_theme(built):
    out, pages = built
    expected = 0
    for fixture in gallery.load_fixtures():
        assert fixture.component in COMPONENTS
        for state, entry in fixture.states.items():
            assert state in COMPONENTS[fixture.component].states
            expected += 1 if entry.theme else 2
    assert len(pages) == expected
    assert all((out / page.path).is_file() for page in pages)
    listed = json.loads((out / "pages.json").read_text(encoding="utf-8"))
    assert [entry["path"] for entry in listed] == [page.path for page in pages] + ["index.html"]


def test_each_page_is_a_whole_document_in_its_theme(built):
    out, pages = built
    for page in pages:
        document = html.fromstring((out / page.path).read_bytes())
        assert document.get("lang") == "en" and document.get("data-theme") == page.theme
        assert document.findtext(".//title").startswith(f"{page.component}: {page.state}")
        assert len(document.findall(".//h1")) == 1 and len(document.findall(".//main")) == 1


def test_a_page_shows_the_strings_files_words(built):
    out, _ = built
    assert ">Pass<" in (out / "state-mark/pass--light.html").read_text(encoding="utf-8")
    error = (out / "field/with_error--dark.html").read_text(encoding="utf-8")
    assert strings.text("widget", "handoff.email_invalid") in error
    assert 'aria-label="Source 1"' in (out / "citation-marker/tinted--light.html").read_text(encoding="utf-8")


def test_every_file_a_page_links_is_in_the_gallery(built):
    out, pages = built
    for page in [*pages, gallery.Page("index.html", "", "", "light")]:
        folder = (out / page.path).parent
        for link in re.findall(r'(?:href|src)="([^"#:]+)"', (out / page.path).read_text(encoding="utf-8")):
            assert (folder / link).resolve().is_file(), f"{page.path} links {link}"
    for font in re.findall(r'url\("([^"]+)"\)', (out / "static/citemark.css").read_text(encoding="utf-8")):
        assert (out / "static" / font).is_file()
    assert not (out / "static/fonts/latin1").exists()  # the report's fonts, not the pages'


def test_the_tokens_page_shows_the_25_pairs_of_its_theme(built):
    out, _ = built
    document = html.fromstring((out / "tokens/dark--dark.html").read_bytes())
    rows = document.findall(".//section[@aria-labelledby='contrast']//tbody/tr")
    assert len(rows) == 25 and all("Pass" in row.text_content() for row in rows)


def test_a_rebuild_replaces_a_gallery_but_never_empties_another_folder(tmp_path):
    out = tmp_path / "site"
    gallery.build(out)
    (out / "stale.html").write_text("old", encoding="utf-8")
    gallery.build(out)
    assert not (out / "stale.html").exists()
    other = tmp_path / "notes"
    other.mkdir()
    (other / "keep.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(gallery.GalleryError, match="isn't empty and isn't a gallery"):
        gallery.build(other)
    assert (other / "keep.txt").read_text(encoding="utf-8") == "mine"


def test_the_gallery_is_built_only_in_a_real_folder(tmp_path):
    marked = tmp_path / "site"
    gallery.build(marked)
    link = tmp_path / "link"
    link.symlink_to(marked)
    with pytest.raises(gallery.GalleryError, match="isn't a folder"):
        gallery.build(link)  # rmtree on a link would fail halfway, or follow it
    file = tmp_path / "notes.txt"
    file.write_text("mine", encoding="utf-8")
    with pytest.raises(gallery.GalleryError, match="isn't a folder"):
        gallery.build(file)
    assert file.read_text(encoding="utf-8") == "mine"


def test_a_linked_marker_doesnt_make_a_folder_a_gallery(tmp_path):
    other = tmp_path / "notes"
    other.mkdir()
    (other / "keep.txt").write_text("mine", encoding="utf-8")
    real = tmp_path / "real-marker"
    real.write_text("x", encoding="utf-8")
    (other / gallery.MARKER).symlink_to(real)
    with pytest.raises(gallery.GalleryError, match="isn't empty and isn't a gallery"):
        gallery.build(other)
    assert (other / "keep.txt").is_file()


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ({"component": "Nope", "macro": "button", "states": {}}, "names a component the manifest doesn't list"),
        ({"component": "Button", "macro": "button", "states": {"huge": {}}}, "Button has no state huge"),
        ({"component": "Button", "macro": "nope", "states": {}}, "names a macro, nope, that doesn't exist"),
        ({"component": "Button", "macro": "button", "page": "base", "states": {}}, "isn't a gallery fixture"),
    ],
)
def test_a_fixture_that_doesnt_fit_the_manifest_is_refused(tmp_path, fixture, message):
    folder = tmp_path / "fixtures"
    folder.mkdir()
    (folder / "x.yaml").write_text(yaml.safe_dump(fixture), encoding="utf-8")
    with pytest.raises(gallery.GalleryError, match=message):
        gallery.build(tmp_path / "site", fixtures=folder)


def test_the_command_builds_it_and_says_where(tmp_path):
    found = CliRunner().invoke(app, ["gallery", "--out", str(tmp_path / "site")])
    assert found.exit_code == 0 and "Open" in found.output and (tmp_path / "site/index.html").is_file()


# --- Fonts ---


def test_the_fonts_are_ibms_files_as_recorded_with_their_license():
    recorded = dict(re.findall(r"- `([^`]+)` ([0-9a-f]{64})", (FONTS / "README.md").read_text(encoding="utf-8")))
    files = sorted(str(path.relative_to(FONTS)) for path in FONTS.rglob("*") if path.suffix in (".woff2", ".txt"))
    assert sorted(recorded) == files
    for name, digest in recorded.items():
        assert hashlib.sha256((FONTS / name).read_bytes()).hexdigest() == digest, name
    assert "SIL OPEN FONT LICENSE Version 1.1" in (FONTS / "OFL.txt").read_text(encoding="utf-8")


def test_every_font_the_stylesheet_names_is_there_and_every_page_font_is_named():
    css = (KIT / "static/citemark.css").read_text(encoding="utf-8")
    named = set(re.findall(r'url\("fonts/([^"]+)"\)', css))
    assert named == {path.name for path in FONTS.glob("*.woff2")}
