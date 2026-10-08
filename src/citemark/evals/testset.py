"""Test-set files: the schema, loading, the fingerprint and the freeze lock.

A test set is a YAML file committed to the repo (PRD 4.3, 5.4). Freezing writes a
lock file next to it holding the SHA-256 of the YAML's bytes; from then on an
edited file is refused under the same version. The hash lives in its own file so
that writing it can't change what it fingerprints.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import Counter
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class TestSetError(Exception):
    """The file can't be read as a test set."""

    __test__ = False


class TestSetChanged(Exception):
    """The file changed after it was frozen."""

    __test__ = False


class AlreadyFrozen(Exception):
    """A frozen test set is never frozen again; changes go into the next version."""


class QuestionType(StrEnum):
    ANSWERABLE = "answerable"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    DECLINE = "decline"
    OFF_TOPIC = "off_topic"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedSource(_Strict):
    url: str
    section: str
    quote: str


class Question(_Strict):
    id: str = Field(pattern=r"^Q\d{3}$")
    type: QuestionType
    question: str = Field(min_length=1)
    expected_answer: list[str] = []
    expected_sources: list[ExpectedSource] = []
    uncovered_part: str | None = None
    expected_option: list[str] = []
    not_covered_terms: list[str] = []
    doc_gap: bool = False
    locked: bool = False  # wording fixed by another document, e.g. shown on the demo page
    notes: str = ""


class SnapshotInfo(_Strict):
    crawled_at: dt.date
    pages: int


class Drafting(_Strict):
    """How the questions were written. The review counts are worked out at the freeze and kept in the lock."""

    method: str


class TestSetFile(_Strict):
    __test__ = False

    name: str
    version: int
    snapshot: SnapshotInfo | None = None
    drafting: Drafting | None = None
    questions: list[Question]


def load(path: Path) -> TestSetFile:
    return _validate(path, _read(path))


def load_draft(path: Path) -> TestSetFile:
    """The AI draft a set was edited from, kept as it was written.

    Only its questions are compared, so its drafting block, which may follow an
    older shape, is left out.
    """
    data = _read(path)
    if isinstance(data, dict):
        data.pop("drafting", None)
    return _validate(path, data)


def _read(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TestSetError(f"{path} can't be read: {exc}") from exc


def _validate(path: Path, data: object) -> TestSetFile:
    try:
        return TestSetFile.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        raise TestSetError(f"{path} isn't a valid test set: {problems}") from exc


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lock_path(path: Path) -> Path:
    return path.with_suffix(".lock.json")


def read_lock(path: Path) -> dict | None:
    lock_file = lock_path(path)
    if not lock_file.exists():
        return None
    return json.loads(lock_file.read_text(encoding="utf-8"))


def verify_unchanged(path: Path) -> dict | None:
    """Return the lock if the set is frozen; raise if it changed since."""
    lock = read_lock(path)
    if lock and lock["sha256"] != fingerprint(path):
        raise TestSetChanged(
            f"{path.name} changed after it was frozen on {lock['frozen_at'][:10]}. "
            f"Put changes in version {lock['version'] + 1} instead."
        )
    return lock


def freeze(
    path: Path,
    test_set: TestSetFile,
    snapshot_manifest_sha256: str | None,
    now: dt.datetime | None = None,
    *,
    flagged: int | None = None,
    edited: int | None = None,
    draft_sha256: str | None = None,
) -> dict:
    """Write the lock. `flagged` and `edited` come from comparing the AI draft (checks.review_counts)."""
    if lock_path(path).exists():
        raise AlreadyFrozen(
            f"{path.name} is already frozen. Put changes in version {test_set.version + 1} instead."
        )
    counts = Counter(q.type.value for q in test_set.questions)
    lock = {
        "test_set": test_set.name,
        "version": test_set.version,
        "file": path.name,
        "sha256": fingerprint(path),
        "frozen_at": (now or dt.datetime.now(dt.UTC)).isoformat(timespec="seconds"),
        "questions": len(test_set.questions),
        "by_type": dict(sorted(counts.items())),
        "flagged": flagged,
        "edited": edited,
        "draft_sha256": draft_sha256,
        "snapshot_manifest_sha256": snapshot_manifest_sha256,
    }
    lock_path(path).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return lock
