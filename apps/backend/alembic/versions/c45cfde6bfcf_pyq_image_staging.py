"""PYQ image-extraction staging — deterministic PYQ ingestion

Revision ID: a1b2c3d4e5f6
Revises: f8a1b2c3d4e5
Create Date: 2026-10-10 00:00:00.000000

New, isolated `pyq_image_staging` schema. Does NOT modify or read any
existing table, and is scoped specifically to the PYQ-with-images
extraction pipeline (deterministic text + image extraction from
NEET Past Papers PDFs). This is a SEPARATE concern/table shape from the
`generation_staging.candidates` table added in f8a1b2c3d4e5 (that table
is for AI/engine-generated MCQ candidates from facts; this one is for
raw PYQ extraction from scanned/born-digital exam PDFs, including
embedded diagram/graph images).

Two tables:
- `questions`: one row per extracted (or partially-extracted) question,
  with an idempotent identity key (source_file + page + question_number
  + paper_code) enforced via unique constraint, so re-running the
  pipeline after interruption does not create duplicate STAGING rows
  for the same already-processed tuple. Content-level duplicates
  (e.g. same question appearing validly more than once) are allowed —
  nothing in this schema hashes/compares question text to block
  insertion.
- `images`: one row per image extracted from a PDF page, with a
  nullable FK to `questions` (nullable because image-to-question
  association is sometimes uncertain — never force a guess) plus an
  explicit association_confidence/association_basis for that link.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c45cfde6bfcf"
down_revision = "f8a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS pyq_image_staging")

    op.create_table(
        "questions",
        sa.Column("id", sa.UUID(), nullable=False),
        # --- idempotent identity (staging-row identity, not content identity) ---
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("source_file_sha256", sa.String(length=64), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("question_number_raw", sa.String(length=20), nullable=True),
        sa.Column("paper_code", sa.String(length=10), nullable=True),
        sa.Column("identity_key", sa.String(length=160), nullable=False),
        # --- exam / paper provenance ---
        sa.Column("exam_year", sa.Integer(), nullable=True),
        sa.Column("exam_name", sa.String(length=120), nullable=True),
        sa.Column("subject", sa.String(length=40), nullable=True),
        sa.Column("doc_kind", sa.String(length=40), nullable=False),  # RAW_QUESTION_PAPER | ANALYSIS_WITH_SOLUTIONS | OTHER
        # --- extracted content ---
        sa.Column("stem_text", sa.Text(), nullable=True),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("answer_raw", sa.String(length=20), nullable=True),
        sa.Column("explanation_text", sa.Text(), nullable=True),
        sa.Column("raw_block_text", sa.Text(), nullable=True),
        # --- confidence / status tracking ---
        sa.Column("extraction_status", sa.String(length=20), nullable=False),  # COMPLETE | PARTIAL | NEEDS_REVIEW
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("review_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("has_image_reference", sa.Boolean(), nullable=False, server_default="false"),
        # --- bookkeeping ---
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("pipeline_version", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_key", name="uq_pyq_image_staging_questions_identity_key"),
        schema="pyq_image_staging",
    )
    op.create_index(
        "ix_pyq_image_staging_questions_source_file",
        "questions",
        ["source_file"],
        schema="pyq_image_staging",
    )
    op.create_index(
        "ix_pyq_image_staging_questions_status",
        "questions",
        ["extraction_status"],
        schema="pyq_image_staging",
    )

    op.create_table(
        "images",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=True),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("source_file_sha256", sa.String(length=64), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("image_index_on_page", sa.Integer(), nullable=False),
        sa.Column("identity_key", sa.String(length=160), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.Column("image_format", sa.String(length=10), nullable=True),
        # --- association to a question (never forced) ---
        sa.Column("association_confidence", sa.String(length=20), nullable=False),  # NONE | LOW | MEDIUM | HIGH
        sa.Column("association_basis", sa.Text(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_key", name="uq_pyq_image_staging_images_identity_key"),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["pyq_image_staging.questions.id"],
            name="fk_pyq_image_staging_images_question_id",
            ondelete="SET NULL",
        ),
        schema="pyq_image_staging",
    )
    op.create_index(
        "ix_pyq_image_staging_images_question_id",
        "images",
        ["question_id"],
        schema="pyq_image_staging",
    )
    op.create_index(
        "ix_pyq_image_staging_images_source_file",
        "images",
        ["source_file"],
        schema="pyq_image_staging",
    )


def downgrade() -> None:
    op.drop_index("ix_pyq_image_staging_images_source_file", table_name="images", schema="pyq_image_staging")
    op.drop_index("ix_pyq_image_staging_images_question_id", table_name="images", schema="pyq_image_staging")
    op.drop_table("images", schema="pyq_image_staging")
    op.drop_index("ix_pyq_image_staging_questions_status", table_name="questions", schema="pyq_image_staging")
    op.drop_index("ix_pyq_image_staging_questions_source_file", table_name="questions", schema="pyq_image_staging")
    op.drop_table("questions", schema="pyq_image_staging")
    op.execute("DROP SCHEMA IF EXISTS pyq_image_staging CASCADE")
