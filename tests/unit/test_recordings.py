"""Recorded replies and the network guard (QA plan 3.2, T5)."""

import re
import socket

import httpx2
import pytest

from citemark.testing.network import NetworkBlocked
from citemark.testing.recordings import MissingRecording, RecordingTransport, request_key

MODEL = "claude-haiku-5-5"
AS_THE_BOT_RUNS_IT = {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}  # PRD Q11
# From Zulip's help center as saved on 2026-10-06 (fixtures/zulip/text/star-a-message.md)
PASSAGE = {
    "type": "search_result",
    "source": "https://zulip.com/help/star-a-message",
    "title": "Star a message",
    "content": [
        {"type": "text", "text": text}
        for text in (
            "Starring messages is a good way to keep track of important messages, such as tasks you need to go "
            "back to or documents you reference often.",
            "Desktop/Web: Hover over a message to reveal three icons on the right. Click the star icon.",
            "Mobile: Press and hold a message until the long-press menu appears. Tap Star message.",
            "Tip: You can unstar a message using the same instructions used to star it.",
        )
    ],
    "citations": {"enabled": True},
}
QUESTION = {
    "model": MODEL,
    "max_tokens": 1024,
    "system": "Answer the customer's question using only the search results, and cite them.",
    "messages": [{"role": "user", "content": [PASSAGE, {"type": "text", "text": "How do I star a message?"}]}],
    **AS_THE_BOT_RUNS_IT,
}


@pytest.mark.anyio
async def test_a_recorded_reply_replays_with_its_citations(anthropic_client):
    message = await anthropic_client.messages.create(**QUESTION)
    cited = [citation for block in message.content if block.type == "text" for citation in block.citations or []]
    assert message.stop_reason == "end_turn"
    assert cited
    assert {citation.type for citation in cited} == {"search_result_location"}


@pytest.mark.anyio
async def test_a_recorded_stream_replays_event_by_event(anthropic_client):
    citation_deltas = 0
    async with anthropic_client.messages.stream(**QUESTION) as stream:
        async for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "citations_delta":
                citation_deltas += 1
        message = await stream.get_final_message()
    assert citation_deltas > 0
    assert message.stop_reason == "end_turn"


@pytest.mark.anyio
async def test_a_missing_recording_fails_and_names_the_command(recorded_transport, recording, request):
    if recording:
        pytest.skip("checks replaying")
    command = re.escape(f"Record it with: uv run pytest {request.node.nodeid} --record")
    async with httpx2.AsyncClient(transport=recorded_transport) as client:
        with pytest.raises(pytest.fail.Exception, match=command):
            await client.post("https://api.example.test/v1/nothing-recorded", json={"question": "?"})


@pytest.mark.anyio
async def test_a_recording_never_holds_headers_and_replays_the_same_reply(tmp_path):
    def live(request):
        return httpx2.Response(200, json={"answer": "Click the star."}, headers={"set-cookie": "session=1"})

    recorder = RecordingTransport(tmp_path, record=True, upstream=httpx2.MockTransport(live))
    async with httpx2.AsyncClient(transport=recorder) as client:
        recorded = await client.post(
            "https://api.example.test/v1/messages", json={"b": 2, "a": 1}, headers={"x-api-key": "sk-ant-secret"}
        )
    [saved] = tmp_path.glob("v1-messages-*.json")
    assert "sk-ant-secret" not in saved.read_text()
    assert "set-cookie" not in saved.read_text()

    # The same body with its keys in another order, and other headers, finds the same recording
    async with httpx2.AsyncClient(transport=RecordingTransport(tmp_path)) as client:
        replayed = await client.post(
            "https://api.example.test/v1/messages",
            content=b'{"a": 1, "b": 2}',
            headers={"content-type": "application/json", "x-api-key": "another"},
        )
        with pytest.raises(MissingRecording):
            await client.post("https://api.example.test/v1/messages", json={"a": 1, "b": 3})
    assert replayed.json() == recorded.json() == {"answer": "Click the star."}


def test_the_key_depends_on_the_method_url_and_body():
    url = "https://api.example.test/v1/messages"
    key, _ = request_key("POST", url, b'{"a": 1}')
    assert key == request_key("POST", url, b'{ "a":1 }')[0]
    assert key != request_key("POST", url, b'{"a": 2}')[0]
    assert key != request_key("POST", url + "?beta=true", b'{"a": 1}')[0]
    assert key != request_key("PUT", url, b'{"a": 1}')[0]


def test_tests_cant_reach_the_network(recording):
    if recording:
        pytest.skip("--record lets tests reach the real APIs")
    with pytest.raises(NetworkBlocked, match=re.escape("api.anthropic.com")):
        socket.getaddrinfo("api.anthropic.com", 443)
    with pytest.raises(NetworkBlocked, match=re.escape("192.0.2.1")):
        socket.create_connection(("192.0.2.1", 443), timeout=1)  # TEST-NET-1: documentation only, never routed
    socket.getaddrinfo("localhost", 5432)  # Postgres stays reachable
