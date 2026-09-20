"""ingestion: pilot MCQ run metadata on ingestion_jobs (ADR-0032 Phase D)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-24 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column("target_mcq_count", sa.Integer(), nullable=True),
        schema="ingestion",
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column("pilot_run_id", sa.String(length=80), nullable=True),
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_jobs_pilot_run_id",
        "ingestion_jobs",
        ["pilot_run_id"],
        schema="ingestion",
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_pilot_run_id", table_name="ingestion_jobs", schema="ingestion")
    op.drop_column("ingestion_jobs", "pilot_run_id", schema="ingestion")
    op.drop_column("ingestion_jobs", "target_mcq_count", schema="ingestion")
