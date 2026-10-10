"""A sample report, for the gallery and the report's own tests: made-up Acme Chat content in every
part of the layout (UI kit 7, rule 8), with the real words from `report.json`.

No test run is behind it, and nothing here is a measurement: the gallery labels it a sample. The
report a run produces is assembled by `report.data.gather`, which has its own tests.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal

from citemark import strings
from citemark.ingest.chunk import PATH_SEPARATOR
from citemark.report import numbers
from citemark.report.data import LABELS, PAGE, PAGES, _cost_line, _count_text, _spread_text, t
from citemark.report.view import (
    Column,
    Comparison,
    Entry,
    Expected,
    FixGroup,
    FixPlan,
    Header,
    Looked,
    MeasureRow,
    Method,
    Quote,
    Record,
    Report,
    Stretch,
    Verdict,
)

HELP = "https://help.acme-chat.example/"
CLIENT = "Acme Chat"
BUILDER = "Casey Morgan"  # made up, like everything here
AGREED_BY = "Alex Rivera"
DATE = "Oct 30, 2026"
AGREED = "Oct 20, 2026"
MEASURED = {  # each measure's median, low, high, total and target
    "correct_answers": (35, 34, 36, 40, 90),
    "right_source": (37, 37, 37, 40, 90),
    "correct_declines": (10, 10, 10, 10, 95),
    "wrongly_declined": (2, 1, 2, 40, 5),
    "right_place": (37, 36, 38, 40, 95),
}


def _path(*headings: str) -> str:
    """A passage's article and section, joined as search keeps them."""
    return PATH_SEPARATOR.join(headings)


def _quote(prefix: str, marker: int, text: str, title: str, page: str) -> Quote:
    return Quote(marker, f"{prefix}-q{marker}", t("evidence.marker_a11y", n=marker), text, title, HELP + page)


def _record(prefix: str, question_id: str, question: str, **given) -> Record:
    blank = Record(
        id=prefix,
        question_id=question_id,
        run=1,
        question=question,
        full_context=False,
        looked=(),
        missed=False,
        looked_note=None,
        quotes=(),
        quote_note=None,
        clarify_question=None,
        options=(),
        chosen=None,
        answer=(),
        gap_line=None,
        passed=True,
        went_wrong=None,
        step=None,
        expected_answer=(),
        expected_sources=(),
    )
    return replace(blank, **given)


def _looked(*titles: tuple[str, str, bool]) -> tuple[Looked, ...]:
    return tuple(Looked(title, HELP + page, expected) for title, page, expected in titles)


def _archive(prefix: str) -> Record:
    """An answer that passed: the traced question."""
    quote = _quote(
        prefix,
        1,
        "Open the channel's menu, choose Archive channel, then confirm. An archived channel keeps its messages.",
        _path("Archive a channel", "Archive a channel"),
        "archive-a-channel",
    )
    return _record(
        prefix,
        "Q004",
        "How do I archive a channel I don't use any more?",
        looked=_looked(
            (_path("Archive a channel", "Archive a channel"), "archive-a-channel", True),
            (_path("Archive a channel", "Unarchive a channel"), "archive-a-channel", False),
            (_path("Channel settings", "Delete a channel"), "channel-settings", False),
            ("Leave a channel", "leave-a-channel", False),
            ("Mute a channel", "mute-a-channel", False),
        ),
        quotes=(quote,),
        answer=(
            Stretch("Archive it from the channel's menu:\n1. Open the channel's menu.\n2. Choose Archive channel.", ()),
            Stretch("\nIts messages are kept.", (quote,)),
        ),
        expected_answer=(
            "Open the channel's menu and choose Archive channel",
            "An archived channel keeps its messages",
        ),
        expected_sources=(Expected("Archive a channel", HELP + "archive-a-channel", "choose Archive channel"),),
    )


