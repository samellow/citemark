"""Embeddings and reranking behind small interfaces, like the model layer (PRD 3). Voyage is
the one provider; a client who needs another adds a class with the same methods."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class EmbedError(Exception):
    """The embedding or reranking service failed. The message is one plain sentence."""


@dataclass(frozen=True)
class Embeddings:
    vectors: list[list[float]]
    tokens: int  # as the provider counted them, for the cost log


class Embedder(Protocol):
    model: str
    dimensions: int
    max_batch: int  # texts per call
    max_batch_tokens: int  # estimated tokens per call (citemark.ingest.chunk.estimate_tokens)

    async def embed_documents(self, texts: Sequence[str]) -> Embeddings: ...

    async def embed_query(self, text: str) -> Embeddings: ...


@dataclass(frozen=True)
class Ranking:
    results: list[tuple[int, float]]  # (index into the documents sent, relevance score), best first
    tokens: int  # as the provider counted them, for the cost log


class Reranker(Protocol):
    model: str

    async def rerank(self, query: str, documents: Sequence[str], top_k: int) -> Ranking: ...
