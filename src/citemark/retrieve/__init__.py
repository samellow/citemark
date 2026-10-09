"""Retrieval (PRD 5.2): which passages the model sees for a question.

Search mode: the question is searched two ways, by meaning (vector) and by its words (keyword),
the two lists are merged by reciprocal rank fusion, and a reranker picks the best few. Full-
context mode sends every live passage instead, where the model's window holds them all.

The settings that change which passages are found are one object, stored on every test run
(`test_run.retrieval_config`), so two runs are compared on the same terms.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import Setting

SETTING = "retrieval"


class RetrievalError(Exception):
    """The message is one plain sentence."""


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidates: int = Field(30, ge=1, le=200)  # from vector search, and again from keyword search
    rrf_k: int = Field(60, ge=1)  # reciprocal rank fusion's constant
    top_k: int = Field(5, ge=1, le=20)  # passages the model gets
    rerank: bool = True
    reranker: str = "rerank-3"  # PRD Q3 (changed 2026-10-09)


async def load_config(session: AsyncSession) -> RetrievalConfig:
    """The defaults, with any changes saved in the `retrieval` setting."""
    saved = await session.scalar(select(Setting.value).where(Setting.key == SETTING))
    try:
        return RetrievalConfig.model_validate(saved or {})
    except ValidationError as exc:
        problem = exc.errors()[0]
        where = ".".join(str(part) for part in problem["loc"]) or "it"
        raise RetrievalError(f'The "{SETTING}" setting isn\'t valid: {where}: {problem["msg"]}.') from exc
