"""The server's rules (PRD 5.3, Q11, Q12) on constructed event sequences, one rule per test.

The recorded replies in test_claude.py show real models producing these shapes. Here each rule
is checked alone, including shapes no model produced on demand.
"""

import uuid

import pytest

from citemark.answer import Reply
from citemark.answer.pipeline import offered_tools
from citemark.answer.rules import decide
from citemark.models import (
    DECISION_TOOLS,
    CitationEvent,
    DecisionEvent,
    Passage,
    TextEvent,
    Turn,
    UsageEvent,
)

PASSAGES = tuple(
    Passage(uuid.uuid4(), f"https://help.example.com/{n}", f"Article {n} \u203a Section", ("First.", "Second."))
    for n in range(5)
)
END = UsageEvent("claude-haiku-5-5", 1000, 50, 0, 0, "end_turn")
TOOL_STOP = UsageEvent("claude-haiku-5-5", 1000, 20, 0, 0, "tool_use")


def cite(block: int, passage: int, start: int = 0, end: int = 1) -> CitationEvent:
    return CitationEvent(block, passage, PASSAGES[passage].blocks[start], start, end)


def run(*events, offered=DECISION_TOOLS) -> Reply:
    return decide(events, passages=PASSAGES, offered=offered, company="Zulip")


def test_cited_text_is_an_answer_with_numbered_sources():
    reply = run(TextEvent(0, "\nTurn it off in "), cite(0, 2), TextEvent(0, "settings."), END)
    assert reply.kind == "answer" and reply.text == "Turn it off in settings."
    assert [(s.marker, s.chunk_id, s.cited_text) for s in reply.sources] == [(1, PASSAGES[2].chunk_id, "First.")]
    assert reply.segments[0].markers == (1,) and not reply.swapped and not reply.problems


def test_sources_are_numbered_by_first_appearance_one_per_passage_and_at_most_three():
    reply = run(
        TextEvent(0, "a"), cite(0, 3), cite(0, 3, 1, 2),
        TextEvent(1, "b"), cite(1, 0), cite(1, 3),
        TextEvent(2, "c"), cite(2, 1), cite(2, 4),
        END,
    )  # fmt: skip
    assert [(s.marker, s.passage) for s in reply.sources] == [(1, 3), (2, 0), (3, 1)]  # passage 4 isn't shown
    assert [segment.markers for segment in reply.segments] == [(1,), (2, 1), (3,)]
    assert reply.problems == ("cited more than 3 passages, so part of the answer shows no source",)


def test_blank_space_between_cited_blocks_keeps_the_paragraphs_apart():
    reply = run(
        TextEvent(0, "\n"),
        TextEvent(1, "First."),
        cite(1, 0),
        TextEvent(2, "\n\n"),
        TextEvent(3, "Then."),
        cite(3, 1),
        END,
    )
    assert reply.text == "First.\n\nThen."


def test_report_gap_after_the_answer_makes_it_partial_with_the_gap_line_last():
    reply = run(TextEvent(0, "Turn it off."), cite(0, 1), DecisionEvent("report_gap", {"missing": "per person."}))
    assert reply.kind == "partial" and reply.gap == "per person"
    assert reply.gap_line == "The help center doesn't say per person."
    assert reply.as_turn().text == "Turn it off.\n\nThe help center doesn't say per person."


def test_report_gap_first_then_the_answer_from_the_second_call_is_partial():
    """PRD Q12: the adapter returned a tool result and the model answered in a second call."""
    reply = run(
        DecisionEvent("report_gap", {"missing": "whether it works per person"}),
        TOOL_STOP,
        TextEvent(0, "Turn it off in settings."),
        cite(0, 1),
        END,
    )
    assert reply.kind == "partial" and reply.text == "Turn it off in settings." and len(reply.calls) == 2
    assert not reply.swapped


