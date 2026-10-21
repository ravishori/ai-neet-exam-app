"""PYQ staging subject/chapter classification columns

Revision ID: b2c3d4e5f6a7
Revises: c45cfde6bfcf
Create Date: 2026-10-10 00:00:00.000000

Adds NEW, nullable columns only to `pyq_image_staging.questions` for a
deterministic (no AI, no paid API) keyword/phrase classification pass
against the NEET_UG_2026 curriculum taxonomy. The original `subject`
column is NEVER written to by this migration or the classification
script that populates these columns -- it is preserved exactly as
extracted (including NULL), per the audit requirement that proposed
corrections never overwrite original extracted fields.

- proposed_subject: Physics / Chemistry / Botany / Zoology (never the
  original `subject` value verbatim unless independently re-derived)
- proposed_chapter_topic: full taxonomy path string, e.g.
  "Biology > Unit 05: Human Physiology (Zoology) > Excretory Products..."
- classification_confidence: HIGH / MEDIUM / MANUAL_REVIEW_REQUIRED
- classification_evidence: free-text explanation of what matched
  (taxonomy phrase / broad-vocabulary keyword / reviewer judgment /
  filename supporting signal), for human audit
- classification_status: CLASSIFIED / MANUAL_REVIEW_REQUIRED
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d8e9f0a1b2c3"
down_revision = "c45cfde6bfcf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("proposed_subject", sa.String(length=40), nullable=True),
        schema="pyq_image_staging",
    )
    op.add_column(
        "questions",
        sa.Column("proposed_chapter_topic", sa.Text(), nullable=True),
        schema="pyq_image_staging",
    )
    op.add_column(
        "questions",
        sa.Column("classification_confidence", sa.String(length=30), nullable=True),
        schema="pyq_image_staging",
    )
    op.add_column(
        "questions",
        sa.Column("classification_evidence", sa.Text(), nullable=True),
        schema="pyq_image_staging",
    )
    op.add_column(
        "questions",
        sa.Column("classification_status", sa.String(length=30), nullable=True),
        schema="pyq_image_staging",
    )
    op.create_index(
        "ix_pyq_image_staging_questions_classification_status",
        "questions",
        ["classification_status"],
        schema="pyq_image_staging",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pyq_image_staging_questions_classification_status",
        table_name="questions",
        schema="pyq_image_staging",
    )
    op.drop_column("questions", "classification_status", schema="pyq_image_staging")
    op.drop_column("questions", "classification_evidence", schema="pyq_image_staging")
    op.drop_column("questions", "classification_confidence", schema="pyq_image_staging")
    op.drop_column("questions", "proposed_chapter_topic", schema="pyq_image_staging")
    op.drop_column("questions", "proposed_subject", schema="pyq_image_staging")
