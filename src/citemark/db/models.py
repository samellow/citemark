"""Table definitions (PRD 4): the Phase 1 tables.

One database is one client, so there's no tenant column. IDs are UUIDv7, made by the
database (`uuid_generate_v7()`, migration 0002), and times are `timestamptz` in UTC.
Feedback, handoffs, flagged questions and admin users arrive in Phase 2.

The rules the database enforces itself live in migration 0002's triggers: a frozen test
set and its questions can't change, and a chunk can't be edited or deleted, only retired.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Named constraints, so migrations can drop and alter them by a predictable name
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

EMBEDDING_DIMENSIONS = 1024  # voyage-4 (PRD 3)

SOURCE_KINDS = ("sitemap", "start_page", "url", "upload")
DOCUMENT_STATUSES = ("active", "removed", "failed")
MESSAGE_KINDS = (
    "answer",
    "partial",
    "clarify",
    "decline_not_covered",
    "decline_off_topic",
    "small_talk",
    "error",
    "stopped",
)
QUESTION_TYPES = ("answerable", "partial", "ambiguous", "decline", "off_topic")
RUN_STATUSES = ("queued", "running", "done", "failed", "cancelled", "over_budget")
VERDICTS = ("correct", "incorrect")
# PRD 5.4, in the order they're assigned
FAILURE_TYPES = ("answered_should_decline", "declined_answerable", "retrieval_miss", "wrong_citation", "wrong_answer")
REPORT_KINDS = ("audit", "build", "monthly", "demo")
JOB_STATUSES = ("queued", "running", "done", "failed", "cancelled")

# A missing value stored as SQL NULL, not JSON null, so `IS NULL` checks hold (found in T8)
NULLABLE_JSON = JSONB(none_as_null=True)

EMPTY_LIST = sql("'[]'::jsonb")
EMPTY_OBJECT = sql("'{}'::jsonb")
ZERO = sql("0")
FALSE = sql("false")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {  # noqa: RUF012 (SQLAlchemy reads this mapping; it's never mutated)
        str: Text(),
        dt.datetime: DateTime(timezone=True),
        dt.date: Date(),
        Decimal: Numeric(12, 6),
    }


def one_of(column: str, values: tuple[str, ...]) -> CheckConstraint:
    """A text column limited to a fixed list, so adding a value later is a plain constraint change."""
    allowed = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=column)


class _Row:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=sql("uuid_generate_v7()"), sort_order=-1)


# --- Knowledge (PRD 4.1) ---


class Source(_Row, Base):
    __tablename__ = "source"
    __table_args__ = (
        one_of("kind", SOURCE_KINDS),
        CheckConstraint("kind = 'upload' OR url IS NOT NULL", name="url"),
    )

    kind: Mapped[str]
    url: Mapped[str | None]
    path_prefix: Mapped[str | None]
    include: Mapped[list[str]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    exclude: Mapped[list[str]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    content_selector: Mapped[str | None]  # overrides the extractor when a layout confuses it (PRD 5.1)
    last_crawled_at: Mapped[dt.datetime | None]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class Document(_Row, Base):
    __tablename__ = "document"
    __table_args__ = (
        one_of("status", DOCUMENT_STATUSES),
        CheckConstraint("status = 'failed' OR content_hash IS NOT NULL", name="content_hash"),
        UniqueConstraint("source_id", "url"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source.id"))
    url: Mapped[str]
    title: Mapped[str | None]
    content_hash: Mapped[str | None]  # decides whether a re-index re-chunks the document
    last_modified: Mapped[dt.datetime | None]
    status: Mapped[str] = mapped_column(server_default="active")
    fetched_at: Mapped[dt.datetime | None]
    error: Mapped[str | None]


class Chunk(_Row, Base):
    """A passage. Never edited or deleted: a re-index adds new chunks and retires the old
    ones, so a citation from last month still opens what it cited (QA promise 14)."""

    __tablename__ = "chunk"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(blocks) = 'array' AND jsonb_array_length(blocks) > 0", name="blocks"),
        # Retrieval only reads live chunks, so its indexes only hold them. The embedding has no
        # index: vector search scans every live passage, so it's exact (PRD Q15, T9)
        Index("ix_chunk_tsv", "tsv", postgresql_using="gin", postgresql_where=sql("retired_at IS NULL")),
        Index("ix_chunk_live", "document_id", "position", postgresql_where=sql("retired_at IS NULL")),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document.id"))
    position: Mapped[int]  # order within the document, for full-context mode
    heading_path: Mapped[str]  # the article title, then the section headings
    anchor_url: Mapped[str | None]
    blocks: Mapped[list[str]] = mapped_column(JSONB)  # the paragraphs, so a citation can point at one
    text: Mapped[str]
    token_count: Mapped[int]
    embedding: Mapped[list[float]] = mapped_column(VECTOR(EMBEDDING_DIMENSIONS))
    tsv: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('english', text)", persisted=True))
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    retired_at: Mapped[dt.datetime | None]


# --- Conversations (PRD 4.2). Deleted after the retention period, so their rows cascade. ---


class Conversation(_Row, Base):
    __tablename__ = "conversation"

    started_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), index=True)
    page_url: Mapped[str | None]
    widget_version: Mapped[str | None]
    model: Mapped[str]
    prompt_version: Mapped[str]


class Message(_Row, Base):
    __tablename__ = "message"
    __table_args__ = (
        one_of("role", ("user", "assistant")),
        one_of("kind", MESSAGE_KINDS),
        # The server sets kind on its own replies from the model's tool calls (PRD 5.3)
        CheckConstraint("(role = 'user') = (kind IS NULL)", name="kind_role"),
        CheckConstraint("kind = 'clarify' OR clarify_options IS NULL", name="clarify_options"),
        CheckConstraint("kind = 'partial' OR gap_text IS NULL", name="gap_text"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), index=True)
    role: Mapped[str]
    content: Mapped[str]
    kind: Mapped[str | None]
    clarify_options: Mapped[list[str] | None] = mapped_column(NULLABLE_JSON)
    gap_text: Mapped[str | None]
    # Text streamed before a late decline or clarifying question, then swapped out (PRD Q11)
    swapped: Mapped[bool] = mapped_column(server_default=FALSE)
    input_tokens: Mapped[int] = mapped_column(server_default=ZERO)
    output_tokens: Mapped[int] = mapped_column(server_default=ZERO)
    cache_read_tokens: Mapped[int] = mapped_column(server_default=ZERO)
    cache_write_tokens: Mapped[int] = mapped_column(server_default=ZERO)
    embed_tokens: Mapped[int] = mapped_column(server_default=ZERO)
    rerank_tokens: Mapped[int] = mapped_column(server_default=ZERO)
    cost_usd: Mapped[Decimal] = mapped_column(server_default=ZERO)
    ttfw_ms: Mapped[int | None]
    total_ms: Mapped[int | None]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class Citation(_Row, Base):
    __tablename__ = "citation"
    __table_args__ = (
        CheckConstraint("marker BETWEEN 1 AND 3", name="marker"),
        # The API's block range: end_block is exclusive
        CheckConstraint("0 <= start_block AND start_block < end_block", name="block_range"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("message.id", ondelete="CASCADE"), index=True)
    marker: Mapped[int]  # the source number the visitor sees, in order of first appearance
    chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chunk.id"))
    cited_text: Mapped[str]
    start_block: Mapped[int]
    end_block: Mapped[int]


class RetrievalHit(_Row, Base):
    __tablename__ = "retrieval_hit"
    __table_args__ = (
        CheckConstraint("rank >= 1", name="rank"),
        UniqueConstraint("message_id", "rank"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("message.id", ondelete="CASCADE"))
    chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chunk.id"))
    rank: Mapped[int]
    vector_score: Mapped[float | None]
    keyword_score: Mapped[float | None]
    rerank_score: Mapped[float | None]


# --- Accuracy (PRD 4.3). Kept indefinitely; nothing here cascades. ---


class TestSet(_Row, Base):
    """Once `frozen_at` is set, the set and its questions can't change; only the agreed targets can."""

    __test__ = False  # not a pytest test class
    __tablename__ = "test_set"
    __table_args__ = (
        one_of("kind", ("accuracy", "abuse")),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("frozen_at IS NULL OR content_hash IS NOT NULL", name="frozen_hash"),
        UniqueConstraint("name", "version"),
    )

    name: Mapped[str]
    version: Mapped[int]
    kind: Mapped[str] = mapped_column(server_default="accuracy")
    frozen_at: Mapped[dt.datetime | None]
    content_hash: Mapped[str | None]  # the YAML file's sha256, from its lock
    threshold: Mapped[dict[str, Any] | None] = mapped_column(NULLABLE_JSON)
    threshold_set_by: Mapped[str | None]
    threshold_set_at: Mapped[dt.datetime | None]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class TestQuestion(_Row, Base):
    """One question of a test set, as in its YAML file (`citemark.evals.testset.Question`)."""

    __test__ = False
    __tablename__ = "test_question"
    __table_args__ = (
        one_of("type", QUESTION_TYPES),
        CheckConstraint("type = 'partial' OR uncovered_part IS NULL", name="uncovered_part"),
        UniqueConstraint("test_set_id", "ext_id"),
    )

    test_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_set.id"))
    ext_id: Mapped[str]  # "Q017"
    type: Mapped[str]
    question: Mapped[str]
    expected_answer: Mapped[list[str]] = mapped_column(JSONB, server_default=EMPTY_LIST)  # the key facts
    expected_sources: Mapped[list[dict[str, str]]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    expected_option: Mapped[list[str]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    uncovered_part: Mapped[str | None]
    not_covered_terms: Mapped[list[str]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    abuse_kind: Mapped[str | None]  # abuse sets only (QA plan 4.3)
    must_not_contain: Mapped[list[str]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    doc_gap: Mapped[bool] = mapped_column(server_default=FALSE)
    locked: Mapped[bool] = mapped_column(server_default=FALSE)
    notes: Mapped[str] = mapped_column(server_default="")


class TestRun(_Row, Base):
    """Every setting that could change a score, so two runs can be compared honestly."""

    __test__ = False
    __tablename__ = "test_run"
    __table_args__ = (
        one_of("mode", ("retrieval", "full_context")),
        one_of("status", RUN_STATUSES),
    )

    test_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_set.id"))
    decision_group: Mapped[uuid.UUID | None] = mapped_column(index=True)  # shared by a decision run's three runs
    mode: Mapped[str]
    model: Mapped[str]
    company: Mapped[str]  # the product name the prompt is filled with
    prompt_version: Mapped[str]
    retrieval_config: Mapped[dict[str, Any] | None] = mapped_column(NULLABLE_JSON)
    git_sha: Mapped[str]
    judge_model: Mapped[str]
    rubric_version: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="queued")
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[dt.datetime | None]
    finished_at: Mapped[dt.datetime | None]
    cost_usd: Mapped[Decimal] = mapped_column(server_default=ZERO)
    budget_usd: Mapped[Decimal]


class TestResult(_Row, Base):
    """The mechanical scores and the judge's verdict, stored separately. An empty score means
    it doesn't apply, such as retrieval in full-context mode."""

    __test__ = False
    __tablename__ = "test_result"
    __table_args__ = (
        one_of("kind", MESSAGE_KINDS),
        one_of("judge_verdict", VERDICTS),
        one_of("failure_type", FAILURE_TYPES),
        UniqueConstraint("test_run_id", "test_question_id"),
    )

    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_run.id"))
    test_question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_question.id"))
    answer: Mapped[str | None]
    kind: Mapped[str | None]
    swapped: Mapped[bool] = mapped_column(server_default=FALSE)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    # The options offered, when the first reply asked which meaning was meant (ambiguous questions)
    clarify_options: Mapped[list[str] | None] = mapped_column(NULLABLE_JSON)
    retrieved: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=EMPTY_LIST)
    retrieval_hit: Mapped[bool | None]
    citation_correct: Mapped[bool | None]
    decline_correct: Mapped[bool | None]
    judge_verdict: Mapped[str | None]
    judge_reason: Mapped[str | None]
    judge_output: Mapped[dict[str, Any] | None] = mapped_column(NULLABLE_JSON)  # the judge's whole structured reply
    failure_type: Mapped[str | None]
    ttfw_ms: Mapped[int | None]
    cost_usd: Mapped[Decimal] = mapped_column(server_default=ZERO)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class HumanGrade(_Row, Base):
    """Your grade on one answer. It locks when its grading sheet is completed, and the database
    then refuses to change it (PRD Q18)."""

    __tablename__ = "human_grade"
    __table_args__ = (one_of("verdict", VERDICTS),)

    test_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_result.id"), unique=True)
    verdict: Mapped[str]
    note: Mapped[str] = mapped_column(server_default="")
    graded_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    locked_at: Mapped[dt.datetime | None]


class Report(_Row, Base):
    __tablename__ = "report"
    __table_args__ = (
        one_of("kind", REPORT_KINDS),
        CheckConstraint("cardinality(test_run_ids) >= 1", name="test_run_ids"),
    )

    kind: Mapped[str]
    test_run_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid()))
    # Hour estimates written by hand, never computed
    fix_plan: Mapped[dict[str, Any] | None] = mapped_column(NULLABLE_JSON)
    html_path: Mapped[str | None]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


