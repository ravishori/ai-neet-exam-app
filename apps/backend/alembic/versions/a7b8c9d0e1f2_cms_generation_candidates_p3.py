"""FACTORY-P3: generation_candidates lineage + stem-hash idempotency

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-01 01:20:00.000000

Does not modify existing content_items / versions / statuses.
"""

from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_candidates",
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("blueprint_id", sa.UUID(), nullable=False),
        sa.Column("blueprint_version", sa.Integer(), nullable=False),
        sa.Column("concept_id", sa.UUID(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("stem_hash", sa.String(length=64), nullable=True),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("is_fallback", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["cms.content_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["cms.generation_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["cms.generation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blueprint_id"], ["cms.question_blueprints.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["concept_id"], ["academic.concepts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["content_item_id"], ["cms.content_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "attempt_no", name="uq_cms_gen_candidates_run_attempt"),
        schema="cms",
    )
    op.create_index("ix_cms_gen_candidates_job_id", "generation_candidates", ["job_id"], schema="cms")
    op.create_index("ix_cms_gen_candidates_run_id", "generation_candidates", ["run_id"], schema="cms")
    op.create_index("ix_cms_gen_candidates_stem_hash", "generation_candidates", ["stem_hash"], schema="cms")
    op.create_index("ix_cms_gen_candidates_status", "generation_candidates", ["status"], schema="cms")
    # One successful insert per normalized stem within a concept (concurrency-safe).
    op.create_index(
        "uq_cms_gen_candidates_concept_stem_created",
        "generation_candidates",
        ["concept_id", "stem_hash"],
        unique=True,
        schema="cms",
        postgresql_where=sa.text("status = 'CREATED' AND stem_hash IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_cms_gen_candidates_concept_stem_created", table_name="generation_candidates", schema="cms")
    op.drop_index("ix_cms_gen_candidates_status", table_name="generation_candidates", schema="cms")
    op.drop_index("ix_cms_gen_candidates_stem_hash", table_name="generation_candidates", schema="cms")
    op.drop_index("ix_cms_gen_candidates_run_id", table_name="generation_candidates", schema="cms")
    op.drop_index("ix_cms_gen_candidates_job_id", table_name="generation_candidates", schema="cms")
    op.drop_table("generation_candidates", schema="cms")
