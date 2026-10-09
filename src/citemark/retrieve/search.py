"""Search mode (PRD 5.2): the question searched by meaning and by its words, the two lists
merged by reciprocal rank fusion, and the best few chosen by a reranker.

Only live passages are searched (`retired_at` is null). Search by meaning scans every one of
them, so it's exact and the same passages always give the same candidates (PRD Q15): with an
approximate HNSW index, which candidates came back depended on the index's state, such as the
dead entries a re-index leaves until vacuum. An exact scan of Zulip's 1,209 passages took 4.5 ms.
Every passage handed on keeps all three scores, so a wrong answer can be traced to the step
that lost the right passage.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import Chunk, Document, RetrievalHit
from citemark.embed import Embedder, Reranker
from citemark.retrieve import RetrievalConfig, RetrievalError
from citemark.retrieve.rrf import fuse

# websearch_to_tsquery joins a question's words with AND, so a question would only find passages
# holding every one of its words: "can I hide that I'm typing" finds nothing. Its parse is kept,
# so a quoted phrase stays a phrase, but the words are joined with OR, and ts_rank_cd puts the
# passages holding more of them, closer together, first. A query with a negation (-word) keeps
# its ANDs, since OR would turn "without this word" into "anything without this word".
BY_WORDS = text(
    """
    WITH parsed AS (SELECT websearch_to_tsquery('english', :query) AS strict),
         terms AS (
             SELECT CASE WHEN strict::text LIKE '%!%' THEN strict
                         ELSE replace(strict::text, ' & ', ' | ')::tsquery END AS query
             FROM parsed)
    SELECT chunk.id, ts_rank_cd(chunk.tsv, terms.query) AS score
    FROM chunk, terms
    WHERE chunk.retired_at IS NULL AND chunk.tsv @@ terms.query
    ORDER BY score DESC, chunk.heading_path, chunk.position, chunk.id
    LIMIT :limit
    """
)
# Ties in keyword score are broken by heading path and page position, not by ID alone. IDs made
# in the same millisecond end in random bits (UUIDv7), so an ID tie-break gave two runs on the
# same passages different candidate lists (found in T7, 1 test run in about 20).


@dataclass(frozen=True)
class Hit:
    chunk_id: uuid.UUID
    rank: int
    url: str  # the article's address
    title: str | None
    heading_path: str
    anchor_url: str | None
    blocks: list[str]
    text: str
    vector_score: float | None  # cosine similarity, if vector search found it
    keyword_score: float | None  # ts_rank_cd, if keyword search found it
    fused_score: float
    rerank_score: float | None  # None when reranking is off


@dataclass(frozen=True)
class Retrieval:
    query: str
    hits: list[Hit]
    embed_tokens: int
    rerank_tokens: int


async def _by_meaning(session: AsyncSession, vector: list[float], limit: int) -> list[tuple[uuid.UUID, float]]:
    distance = Chunk.embedding.cosine_distance(vector)
    rows = await session.execute(
        select(Chunk.id, distance).where(Chunk.retired_at.is_(None)).order_by(distance).limit(limit)
    )
    return [(chunk_id, 1.0 - float(found)) for chunk_id, found in rows]


async def _by_words(session: AsyncSession, query: str, limit: int) -> list[tuple[uuid.UUID, float]]:
    rows = await session.execute(BY_WORDS, {"query": query, "limit": limit})
    return [(chunk_id, float(score)) for chunk_id, score in rows]


async def _passages(session: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple]:
    rows = await session.execute(
        select(Chunk.id, Document.url, Document.title, Chunk.heading_path, Chunk.anchor_url, Chunk.blocks, Chunk.text)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.id.in_(ids))
    )
    return {row[0]: tuple(row[1:]) for row in rows}


async def retrieve(
    session: AsyncSession,
    query: str,
    *,
    embedder: Embedder,
    reranker: Reranker | None,
    config: RetrievalConfig,
) -> Retrieval:
    """The passages the model gets for a standalone question (rewritten first if it's a follow-up)."""
    query = " ".join(query.split())
    if config.rerank and (reranker is None or reranker.model != config.reranker):
        given = reranker.model if reranker else "none"
        raise RetrievalError(f"The settings ask for reranking with {config.reranker}, but the reranker is {given}.")
    if not query:
        return Retrieval(query, [], 0, 0)

    embedded = await embedder.embed_query(query)
    meaning = await _by_meaning(session, embedded.vectors[0], config.candidates)
    words = await _by_words(session, query, config.candidates)
    fused = fuse([[chunk_id for chunk_id, _ in meaning], [chunk_id for chunk_id, _ in words]], k=config.rrf_k)
    if not fused:
        return Retrieval(query, [], embedded.tokens, 0)

    passages = await _passages(session, [chunk_id for chunk_id, _ in fused])
    rerank_tokens = 0
    if config.rerank:
        assert reranker is not None
        ranking = await reranker.rerank(query, [passages[chunk_id][5] for chunk_id, _ in fused], config.top_k)
        chosen: list[tuple[int, float | None]] = list(ranking.results)
        rerank_tokens = ranking.tokens
    else:
        chosen = [(index, None) for index in range(min(config.top_k, len(fused)))]

    by_meaning, by_words = dict(meaning), dict(words)
    hits = []
    for rank, (index, rerank_score) in enumerate(chosen, 1):
        chunk_id, fused_score = fused[index]
        url, title, heading_path, anchor_url, blocks, passage_text = passages[chunk_id]
        hits.append(
            Hit(
                chunk_id=chunk_id,
                rank=rank,
                url=url,
                title=title,
                heading_path=heading_path,
                anchor_url=anchor_url,
                blocks=list(blocks),
                text=passage_text,
                vector_score=by_meaning.get(chunk_id),
                keyword_score=by_words.get(chunk_id),
                fused_score=fused_score,
                rerank_score=rerank_score,
            )
        )
    return Retrieval(query, hits, embedded.tokens, rerank_tokens)


def save_hits(session: AsyncSession, message_id: uuid.UUID, hits: Sequence[Hit]) -> None:
    """Keep what was retrieved for a message, for the conversation viewer and failure diagnosis."""
    session.add_all(
        RetrievalHit(
            message_id=message_id,
            chunk_id=hit.chunk_id,
            rank=hit.rank,
            vector_score=hit.vector_score,
            keyword_score=hit.keyword_score,
            rerank_score=hit.rerank_score,
        )
        for hit in hits
    )
