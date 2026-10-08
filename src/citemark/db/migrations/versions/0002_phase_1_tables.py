"""The Phase 1 tables (PRD 4), and the rules the database enforces itself (T3).

- `uuid_generate_v7()` makes the IDs. Postgres 18 has `uuidv7()` built in; 16 doesn't.
- A frozen test set can't change, apart from its agreed targets, and neither can its
  questions (QA promise 13).
- A chunk is never deleted or edited. A re-index retires it by setting `retired_at` once,
  so a citation from last month still opens its passage (QA promise 14).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A random v4 UUID with its first 48 bits replaced by the Unix time in milliseconds, and its
# version changed from 4 (0100) to 7 (0111) by setting bits 52 and 53.
UUID_V7 = """
CREATE FUNCTION uuid_generate_v7() RETURNS uuid LANGUAGE sql VOLATILE PARALLEL SAFE AS $$
  SELECT encode(
    set_bit(set_bit(
      overlay(uuid_send(gen_random_uuid())
              PLACING substring(int8send(floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint) FROM 3)
              FROM 1 FOR 6),
      52, 1), 53, 1),
    'hex')::uuid
$$
"""

RULES = [
    """
    CREATE FUNCTION refuse_frozen_set_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.frozen_at IS NOT NULL THEN
        IF TG_OP = 'DELETE' THEN
          RAISE EXCEPTION 'Test set % version % is frozen, so it can''t be deleted.', OLD.name, OLD.version
            USING ERRCODE = 'restrict_violation';
        END IF;
        IF (NEW.name, NEW.version, NEW.kind, NEW.frozen_at, NEW.content_hash)
           IS DISTINCT FROM (OLD.name, OLD.version, OLD.kind, OLD.frozen_at, OLD.content_hash) THEN
          RAISE EXCEPTION 'Test set % version % is frozen: only its targets can change.', OLD.name, OLD.version
            USING ERRCODE = 'restrict_violation';
        END IF;
      END IF;
      IF TG_OP = 'DELETE' THEN
        RETURN OLD;
      END IF;
      RETURN NEW;
    END
    $$
    """,
    """
    CREATE TRIGGER test_set_frozen BEFORE UPDATE OR DELETE ON test_set
    FOR EACH ROW EXECUTE FUNCTION refuse_frozen_set_change()
    """,
    """
    CREATE FUNCTION refuse_frozen_question_change() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      set_ids uuid[] := '{}';
    BEGIN
      IF TG_OP <> 'INSERT' THEN
        set_ids := set_ids || OLD.test_set_id;
      END IF;
      IF TG_OP <> 'DELETE' THEN
        set_ids := set_ids || NEW.test_set_id;
      END IF;
      -- FOR SHARE waits for a freeze in progress, so a question can't slip in as its set is frozen
      PERFORM 1 FROM test_set WHERE id = ANY (set_ids) FOR SHARE;
      IF EXISTS (SELECT 1 FROM test_set WHERE id = ANY (set_ids) AND frozen_at IS NOT NULL) THEN
        RAISE EXCEPTION 'The test set is frozen, so its questions can''t change. Put changes in the next version.'
          USING ERRCODE = 'restrict_violation';
      END IF;
      IF TG_OP = 'DELETE' THEN
        RETURN OLD;
      END IF;
      RETURN NEW;
    END
    $$
    """,
    """
    CREATE TRIGGER test_question_frozen BEFORE INSERT OR UPDATE OR DELETE ON test_question
    FOR EACH ROW EXECUTE FUNCTION refuse_frozen_question_change()
    """,
    """
    CREATE FUNCTION refuse_chunk_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Chunks are never deleted. A re-index retires them instead, so old citations still open.'
          USING ERRCODE = 'restrict_violation';
      END IF;
      -- The one change allowed is retiring a live chunk. tsv is generated after this trigger runs.
      IF OLD.retired_at IS NOT NULL
         OR NEW.retired_at IS NULL
         OR (to_jsonb(NEW) - 'retired_at' - 'tsv') IS DISTINCT FROM (to_jsonb(OLD) - 'retired_at' - 'tsv') THEN
        RAISE EXCEPTION 'Chunks are never edited. The only change allowed is retiring one, once.'
          USING ERRCODE = 'restrict_violation';
      END IF;
      RETURN NEW;
    END
    $$
    """,
    """
    CREATE TRIGGER chunk_never_changes BEFORE UPDATE OR DELETE ON chunk
    FOR EACH ROW EXECUTE FUNCTION refuse_chunk_change()
    """,
]
RULE_FUNCTIONS = ["refuse_frozen_set_change", "refuse_frozen_question_change", "refuse_chunk_change"]


def upgrade() -> None:
    op.execute(UUID_V7)
    op.create_table(
        "conversation",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("widget_version", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation")),
    )
    op.create_index(op.f("ix_conversation_started_at"), "conversation", ["started_at"], unique=False)
    op.create_table(
        "job",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("progress_done", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("progress_label", sa.Text(), server_default="", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed', 'cancelled')", name=op.f("ck_job_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job")),
    )
    op.create_index("ix_job_queued", "job", ["created_at"], unique=False, postgresql_where=sa.text("status = 'queued'"))
    op.create_table(
        "price_table",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("min_prompt_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("input_per_mtok", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("output_per_mtok", sa.Numeric(precision=10, scale=4), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "cache_read_per_mtok", sa.Numeric(precision=10, scale=4), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "cache_write_per_mtok", sa.Numeric(precision=10, scale=4), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_table")),
        sa.UniqueConstraint(
            "model",
            "min_prompt_tokens",
            "effective_from",
            name=op.f("uq_price_table_model_min_prompt_tokens_effective_from"),
        ),
    )
    op.create_table(
        "report",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("test_run_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("fix_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("html_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('audit', 'build', 'monthly', 'demo')", name=op.f("ck_report_kind")),
        sa.CheckConstraint("cardinality(test_run_ids) >= 1", name=op.f("ck_report_test_run_ids")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report")),
    )
    op.create_table(
        "setting",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_setting")),
    )
    op.create_table(
        "source",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("path_prefix", sa.Text(), nullable=True),
        sa.Column(
            "include", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "exclude", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("content_selector", sa.Text(), nullable=True),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind = 'upload' OR url IS NOT NULL", name=op.f("ck_source_url")),
        sa.CheckConstraint("kind IN ('sitemap', 'start_page', 'url', 'upload')", name=op.f("ck_source_kind")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source")),
    )
    op.create_table(
        "test_set",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), server_default="accuracy", nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("threshold", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("threshold_set_by", sa.Text(), nullable=True),
        sa.Column("threshold_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('accuracy', 'abuse')", name=op.f("ck_test_set_kind")),
        sa.CheckConstraint("frozen_at IS NULL OR content_hash IS NOT NULL", name=op.f("ck_test_set_frozen_hash")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_test_set_version")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_set")),
        sa.UniqueConstraint("name", "version", name=op.f("uq_test_set_name_version")),
    )
    op.create_table(
        "document",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint("status = 'failed' OR content_hash IS NOT NULL", name=op.f("ck_document_content_hash")),
        sa.CheckConstraint("status IN ('active', 'removed', 'failed')", name=op.f("ck_document_status")),
        sa.ForeignKeyConstraint(["source_id"], ["source.id"], name=op.f("fk_document_source_id_source")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document")),
        sa.UniqueConstraint("source_id", "url", name=op.f("uq_document_source_id_url")),
    )
    op.create_table(
        "message",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.Column("clarify_options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("gap_text", sa.Text(), nullable=True),
        sa.Column("swapped", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cache_write_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("embed_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rerank_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("ttfw_ms", sa.Integer(), nullable=True),
        sa.Column("total_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("(role = 'user') = (kind IS NULL)", name=op.f("ck_message_kind_role")),
        sa.CheckConstraint("kind = 'clarify' OR clarify_options IS NULL", name=op.f("ck_message_clarify_options")),
        sa.CheckConstraint("kind = 'partial' OR gap_text IS NULL", name=op.f("ck_message_gap_text")),
        sa.CheckConstraint(
            "kind IN ('answer', 'partial', 'clarify', 'decline_not_covered', 'decline_off_topic', 'small_talk', 'error', 'stopped')",
            name=op.f("ck_message_kind"),
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name=op.f("ck_message_role")),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_message_conversation_id_conversation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message")),
    )
    op.create_index(op.f("ix_message_conversation_id"), "message", ["conversation_id"], unique=False)
    op.create_table(
        "test_question",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("test_set_id", sa.Uuid(), nullable=False),
        sa.Column("ext_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "expected_answer",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "expected_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "expected_option",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("uncovered_part", sa.Text(), nullable=True),
        sa.Column(
            "not_covered_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("abuse_kind", sa.Text(), nullable=True),
        sa.Column(
            "must_not_contain",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("doc_gap", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("locked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.CheckConstraint("type = 'partial' OR uncovered_part IS NULL", name=op.f("ck_test_question_uncovered_part")),
        sa.CheckConstraint(
            "type IN ('answerable', 'partial', 'ambiguous', 'decline', 'off_topic')", name=op.f("ck_test_question_type")
        ),
        sa.ForeignKeyConstraint(["test_set_id"], ["test_set.id"], name=op.f("fk_test_question_test_set_id_test_set")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_question")),
        sa.UniqueConstraint("test_set_id", "ext_id", name=op.f("uq_test_question_test_set_id_ext_id")),
    )
    op.create_table(
        "test_run",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("test_set_id", sa.Uuid(), nullable=False),
        sa.Column("decision_group", sa.Uuid(), nullable=True),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("retrieval_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("git_sha", sa.Text(), nullable=False),
        sa.Column("judge_model", sa.Text(), nullable=False),
        sa.Column("rubric_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("budget_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.CheckConstraint("mode IN ('retrieval', 'full_context')", name=op.f("ck_test_run_mode")),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed', 'cancelled', 'over_budget')",
            name=op.f("ck_test_run_status"),
        ),
        sa.ForeignKeyConstraint(["test_set_id"], ["test_set.id"], name=op.f("fk_test_run_test_set_id_test_set")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_run")),
    )
    op.create_index(op.f("ix_test_run_decision_group"), "test_run", ["decision_group"], unique=False)
    op.create_table(
        "chunk",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.Text(), nullable=False),
        sa.Column("anchor_url", sa.Text(), nullable=True),
        sa.Column("blocks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", VECTOR(dim=1024), nullable=False),
        sa.Column(
            "tsv", postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', text)", persisted=True), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "jsonb_typeof(blocks) = 'array' AND jsonb_array_length(blocks) > 0", name=op.f("ck_chunk_blocks")
        ),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], name=op.f("fk_chunk_document_id_document")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunk")),
    )
    op.create_index(
        "ix_chunk_embedding",
        "chunk",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("retired_at IS NULL"),
    )
    op.create_index(
        "ix_chunk_live",
        "chunk",
        ["document_id", "position"],
        unique=False,
        postgresql_where=sa.text("retired_at IS NULL"),
    )
    op.create_index(
        "ix_chunk_tsv",
        "chunk",
        ["tsv"],
        unique=False,
        postgresql_using="gin",
        postgresql_where=sa.text("retired_at IS NULL"),
    )
    op.create_table(
        "test_result",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("test_run_id", sa.Uuid(), nullable=False),
        sa.Column("test_question_id", sa.Uuid(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.Column("swapped", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "citations", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "retrieved", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("retrieval_hit", sa.Boolean(), nullable=True),
        sa.Column("citation_correct", sa.Boolean(), nullable=True),
        sa.Column("decline_correct", sa.Boolean(), nullable=True),
        sa.Column("judge_verdict", sa.Text(), nullable=True),
        sa.Column("judge_reason", sa.Text(), nullable=True),
        sa.Column("judge_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("failure_type", sa.Text(), nullable=True),
        sa.Column("ttfw_ms", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "failure_type IN ('answered_should_decline', 'declined_answerable', 'retrieval_miss', 'wrong_citation', 'wrong_answer')",
            name=op.f("ck_test_result_failure_type"),
        ),
        sa.CheckConstraint("judge_verdict IN ('correct', 'incorrect')", name=op.f("ck_test_result_judge_verdict")),
        sa.CheckConstraint(
            "kind IN ('answer', 'partial', 'clarify', 'decline_not_covered', 'decline_off_topic', 'small_talk', 'error', 'stopped')",
            name=op.f("ck_test_result_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["test_question_id"], ["test_question.id"], name=op.f("fk_test_result_test_question_id_test_question")
        ),
        sa.ForeignKeyConstraint(["test_run_id"], ["test_run.id"], name=op.f("fk_test_result_test_run_id_test_run")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_result")),
        sa.UniqueConstraint(
            "test_run_id", "test_question_id", name=op.f("uq_test_result_test_run_id_test_question_id")
        ),
    )
    op.create_table(
        "citation",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("marker", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("cited_text", sa.Text(), nullable=False),
        sa.Column("start_block", sa.Integer(), nullable=False),
        sa.Column("end_block", sa.Integer(), nullable=False),
        sa.CheckConstraint("0 <= start_block AND start_block < end_block", name=op.f("ck_citation_block_range")),
        sa.CheckConstraint("marker BETWEEN 1 AND 3", name=op.f("ck_citation_marker")),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunk.id"], name=op.f("fk_citation_chunk_id_chunk")),
        sa.ForeignKeyConstraint(
            ["message_id"], ["message.id"], name=op.f("fk_citation_message_id_message"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_citation")),
    )
    op.create_index(op.f("ix_citation_message_id"), "citation", ["message_id"], unique=False)
    op.create_table(
        "human_grade",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("test_result_id", sa.Uuid(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("verdict IN ('correct', 'incorrect')", name=op.f("ck_human_grade_verdict")),
        sa.ForeignKeyConstraint(
            ["test_result_id"], ["test_result.id"], name=op.f("fk_human_grade_test_result_id_test_result")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_human_grade")),
        sa.UniqueConstraint("test_result_id", name=op.f("uq_human_grade_test_result_id")),
    )
    op.create_table(
        "retrieval_hit",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("vector_score", sa.Double(), nullable=True),
        sa.Column("keyword_score", sa.Double(), nullable=True),
        sa.Column("rerank_score", sa.Double(), nullable=True),
        sa.CheckConstraint("rank >= 1", name=op.f("ck_retrieval_hit_rank")),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunk.id"], name=op.f("fk_retrieval_hit_chunk_id_chunk")),
        sa.ForeignKeyConstraint(
            ["message_id"], ["message.id"], name=op.f("fk_retrieval_hit_message_id_message"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retrieval_hit")),
        sa.UniqueConstraint("message_id", "rank", name=op.f("uq_retrieval_hit_message_id_rank")),
    )
    for statement in RULES:
        op.execute(statement)


def downgrade() -> None:
    # Dropping a table drops its triggers; the functions go once the tables are gone
    op.drop_table("retrieval_hit")
    op.drop_table("human_grade")
    op.drop_index(op.f("ix_citation_message_id"), table_name="citation")
    op.drop_table("citation")
    op.drop_table("test_result")
    op.drop_index(
        "ix_chunk_tsv", table_name="chunk", postgresql_using="gin", postgresql_where=sa.text("retired_at IS NULL")
    )
    op.drop_index("ix_chunk_live", table_name="chunk", postgresql_where=sa.text("retired_at IS NULL"))
    op.drop_index(
        "ix_chunk_embedding",
        table_name="chunk",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("retired_at IS NULL"),
    )
    op.drop_table("chunk")
    op.drop_index(op.f("ix_test_run_decision_group"), table_name="test_run")
    op.drop_table("test_run")
    op.drop_table("test_question")
    op.drop_index(op.f("ix_message_conversation_id"), table_name="message")
    op.drop_table("message")
    op.drop_table("document")
    op.drop_table("test_set")
    op.drop_table("source")
    op.drop_table("setting")
    op.drop_table("report")
    op.drop_table("price_table")
    op.drop_index("ix_job_queued", table_name="job", postgresql_where=sa.text("status = 'queued'"))
    op.drop_table("job")
    op.drop_index(op.f("ix_conversation_started_at"), table_name="conversation")
    op.drop_table("conversation")
    for function in RULE_FUNCTIONS:
        op.execute(f"DROP FUNCTION {function}()")
    op.execute("DROP FUNCTION uuid_generate_v7()")
