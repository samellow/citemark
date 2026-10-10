"""What the report's templates lay out (PRD 8.1): every word and number already decided.

`report.data.gather` fills these from the database, and the templates only place them, so a
template holds no text of its own (UI kit 2, rule 6) and a test can check the content without
drawing it. A `**bold**` stretch in a sentence is drawn bold.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Header:
    title: str
    prepared_by: str
    for_line: str  # the client, or the demo's unofficial label
    questions: str
    date: str
    model: str


@dataclass(frozen=True)
class Verdict:
    state: str  # pass, not_pass or baseline
    sentence: str  # starts with its **bold** word


@dataclass(frozen=True)
class MeasureRow:
    key: str
    name: str
    definition: str | None
    count: str | None  # "37 of 40 (92%)", or the cost line
    target: str | None
    state: str | None  # pass, warn or fail, from the exact value
    spread: str | None  # "3 runs: 35 to 37", as the range is written
    missing: str | None  # why there's no count
    link: str | None  # to the questions that failed it


@dataclass(frozen=True)
class Looked:
    title: str
    url: str | None  # unlinked when it isn't a web address, such as an uploaded file's
    expected: bool  # one of the sections the answer is in


@dataclass(frozen=True)
class Quote:
    marker: int
    id: str
    label: str  # "Source 1", the marker's name
    text: str  # copied by the API, word for word
    title: str
    url: str | None


@dataclass(frozen=True)
class Stretch:
    text: str
    markers: tuple[Quote, ...]  # the quotes this stretch rests on


@dataclass(frozen=True)
class Expected:
    section: str
    url: str | None
    quote: str


@dataclass(frozen=True)
class Record:
    """The five steps of one answer (EvidenceRecord). `id` prefixes every id inside it, so the
    traced question and its own entry in the list can share a page."""

    id: str
    question_id: str
    run: int
    question: str
    full_context: bool
    looked: tuple[Looked, ...]
    missed: bool  # a retrieval miss: the visible break at step 2
    looked_note: str | None  # why there's no list at step 2
    quotes: tuple[Quote, ...]
    quote_note: str | None  # why there's no quote at step 3
    clarify_question: str | None
    options: tuple[str, ...]
    chosen: str | None
    answer: tuple[Stretch, ...]
    gap_line: str | None
    passed: bool
    went_wrong: str | None  # "Went wrong at step 4."
    step: int | None  # the step it went wrong at
    expected_answer: tuple[str, ...]
    expected_sources: tuple[Expected, ...]


@dataclass(frozen=True)
class Entry:
    """One question in the list (QuestionEntry): failed ones open, passed ones folded."""

    record: Record
    runs_line: str | None  # "Failed in 1 run of 3. Shown: run 2."
    failed_measures: tuple[str, ...]  # in any run, for the filter


@dataclass(frozen=True)
class FixGroup:
    key: str
    title: str
    what: str
    count: str
    owner: str
    questions: tuple[str, ...]


@dataclass(frozen=True)
class FixPlan:
    heading: str
    groups: tuple[FixGroup, ...]
    none: str | None


@dataclass(frozen=True)
class Column:
    model: str
    mode: str
    date: str
    cells: dict[str, str]  # a measure's key: what the column shows


@dataclass(frozen=True)
class Comparison:
    rows: tuple[tuple[str, str], ...]  # a measure's key and name
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class Method:
    paragraphs: tuple[str, ...]
    setups: tuple[str, ...]


@dataclass(frozen=True)
class Report:
    kind: str
    lang: str
    labels: dict[str, str]
    header: Header
    verdict: Verdict
    measures: tuple[MeasureRow, ...]
    trace: Record
    fix_plan: FixPlan
    failed: tuple[Entry, ...]
    passed: tuple[Entry, ...]
    folded: str  # "38 questions passed. Show them."
    filters: tuple[tuple[str, str], ...]  # the measures a question can be shown by
    comparison: Comparison | None
    method: Method
    pass_mark: str
    prepared: str
    footer: tuple[str, str, str]  # around the page number and the page count
    run_ids: tuple[uuid.UUID, ...]
    fix_estimates: dict[str, dict[str, int]]