def test_a_second_calls_text_starts_a_new_paragraph():
    reply = run(
        TextEvent(0, "Two parts here."),
        DecisionEvent("report_gap", {"missing": "that"}),
        TOOL_STOP,
        TextEvent(1, "Turn it off "),
        cite(1, 1),
        TextEvent(2, "in settings."),
        END,
    )
    assert reply.text == "Two parts here.\n\nTurn it off in settings."
    assert [segment.text for segment in reply.segments] == ["Two parts here.", "\n\nTurn it off ", "in settings."]


@pytest.mark.parametrize(("reason", "text"), [
    ("not_covered", "The help center doesn't cover that."),
    ("off_topic", "I can only answer questions about Zulip's product."),
])  # fmt: skip
def test_a_decline_first_shows_the_locked_sentence(reason, text):
    reply = run(DecisionEvent("decline", {"reason": reason}), TOOL_STOP)
    assert reply.kind == f"decline_{reason}" and reply.text == text and not reply.swapped


def test_a_late_decline_swaps_out_the_text_and_counts_it():
    """Promise 2: text streamed before a decline is replaced by the decline, and counted."""
    reply = run(TextEvent(0, "Here's how to "), cite(0, 0), DecisionEvent("decline", {"reason": "not_covered"}))
    assert reply.kind == "decline_not_covered" and reply.swapped and not reply.sources


def test_a_clarifying_question_shows_the_locked_question_and_the_options():
    reply = run(DecisionEvent("ask_clarifying_question", {"options": ["Login emails", " Newsletter ", "login EMAILS"]}))
    assert reply.kind == "clarify" and reply.text == "Which one do you mean?"
    assert reply.clarify_options == ("Login emails", "Newsletter") and not reply.swapped


def test_a_late_clarifying_question_swaps_out_the_text_and_counts_it():
    """Promise 2, for clarifying questions too (PRD Q11)."""
    question = DecisionEvent("ask_clarifying_question", {"options": ["A", "B"]})
    reply = run(TextEvent(0, "There are a few kinds."), question)
    assert reply.kind == "clarify" and reply.swapped


def test_blank_text_before_a_decision_isnt_a_swap():
    reply = run(TextEvent(0, "\n\n"), DecisionEvent("decline", {"reason": "off_topic"}))
    assert reply.kind == "decline_off_topic" and not reply.swapped


@pytest.mark.parametrize(("kind", "text"), [
    ("greeting", "Hi, what can I help you find?"),
    ("thanks", "You're welcome. Ask another question any time."),
    ("goodbye", "Bye. The help center is here when you need it."),
])  # fmt: skip
def test_small_talk_shows_the_fixed_string_never_the_models_words(kind, text):
    reply = run(DecisionEvent("small_talk", {"kind": kind}), TextEvent(0, "Glad I could help with Zulip!"), END)
    assert reply.kind == "small_talk" and reply.text == text and not reply.segments


def test_uncited_text_becomes_a_decline():
    """Promise 1: an answer with no source is never shown."""
    reply = run(TextEvent(0, "Zulip probably lets you do that in settings."), END)
    assert reply.kind == "decline_not_covered" and reply.text == "The help center doesn't cover that."
    assert reply.swapped and reply.problems == ("wrote text with no citations",)


def test_a_gap_with_no_cited_answer_before_or_after_it_becomes_a_decline():
    reply = run(DecisionEvent("report_gap", {"missing": "that"}), TOOL_STOP, TextEvent(0, "Sorry."), END)
    assert reply.kind == "decline_not_covered" and reply.problems == ("reported a gap with no cited answer",)


def test_an_empty_reply_becomes_a_decline():
    assert run(END).kind == "decline_not_covered"


def test_a_tool_that_wasnt_offered_is_ignored():
    """Promise 3: after a clarifying question the tool is withdrawn, and a call to it anyway
    can't produce a second question in a row."""
    offered = tuple(tool for tool in DECISION_TOOLS if tool != "ask_clarifying_question")
    reply = run(DecisionEvent("ask_clarifying_question", {"options": ["A", "B"]}), offered=offered)
    assert reply.kind == "decline_not_covered"
    assert reply.problems[0] == "called ask_clarifying_question, which wasn't offered"


