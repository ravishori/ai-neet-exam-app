"""cms.review_sessions + cms.review_claims — HR-1 review queue foundation.

review_sessions: a reviewer's working set of IN_REVIEW question IDs, with
size (default 25), position/progress, and status, so a reviewer can resume
where they left off. review_claims: a lease-based per-question claim so two
reviewers cannot work the same question at once; a partial unique index
enforces "at most one ACTIVE claim per content_item_id" atomically at the
database level (races resolve via the unique-violation, not app logic).

Revision ID: a2b3c4d5e6f7
Revises: e5f7a8b9c0d1
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "e5f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "reviewer_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_size", sa.Integer, nullable=False, server_default="25"),
        sa.Column(
            "item_ids",
            sa.dialects.postgresql.ARRAY(sa.dialects.postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        # ACTIVE | COMPLETED | ABANDONED
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('ACTIVE','COMPLETED','ABANDONED')", name="ck_review_sessions_status"
        ),
        schema="cms",
    )
    op.create_index(
        "ix_cms_review_sessions_reviewer_id",
        "review_sessions",
        ["reviewer_id"],
        schema="cms",
    )

    op.create_table(
        "review_claims",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "content_item_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cms.content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cms.review_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # ACTIVE | RELEASED | EXPIRED | COMPLETED
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('ACTIVE','RELEASED','EXPIRED','COMPLETED')", name="ck_review_claims_status"
        ),
        schema="cms",
    )
    op.create_index(
        "ix_cms_review_claims_content_item_id",
        "review_claims",
        ["content_item_id"],
        schema="cms",
    )
    op.create_index(
        "ix_cms_review_claims_reviewer_id",
        "review_claims",
        ["reviewer_id"],
        schema="cms",
    )
    # The exclusivity guarantee: at most one ACTIVE claim per content item,
    # enforced by Postgres regardless of application-level races.
    op.create_index(
        "uq_cms_review_claims_active_item",
        "review_claims",
        ["content_item_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        schema="cms",
    )


def downgrade() -> None:
    op.drop_index("uq_cms_review_claims_active_item", table_name="review_claims", schema="cms")
    op.drop_index("ix_cms_review_claims_reviewer_id", table_name="review_claims", schema="cms")
    op.drop_index("ix_cms_review_claims_content_item_id", table_name="review_claims", schema="cms")
    op.drop_table("review_claims", schema="cms")
    op.drop_index("ix_cms_review_sessions_reviewer_id", table_name="review_sessions", schema="cms")
    op.drop_table("review_sessions", schema="cms")
