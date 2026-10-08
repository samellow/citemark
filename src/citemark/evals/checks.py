"""Mechanical checks on a test set before it's frozen (content spec 4.5).

They catch what a reviewer misses by eye: an expected source or quote that isn't
in the help center, a "not covered" question the help center does cover, and a
question that copies its article's wording instead of a customer's.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from citemark.evals.snapshot import HelpCenterSnapshot, normalize
from citemark.evals.testset import Question, QuestionType, TestSetFile

# Small words the wording check ignores ("ignoring words like how, do, I and a")
STOPWORDS = frozenset(
    "a an and are at be can could did do does for from how i im in is it its me my of on or "
    "the there this that to what when where why with you your".split()
)
WORD = re.compile(r"[a-z0-9]+")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\+?\d[\d ().-]{7,}\d")
RUN_LENGTH = 3
MIN_DECLINE_TERMS = 3
QUOTE_WORDS = (5, 25)
NEEDS_ANSWER = {QuestionType.ANSWERABLE, QuestionType.PARTIAL, QuestionType.AMBIGUOUS}


@dataclass(frozen=True)
class Finding:
    check: str
    message: str
    question_id: str | None = None
    blocking: bool = True


def content_words(text: str) -> list[str]:
    plain = text.casefold().replace("'", "").replace(chr(0x2019), "")
    return [w for w in WORD.findall(plain) if w not in STOPWORDS]


def shared_run(question: str, source_text: str, length: int = RUN_LENGTH) -> str | None:
    """The first run of `length` words, small words ignored, that the question shares with the text."""
    q, s = content_words(question), content_words(source_text)
    runs = {tuple(s[i : i + length]) for i in range(len(s) - length + 1)}
    for i in range(len(q) - length + 1):
        if tuple(q[i : i + length]) in runs:
            return " ".join(q[i : i + length])
    return None


def check_fields(q: Question) -> list[Finding]:
    found: list[Finding] = []

    def bad(message: str) -> None:
        found.append(Finding("fields", message, q.id))

    if q.type in NEEDS_ANSWER:
        if not q.expected_answer:
            bad("needs at least one key fact in expected_answer")
        if not q.expected_sources:
            bad("needs at least one expected source")
    elif q.expected_answer or q.expected_sources:
        bad(f"a {q.type} question has no expected answer or sources")
    if (q.type == QuestionType.PARTIAL) != bool(q.uncovered_part):
        bad("uncovered_part is set on partial questions, and only on them")
    if (q.type == QuestionType.AMBIGUOUS) != bool(q.expected_option):
        bad("expected_option is set on ambiguous questions, and only on them")
    if q.type == QuestionType.DECLINE and len(q.not_covered_terms) < MIN_DECLINE_TERMS:
        bad(f"needs at least {MIN_DECLINE_TERMS} not_covered_terms")
    if q.type != QuestionType.DECLINE and q.not_covered_terms:
        bad("not_covered_terms is set only on decline questions")
    if EMAIL.search(q.question) or PHONE.search(q.question):
        found.append(Finding("personal_data", "the question contains an email address or phone number", q.id))
    return found


def check_sources(q: Question, snapshot: HelpCenterSnapshot) -> list[Finding]:
    found: list[Finding] = []
    for source in q.expected_sources:
        article = snapshot.article(source.url)
        if article is None:
            found.append(Finding("source", f"{source.url} isn't in the snapshot", q.id))
            continue
        sections = article.sections_named(source.section)
        if not sections:
            found.append(Finding("source", f'no section "{source.section}" in {source.url}', q.id))
            continue
        if not any(normalize(source.quote) in normalize(s.text) for s in sections):
            found.append(
                Finding("source", f'the quote isn\'t in "{source.section}" word for word: "{source.quote[:60]}"', q.id)
            )
        words = len(source.quote.split())
        if not QUOTE_WORDS[0] <= words <= QUOTE_WORDS[1]:
            found.append(
                Finding("source", f"the quote is {words} words; use {QUOTE_WORDS[0]} to {QUOTE_WORDS[1]}", q.id, False)
            )
    return found


def check_wording(q: Question, snapshot: HelpCenterSnapshot) -> list[Finding]:
    for source in q.expected_sources:
        article = snapshot.article(source.url)
        for section in article.sections_named(source.section) if article else []:
            for part, text in (("heading", section.heading), ("first paragraph", section.first_paragraph)):
                run = shared_run(q.question, text)
                if run:
                    advice = "kept, as its wording is locked" if q.locked else "rewrite it the way a customer would"
                    message = f'shares "{run}" with its section\'s {part}; {advice}'
                    return [Finding("wording", message, q.id, blocking=not q.locked)]
    return []


def check_not_covered(q: Question, snapshot: HelpCenterSnapshot) -> list[Finding]:
    found: list[Finding] = []
    for term in q.not_covered_terms:
        hits = snapshot.search(term)
        if hits:
            shown = ", ".join(url.rstrip("/").rsplit("/", 1)[-1] for url in hits[:3])
            noun = "article" if len(hits) == 1 else "articles"
            message = f'"{term}" appears in {len(hits)} {noun} ({shown}). Check whether the help center covers it.'
            found.append(Finding("not_covered", message, q.id))
    return found


def check_set(
    test_set: TestSetFile,
    expect: dict[str, int] | None = None,
    max_per_article: int | None = None,
) -> list[Finding]:
    found: list[Finding] = []
    for qid, n in Counter(q.id for q in test_set.questions).items():
        if n > 1:
            found.append(Finding("duplicate", f"{qid} is used {n} times"))
    for text, n in Counter(normalize(q.question) for q in test_set.questions).items():
        if n > 1:
            found.append(Finding("duplicate", f'"{text[:60]}" is asked {n} times'))
    if expect:
        counts = Counter(q.type.value for q in test_set.questions)
        for qtype in sorted(set(expect) | set(counts)):
            have, want = counts.get(qtype, 0), expect.get(qtype, 0)
            if have != want:
                found.append(Finding("composition", f"{have} {qtype} questions; expected {want}"))
    if max_per_article:
        per_article = Counter(url for q in test_set.questions for url in {s.url for s in q.expected_sources})
        for url, n in sorted(per_article.items()):
            if n > max_per_article:
                found.append(Finding("spread", f"{n} questions use {url}; at most {max_per_article}"))
    return found


def run_checks(
    test_set: TestSetFile,
    snapshot: HelpCenterSnapshot,
    expect: dict[str, int] | None = None,
    max_per_article: int | None = None,
) -> list[Finding]:
    found = check_set(test_set, expect, max_per_article)
    for q in test_set.questions:
        found += check_fields(q)
        found += check_sources(q, snapshot)
        found += check_wording(q, snapshot)
        found += check_not_covered(q, snapshot)
    return found


def review_counts(draft: TestSetFile, final: TestSetFile, snapshot: HelpCenterSnapshot) -> tuple[int, int]:
    """How many draft questions the wording check flagged, and how many the reviewer changed.

    A locked question's wording came from another document, not the draft, so
    it's never counted as flagged. A question counts as changed when anything
    but its notes differs from the draft, or when the draft didn't have it.
    """
    locked = {q.id for q in final.questions if q.locked}
    flagged = sum(1 for q in draft.questions if q.id not in locked and check_wording(q, snapshot))
    before = {q.id: _reviewed_fields(q) for q in draft.questions}
    edited = sum(1 for q in final.questions if before.get(q.id) != _reviewed_fields(q))
    return flagged, edited


def _reviewed_fields(q: Question) -> dict:
    return q.model_dump(exclude={"notes", "locked"})


def parse_expect(spec: str | None) -> dict[str, int] | None:
    """ "answerable=32,partial=5" becomes {"answerable": 32, "partial": 5}."""
    if not spec:
        return None
    pairs = (item.split("=", 1) for item in spec.split(",") if item.strip())
    expect = {name.strip(): int(count) for name, count in pairs}
    unknown = set(expect) - {t.value for t in QuestionType}
    if unknown:
        raise ValueError(f"unknown question types: {', '.join(sorted(unknown))}")
    return expect
