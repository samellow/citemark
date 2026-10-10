"""The demo's published results (PRD 8.2): what the page shows from the test run, in one file.

The decision runs are made once (implementation plan 5.3) and their report is committed to
`demo/published/`. This file sits beside it and holds what the demo page takes from the same runs,
words and numbers already written, so the page shows them exactly as the report does:

- the verdict and the five measure counts, for the first screen
- the two recorded turns, copied from the run with their sources (content spec 6.3)
- the three suggested questions, each one that passed

`from_report` writes it from a built report, and refuses a turn or a suggestion whose question
didn't pass, since each must pass before it's shown.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from citemark import strings
from citemark.evals.scoring import MEASURES
from citemark.report.render import bold_part
from citemark.report.view import Report
from citemark.web.view import HeroMeasure, Turn

RECORDED = 2
SUGGESTED = 3


class PublishedError(ValueError):
    """The results file can't be read, or a report can't give one. The message is one plain sentence."""


@dataclass(frozen=True)
class Published:
    report: str  # the report's id, served at /reports/<id>
    total: int  # questions in the test set
    verdict_state: str  # pass or not_pass
    verdict_word: str  # "Pass" or "Not pass", as the report's verdict starts
    measures: tuple[HeroMeasure, ...]
    recorded: tuple[Turn, ...]
    suggestions: tuple[str, ...]

    def __post_init__(self) -> None:
        if [measure.key for measure in self.measures] != list(MEASURES):
            raise PublishedError(f"The results need the five measures in order: {', '.join(MEASURES)}.")
        if len(self.recorded) != RECORDED or len(self.suggestions) != SUGGESTED:
            raise PublishedError(f"The results need {RECORDED} recorded turns and {SUGGESTED} suggested questions.")
        if any(turn.record is None for turn in self.recorded):
            raise PublishedError("A recorded turn needs its evidence record.")


ADAPTER = TypeAdapter(Published)


def load(path: Path) -> Published:
    try:
        return ADAPTER.validate_json(path.read_bytes())
    except FileNotFoundError as exc:
        raise PublishedError(f"There's no results file at {path}.") from exc
    except ValidationError as exc:
        raise PublishedError(f"{path} isn't a results file: {exc.errors()[0]['msg']}.") from exc


def dump(published: Published, path: Path) -> None:
    path.write_text(json.dumps(asdict(published), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def from_report(
    report: Report, *, report_id: str, recorded: tuple[str, ...], suggestions: tuple[str, ...]
) -> Published:
    """The results a demo page shows, from the report built on the same runs. `recorded` and
    `suggestions` are question IDs, such as Q012."""
    entries = {entry.record.question_id: entry for entry in report.failed + report.passed}

    def passed(question_id: str):
        entry = entries.get(question_id)
        if entry is None:
            raise PublishedError(f"{question_id} isn't one of the report's questions.")
        if not entry.record.passed:
            raise PublishedError(f"{question_id} failed in the test run, so the demo can't show it.")
        return entry.record

    rows = {row.key: row for row in report.measures}
    measures = []
    for key in MEASURES:
        row = rows.get(key)
        if row is None or row.count is None or row.state is None:
            raise PublishedError(f"The report has no count for {key}, so the demo's first screen can't show it.")
        measures.append(
            HeroMeasure(
                key,
                strings.text("demo", f"hero.measure.{key}"),
                row.count,
                row.state,
                report.labels[f"state.{row.state}"],
            )
        )
    return Published(
        report=report_id,
        total=len(entries),
        verdict_state=report.verdict.state,
        verdict_word=bold_part(report.verdict.sentence).rstrip("."),
        measures=tuple(measures),
        recorded=tuple(Turn(record.question, record) for record in map(passed, recorded)),
        suggestions=tuple(passed(question_id).question for question_id in suggestions),
    )
