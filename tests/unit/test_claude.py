"""The Claude adapter (PRD 5.3): what it sends, and each outcome on recorded replies.

The passages come from 7 Zulip articles the frozen test set doesn't use, chunked as ingestion
chunks them. The questions are written for these tests only, on topics the frozen set doesn't
ask about. Re-recording calls the real API: `uv run pytest tests/unit/test_claude.py --record`.

Some shapes come only some of the time, such as text written before a decline. Those tests
check that their recording still shows the shape, and say so if a re-recording lost it.
"""

import json
import uuid
from pathlib import Path

import anthropic
import httpx2
import pytest

from citemark.answer import Reply
from citemark.answer.pipeline import offered_tools
from citemark.answer.rules import decide
from citemark.ingest.chunk import chunk_document
from citemark.models import (
    DECISION_TOOLS,
    AnswerRequest,
    CitationEvent,
    DecisionEvent,
    ModelCallFailed,
    Passage,
    TextEvent,
    Turn,
    UsageEvent,
)
from citemark.models.claude import ClaudeAnswerer
from citemark.models.registry import UnknownModel

ZULIP = Path(__file__).parents[2] / "fixtures" / "zulip" / "text"
RECORDINGS = Path(__file__).parents[1] / "recordings"
ARTICLES = {  # none of them used by the frozen test set
    "typing-notifications": "Typing notifications",
    "font-size": "Font size",
    "change-your-language": "Change your language",
    "custom-emoji": "Custom emoji",
    "email-notifications": "Email notifications",
    "topic-notifications": "Topic notifications",
    "keyboard-shortcuts": "Keyboard shortcuts",
}
HAIKU, SONNET, OPUS = "claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"
OFFLINE = anthropic.AsyncAnthropic(api_key="unused")  # building a request sends nothing


def _passages() -> dict[str, Passage]:
    found = {}
    for slug, title in ARTICLES.items():
        url = f"https://zulip.com/help/{slug}"
        for chunk in chunk_document(title, (ZULIP / f"{slug}.md").read_text(encoding="utf-8"), url):
            chunk_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{url}#{chunk.heading_path}")
            found[chunk.heading_path] = Passage(chunk_id, url, chunk.heading_path, chunk.blocks)
    return found


ALL = _passages()


def passages(*headings: str) -> tuple[Passage, ...]:
    """Passages by heading path, with " > " standing for the separator, as search might return them."""
    return tuple(ALL[heading.replace(" > ", " \u203a ")] for heading in headings)


TYPING = passages(
    "Typing notifications > Disable sending typing notifications",
    "Typing notifications > Disable seeing typing notifications",
    "Typing notifications",
    "Keyboard shortcuts > Composing messages",
    "Font size > Change font size",
)
EMAILS = passages(
    "Email notifications > Message notification emails",
    "Email notifications > New login emails > Disable new login emails",
    "Email notifications > Low-traffic newsletter > Managing your newsletter subscription",
    "Email notifications > New login emails",
    "Topic notifications > Configure notifications for followed topics",
)
EMOJI = passages(
    "Custom emoji > Add custom emoji",
    "Custom emoji",
    "Custom emoji > Change who can add custom emoji",
    "Custom emoji > Deactivate custom emoji",
    "Custom emoji > Add custom emoji > Bulk add emoji",
)
TYPING_QUESTION = "Can I stop people from seeing when I'm typing?"
PARTIAL_QUESTION = "How do I stop people seeing that I'm typing? And can I hide it from just one person?"
AMBIGUOUS = "How do I stop getting emails?"
OFF_TOPIC = "What's the capital of Australia?"


def answerer(client, model: str = HAIKU) -> ClaudeAnswerer:
    return ClaudeAnswerer(client, model, company="Zulip")


async def ask(bot: ClaudeAnswerer, request: AnswerRequest) -> tuple[list, Reply]:
    events = [event async for event in bot.stream(request)]
    return events, decide(events, passages=request.passages, offered=request.tools, company="Zulip")


def blocks_streamed(recording: Path) -> list[str]:
    """The types of the content blocks in a recorded stream, in order."""
    lines = json.loads(recording.read_text(encoding="utf-8"))["response"]["body"]
    events = [json.loads(line.removeprefix("data: ")) for line in lines if line.startswith("data: ")]
    return [event["content_block"]["type"] for event in events if event["type"] == "content_block_start"]


