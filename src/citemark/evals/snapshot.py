"""A saved copy of a help center: its manifest and each article's extracted text.

Test-set checks run against the same copy the questions were written from, so
an expected source that doesn't exist is caught before the set is frozen.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
LABEL_LINE = re.compile(r"^\*\*[^*]+:\*\*$")  # "**Desktop/Web:**", "**Note:**"
_PLAIN_QUOTES = str.maketrans({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"'})


def normalize(text: str) -> str:
    """For comparing quotes and headings: no bold marks, plain quotes, single spaces, any case."""
    return " ".join(text.replace("**", "").translate(_PLAIN_QUOTES).split()).casefold()


@dataclass(frozen=True)
class Section:
    heading: str
    level: int
    text: str

    @property
    def first_paragraph(self) -> str:
        for block in re.split(r"\n\s*\n", self.text):
            block = block.strip()
            if block and not LABEL_LINE.match(block):
                return block
        return ""


@dataclass
class Article:
    url: str
    title: str
    text: str
    sections: list[Section] = field(default_factory=list)

    def sections_named(self, heading: str) -> list[Section]:
        """Every section with this heading. A title often repeats as the first section heading."""
        wanted = normalize(heading)
        return [s for s in self.sections if normalize(s.heading) == wanted]


def split_sections(title: str, text: str) -> list[Section]:
    """Each heading's section runs to the next heading at its level or above.

    The title section holds only the text before the first section heading.
    A page extracted without headings becomes one title section.
    """
    lines = text.splitlines()
    heads = [(i, len(m.group(1)), m.group(2)) for i, line in enumerate(lines) if (m := HEADING.match(line))]
    title_head = next(((i, h) for i, level, h in heads if level == 1), None)
    intro_start = title_head[0] + 1 if title_head else 0
    intro_end = next((i for i, level, _ in heads if level > 1), len(lines))
    sections = [Section(title_head[1] if title_head else title, 1, "\n".join(lines[intro_start:intro_end]).strip())]
    for n, (i, level, heading) in enumerate(heads):
        if level == 1:
            continue
        end = next((j for j, other, _ in heads[n + 1 :] if other <= level), len(lines))
        sections.append(Section(heading, level, "\n".join(lines[i + 1 : end]).strip()))
    return sections


class HelpCenterSnapshot:
    def __init__(self, directory: Path) -> None:
        manifest_file = directory / "manifest.json"
        self.manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        self.manifest_sha256 = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
        self.articles: dict[str, Article] = {}
        for page in self.manifest["pages"]:
            text = (directory / "text" / f"{page['slug']}.md").read_text(encoding="utf-8")
            title = page.get("title", "").split(" | ")[0].strip()
            self.articles[page["url"]] = Article(page["url"], title, text, split_sections(title, text))
        self._normalized = {url: normalize(article.text) for url, article in self.articles.items()}

    def article(self, url: str) -> Article | None:
        return self.articles.get(url) or self.articles.get(url.rstrip("/"))

    def search(self, term: str) -> list[str]:
        """URLs of the articles whose text contains the term, ignoring case."""
        wanted = normalize(term)
        return [url for url, text in self._normalized.items() if wanted in text]
