"""FACTORY-P5: factory_review_items + candidate factory_review_status

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-01 03:00:00.000000

Does not modify content_items bodies or ECAEP statuses.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_candidates",
        sa.Column("factory_review_status", sa.String(length=30), nullable=True),
        schema="cms",
    )
    op.add_column(
        "generation_candidates",
        sa.Column("latest_factory_review_item_id", sa.UUID(), nullable=True),
        schema="cms",
    )
    op.create_index(
        "ix_cms_gen_candidates_factory_review_status",
        "generation_candidates",
        ["factory_review_status"],
        schema="cms",
    )

    op.create_table(
        "factory_review_items",
        sa.Column("sample_id", sa.UUID(), nullable=False),
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("qa_result_id", sa.UUID(), nullable=True),
        sa.Column("qa_version", sa.String(length=40), nullable=True),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("selection_class", sa.String(length=20), nullable=False),
        sa.Column("selection_reason", sa.String(length=120), nullable=True),
        sa.Column("review_status", sa.String(length=30), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=True),
        sa.Column("reviewer_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("checklist", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failure_reasons", postgresql.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column("ecaep_submit_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "disclaimer",
            sa.Text(),
            nullable=False,
            server_default="Factory human review ≠ ECAEP approval ≠ publication ≠ scientific certification of the full batch",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["sample_id"], ["cms.review_samples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batch_id"], ["cms.content_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["cms.generation_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_item_id"], ["cms.content_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["qa_result_id"], ["cms.qa_results.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sample_id", "candidate_id", name="uq_cms_factory_review_items_sample_candidate"),
        schema="cms",
    )
    op.create_index("ix_cms_factory_review_items_batch_id", "factory_review_items", ["batch_id"], schema="cms")
    op.create_index("ix_cms_factory_review_items_status", "factory_review_items", ["review_status"], schema="cms")
    op.create_index(
        "ix_cms_factory_review_items_selection_class", "factory_review_items", ["selection_class"], schema="cms"
    )
    op.create_index(
        "ix_cms_factory_review_items_content_item_id", "factory_review_items", ["content_item_id"], schema="cms"
    )
    op.create_index(
        "ix_cms_factory_review_items_candidate_id", "factory_review_items", ["candidate_id"], schema="cms"
    )


def downgrade() -> None:
    op.drop_index("ix_cms_factory_review_items_candidate_id", table_name="factory_review_items", schema="cms")
    op.drop_index("ix_cms_factory_review_items_content_item_id", table_name="factory_review_items", schema="cms")
    op.drop_index("ix_cms_factory_review_items_selection_class", table_name="factory_review_items", schema="cms")
    op.drop_index("ix_cms_factory_review_items_status", table_name="factory_review_items", schema="cms")
    op.drop_index("ix_cms_factory_review_items_batch_id", table_name="factory_review_items", schema="cms")
    op.drop_table("factory_review_items", schema="cms")
    op.drop_index("ix_cms_gen_candidates_factory_review_status", table_name="generation_candidates", schema="cms")
    op.drop_column("generation_candidates", "latest_factory_review_item_id", schema="cms")
    op.drop_column("generation_candidates", "factory_review_status", schema="cms")
