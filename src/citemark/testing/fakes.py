"""Stand-ins for paid services, for tests that need their shape but not their meaning."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from citemark.db.models import EMBEDDING_DIMENSIONS
from citemark.embed import Embeddings, EmbedError
from citemark.ingest.chunk import estimate_tokens


def fake_vector(text: str) -> list[float]:
    """The same text always gets the same vector, and different texts different ones."""
    return [(byte - 127.5) / 127.5 for byte in hashlib.shake_256(text.encode("utf-8")).digest(EMBEDDING_DIMENSIONS)]


class FakeEmbedder:
    """Vectors from each text's hash, for tests about what gets embedded rather than what the
    vectors mean. It counts its calls, so a test can check that an unchanged site costs none,
    and `fail_on` makes one call fail, as an outage would."""

    model = "fake"
    dimensions = EMBEDDING_DIMENSIONS

    def __init__(self, *, max_batch: int = 128, max_batch_tokens: int = 1_000_000, fail_on: int | None = None) -> None:
        self.max_batch, self.max_batch_tokens, self.fail_on = max_batch, max_batch_tokens, fail_on
        self.calls = 0
        self.texts: list[str] = []

    async def embed_documents(self, texts: Sequence[str]) -> Embeddings:
        self.calls += 1
        if self.calls == self.fail_on:
            raise EmbedError("The embedding service failed (a test outage).")
        self.texts += texts
        return Embeddings([fake_vector(text) for text in texts], sum(estimate_tokens(text) for text in texts))

    async def embed_query(self, text: str) -> Embeddings:
        return await self.embed_documents([text])