# --- Operations (PRD 4.4) ---


class Job(_Row, Base):
    __tablename__ = "job"
    __table_args__ = (
        one_of("status", JOB_STATUSES),
        Index("ix_job_queued", "created_at", postgresql_where=sql("status = 'queued'")),
    )

    type: Mapped[str]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=EMPTY_OBJECT)
    status: Mapped[str] = mapped_column(server_default="queued")
    progress_done: Mapped[int] = mapped_column(server_default=ZERO)
    progress_total: Mapped[int | None]
    progress_label: Mapped[str] = mapped_column(server_default="")  # "120 of 257 articles"
    attempts: Mapped[int] = mapped_column(server_default=ZERO)
    error: Mapped[str | None]
    locked_at: Mapped[dt.datetime | None]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[dt.datetime | None]


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_by: Mapped[str | None]
    updated_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class Price(_Row, Base):
    """A dated price, so a report from March keeps March's prices (PRD 5.12). USD per million tokens."""

    __tablename__ = "price_table"
    __table_args__ = (UniqueConstraint("model", "min_prompt_tokens", "effective_from"),)

    model: Mapped[str]
    # The row applies to prompts of at least this many tokens: Haiku 5.5 costs more above 100k
    min_prompt_tokens: Mapped[int] = mapped_column(server_default=ZERO)
    input_per_mtok: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    output_per_mtok: Mapped[Decimal] = mapped_column(Numeric(10, 4), server_default=ZERO)
    cache_read_per_mtok: Mapped[Decimal] = mapped_column(Numeric(10, 4), server_default=ZERO)
    cache_write_per_mtok: Mapped[Decimal] = mapped_column(Numeric(10, 4), server_default=ZERO)
    effective_from: Mapped[dt.date]
