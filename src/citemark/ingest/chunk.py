"""Chunking (PRD 5.1): headings split each article into sections, and each section becomes a
passage of up to about 500 tokens. A longer section splits at paragraph boundaries.

Each passage starts with its heading path (the article's title, then the section headings),
and keeps its paragraphs as separate blocks, so a citation can point at one paragraph. A label
line such as "**Mobile:**" or "**Note:**" stays with the block it introduces, so a cited step
still says which app it's for.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

PATH_SEPARATOR = " \u203a "  # a single right-pointing angle quote, as in PRD 4.1
MAX_TOKENS = 500
# Token counts here are estimates: about 4 characters a token for English. Voyage and Claude
# each count differently, so where an exact count matters (fitting a model's context window,
# T7) it's measured, not taken from here.
CHARS_PER_TOKEN = 4

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
BACKTICKS = re.compile(r"`+")
LABEL = re.compile(r"^\*\*[^*\n]+:\*\*$")  # "**Desktop/Web:**", "**Note:**"
LIST_ITEM = re.compile(r"^(\d+\.|[-*+])\s")  # a top-level item: numbered or bulleted, not indented


@dataclass(frozen=True)
class Passage:
    position: int
    heading_path: str
    anchor_url: str | None
    blocks: tuple[str, ...]
    text: str
    token_count: int  # an estimate (see CHARS_PER_TOKEN)


@dataclass
class _Section:
    path: list[str]
    anchor: str | None
    lines: list[str]


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def _plain(heading: str) -> str:
    return " ".join(heading.replace("**", "").replace("`", "").split())


def _key(heading: str) -> str:
    return _plain(heading).casefold()


def _fence(line: str, open_length: int) -> int:
    """The code fence open after this line: 0 if none, else the length of its opening run.

    As in CommonMark, a fence closes only on a line of at least as many backticks, so a
    four-backtick fence can show a three-backtick example. The extractor sometimes opens a
    fence at the end of a sentence ("run the following: ```"), so a run of three or more
    that no later run on the line closes counts too; a code span like ```` ``` ```` doesn't."""
    if open_length:
        closing = line.strip()
        return 0 if closing and set(closing) == {"`"} and len(closing) >= open_length else open_length
    unclosed = 0
    for run in BACKTICKS.findall(line):
        if not unclosed:
            unclosed = len(run)
        elif len(run) == unclosed:
            unclosed = 0
    return unclosed if unclosed >= 3 else 0


def _sections(title: str, markdown: str, anchors: Iterable[tuple[str, str]]) -> list[_Section]:
    keys = [(_key(text), anchor) for text, anchor in anchors]
    next_anchor = 0  # headings can repeat on a page, so anchors are matched in page order
    stack: list[tuple[int, str, str | None]] = []
    sections = [_Section([title], None, [])]
    fence, title_seen = 0, False
    for line in markdown.splitlines():
        match = None if fence else HEADING.match(line)
        fence = _fence(line, fence)
        if not match:
            sections[-1].lines.append(line)
            continue
        level, heading = len(match.group(1)), _plain(match.group(2))
        if level == 1 and not title_seen:
            title_seen = True  # the title, already at the start of every path
            continue
        anchor = None
        for i in range(next_anchor, len(keys)):
            if keys[i][0] == _key(heading):
                anchor, next_anchor = keys[i][1], i + 1
                break
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, heading, anchor))
        path = [title]
        for _, name, _ in stack:
            if _key(name) != _key(path[-1]):  # "Star a message > Star a message" reads once
                path.append(name)
        nearest = next((a for _, _, a in reversed(stack) if a), None)
        sections.append(_Section(path, nearest, []))
    return sections


def _blocks(lines: list[str]) -> list[str]:
    """Paragraphs, lists, callouts and code blocks, split at blank lines outside code."""
    blocks: list[str] = []
    current: list[str] = []
    fence = 0
    for line in lines:
        fence = _fence(line, fence)
        if not fence and not line.strip():
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip())

    merged: list[str] = []
    labels: list[str] = []
    for block in blocks:
        if LABEL.match(block):
            labels.append(block)
        else:
            merged.append("\n".join([*labels, block]))
            labels = []
    if labels:
        merged.append("\n".join(labels))
    return [piece for block in merged for piece in _split_list(block)]


def _split_list(block: str) -> list[str]:
    """A list too long for one passage, in runs of whole items, so a citation can point at a
    step. Anything before the first item, such as a label, stays with the first run."""
    if estimate_tokens(block) <= MAX_TOKENS:
        return [block]
    pieces: list[list[str]] = [[]]
    fence = 0
    for line in block.split("\n"):
        item = not fence and LIST_ITEM.match(line)
        if item and estimate_tokens("\n".join(pieces[-1])) >= MAX_TOKENS / 2:
            pieces.append([])
        pieces[-1].append(line)
        fence = _fence(line, fence)
    return ["\n".join(piece) for piece in pieces]


def _parts(blocks: list[str]) -> list[list[str]]:
    """Blocks in groups of about the same size, none over MAX_TOKENS unless one block is."""
    sizes = [estimate_tokens(block) for block in blocks]
    total = sum(sizes)
    if total <= MAX_TOKENS:
        return [blocks]
    target = total / math.ceil(total / MAX_TOKENS)
    parts: list[list[str]] = [[]]
    size = 0
    for block, block_size in zip(blocks, sizes, strict=True):
        if parts[-1] and (size >= target or size + block_size > MAX_TOKENS):
            parts.append([])
            size = 0
        parts[-1].append(block)
        size += block_size
    return parts


def chunk_document(title: str, markdown: str, url: str, anchors: Iterable[tuple[str, str]] = ()) -> list[Passage]:
    passages: list[Passage] = []
    for section in _sections(title, markdown, anchors):
        blocks = _blocks(section.lines)
        if not blocks:
            continue  # a heading followed straight by a smaller heading
        heading_path = PATH_SEPARATOR.join(section.path)
        anchor_url = f"{url.split('#')[0]}#{section.anchor}" if section.anchor else None
        for part in _parts(blocks):
            text = heading_path + "\n\n" + "\n\n".join(part)
            passages.append(Passage(len(passages), heading_path, anchor_url, tuple(part), text, estimate_tokens(text)))
    return passages