def _questions() -> tuple[tuple[Entry, ...], tuple[Entry, ...]]:
    missed_quote = _quote(
        "Q017", 1, "You can't change who can see a message after it's sent.", "Message privacy", "message-privacy"
    )
    missed = _record(
        "Q017",
        "Q017",
        "Can I hide a message from one person in a group chat? <script>alert(1)</script>",
        run=2,
        looked=_looked(
            ("Message privacy", "message-privacy", False),
            (_path("Group chats", "Start a group chat"), "group-chats", False),
            (_path("Group chats", "Leave a group chat"), "group-chats", False),
            ("Block a person", "block-a-person", False),
            (_path("Delete a message", "Delete for everyone"), "delete-a-message", False),
        ),
        missed=True,
        quotes=(missed_quote,),
        answer=(Stretch("You can't change who sees a message once it's sent.", (missed_quote,)),),
        gap_line=strings.text("widget", "partial.gap", gap="whether you can hide a message from one person"),
        passed=False,
        went_wrong=t("trace.went_wrong", step=2),
        step=2,
        expected_answer=("Everyone in a group chat sees its messages", "A message can't be hidden from one person"),
        expected_sources=(Expected("Who can see a message", HELP + "group-chats", "everyone in the group chat"),),
    )
    declined = _record(
        "Q023",
        "Q023",
        "How do I turn on read receipts?",
        looked=_looked(
            ("Read receipts", "read-receipts", True),
            (_path("Notifications", "Desktop notifications"), "notifications", False),
            ("Message status", "message-status", False),
        ),
        quote_note=t("trace.no_quote"),
        answer=(Stretch(strings.text("widget", "decline.not_covered"), ()),),
        passed=False,
        went_wrong=t("trace.went_wrong", step=4),
        step=4,
        expected_answer=("Settings, then Privacy, then turn on Send read receipts",),
        expected_sources=(Expected("Read receipts", HELP + "read-receipts", "Send read receipts"),),
    )
    not_covered = _record(
        "Q041",
        "Q041",
        "Can Acme Chat translate my messages?",
        looked=_looked(("Change your language", "change-your-language", False)),
        quote_note=t("trace.decline_step3"),
        answer=(Stretch(strings.text("widget", "decline.not_covered"), ()),),
    )
    chosen_quote = _quote(
        "Q030",
        1,
        "Turn off email notifications under Settings, then Notifications.",
        _path("Notifications", "Email"),
        "email",
    )
    clarified = _record(
        "Q030",
        "Q030",
        "How do I stop the emails?",
        looked=_looked((_path("Notifications", "Email"), "email", True)),
        quotes=(chosen_quote,),
        clarify_question=strings.text("widget", "clarify.question"),
        options=("Notification emails", "Weekly digest", "Login alerts"),
        chosen=t("evidence.chosen", option="Notification emails"),
        answer=(Stretch("Turn them off in Settings, then Notifications.", (chosen_quote,)),),
        expected_answer=("Settings, then Notifications, then turn off email notifications",),
        expected_sources=(Expected("Email", HELP + "email", "Turn off email notifications"),),
    )
    failed = (
        Entry(missed, t("questions.failed_runs", failed=2, run=2), ("correct_answers", "right_place")),
        Entry(declined, t("questions.failed_runs", failed=1, run=1), ("correct_answers", "wrongly_declined")),
    )
    passed = (Entry(_archive("Q004"), None, ()), Entry(clarified, None, ()), Entry(not_covered, None, ()))
    return failed, passed


def _measures() -> tuple[tuple[MeasureRow, ...], int]:
    rows, met = [], 0
    for name, (median, low, high, total, target) in MEASURED.items():
        lower = name == "wrongly_declined"
        state = numbers.state(median, total, target, lower_is_better=lower)
        met += state == "pass"
        rows.append(
            MeasureRow(
                name,
                t(f"measure.{name}.name"),
                t(f"measure.{name}.definition"),
                _count_text(name, median, total),
                t("target.at_most" if lower else "target.at_least", target=target),
                state,
                _spread_text(low, high),
                None,
                f"#show-{name}" if name in ("correct_answers", "right_place", "wrongly_declined") else None,
            )
        )
    name = "time_to_first_word"
    rows.append(MeasureRow(name, t(f"measure.{name}.name"), None, None, None, None, None, t("not_measured"), None))
    cost = _cost_line(Decimal("0.0031"))
    rows.append(MeasureRow("cost", t("measure.cost.name"), None, cost, None, None, None, None, None))
    return tuple(rows), met