def text_came_first(events) -> bool:
    """Whether the first thing a visitor could see was text rather than a decision."""
    for event in events:
        if isinstance(event, TextEvent) and event.text.strip():
            return True
        if isinstance(event, DecisionEvent) and event.tool != "report_gap":
            return False
    return False


# --- What the adapter sends (no API calls) ---


def test_each_passage_is_a_search_result_with_citations_and_its_paragraphs_as_blocks():
    params = answerer(OFFLINE).request(AnswerRequest("hi", TYPING[:1]))
    [message] = params["messages"]
    result, question = message["content"]
    assert result == {
        "type": "search_result",
        "source": "https://zulip.com/help/typing-notifications",
        "title": "Typing notifications \u203a Disable sending typing notifications",
        "content": [{"type": "text", "text": block} for block in TYPING[0].blocks],
        "citations": {"enabled": True},
    }
    assert question == {"type": "text", "text": "hi"}


def test_the_system_prompt_names_the_company_and_is_cached_with_the_tools():
    params = ClaudeAnswerer(OFFLINE, HAIKU, company="Acme", bot_name="Ace").request(AnswerRequest("hi", ()))
    [system] = params["system"]
    assert system["text"].startswith("You are Ace, the AI assistant for Acme's help center.")
    assert system["cache_control"] == {"type": "ephemeral"} and "{" not in system["text"]
    assert [tool["name"] for tool in params["tools"]] == list(DECISION_TOOLS)
    assert "isn't about Acme's product" in params["tools"][0]["description"]


def test_the_bot_name_defaults_to_the_company_help():
    assert answerer(OFFLINE).system.startswith("You are Zulip Help,")


def test_search_mode_sends_the_last_six_turns_as_text_then_the_passages_with_the_question():
    history = tuple(Turn("user" if n % 2 == 0 else "assistant", f"turn {n}") for n in range(8))
    messages = answerer(OFFLINE).request(AnswerRequest("and now?", TYPING, history))["messages"]
    assert [m["content"][0]["text"] for m in messages[:-1]] == [f"turn {n}" for n in range(2, 8)]
    last = messages[-1]["content"]
    assert [block["type"] for block in last] == ["search_result"] * len(TYPING) + ["text"]
    assert not any("cache_control" in block for block in last)


def test_full_context_mode_puts_the_cached_help_center_first():
    history = (Turn("user", "how do i stop emails"), Turn("assistant", "Which one do you mean?", "clarify"))
    request = AnswerRequest("login ones", tuple(ALL.values()), history, full_context=True)
    first, answer, question = answerer(OFFLINE).request(request)["messages"]
    results = first["content"][: len(ALL)]
    assert all(block["type"] == "search_result" for block in results)
    assert results[-1]["cache_control"] == {"type": "ephemeral"}  # the same prefix for every question
    assert first["content"][len(ALL)] == {"type": "text", "text": "how do i stop emails"}
    assert answer["role"] == "assistant" and question["content"] == [{"type": "text", "text": "login ones"}]


def test_after_a_clarifying_question_the_tool_isnt_offered():
    history = (Turn("user", "how do i stop emails"), Turn("assistant", "Which one do you mean?", "clarify"))
    params = answerer(OFFLINE).request(AnswerRequest("all", EMAILS, history, offered_tools(history)))
    assert [tool["name"] for tool in params["tools"]] == ["decline", "report_gap", "small_talk"]


@pytest.mark.parametrize(("model", "settings"), [
    (HAIKU, {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}),
    (SONNET, {"output_config": {"effort": "low"}}),
    (OPUS, {"output_config": {"effort": "low"}}),
])  # fmt: skip
def test_each_answer_model_runs_at_low_effort_and_haiku_without_thinking(model, settings):
    params = answerer(OFFLINE, model).request(AnswerRequest("hi", ()))
    assert {key: params[key] for key in ("thinking", "output_config") if key in params} == settings


def test_a_model_that_isnt_an_answer_model_is_refused():
    with pytest.raises(UnknownModel, match="claude-haiku-4-5 isn't an answer model"):
        answerer(OFFLINE, "claude-haiku-4-5")


# --- Each outcome, on recorded replies ---


@pytest.mark.anyio
async def test_an_answer_cites_the_passage_it_comes_from(anthropic_client):
    events, reply = await ask(answerer(anthropic_client), AnswerRequest(TYPING_QUESTION, TYPING))
    assert reply.kind == "answer" and not reply.problems
    assert reply.sources[0].title == "Typing notifications \u203a Disable sending typing notifications"
    assert all(source.cited_text in "".join(TYPING[source.passage].blocks) for source in reply.sources)
    [usage] = [event for event in events if isinstance(event, UsageEvent)]
    assert usage.input_tokens > 0 and usage.output_tokens > 0