def test_the_clarifying_tool_is_withdrawn_right_after_a_clarifying_question():
    asked = [Turn("user", "how do i stop emails"), Turn("assistant", "Which one do you mean?", "clarify")]
    assert "ask_clarifying_question" not in offered_tools(asked)
    answered = [*asked, Turn("user", "login ones"), Turn("assistant", "Do this.", "answer")]
    assert offered_tools(answered) == DECISION_TOOLS
    assert offered_tools([]) == DECISION_TOOLS


def test_the_first_decision_wins_and_a_second_is_a_problem():
    reply = run(DecisionEvent("decline", {"reason": "off_topic"}), DecisionEvent("small_talk", {"kind": "thanks"}))
    assert reply.kind == "decline_off_topic" and reply.problems == ("called small_talk after decline",)


def test_a_reply_cut_off_by_the_token_limit_is_an_error_not_a_short_answer():
    reply = run(TextEvent(0, "Step one"), cite(0, 0), UsageEvent("claude-haiku-5-5", 1, 4096, 0, 0, "max_tokens"))
    assert reply.kind == "error" and reply.text == "" and not reply.sources


def test_a_whole_decision_stands_when_what_followed_was_cut_off_and_the_cut_is_logged():
    reply = run(
        DecisionEvent("decline", {"reason": "not_covered"}), UsageEvent("claude-haiku-5-5", 1, 4096, 0, 0, "max_tokens")
    )
    assert reply.kind == "decline_not_covered" and reply.problems == ("ran out of tokens before the reply ended",)


def test_a_refused_reply_is_declined_as_off_topic():
    assert run(UsageEvent("claude-opus-5-5", 1, 0, 0, 0, "refusal")).kind == "decline_off_topic"


@pytest.mark.parametrize(("event", "problem"), [
    (DecisionEvent("decline", {"reason": "rude"}), "declined with the reason 'rude'"),
    (
        DecisionEvent("ask_clarifying_question", {"options": ["Only one"]}),
        "asked a clarifying question with 1 usable options",
    ),
    (DecisionEvent("small_talk", {"kind": "weather"}), "made small talk of the kind 'weather'"),
])  # fmt: skip
def test_a_decision_the_visitor_cant_be_shown_falls_to_the_safety_net(event, problem):
    reply = run(event)
    assert reply.kind == "decline_not_covered" and problem in reply.problems


def test_more_than_three_options_keeps_the_first_three():
    reply = run(DecisionEvent("ask_clarifying_question", {"options": ["A", "B", "C", "D"]}))
    assert reply.clarify_options == ("A", "B", "C") and reply.problems == ("gave 4 options",)


def test_citations_to_passages_or_paragraphs_that_werent_sent_are_dropped():
    reply = run(
        TextEvent(0, "a"), CitationEvent(0, 9, "x", 0, 1), TextEvent(1, "b"), CitationEvent(1, 0, "x", 1, 5), END
    )
    assert reply.kind == "decline_not_covered"  # nothing valid was cited
    assert reply.problems[:2] == ("cited passage 9, which wasn't sent", "cited paragraphs 1-5 of a passage with fewer")


def test_a_gap_with_no_words_keeps_the_answer_partial_without_the_line():
    """Content spec 10: the answer is shown as partial without the gap line, and it's logged."""
    reply = run(TextEvent(0, "Turn it off."), cite(0, 0), DecisionEvent("report_gap", {"missing": " "}), END)
    assert reply.kind == "partial" and reply.gap is None and reply.gap_line is None
    assert reply.problems == ("reported a gap without naming it",)


def test_a_clarifying_reply_carries_its_options_into_the_history():
    reply = run(DecisionEvent("ask_clarifying_question", {"options": ["Login emails", "Newsletter"]}))
    assert reply.as_turn() == Turn("assistant", "Which one do you mean? Login emails / Newsletter", "clarify")
