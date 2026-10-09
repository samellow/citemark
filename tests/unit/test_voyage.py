"""Voyage embeddings through its REST API (PRD 3): the request, retries, errors, and one recorded call."""

import base64
import json
import math
import struct

import httpx2
import pytest

from citemark.embed import EmbedError
from citemark.embed.voyage import MAX_BATCH, VoyageEmbedder, VoyageReranker

# From Zulip's help center as saved on 2026-10-06 (fixtures/zulip/text/)
STAR = (
    "Star a message \u203a Star a message\n\n"
    "**Desktop/Web:**\n1. Hover over a message to reveal three icons on the right.\n2. Click the **star** icon.\n\n"
    "**Tip:** You can unstar a message using the same instructions used to star it."
)
DELETE = (
    "Delete a message \u203a Delete a message completely\n\n"
    "In some cases, such as when a message accidentally shares secret information, or contains spam or abuse, "
    "it makes sense to delete a message completely."
)


def encoded(values: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(values)}f", *values)).decode()


def reply(count: int, size: int = 1024) -> httpx2.Response:
    data = [{"object": "embedding", "embedding": encoded([0.5] * size), "index": i} for i in reversed(range(count))]
    return httpx2.Response(200, json={"object": "list", "data": data, "usage": {"total_tokens": 7 * count}})


class Waits:
    def __init__(self) -> None:
        self.seconds: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


def embedder_answering(*answers: httpx2.Response, seen: list | None = None, waits: Waits | None = None):
    queue = list(answers)

    def handle(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        return queue.pop(0)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
    return client, VoyageEmbedder("voyage-key", client, sleep=waits or Waits())


@pytest.mark.anyio
async def test_the_request_asks_for_voyage_4_at_1024_dimensions():
    seen: list[httpx2.Request] = []
    client, embedder = embedder_answering(reply(2), reply(1), seen=seen)
    async with client:
        documents = await embedder.embed_documents([STAR, DELETE])
        await embedder.embed_query("how do I keep track of an important message")
    body = json.loads(seen[0].content)
    assert body == {
        "input": [STAR, DELETE],
        "model": "voyage-4",
        "input_type": "document",
        "output_dimension": 1024,
        "encoding_format": "base64",
    }
    assert json.loads(seen[1].content)["input_type"] == "query"
    assert seen[0].headers["authorization"] == "Bearer voyage-key"
    assert [len(vector) for vector in documents.vectors] == [1024, 1024] and documents.tokens == 14


@pytest.mark.anyio
async def test_a_busy_service_is_tried_again_after_a_growing_wait():
    waits = Waits()
    busy = httpx2.Response(429)
    asked = httpx2.Response(429, headers={"retry-after": "30"})
    client, embedder = embedder_answering(busy, httpx2.Response(503), asked, reply(1), waits=waits)
    async with client:
        result = await embedder.embed_documents([STAR])
    assert len(result.vectors) == 1
    assert waits.seconds == [5, 2, 30]  # longer for a rate limit; as asked when Voyage says how long


@pytest.mark.anyio
async def test_it_gives_up_after_six_tries():
    waits = Waits()
    client, embedder = embedder_answering(*[httpx2.Response(429)] * 6, waits=waits)
    async with client:
        with pytest.raises(EmbedError, match="status 429 after 6 tries"):
            await embedder.embed_documents([STAR])
    assert waits.seconds == [5, 10, 20, 40, 60]  # past the next minute's limit before giving up


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (httpx2.Response(401), "refused the API key"),
        (httpx2.Response(400, json={"detail": "bad input"}), "status 400"),
        (reply(1, size=10), "40 bytes, not 4096"),
        (reply(2), "2 embeddings for 1 texts"),
    ],
)
async def test_a_failure_says_what_went_wrong(answer, message):
    client, embedder = embedder_answering(answer)
    async with client:
        with pytest.raises(EmbedError, match=message):
            await embedder.embed_documents([STAR])