@pytest.mark.anyio
async def test_a_partial_answer_names_what_the_help_center_doesnt_say(anthropic_client):
    _, reply = await ask(answerer(anthropic_client), AnswerRequest(PARTIAL_QUESTION, TYPING))
    assert reply.kind == "partial" and reply.sources and reply.gap
    assert reply.gap_line == f"The help center doesn't say {reply.gap}."


@pytest.mark.anyio
async def test_a_gap_reported_first_gets_a_tool_result_and_the_answer_comes_in_a_second_call(anthropic_client):
    """PRD Q12, on Sonnet 5.5, which reported the gap before any cited text 6 times of 6 in T2.
    Here it wrote an uncited sentence first, then the gap, then the cited answer once given the
    tool result. The sentence stays, as uncited text in an answer does, as its own paragraph."""
    events, reply = await ask(answerer(anthropic_client, SONNET), AnswerRequest(PARTIAL_QUESTION, TYPING))
    calls = [event for event in events if isinstance(event, UsageEvent)]
    assert len(calls) == 2, "This recording no longer reports the gap first. Re-record it, or use another model."
    first_call = events[: events.index(calls[0])]
    assert calls[0].stop_reason == "tool_use" and not any(isinstance(e, CitationEvent) for e in first_call)
    assert [e.tool for e in first_call if isinstance(e, DecisionEvent)] == ["report_gap"]
    assert reply.kind == "partial" and reply.sources and reply.gap and not reply.swapped
    written_first = "".join(e.text for e in first_call if isinstance(e, TextEvent)).strip()
    assert reply.text.startswith(written_first + "\n\n")


@pytest.mark.anyio
async def test_an_ambiguous_question_gets_a_clarifying_question(anthropic_client):
    events, reply = await ask(answerer(anthropic_client), AnswerRequest(AMBIGUOUS, EMAILS))
    assert reply.kind == "clarify" and reply.text == "Which one do you mean?"
    assert 2 <= len(reply.clarify_options) <= 3
    assert reply.swapped == text_came_first(events)


@pytest.mark.anyio
async def test_a_question_the_passages_dont_answer_is_declined(anthropic_client):
    question = "How do I change my profile picture?"  # the passages are all about custom emoji
    events, reply = await ask(answerer(anthropic_client), AnswerRequest(question, EMOJI))
    assert reply.kind == "decline_not_covered" and reply.text == "The help center doesn't cover that."
    assert reply.swapped == text_came_first(events)


@pytest.mark.anyio
async def test_a_question_about_something_else_is_declined_as_off_topic(anthropic_client):
    events, reply = await ask(answerer(anthropic_client), AnswerRequest(OFF_TOPIC, TYPING))
    assert reply.kind == "decline_off_topic" and reply.text == "I can only answer questions about Zulip's product."
    assert reply.swapped == text_came_first(events)


@pytest.mark.anyio
async def test_a_late_decline_swaps_out_the_text_and_counts_it(anthropic_client):
    """Promise 2. Haiku 5.5 with thinking off wrote an apology before declining."""
    events, reply = await ask(answerer(anthropic_client), AnswerRequest(OFF_TOPIC, TYPING))
    assert text_came_first(events), "This recording no longer writes text before the decline. Re-record it."
    assert reply.kind == "decline_off_topic" and reply.swapped and not reply.segments


@pytest.mark.anyio
async def test_a_late_clarifying_question_swaps_out_the_text_and_counts_it(anthropic_client):
    """Promise 2, for clarifying questions too (PRD Q11). Haiku 5.5 explained itself first."""
    events, reply = await ask(answerer(anthropic_client), AnswerRequest(AMBIGUOUS, EMAILS))
    assert text_came_first(events), "This recording no longer writes text before the question. Re-record it."
    assert reply.kind == "clarify" and reply.swapped and reply.text == "Which one do you mean?"


