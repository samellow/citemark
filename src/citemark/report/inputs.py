"""What a report is built from, besides the runs: a YAML file you write (PRD 5.5).

    kind: audit                  # audit, build, monthly or demo
    client: Acme Chat            # not on a demo report, which has no client
    client_questions: true       # not on a demo: the questions are the client's, and it reviewed the answers
    test_set: ../test-sets/acme-v1.yaml   # the frozen file, relative to this one
    decision: 0192f7c0-…         # the decision run the verdict is on, or any of its runs
    compare: [0192f7d1-…]        # other decision runs, side by side
    traced: Q017                 # the question traced step by step; a default is chosen if left out
    judge_check:
      run: 0192f6a0-…            # a run whose every judged answer you graded
      rechecks: [0192f7e2-…]     # runs re-checked on their 10-answer sample
    abuse: 0192f8a3-…            # the abuse set's decision run, in ABUSE_DATABASE_URL
    fix_plan:                    # your estimates, never computed: one per group with failures
      retrieval_miss: {hours: 4}
      doc_gap: {articles: 2}

`client_questions` is yours to confirm, since the method says so and nothing in the runs could
show it: the questions are ones the client's customers asked, and the client reviewed the expected
answers (content spec 5.5, `method.authorship.client`).

Every estimate is a whole number of at least 1. The build refuses one missing for a group that has
failures, and one given for a group that has none, so a plan copied from another report can't
pass unnoticed.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from citemark.db.models import FAILURE_TYPES

DOC_GAP = "doc_gap"  # the client's group: a failure on a question marked doc_gap (PRD 5.4)
GROUPS = (*FAILURE_TYPES, DOC_GAP)
MAX_COMPARED = 6  # the demo's five setups, and the run without reranking it improved on

Group = Literal[
    "answered_should_decline", "declined_answerable", "retrieval_miss", "wrong_citation", "wrong_answer", "doc_gap"
]


class InputsError(Exception):
    """The report's file can't be used. The message is one plain sentence."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Estimate(_Strict):
    hours: int | None = Field(None, ge=1)
    articles: int | None = Field(None, ge=1)


class JudgeCheck(_Strict):
    run: uuid.UUID
    rechecks: list[uuid.UUID] = []


class ReportFile(_Strict):
    kind: Literal["audit", "build", "monthly", "demo"]
    client: str | None = Field(None, min_length=1)
    client_questions: bool | None = None
    test_set: Path
    decision: uuid.UUID
    compare: list[uuid.UUID] = Field([], max_length=MAX_COMPARED - 1)
    traced: str | None = Field(None, pattern=r"^Q\d{3}$")
    judge_check: JudgeCheck
    abuse: uuid.UUID | None = None
    fix_plan: dict[Group, Estimate] = {}

    @model_validator(mode="after")
    def _consistent(self) -> ReportFile:
        if self.kind == "demo" and self.client is not None:
            raise ValueError("a demo report has no client, so leave client out")
        if self.kind != "demo" and self.client is None:
            raise ValueError(f"this kind of report ({self.kind}) needs the client's name")
        if self.client is not None and any(ord(char) < 32 or ord(char) == 127 for char in self.client):
            raise ValueError("the client's name has a control character in it")
        if self.kind == "demo" and self.client_questions is not None:
            raise ValueError("a demo's questions were drafted for it, so leave client_questions out")
        if self.kind != "demo" and self.client_questions is not True:
            raise ValueError(
                "the method will say the questions are ones the client's customers asked, and that the client "
                "reviewed the expected answers. If that's so, say client_questions: true"
            )
        for group, estimate in self.fix_plan.items():
            wanted = "articles" if group == DOC_GAP else "hours"
            given = {name for name in ("hours", "articles") if getattr(estimate, name) is not None}
            if given != {wanted}:
                raise ValueError(f"fix_plan.{group} takes {wanted}, and only {wanted}")
        return self


def load(path: Path) -> ReportFile:
    """The report's file, with its test set's path made relative to where it is."""
    try:
        found = ReportFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except OSError as exc:
        raise InputsError(f"{path} can't be read: {exc.strerror or exc}.") from exc
    except yaml.YAMLError as exc:
        raise InputsError(f"{path} isn't valid YAML: {exc}") from exc
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in error['loc']) or 'the file'}: {error['msg']}" for error in exc.errors()
        )
        raise InputsError(f"{path} isn't a report's file. {problems}.") from exc
    return found.model_copy(update={"test_set": (path.parent / found.test_set).resolve()})
