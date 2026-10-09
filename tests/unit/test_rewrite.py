"""Follow-up questions rewritten to stand alone (PRD 5.2, content spec 4.3), with recorded replies."""

import anthropic
import httpx2
import pytest

from citemark.retrieve.rewrite import MODEL, Rewritten, Turn, _request, rewrite

HISTORY = [
    Turn("user", "can other people see when i'm typing a message?"),
    Turn("assistant", "Yes. Zulip shows others when you're typing in direct messages and in smaller channels."),
]


@pytest.mark.anyio
async def test_a_first_message_is_searched_as_it_is_without_a_call(anthropic_client):
    # The recorded client fails any call it has no recording for, so this proves none was made
    assert await rewrite(anthropic_client, [], "how do i stop that?") == Rewritten("how do i stop that?", called=False)


@pytest.mark.anyio
async def test_a_follow_up_is_rewritten_to_stand_alone(anthropic_client):
    result = await rewrite(anthropic_client, HISTORY, "how do i turn that off?")
    assert result.called and result.input_tokens > 0 and result.output_tokens > 0
    assert "typing" in result.question.lower()


@pytest.mark.anyio
async def test_a_question_that_already_stands_alone_is_kept(anthropic_client):
    question = "How do I make the text bigger?"
    result = await rewrite(anthropic_client, HISTORY, question)
    assert result.called and result.question == question


@pytest.mark.anyio
async def test_a_failed_call_searches_the_message_as_it_is():
    transport = httpx2.MockTransport(lambda request: httpx2.Response(500, json={"type": "error"}))
    http_client = anthropic.DefaultAsyncHttpxClient(transport=transport)
    async with anthropic.AsyncAnthropic(api_key="unused", max_retries=0, http_client=http_client) as client:
        result = await rewrite(client, HISTORY, "how do i turn that off?")
    assert result == Rewritten("how do i turn that off?", called=False)


def test_only_the_last_three_exchanges_are_sent():
    history = [Turn("user" if n % 2 == 0 else "assistant", f"turn {n}") for n in range(10)]
    [message] = _request(history, "and then?")
    assert "turn 3" not in message["content"] and "turn 4" in message["content"]
    assert message["content"].endswith("<latest_message>\nand then?\n</latest_message>")
    assert MODEL == "claude-haiku-4-5"  # PRD 5.2
