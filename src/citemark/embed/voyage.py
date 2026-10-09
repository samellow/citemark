"""Voyage AI (PRD 3): `voyage-4` embeddings at 1024 dimensions, and `rerank-3` reranking,
called through its REST API.

Through `httpx2` rather than Voyage's SDK, so the recorded replies in tests (QA plan 3.2)
work as they do for Claude, and the image doesn't carry the SDK's dependencies (implementation
plan T5). Vectors come back base64-encoded, about a quarter the size of a list of numbers.
"""

from __future__ import annotations

import base64
import math
import struct
from collections.abc import Sequence

import anyio
import httpx2

from citemark.db.models import EMBEDDING_DIMENSIONS
from citemark.embed import Embeddings, EmbedError, Ranking

API_URL = "https://api.voyageai.com/v1/embeddings"
RERANK_URL = "https://api.voyageai.com/v1/rerank"
MODEL = "voyage-4"
# PRD Q3 chose rerank-2.5; on 2026-10-09 Voyage listed it as legacy and rerank-3 as its "highest
# accuracy" model, at the same price ($0.05 per million tokens) and context (32K).
RERANK_MODEL = "rerank-3"
# Voyage takes up to 1,000 texts and 320K tokens a call for voyage-4. Calls are kept much
# smaller, so an account on a low rate limit isn't sent a call it can never accept: a 128-passage
# call was refused with 429 five times running on the first live crawl (2026-10-08). Small calls
# cost the same per token. The token cap is by our estimate (chars / 4), which counted 138 where
# Voyage counted 90, so a call holds about 5,000 of Voyage's tokens.
MAX_BATCH = 128
MAX_BATCH_TOKENS = 8_000
ATTEMPTS = 6
SERVER_WAITS = (1, 2, 4, 8, 16)  # seconds, when Voyage fails (5xx) or doesn't answer
RATE_LIMIT_WAITS = (5, 10, 20, 40, 60)  # when it's busy (429): about 2 minutes, past the next minute's limit
MAX_RETRY_AFTER = 120.0
TIMEOUT = 60.0


def _retry_after(value: str | None) -> float | None:
    try:
        return min(MAX_RETRY_AFTER, max(0.0, float(value))) if value else None
    except ValueError:
        return None


async def _post(client: httpx2.AsyncClient, url: str, body: dict, api_key: str, sleep) -> dict:
    """One call to Voyage, tried again while it's busy (429) or failing (5xx)."""
    headers = {"Authorization": f"Bearer {api_key}"}
    for attempt in range(1, ATTEMPTS + 1):
        last = attempt == ATTEMPTS
        try:
            response = await client.post(url, json=body, headers=headers, timeout=TIMEOUT)
        except httpx2.TransportError as exc:
            if last:
                raise EmbedError(f"Voyage didn't answer after {ATTEMPTS} tries ({type(exc).__name__}).") from exc
            await sleep(SERVER_WAITS[attempt - 1])
            continue
        if response.status_code == 429 or response.status_code >= 500:
            if last:
                raise EmbedError(f"Voyage answered with status {response.status_code} after {ATTEMPTS} tries.")
            waits = RATE_LIMIT_WAITS if response.status_code == 429 else SERVER_WAITS
            await sleep(_retry_after(response.headers.get("retry-after")) or waits[attempt - 1])
            continue
        if response.status_code in (401, 403):
            raise EmbedError("Voyage refused the API key. Check VOYAGE_API_KEY.")
        if response.status_code != 200:
            raise EmbedError(f"Voyage answered with status {response.status_code}: {response.text[:200]}")
        return response.json()
    raise AssertionError("unreachable")


class VoyageEmbedder:
    model = MODEL
    dimensions = EMBEDDING_DIMENSIONS
    max_batch = MAX_BATCH
    max_batch_tokens = MAX_BATCH_TOKENS

    def __init__(self, api_key: str, client: httpx2.AsyncClient, *, sleep=anyio.sleep) -> None:
        self._api_key, self._client, self._sleep = api_key, client, sleep

    async def embed_documents(self, texts: Sequence[str]) -> Embeddings:
        return await self._embed(texts, "document")

    async def embed_query(self, text: str) -> Embeddings:
        return await self._embed([text], "query")

    async def _embed(self, texts: Sequence[str], input_type: str) -> Embeddings:
        if not texts:
            return Embeddings([], 0)
        if len(texts) > MAX_BATCH:
            raise ValueError(f"at most {MAX_BATCH} texts a call")
        body = {
            "input": list(texts),
            "model": self.model,
            "input_type": input_type,
            "output_dimension": self.dimensions,
            "encoding_format": "base64",
        }
        return self._read(await _post(self._client, API_URL, body, self._api_key, self._sleep), len(texts))

    def _read(self, data: dict, count: int) -> Embeddings:
        items = sorted(data.get("data", []), key=lambda item: item["index"])
        if len(items) != count:
            raise EmbedError(f"Voyage returned {len(items)} embeddings for {count} texts.")
        vectors = [self._vector(item["embedding"]) for item in items]
        return Embeddings(vectors, int(data.get("usage", {}).get("total_tokens", 0)))

    def _vector(self, encoded: str | list[float]) -> list[float]:
        """A base64 vector is a NumPy float32 array, which is little-endian on the machines
        Voyage runs. A wrong guess would give the wrong size or non-numbers, so both are checked."""
        if isinstance(encoded, str):
            raw = base64.b64decode(encoded)
            if len(raw) != 4 * self.dimensions:
                raise EmbedError(f"Voyage returned an embedding of {len(raw)} bytes, not {4 * self.dimensions}.")
            vector = list(struct.unpack(f"<{self.dimensions}f", raw))
        else:
            vector = encoded
        if len(vector) != self.dimensions or not all(math.isfinite(value) for value in vector):
            raise EmbedError(f"Voyage returned an embedding that isn't {self.dimensions} numbers.")
        return vector


class VoyageReranker:
    """Reorders passages by how well each answers the question, and keeps the best `top_k`."""

    def __init__(self, api_key: str, client: httpx2.AsyncClient, *, model: str = RERANK_MODEL, sleep=anyio.sleep):
        self.model = model
        self._api_key, self._client, self._sleep = api_key, client, sleep

    async def rerank(self, query: str, documents: Sequence[str], top_k: int) -> Ranking:
        if not documents:
            return Ranking([], 0)
        body = {"query": query, "documents": list(documents), "model": self.model, "top_k": min(top_k, len(documents))}
        data = await _post(self._client, RERANK_URL, body, self._api_key, self._sleep)
        results = [(int(item["index"]), float(item["relevance_score"])) for item in data.get("data", [])]
        indexes = [index for index, _ in results]
        if len(set(indexes)) != len(indexes) or not all(0 <= index < len(documents) for index in indexes):
            raise EmbedError("Voyage's reranking named passages that weren't sent.")
        results.sort(key=lambda pair: -pair[1])
        return Ranking(results[:top_k], int(data.get("usage", {}).get("total_tokens", 0)))