def _comparison() -> Comparison:
    columns = []
    for model, mode, cost in (
        ("Claude Haiku 5.5", t("compare.mode.retrieval"), Decimal("0.0031")),
        ("Claude Sonnet 5.5", t("compare.mode.full_context"), Decimal("0.0412")),
    ):
        cells = {}
        for name, (median, low, high, total, _target) in MEASURED.items():
            searched = mode == t("compare.mode.retrieval")
            measured = f"{_count_text(name, median, total)} · {_spread_text(low, high)}"
            cells[name] = measured if searched or name != "right_place" else t("compare.not_measured")
        cells["cost"] = _cost_line(cost)
        columns.append(Column(model, mode, DATE, cells))
    return Comparison(tuple((name, t(f"measure.{name}.name")) for name in (*MEASURED, "cost")), tuple(columns))


def _method(runs: list[uuid.UUID]) -> Method:
    return Method(
        (
            t(
                "method.questions",
                total=50,
                answerable=32,
                partial=5,
                ambiguous=3,
                should_decline=10,
                frozen_date="Oct 8, 2026",
                version=1,
                fingerprint="0a1b2c3d",
            ),
            t("method.authorship.client", client=CLIENT, builder_name=BUILDER),
            t("method.grading", judge_model="Claude Opus 5.5", builder_name=BUILDER, graded=40, agreed=38),
            t(
                "method.grading_recheck",
                builder_name=BUILDER,
                rechecked=10,
                recheck_models="Claude Sonnet 5.5",
                re_agreed=9,
            ),
            t("method.grading_queue", builder_name=BUILDER, queued=3),
            t("method.quotes"),
            t("method.abuse_not_measured"),
            t("method.runs"),
            t("method.cost", price_date=DATE),
        ),
        (
            t(
                "method.setup",
                setup=f"Claude Haiku 5.5 · {t('compare.mode.retrieval')}",
                prompt_version="answer.v1",
                commit="0123456789ab",
                run_ids=t("list.and", first=f"{runs[0]}, {runs[1]}", last=str(runs[2])),
            ),
        ),
    )


def report() -> Report:
    """The sample: an audit that missed its pass mark, with two failures and two setups compared."""
    measures, met = _measures()
    failed, passed = _questions()
    runs = [uuid.UUID(int=n) for n in range(1, 7)]
    fix = FixPlan(
        t("fix.heading.not_pass"),
        (
            FixGroup(
                "retrieval_miss",
                t("fix.group.retrieval_miss.title"),
                t("fix.group.retrieval_miss.what"),
                t("fix.count", count=1),
                t("fix.owner.builder", builder_name=BUILDER, hours=3),
                ("Q017",),
            ),
            FixGroup(
                "declined_answerable",
                t("fix.group.declined_answerable.title"),
                t("fix.group.declined_answerable.what"),
                t("fix.count", count=1),
                t("fix.owner.either", builder_name=BUILDER, client=CLIENT, hours=1),
                ("Q023",),
            ),
        ),
        None,
    )
    footer = t("print.footer", client=CLIENT, report_date=DATE, page=PAGE, pages=PAGES)
    before, rest = footer.split(PAGE)
    middle, after = rest.split(PAGES)
    return Report(
        kind="audit",
        lang="en",
        labels={key: t(key) for key in LABELS},
        header=Header(
            t("title"),
            t("header.prepared_by", builder_name=BUILDER),
            t("header.for", client=CLIENT),
            t("header.questions", total=50, version=1),
            t("header.date", report_date=DATE),
            t("header.model", model_name="Claude Haiku 5.5"),
        ),
        verdict=Verdict(
            "not_pass", t("verdict.not_pass", met=met, target_count=len(MEASURED), client=CLIENT, threshold_date=AGREED)
        ),
        measures=measures,
        trace=_archive("trace"),
        fix_plan=fix,
        failed=failed,
        passed=passed,
        folded=t("questions.folded_passes", count=len(passed)),
        filters=tuple(
            (name, t(f"measure.{name}.name")) for name in ("correct_answers", "wrongly_declined", "right_place")
        ),
        comparison=_comparison(),
        method=_method(runs),
        pass_mark=t("signed.agreed", threshold_agreed_by=AGREED_BY, builder_name=BUILDER, threshold_date=AGREED),
        prepared=t("signed.prepared", builder_name=BUILDER, report_date=DATE),
        footer=(before, middle, after),
        run_ids=tuple(runs),
        fix_estimates={"retrieval_miss": {"hours": 3}, "declined_answerable": {"hours": 1}},
    )
