"""FACTORY-P1: cms.content_batches / generation_jobs / generation_runs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-01 00:30:00.000000

Does not modify content_items, content_versions, reviews, or ECAEP statuses.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_batches",
        sa.Column("batch_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("chapter_id", sa.UUID(), nullable=True),
        sa.Column("topic_id", sa.UUID(), nullable=True),
        sa.Column("concept_id", sa.UUID(), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_tier", sa.String(length=30), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("qa_pass_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["academic.subjects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["chapter_id"], ["academic.chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["academic.topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["concept_id"], ["academic.concepts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_key", name="uq_cms_content_batches_batch_key"),
        schema="cms",
    )
    op.create_index("ix_cms_content_batches_status", "content_batches", ["status"], schema="cms")
    op.create_index("ix_cms_content_batches_subject_id", "content_batches", ["subject_id"], schema="cms")
    op.create_index("ix_cms_content_batches_created_at", "content_batches", ["created_at"], schema="cms")

    op.create_table(
        "generation_jobs",
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("job_key", sa.String(length=120), nullable=False),
        sa.Column("job_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["cms.content_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "job_key", name="uq_cms_generation_jobs_batch_job_key"),
        schema="cms",
    )
    op.create_index("ix_cms_generation_jobs_batch_id", "generation_jobs", ["batch_id"], schema="cms")
    op.create_index("ix_cms_generation_jobs_status", "generation_jobs", ["status"], schema="cms")

    op.create_table(
        "generation_runs",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("execution_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["cms.generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_cms_generation_runs_job_attempt"),
        schema="cms",
    )
    op.create_index("ix_cms_generation_runs_job_id", "generation_runs", ["job_id"], schema="cms")
    op.create_index("ix_cms_generation_runs_status", "generation_runs", ["status"], schema="cms")


def downgrade() -> None:
    op.drop_index("ix_cms_generation_runs_status", table_name="generation_runs", schema="cms")
    op.drop_index("ix_cms_generation_runs_job_id", table_name="generation_runs", schema="cms")
    op.drop_table("generation_runs", schema="cms")
    op.drop_index("ix_cms_generation_jobs_status", table_name="generation_jobs", schema="cms")
    op.drop_index("ix_cms_generation_jobs_batch_id", table_name="generation_jobs", schema="cms")
    op.drop_table("generation_jobs", schema="cms")
    op.drop_index("ix_cms_content_batches_created_at", table_name="content_batches", schema="cms")
    op.drop_index("ix_cms_content_batches_subject_id", table_name="content_batches", schema="cms")
    op.drop_index("ix_cms_content_batches_status", table_name="content_batches", schema="cms")
    op.drop_table("content_batches", schema="cms")
