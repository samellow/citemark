"""The bot's instructions (content spec 4), read from `prompts/` at the kit's root.

Each file's name carries its version (`rewrite.v1.md`), and every test run records the version
it used, so a changed prompt is a new file and old runs stay comparable (QA plan 4.5).
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"  # the kit's root, in the repo and the image


@cache
def load(name: str) -> str:
    """A prompt's text, without its final newline. `name` is the file's name without `.md`."""
    return _read(f"{name}.md").rstrip("\n")


def load_tools(name: str) -> list[dict[str, Any]]:
    """A tools file, such as `tools.v1`: a fresh copy each time, so a caller can fill in its slots."""
    return json.loads(_read(f"{name}.json"))


@cache
def _read(filename: str) -> str:
    path = PROMPTS / filename
    if not path.is_file():
        raise FileNotFoundError(f"No prompt {path.stem} in {PROMPTS}.")
    return path.read_text(encoding="utf-8")
