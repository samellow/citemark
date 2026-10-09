"""Full-context mode (PRD 5.2, test runs only): every live passage, grouped by article.

Articles come in address order and passages in page order, so the same help center always
makes the same block, which is what lets prompt caching reuse it from question to question.
Whether it fits a model's window is checked on a measured count (`models.registry`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import Chunk, Document


@dataclass(frozen=True)
class ContextPassage:
    chunk_id: uuid.UUID
    heading_path: str
    anchor_url: str | None
    blocks: list[str]


@dataclass(frozen=True)
class Article:
    url: str
    title: str | None
    passages: list[ContextPassage] = field(default_factory=list)


async def full_context(session: AsyncSession) -> list[Article]:
    rows = await session.execute(
        select(Document.url, Document.title, Chunk.id, Chunk.heading_path, Chunk.anchor_url, Chunk.blocks)
        .join(Chunk, Chunk.document_id == Document.id)
        .where(Chunk.retired_at.is_(None), Document.status == "active")
        .order_by(Document.url, Chunk.position)
    )
    articles: list[Article] = []
    for url, title, chunk_id, heading_path, anchor_url, blocks in rows:
        if not articles or articles[-1].url != url:
            articles.append(Article(url, title))
        articles[-1].passages.append(ContextPassage(chunk_id, heading_path, anchor_url, list(blocks)))
    return articles
