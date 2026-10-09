"""Jinja rendering (UI kit 2): the macros the Python-rendered surfaces share, starting with the
primitives (UI kit 5.2). The report, the demo page and the ask page all render through here.

- **Autoescape is on** for every template, since the evidence record shows visitor text. Markup
  that's safe by construction, like a glyph's SVG, is marked as such where it's made.
- **No text lives in a macro** (UI kit 2, rule 6). Each label is passed in by the caller, from a
  strings file: `t("report", "state.pass")`.
- **Undefined is an error,** so a missing value fails the render rather than leaving a gap.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any, NoReturn

from jinja2 import Environment, PackageLoader, StrictUndefined
from markupsafe import Markup

from citemark import strings

KIT = Path(__file__).resolve().parents[3]
GLYPHS = KIT / "design" / "glyphs"


class RenderError(Exception):
    """A macro was called with something it can't render. The message is one plain sentence."""


@cache
def glyph(name: str) -> Markup:
    """A glyph's SVG, to inline in a page. Its drawing is the file in `design/glyphs/`."""
    path = GLYPHS / f"{name}.svg"
    if not path.is_file():
        raise RenderError(f"There's no glyph {name} in {GLYPHS}.")
    return Markup(path.read_text(encoding="utf-8").strip())


def refuse(message: str) -> NoReturn:
    """Lets a macro stop the render with a reason, since Jinja has no raise."""
    raise RenderError(message)


@cache
def environment() -> Environment:
    env = Environment(
        loader=PackageLoader("citemark.report", "templates"),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(glyph=glyph, refuse=refuse, t=strings.text)
    return env


def primitives() -> Any:
    """The primitives' macros, each callable with keyword arguments and returning Markup."""
    return environment().get_template("primitives.html").module
