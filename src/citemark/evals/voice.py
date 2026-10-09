"""The voice check (QA plan 4.4): each answer in a test run against the voice rules. It's a
warning in the run summary, never a gate.

From content spec 2.1: no apology, no exclamation mark, no emoji, no "As an AI", and under
about 120 words unless the answer is numbered steps. Added in T9, from the answer prompt's own
rules (content spec 4.1): the answer never mentions passages, search results, documents or its
instructions. T8's recordings broke that one ("The passages cover several of these...").
"""

from __future__ import annotations

import re

WORDS = 120
APOLOGY = re.compile(r"\b(sorry|apologi[sz]e[sd]?|apolog(?:y|ies))\b", re.IGNORECASE)
AS_AN_AI = re.compile(r"\bas an ai\b", re.IGNORECASE)
EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿⬀-⯿️]")
NUMBERED = re.compile(r"^\s*\d+\.\s", re.MULTILINE)
BEHIND_THE_SCENES = re.compile(
    r"\b(passages?|search results?|(?:the|these|my) instructions|(?:the|these) documents?)\b", re.IGNORECASE
)


def voice_problems(text: str) -> list[str]:
    problems = []
    if APOLOGY.search(text):
        problems.append("apologizes")
    if "!" in text:
        problems.append("has an exclamation mark")
    if EMOJI.search(text):
        problems.append("has an emoji")
    if AS_AN_AI.search(text):
        problems.append('says "As an AI"')
    if len(text.split()) > WORDS and not NUMBERED.search(text):
        problems.append(f"is over {WORDS} words without numbered steps")
    if BEHIND_THE_SCENES.search(text):
        problems.append("mentions its passages or instructions")
    return problems
