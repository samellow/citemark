"""The report's file (PRD 5.5) and the pass mark's targets: what you write by hand, checked before
any run is read."""

import uuid
from typing import get_args

import pytest
import yaml

from citemark.evals import passmark
from citemark.report import inputs

RUN = str(uuid.UUID(int=1))
BASE = {
    "kind": "audit",
    "client": "Acme Chat",
    "client_questions": True,
    "test_set": "../test-sets/acme-v1.yaml",
    "decision": RUN,
    "judge_check": {"run": RUN},
}


def written(tmp_path, **changes):
    data = {**BASE, **changes}
    folder = tmp_path / "reports"
    folder.mkdir(exist_ok=True)
    path = folder / "acme.yaml"
    path.write_text(yaml.safe_dump({k: v for k, v in data.items() if v is not None}), encoding="utf-8")
    return path


def test_a_report_file_is_read_with_its_test_set_beside_it(tmp_path):
    found = inputs.load(written(tmp_path, fix_plan={"retrieval_miss": {"hours": 4}, "doc_gap": {"articles": 2}}))
    assert found.test_set == (tmp_path / "test-sets" / "acme-v1.yaml").resolve()
    assert found.fix_plan["retrieval_miss"].hours == 4 and found.fix_plan["doc_gap"].articles == 2


def test_the_groups_are_the_five_failure_types_and_the_doc_gap():
    assert set(get_args(inputs.Group)) == set(inputs.GROUPS)


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"client": None}, "needs the client's name"),
        ({"kind": "demo"}, "a demo report has no client"),
        ({"client_questions": None}, "say client_questions: true"),
        ({"client_questions": False}, "say client_questions: true"),
        ({"kind": "demo", "client": None}, "leave client_questions out"),
        ({"client": "Acme\rChat"}, "control character"),
        ({"kind": "invoice"}, "kind"),
        ({"fix_plan": {"retrieval_miss": {"articles": 2}}}, "takes hours"),
        ({"fix_plan": {"doc_gap": {"hours": 2}}}, "takes articles"),
        ({"fix_plan": {"retrieval_miss": {"hours": 0}}}, "greater than or equal to 1"),
        ({"fix_plan": {"retrieval_miss": {"hours": 1.5}}}, "integer"),
        ({"fix_plan": {"typo": {"hours": 1}}}, "fix_plan"),
        ({"traced": "17"}, "traced"),
        ({"surprise": 1}, "surprise"),
        ({"compare": [RUN] * 6}, "compare"),
        ({"judge_check": None}, "judge_check"),
    ],
)
def test_a_file_that_cant_be_used_is_refused_with_its_problem(tmp_path, changes, problem):
    with pytest.raises(inputs.InputsError, match=problem):
        inputs.load(written(tmp_path, **changes))


def test_a_demo_report_has_no_client(tmp_path):
    assert inputs.load(written(tmp_path, kind="demo", client=None, client_questions=None)).client is None


def test_a_missing_file_is_one_plain_sentence(tmp_path):
    with pytest.raises(inputs.InputsError, match="can't be read"):
        inputs.load(tmp_path / "nowhere.yaml")


# --- The pass mark's targets ---

ALL = "correct_answers=90,right_source=90,correct_declines=95,wrongly_declined=5,right_place=95"


def test_a_pass_mark_has_a_whole_percent_for_each_measure():
    assert passmark.parse(ALL) == {
        "correct_answers": 90,
        "right_source": 90,
        "correct_declines": 95,
        "wrongly_declined": 5,
        "right_place": 95,
    }
    assert passmark.parse(" " + ALL.replace(",", " , ") + ",") == passmark.parse(ALL)


@pytest.mark.parametrize(
    ("spec", "problem"),
    [
        (ALL.replace("right_place=95", ""), "Missing: right_place"),
        (ALL + ",correct_answers=80", "given twice"),
        (ALL.replace("correct_answers", "accuracy"), "isn't a measure"),
        (ALL.replace("=90,right_source", "=90.5,right_source"), "whole percent"),
        (ALL.replace("=95,wrongly", "=101,wrongly"), "whole percent"),
        (ALL.replace("=5,right", "=,right"), "not nothing"),
        (ALL.replace("=5,right", "=\u00b2,right"), "whole percent"),  # a digit to isdigit(), not to int()
    ],
)
def test_a_pass_mark_it_cant_use_is_refused(spec, problem):
    with pytest.raises(passmark.PassMarkError, match=problem):
        passmark.parse(spec)
