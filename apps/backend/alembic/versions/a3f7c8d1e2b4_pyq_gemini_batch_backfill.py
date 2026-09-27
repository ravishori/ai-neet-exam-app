"""pyq: Gemini Batch API job/item tracking for the Stage-2 backfill

New tables only — never touches pyq.questions or pyq.answer_assertions'
schema. gemini_batch_jobs is one row per submitted batch (e.g. the one-time
full backfill); gemini_batch_items is one row per question included in
that batch, carrying the custom_id used to map a Gemini batch result back
to the question, and its own apply-state so polling/applying results is
resumable and idempotent (a row already APPLIED is never re-applied).

Revision ID: a3f7c8d1e2b4
Revises: c6cfdf360a4b
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "a3f7c8d1e2b4"
down_revision = "c6cfdf360a4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gemini_batch_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_type", sa.String(30), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="SUBMITTED",
        ),
        sa.Column("gemini_batch_name", sa.String(200), nullable=True),
        sa.Column("gemini_model", sa.String(80), nullable=False),
        sa.Column("question_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('SUBMITTED','PROCESSING','COMPLETED','PARTIAL','FAILED','CANCELLED')",
            name="ck_gemini_batch_jobs_status",
        ),
        schema="pyq",
    )
    # Hard protection against launching the same full backfill twice: at
    # most one non-terminal (SUBMITTED/PROCESSING) job per job_type.
    op.create_index(
        "uq_pyq_gemini_batch_jobs_active_by_type",
        "gemini_batch_jobs",
        ["job_type"],
        unique=True,
        postgresql_where=sa.text("status IN ('SUBMITTED','PROCESSING')"),
        schema="pyq",
    )

    op.create_table(
        "gemini_batch_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "batch_job_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pyq.gemini_batch_jobs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "question_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pyq.questions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("custom_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="SUBMITTED"),
        sa.Column("raw_result", postgresql.JSONB, nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('SUBMITTED','RESULT_RECEIVED','APPLIED','FAILED','SKIPPED')",
            name="ck_gemini_batch_items_status",
        ),
        sa.UniqueConstraint("batch_job_id", "question_id", name="uq_pyq_gemini_batch_items_job_question"),
        sa.UniqueConstraint("batch_job_id", "custom_id", name="uq_pyq_gemini_batch_items_job_custom_id"),
        schema="pyq",
    )
    op.create_index(
        "ix_pyq_gemini_batch_items_batch_job_id", "gemini_batch_items", ["batch_job_id"], schema="pyq"
    )
    op.create_index(
        "ix_pyq_gemini_batch_items_status", "gemini_batch_items", ["status"], schema="pyq"
    )


def downgrade() -> None:
    op.drop_index("ix_pyq_gemini_batch_items_status", table_name="gemini_batch_items", schema="pyq")
    op.drop_index("ix_pyq_gemini_batch_items_batch_job_id", table_name="gemini_batch_items", schema="pyq")
    op.drop_table("gemini_batch_items", schema="pyq")
    op.drop_index("uq_pyq_gemini_batch_jobs_active_by_type", table_name="gemini_batch_jobs", schema="pyq")
    op.drop_table("gemini_batch_jobs", schema="pyq")