@pytest.mark.anyio
async def test_a_call_holds_at_most_one_batch():
    client, embedder = embedder_answering()
    async with client:
        with pytest.raises(ValueError, match=f"at most {MAX_BATCH}"):
            await embedder.embed_documents(["text"] * (MAX_BATCH + 1))


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True)) / (math.hypot(*a) * math.hypot(*b))


@pytest.mark.anyio
async def test_voyage_puts_a_question_nearest_the_passage_that_answers_it(recorded_transport, recording):
    """A recorded reply from the real API: the vectors decode to unit length, and a question about
    keeping track of a message lands nearer the starring passage than the deleting one."""
    from citemark.settings import get_settings

    key = get_settings().voyage_api_key if recording else None
    if recording and key is None:
        pytest.fail("--record needs VOYAGE_API_KEY in .env or the environment.", pytrace=False)
    async with httpx2.AsyncClient(transport=recorded_transport) as client:
        embedder = VoyageEmbedder(key.get_secret_value() if key else "replayed", client)
        documents = await embedder.embed_documents([STAR, DELETE])
        query = await embedder.embed_query("how do I keep track of an important message")
    vectors = [*documents.vectors, *query.vectors]
    assert all(abs(math.hypot(*vector) - 1) < 0.01 for vector in vectors)
    star, delete = (cosine(query.vectors[0], vector) for vector in documents.vectors)
    assert star > delete
    assert documents.tokens > 0


def ranked(*pairs: tuple[int, float], tokens: int = 40) -> httpx2.Response:
    data = [{"index": index, "relevance_score": score} for index, score in pairs]
    body = {"object": "list", "data": data, "model": "rerank-3", "usage": {"total_tokens": tokens}}
    return httpx2.Response(200, json=body)


def reranker_answering(*answers: httpx2.Response, seen: list | None = None):
    queue = list(answers)

    def handle(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        return queue.pop(0)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
    return client, VoyageReranker("voyage-key", client, sleep=Waits())


@pytest.mark.anyio
async def test_the_reranker_asks_for_rerank_3_and_returns_the_best_first():
    seen: list[httpx2.Request] = []
    client, reranker = reranker_answering(ranked((1, 0.2), (0, 0.9)), seen=seen)
    async with client:
        ranking = await reranker.rerank("how do I keep track of a message", [STAR, DELETE, "a third passage"], 2)
    assert json.loads(seen[0].content) == {
        "query": "how do I keep track of a message",
        "documents": [STAR, DELETE, "a third passage"],
        "model": "rerank-3",
        "top_k": 2,
    }
    assert ranking.results == [(0, 0.9), (1, 0.2)] and ranking.tokens == 40


@pytest.mark.anyio
async def test_a_reranking_that_names_a_passage_never_sent_is_refused():
    client, reranker = reranker_answering(ranked((0, 0.9), (7, 0.5)))
    async with client:
        with pytest.raises(EmbedError, match="named passages that weren't sent"):
            await reranker.rerank("question", [STAR, DELETE], 2)


@pytest.mark.anyio
async def test_no_passages_means_no_call():
    client, reranker = reranker_answering()
    async with client:
        assert (await reranker.rerank("question", [], 5)).results == []


@pytest.mark.anyio
async def test_rerank_3_puts_the_passage_that_answers_first(recorded_transport, recording):
    """A recorded reply from the real API."""
    from citemark.settings import get_settings

    key = get_settings().voyage_api_key if recording else None
    async with httpx2.AsyncClient(transport=recorded_transport) as client:
        reranker = VoyageReranker(key.get_secret_value() if key else "replayed", client)
        ranking = await reranker.rerank("how do I keep track of an important message", [DELETE, STAR], 2)
    assert [index for index, _ in ranking.results] == [1, 0]
    assert ranking.results[0][1] > ranking.results[1][1] and ranking.tokens > 0
