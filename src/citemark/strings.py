"""Visible text (content spec 1), read from `content/en/*.json` at the kit's root.

No visible string lives in code (implementation plan 2). A string's slots, such as `{company}`,
are filled here, and so are plurals in ICU's form (content spec 2.3), such as
`{hours, plural, one {# hour} other {# hours}}`:

- **A case** is `=N` for an exact number, or `one` or `other`, English's two categories.
- **`#`** in a case is the number, written with thousands separators.
- **An apostrophe is a letter,** never ICU's quote, so "doesn't" needs no escaping.

Anything else in braces, such as a `select` pattern, is refused rather than shown with its braces.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

CONTENT = Path(__file__).resolve().parents[2] / "content" / "en"  # the kit's root, in the repo and the image
NAME = re.compile(r"\s*(\w+)\s*")
PLURAL = re.compile(r",\s*plural\s*,")
CASE = re.compile(r"\s*(=\d+|one|other)\s*\{")
CLOSING = re.compile(r"\s*\}")


class StringError(ValueError):
    """A string can't be read as a message. The message is one plain sentence."""


@dataclass(frozen=True)
class Slot:
    name: str


@dataclass(frozen=True)
class Plural:
    name: str
    cases: dict[str, tuple[Part, ...]]  # "=0", "one" or "other": the message for it


type Part = str | Slot | Plural | None  # None is a plural's "#"


def parse(template: str) -> tuple[Part, ...]:
    """A string as its parts: text, slots, and plurals with their cases."""
    parts, end = _message(template, 0, in_case=False)
    if end != len(template):
        raise StringError(f"{template!r} has a closing brace with no opening one.")
    return parts


def _message(template: str, at: int, *, in_case: bool) -> tuple[tuple[Part, ...], int]:
    """Text up to the brace that closes it, or to the end."""
    parts: list[Part] = []
    text: list[str] = []
    while at < len(template) and template[at] != "}":
        char = template[at]
        if char == "#" and in_case:
            parts += ["".join(text), None]
            text, at = [], at + 1
        elif char == "{":
            part, at = _argument(template, at + 1)
            parts += ["".join(text), part]
            text = []
        else:
            text.append(char)
            at += 1
    parts.append("".join(text))
    return tuple(part for part in parts if part != ""), at


def _argument(template: str, at: int) -> tuple[Part, int]:
    """After an opening brace: a slot, or a plural with its cases."""
    name = NAME.match(template, at)
    if name is None:
        raise StringError(f"{template!r} has a brace without a slot name after it.")
    at = name.end()
    if template.startswith("}", at):
        return Slot(name.group(1)), at + 1
    kind = PLURAL.match(template, at)
    if kind is None:
        raise StringError(f"{template!r} has a pattern other than a slot or a plural, which isn't supported.")
    at = kind.end()
    cases: dict[str, tuple[Part, ...]] = {}
    while (case := CASE.match(template, at)) is not None:
        message, at = _message(template, case.end(), in_case=True)
        if not template.startswith("}", at):
            raise StringError(f"{template!r} has a plural case that isn't closed.")
        cases[case.group(1)] = message
        at += 1
    closing = CLOSING.match(template, at)
    if closing is None or "other" not in cases:
        raise StringError(f"{template!r} has a plural that doesn't end with an other case and a closing brace.")
    return Plural(name.group(1), cases), closing.end()


@cache
def load(name: str) -> dict[str, str]:
    """One strings file, such as `widget`, as key: text."""
    path = CONTENT / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"No strings file {name} in {CONTENT}.")
    return json.loads(path.read_text(encoding="utf-8"))


def text(name: str, key: str, **slots: str | int) -> str:
    """A string with its slots and plurals filled. A missing key or slot is an error, never an
    empty gap, and a plural's slot needs a whole number."""
    strings = load(name)
    if key not in strings:
        raise KeyError(f"No string {key} in {name}.json.")
    try:
        parts = parse(strings[key])
    except StringError as exc:
        raise StringError(f"The string {key} in {name}.json can't be read: {exc}") from exc
    # Filled in one pass, so a value holding braces (a gap phrase is the model's words) stays as it is
    return _filled(key, parts, slots, number=None)


def _filled(key: str, parts: tuple[Part, ...], slots: dict[str, str | int], number: int | None) -> str:
    out = []
    for part in parts:
        if part is None:
            out.append(f"{number:,}")
        elif isinstance(part, str):
            out.append(part)
        elif part.name not in slots:
            raise KeyError(f"The string {key} needs a value for {{{part.name}}}.")
        elif isinstance(part, Slot):
            out.append(str(slots[part.name]))
        else:
            value = slots[part.name]
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"The string {key} counts {{{part.name}}}, so it needs a whole number, not {value!r}.")
            case = f"={value}" if f"={value}" in part.cases else ("one" if value == 1 else "other")
            out.append(_filled(key, part.cases.get(case, part.cases["other"]), slots, value))
    return "".join(out)
