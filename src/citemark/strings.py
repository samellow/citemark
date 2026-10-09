"""Visible text (content spec 1), read from `content/en/*.json` at the kit's root.

No visible string lives in code (implementation plan 2). A string's slots, such as `{company}`,
are filled here. Plural and select patterns aren't needed yet, so a string holding one is refused
rather than shown with its braces.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

CONTENT = Path(__file__).resolve().parents[2] / "content" / "en"  # the kit's root, in the repo and the image
SLOT = re.compile(r"\{(\w+)\}")


@cache
def load(name: str) -> dict[str, str]:
    """One strings file, such as `widget`, as key: text."""
    path = CONTENT / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"No strings file {name} in {CONTENT}.")
    return json.loads(path.read_text(encoding="utf-8"))


def text(name: str, key: str, **slots: str) -> str:
    """A string with its slots filled. A missing key or slot is an error, never an empty gap."""
    strings = load(name)
    if key not in strings:
        raise KeyError(f"No string {key} in {name}.json.")
    template = strings[key]
    if "{" in SLOT.sub("", template) or "}" in SLOT.sub("", template):
        raise ValueError(f"The string {key} has a plural or select pattern, which isn't supported yet.")
    missing = [slot for slot in SLOT.findall(template) if slot not in slots]
    if missing:
        raise KeyError(f"The string {key} needs a value for {{{missing[0]}}}.")
    # Filled in one pass, so a value holding braces (a gap phrase is the model's words) stays as it is
    return SLOT.sub(lambda match: slots[match.group(1)], template)