def recording_for(model: str, question: str) -> Path:
    """The recorded reply to a first question on a model."""
    for path in sorted(RECORDINGS.glob("v1-messages-*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))["request"]["body"]
        [first, *later] = body["messages"]
        if body.get("model") == model and not later and first["content"][-1].get("text") == question:
            return path
    raise LookupError(f"No recording of {question!r} on {model}.")


def recorded_events(model: str, question: str) -> list[str]:
    """A recorded stream's server-sent events, as text."""
    return "\n".join(json.loads(recording_for(model, question).read_text())["response"]["body"]).split("\n\n")


def serving(stream: str) -> anthropic.AsyncAnthropic:
    """A client whose every call gets this stream, for the few shapes built rather than recorded."""
    transport = httpx2.MockTransport(
        lambda request: httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=stream.encode())
    )
    http_client = anthropic.DefaultAsyncHttpxClient(transport=transport)
    return anthropic.AsyncAnthropic(api_key="unused", max_retries=0, http_client=http_client)


@pytest.mark.anyio
async def test_uncited_text_with_no_decision_becomes_a_decline():
    """Promise 1: the safety net. CONSTRUCTED, not recorded: no model wrote uncited text alone on
    demand. Three tries each called a tool after the text ("Are you a real person or a bot?",
    "ok") or cited the passages ("What can you help me with?"). So this replays the real answer
    to TYPING_QUESTION with its citation events taken out."""
    kept = [event for event in recorded_events(HAIKU, TYPING_QUESTION) if '"citations_delta"' not in event]
    async with serving("\n\n".join(kept)) as client:
        events, reply = await ask(answerer(client), AnswerRequest(TYPING_QUESTION, TYPING))
    assert not [event for event in events if isinstance(event, (DecisionEvent, CitationEvent))]
    assert text_came_first(events)
    assert reply.kind == "decline_not_covered" and reply.swapped
    assert reply.text == "The help center doesn't cover that." and reply.problems == ("wrote text with no citations",)


@pytest.mark.anyio
async def test_a_call_that_fails_partway_still_reports_the_tokens_it_was_billed():
    """CONSTRUCTED: the real answer to TYPING_QUESTION, cut after its first text and ended with
    the overloaded error the API can send mid-stream."""
    events = recorded_events(HAIKU, TYPING_QUESTION)
    first_text = next(n for n, event in enumerate(events) if '"text_delta"' in event)
    error = 'event: error\ndata: {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}'
    seen = []
    async with serving("\n\n".join([*events[: first_text + 1], error, ""])) as client:
        with pytest.raises(ModelCallFailed, match="The call to claude-haiku-5-5 failed"):
            async for event in answerer(client).stream(AnswerRequest(TYPING_QUESTION, TYPING)):
                seen.append(event)
    usage = seen[-1]
    assert isinstance(seen[0], TextEvent) and isinstance(usage, UsageEvent) and usage.stop_reason is None
    assert usage.input_tokens > 0 and usage.cache_write_tokens + usage.cache_read_tokens > 0


@pytest.mark.anyio
async def test_thanks_gets_the_fixed_reply(anthropic_client):
    _, reply = await ask(answerer(anthropic_client), AnswerRequest("thanks, that's all I needed!", TYPING))
    assert reply.kind == "small_talk" and reply.text == "You're welcome. Ask another question any time."


@pytest.mark.anyio
async def test_a_second_clarifying_question_in_a_row_cant_happen(anthropic_client):
    """Promise 3: right after a clarifying question the tool isn't offered, so the follow-up
    gets an answer or a decline."""
    history = (
        Turn("user", "How do I stop getting emails?"),
        Turn(
            "assistant",
            "Which one do you mean? Message notification emails / New login emails / Newsletter",
            "clarify",
        ),
    )
    request = AnswerRequest("the other kind", EMAILS, history, offered_tools(history))
    bot = answerer(anthropic_client)
    assert "ask_clarifying_question" not in [tool["name"] for tool in bot.request(request)["tools"]]
    _, reply = await ask(bot, request)
    assert reply.kind != "clarify"


@pytest.mark.anyio
async def test_a_leading_empty_thinking_block_is_skipped(anthropic_client, recorded_transport):
    """Opus 5.5 can open with an empty thinking block: on the ambiguous and partial questions in
    T2, not on plain answers. The decision is read from the first block a visitor could see."""
    events, reply = await ask(answerer(anthropic_client, OPUS), AnswerRequest(AMBIGUOUS, EMAILS))
    [recording] = recorded_transport.used
    assert blocks_streamed(recording)[0] == "thinking", "This recording no longer opens with a thinking block."
    assert reply.kind == "clarify" and reply.swapped == text_came_first(events)
