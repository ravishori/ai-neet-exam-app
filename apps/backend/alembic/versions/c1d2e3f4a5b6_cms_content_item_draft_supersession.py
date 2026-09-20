"""CMS ContentItem DRAFT supersession lineage (replaces_id + SUPERSEDED).

Revision ID: c1d2e3f4a5b6
Revises: rs003b1_chapter_cls
Create Date: 2026-09-11 16:30:00.000000

Adds nullable self-referential lineage column cms.content_items.replaces_id
(replacement → original), matching the KnowledgeUnit superseded_by pattern
directionally inverted for query convenience:
  - Replacement item.replaces_id points at the retired original.
  - Reverse lookup: WHERE replaces_id = :original_id
  - UNIQUE partial index ensures one replacement per original.

Does NOT:
  - change any existing row status
  - invent ARCHIVED semantics for DRAFT
  - touch published content
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c1d2e3f4a5b6"
down_revision = "rs003b1_chapter_cls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "content_items",
        sa.Column("replaces_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="cms",
    )
    op.create_foreign_key(
        "fk_cms_content_items_replaces_id",
        "content_items",
        "content_items",
        ["replaces_id"],
        ["id"],
        source_schema="cms",
        referent_schema="cms",
        ondelete="SET NULL",
    )
    # One replacement may replace at most one original; originals may only
    # be targeted by one active replacement pointer.
    op.create_index(
        "uq_cms_content_items_replaces_id",
        "content_items",
        ["replaces_id"],
        unique=True,
        schema="cms",
        postgresql_where=sa.text("replaces_id IS NOT NULL"),
    )
    op.create_index(
        "ix_cms_content_items_replaces_id",
        "content_items",
        ["replaces_id"],
        unique=False,
        schema="cms",
    )


def downgrade() -> None:
    op.drop_index("ix_cms_content_items_replaces_id", table_name="content_items", schema="cms")
    op.drop_index("uq_cms_content_items_replaces_id", table_name="content_items", schema="cms")
    op.drop_constraint("fk_cms_content_items_replaces_id", "content_items", schema="cms", type_="foreignkey")
    op.drop_column("content_items", "replaces_id", schema="cms")
