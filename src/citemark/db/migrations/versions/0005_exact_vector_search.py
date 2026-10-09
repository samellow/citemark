"""Vector search scans every live passage instead of using an approximate index (PRD Q15).

With the HNSW index, which passages came back for a question depended on the index's state,
such as the dead entries a re-index leaves until vacuum, and on whether the planner chose the
index at all. An exact scan always gives the same candidates for the same passages, and on
Zulip's 1,209 passages it took 4.5 ms (T9). A help center far larger than any in view would need
an index again.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_chunk_embedding", table_name="chunk", postgresql_where=sa.text("retired_at IS NULL"))


def downgrade() -> None:
    op.create_index(
        "ix_chunk_embedding",
        "chunk",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("retired_at IS NULL"),
    )
