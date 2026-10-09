"""The component gallery (UI kit 4): one static page per component, state and theme, built from
`design/fixtures/` by `citemark gallery`. The accessibility check runs on every page in CI, and
Phase 2's keyboard, snapshot and markup-contract tests will run on them too.

- **A Jinja component** renders through its macro, with the fixture's arguments. A value written
  `{string: file:key}` comes from `content/en/`, so the gallery shows the real words.
- **A foundation** (the tokens, the base stylesheet, the glyphs) has a page of its own.
- **Each state in both themes,** as two pages, unless the state is itself a theme.
- **Self-contained:** the pages and a copy of `static/` go in one folder, which opens from disk
  and can be published as it is.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader, StrictUndefined
from markupsafe import Markup
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from citemark import strings
from citemark.design import manifest, tokens
from citemark.report.render import glyph, refuse

KIT = Path(__file__).resolve().parents[3]
FIXTURES = KIT / "design" / "fixtures"
STATIC = KIT / "static"
TEMPLATES = Path(__file__).parent / "templates"
MARKER = ".citemark-gallery"  # marks a folder this builds, so a rebuild never empties another
THEMES = ("light", "dark")
RENDERED_BY = {"J": "Jinja", "R": "React", "P": "Preact", "L": "the loader", "CSS": "CSS", "All": "every renderer"}


class GalleryError(Exception):
    """The gallery can't be built. The message is one plain sentence."""


class _State(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    theme: Literal["light", "dark"] | None = None  # a state that is a theme has one page
    before: str | None = None  # sample text the component follows, as a marker follows a claim
    arguments: dict[str, Any] = Field(default_factory=dict, alias="with")


class Fixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    macro: str | None = None  # a primitive's macro, in report/templates/primitives.html
    page: str | None = None  # or a foundation's own page, in design/templates/
    states: dict[str, _State]

    @model_validator(mode="after")
    def _macro_or_page(self) -> Fixture:
        if (self.macro is None) == (self.page is None):
            raise ValueError("a fixture names a macro or a page, not both or neither")
        return self


@dataclass(frozen=True)
class Page:
    path: str  # relative to the gallery folder
    component: str
    state: str
    theme: str


def load_fixtures(folder: Path = FIXTURES) -> list[Fixture]:
    found = []
    for path in sorted(folder.glob("*.yaml")):
        try:
            found.append(Fixture.model_validate(yaml.safe_load(path.read_text(encoding="utf-8"))))
        except (yaml.YAMLError, ValidationError) as exc:
            raise GalleryError(f"{path.name} isn't a gallery fixture: {exc}") from exc
    return found


def _value(value: Any) -> Any:
    """A fixture's value: a string's text when written {string: file:key}, else as written."""
    if isinstance(value, dict) and "string" in value and set(value) <= {"string", "slots"}:
        file, _, key = value["string"].partition(":")
        return strings.text(file, key, **{name: str(slot) for name, slot in value.get("slots", {}).items()})
    return value


def environment() -> Environment:
    env = Environment(
        loader=ChoiceLoader([FileSystemLoader(TEMPLATES), PackageLoader("citemark.report", "templates")]),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(glyph=glyph, refuse=refuse, t=strings.text)
    return env


def _prepare(out: Path) -> None:
    """Empty the output folder, but only one this built before: a real folder, marked by a real file."""
    if out.is_symlink() or (out.exists() and not out.is_dir()):
        raise GalleryError(f"{out} isn't a folder, so the gallery isn't built there. Choose a folder.")
    if out.exists():
        marker = out / MARKER
        if not (marker.is_file() and not marker.is_symlink()) and any(out.iterdir()):
            raise GalleryError(f"{out} isn't empty and isn't a gallery, so it's left as it is. Choose another folder.")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / MARKER).write_text("Built by citemark gallery. Rebuilding empties this folder.\n", encoding="utf-8")
    shutil.copytree(STATIC, out / "static", ignore=shutil.ignore_patterns("latin1"))  # those are the report's
    shutil.copy(TEMPLATES / "gallery.css", out / "gallery.css")


def build(out: Path, *, fixtures: Path = FIXTURES, manifest_path: Path = manifest.MANIFEST) -> list[Page]:
    """Write the gallery to `out` and return its pages."""
    components = manifest.load(manifest_path)
    loaded = load_fixtures(fixtures)
    env = environment()
    macros = env.get_template("primitives.html").module
    design = tokens.load()
    context = {
        "colors": tokens.colors(design),
        "usage": {token["name"]: token["usage"] for token in design["color"]["tokens"]},
        "pairs": tokens.pairs(design),
    }
    _prepare(out)
    pages: list[Page] = []
    for fixture in loaded:
        component = components.get(fixture.component)
        if component is None:
            raise GalleryError(f"The fixture for {fixture.component} names a component the manifest doesn't list.")
        if fixture.macro and not hasattr(macros, fixture.macro):
            raise GalleryError(f"The fixture for {component.name} names a macro, {fixture.macro}, that doesn't exist.")
        for state, entry in fixture.states.items():
            if state not in component.states:
                raise GalleryError(f"{component.name} has no state {state} in the manifest.")
            arguments = {name: _value(value) for name, value in entry.arguments.items()}
            themes = (entry.theme,) if entry.theme else THEMES
            for theme in themes:
                if fixture.macro:
                    body = getattr(macros, fixture.macro)(**arguments)
                else:
                    body = Markup(env.get_template(f"{fixture.page}.html").render(theme=theme, **context, **arguments))
                path = f"{component.slug}/{state}--{theme}.html"
                other = None
                if len(themes) == 2:
                    other_theme = THEMES[1 - THEMES.index(theme)]
                    other = {"href": f"{state}--{other_theme}.html", "theme": other_theme}
                html = env.get_template("page.html").render(
                    component=component,
                    state=state,
                    theme=theme,
                    body=body,
                    before=entry.before,
                    rendered_by=RENDERED_BY["J"] if fixture.macro else "a page of its own",
                    other=other,
                    root="../",
                )
                (out / component.slug).mkdir(exist_ok=True)
                (out / path).write_text(html, encoding="utf-8")
                pages.append(Page(path, component.name, state, theme))
    paged = {page.component for page in pages}
    index = env.get_template("index.html").render(
        components=list(components.values()),
        pages=pages,
        paged=paged,
        rendered_by=RENDERED_BY,
        root="",
    )
    (out / "index.html").write_text(index, encoding="utf-8")
    index_page = {"path": "index.html", "component": "", "state": "", "theme": "light"}
    listing = [asdict(page) for page in pages] + [index_page]
    (out / "pages.json").write_text(json.dumps(listing, indent=2) + "\n", encoding="utf-8")
    return pages
