"""Jinja rendering (UI kit 2): the macros the Python-rendered surfaces share, starting with the
primitives (UI kit 5.2). The report, the demo page and the ask page all render through here.

- **Autoescape is on** for every template, since the evidence record shows visitor text. Markup
  that's safe by construction, like a glyph's SVG, is marked as such where it's made.
- **No text lives in a macro** (UI kit 2, rule 6). Each label is passed in by the caller, from a
  strings file: `t("report", "state.pass")`.
- **Undefined is an error,** so a missing value fails the render rather than leaving a gap.
- **`**bold**` in a string is drawn bold** (`rich`), after the rest is escaped, so the content
  spec's strings are used as written: "**Pass.** The bot met every target…".
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Any, NoReturn

from jinja2 import ChoiceLoader, Environment, PackageLoader, StrictUndefined
from markupsafe import Markup, escape

from citemark import strings

KIT = Path(__file__).resolve().parents[3]
GLYPHS = KIT / "design" / "glyphs"
BOLD = re.compile(r"\*\*(.+?)\*\*")


class RenderError(Exception):
    """A macro was called with something it can't render. The message is one plain sentence."""


@cache
def glyph(name: str) -> Markup:
    """A glyph's SVG, to inline in a page. Its drawing is the file in `design/glyphs/`."""
    path = GLYPHS / f"{name}.svg"
    if not path.is_file():
        raise RenderError(f"There's no glyph {name} in {GLYPHS}.")
    return Markup(path.read_text(encoding="utf-8").strip())


def rich(text: str) -> Markup:
    """A string with its `**bold**` stretches drawn bold, and everything else escaped."""
    return Markup(BOLD.sub(lambda match: f"<strong>{match.group(1)}</strong>", str(escape(text))))


def bold_part(text: str) -> str:
    """Only a string's bold stretch, such as a step's short name: "1 · The question"."""
    found = BOLD.search(text)
    if found is None:
        raise RenderError(f"{text!r} has no bold stretch to shorten it to.")
    return found.group(1)


def refuse(message: str) -> NoReturn:
    """Lets a macro stop the render with a reason, since Jinja has no raise."""
    raise RenderError(message)


@cache
def environment() -> Environment:
    env = Environment(
        loader=ChoiceLoader([PackageLoader(package, "templates") for package in ("citemark.report", "citemark.web")]),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(glyph=glyph, refuse=refuse, t=strings.text)
    env.filters.update(rich=rich, bold_part=bold_part)
    return env


def primitives() -> Any:
    """The primitives' macros, each callable with keyword arguments and returning Markup."""
    return environment().get_template("primitives.html").module
