"""The report's rules that need no database (PRD 8.1; content spec 5): counts, the fix plan's order
and owners, which answer a failed question shows, and which addresses become links."""

import uuid

from citemark.db.models import TestQuestion
from citemark.report import inputs
from citemark.report.build import css_string
from citemark.report.data import _Answer, _count_text, _fix_plan, _group_of, _link, t
from citemark.report.view import Verdict

RUN = uuid.UUID(int=1)


def test_a_count_rounds_against_the_bot_in_both_directions():
    assert _count_text("correct_answers", 2, 3) == "2 of 3 (66%)"  # 66.7%, down
    assert _count_text("wrongly_declined", 1, 3) == "1 of 3 (34%)"  # 33.3%, up: lower is better


def report_file(**plan) -> inputs.ReportFile:
    return inputs.ReportFile(
        kind="audit",
        client="Acme Chat",
        client_questions=True,
        test_set="acme-v1.yaml",
        decision=RUN,
        judge_check={"run": RUN},
        fix_plan=plan,
    )


def test_the_fix_plan_puts_the_biggest_group_first_then_keeps_the_failure_order():
    groups = {
        "doc_gap": ["Q009"],
        "wrong_answer": ["Q001", "Q002"],
        "answered_should_decline": ["Q005"],
        "retrieval_miss": ["Q003", "Q004"],
        "declined_answerable": ["Q006"],
    }
    plan = _fix_plan(
        report_file(
            doc_gap={"articles": 2},
            wrong_answer={"hours": 3},
            answered_should_decline={"hours": 1},
            retrieval_miss={"hours": 4},
            declined_answerable={"hours": 1},
        ),
        groups,
        Verdict("not_pass", ""),
        builder_name="Casey Morgan",
        client="Acme Chat",
    )
    order = [group.key for group in plan.groups]
    assert order == ["retrieval_miss", "wrong_answer", "answered_should_decline", "declined_answerable", "doc_gap"]
    owners = {group.key: group.owner for group in plan.groups}
    assert owners["doc_gap"] == "Fixed by Acme Chat · 2 articles to write"
    assert owners["declined_answerable"] == "Fixed by Casey Morgan or Acme Chat · about 1 hour"
    assert owners["retrieval_miss"] == "Fixed by Casey Morgan · about 4 hours"
    doc_gap = next(group for group in plan.groups if group.key == "doc_gap")
    assert doc_gap.what == t("fix.group.doc_gap.what", client="Acme Chat") and doc_gap.count == "1 question"
    assert plan.heading == t("fix.heading.not_pass") and plan.none is None


def answer(run: int, failure: str | None) -> _Answer:
    return _Answer(run, None, {}, failure)  # type: ignore[arg-type]


def test_a_question_that_failed_differently_is_grouped_by_the_first_failure_in_order():
    failing = [answer(1, "wrong_answer"), answer(2, "wrong_answer"), answer(3, "retrieval_miss")]
    group, shown = _group_of(TestQuestion(doc_gap=False), failing)
    assert (group, shown.run) == ("retrieval_miss", 3)
    group, shown = _group_of(TestQuestion(doc_gap=False), failing[:2])
    assert (group, shown.run) == ("wrong_answer", 1)


def test_a_failure_on_a_question_the_help_center_lacks_is_the_clients_to_fix():
    group, shown = _group_of(TestQuestion(doc_gap=True), [answer(2, "retrieval_miss")])
    assert (group, shown.run) == ("doc_gap", 2)


def test_only_a_web_address_becomes_a_link():
    assert _link("https://zulip.com/help/x") == "https://zulip.com/help/x"
    assert _link("http://example.com/") == "http://example.com/"
    assert _link("upload:guide.md") is None
    assert _link("javascript:alert(1)") is None


def test_a_css_string_holds_any_text():
    assert css_string('a"b\\c') == '"a\\"b\\\\c"'
    assert css_string("a\nb\rc\fd") == '"a\\A b\\D c\\C d"'
    assert css_string("</style>") == '"\\3C /style\\3E "'
