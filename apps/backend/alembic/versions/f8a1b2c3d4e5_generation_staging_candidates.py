"""Generation staging — deterministic MCQ candidate inventory

Revision ID: f8a1b2c3d4e5
Revises: 62aa0447d463
Create Date: 2026-10-10 00:00:00.000000

New, clearly-isolated `generation_staging` schema. Does NOT modify any
existing table and carries no enforced foreign key into cms.*/pyq.*
content tables — `duplicate_of_question_id` is a loosely-typed reference
(plain string), not an FK, so it can never cascade-affect live content.

Purpose: persistently store EVERY deterministic-engine generation
candidate (accepted AND rejected/duplicate), additive to the existing
JSON file output under data/generated_mcqs/. Duplicates are flagged via
`is_duplicate` + `duplicate_of_question_id`, never rejected by a DB
constraint — only the staging row's own identity (batch_id + fact_id +
attempt_number) is unique-constrained, to make batch resume idempotent.
`concept_id` stays nullable throughout.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f8a1b2c3d4e5"
down_revision = "62aa0447d463"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS generation_staging")

    op.create_table(
        "candidates",
        # --- staging identity (not content identity) ---
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("batch_id", sa.String(length=80), nullable=False),
        sa.Column("sequence_in_batch", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("generation_method", sa.String(length=80), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        # --- source provenance ---
        sa.Column("fact_id", sa.String(length=120), nullable=False),
        sa.Column("source_pdf", sa.Text(), nullable=True),
        sa.Column("source_relative_path", sa.Text(), nullable=True),
        sa.Column("evidence_pages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence_quoted_text", sa.Text(), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # --- taxonomy (concept_id stays nullable/optional) ---
        sa.Column("subject", sa.String(length=40), nullable=True),
        sa.Column("class_level", sa.String(length=10), nullable=True),
        sa.Column("chapter", sa.String(length=200), nullable=True),
        sa.Column("topic", sa.String(length=200), nullable=True),
        sa.Column("concept", sa.String(length=200), nullable=True),
        sa.Column("concept_id", sa.String(length=120), nullable=True),
        sa.Column("syllabus_binding", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # --- question content ---
        sa.Column("question_type", sa.String(length=40), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=True),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correct_answer", sa.String(length=10), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("stem_hash", sa.String(length=64), nullable=True),
        sa.Column("option_stem_hash", sa.String(length=64), nullable=True),
        # --- outcome / validation ---
        sa.Column("outcome", sa.String(length=20), nullable=False),  # ACCEPTED | REJECTED
        sa.Column("rejection_reason", sa.String(length=80), nullable=True),
        sa.Column("rejection_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_status", sa.String(length=40), nullable=True),
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # --- content-duplicate flag (NOT a uniqueness constraint — duplicates are storable) ---
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("duplicate_of_question_id", sa.String(length=120), nullable=True),
        sa.Column("duplicate_matched_source_file", sa.String(length=255), nullable=True),
        sa.Column("duplicate_similarity", sa.Float(), nullable=True),
        # --- full raw payload captured for lossless replay / debugging ---
        sa.Column("raw_candidate", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "fact_id",
            "attempt_number",
            name="uq_generation_staging_candidates_batch_fact_attempt",
        ),
        schema="generation_staging",
    )
    op.create_index(
        "ix_generation_staging_candidates_batch_id",
        "candidates",
        ["batch_id"],
        schema="generation_staging",
    )
    op.create_index(
        "ix_generation_staging_candidates_fact_id",
        "candidates",
        ["fact_id"],
        schema="generation_staging",
    )
    op.create_index(
        "ix_generation_staging_candidates_outcome",
        "candidates",
        ["outcome"],
        schema="generation_staging",
    )
    op.create_index(
        "ix_generation_staging_candidates_is_duplicate",
        "candidates",
        ["is_duplicate"],
        schema="generation_staging",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generation_staging_candidates_is_duplicate",
        table_name="candidates",
        schema="generation_staging",
    )
    op.drop_index(
        "ix_generation_staging_candidates_outcome",
        table_name="candidates",
        schema="generation_staging",
    )
    op.drop_index(
        "ix_generation_staging_candidates_fact_id",
        table_name="candidates",
        schema="generation_staging",
    )
    op.drop_index(
        "ix_generation_staging_candidates_batch_id",
        table_name="candidates",
        schema="generation_staging",
    )
    op.drop_table("candidates", schema="generation_staging")
    op.execute("DROP SCHEMA IF EXISTS generation_staging CASCADE")
