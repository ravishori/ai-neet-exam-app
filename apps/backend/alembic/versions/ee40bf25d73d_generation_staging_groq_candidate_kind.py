"""Generation staging — Groq-factory candidate_kind + evidence relocation flag

Revision ID: ee40bf25d73d
Revises: d8e9f0a1b2c3
Create Date: 2026-10-11 00:00:00.000000

Additive-only migration for MCQ-FACTORY-GROQ-001. Adds two NULLABLE
columns to the existing ``generation_staging.candidates`` table (created
by f8a1b2c3d4e5_generation_staging_candidates.py) so the new Groq-backed
NEW QUESTION GENERATION pipeline can reuse that same staging table
instead of creating a parallel one:

- ``candidate_kind``: distinguishes a freshly-GENERATED practice question
  (``GENERATED_PRACTICE``) from a HISTORICAL PYQ row that happens to also
  be staged here (``HISTORICAL_PYQ``). NULL means "not set" (pre-existing
  rows / other producers), never a default that would mislabel old data.
- ``evidence_relocation_confirmed``: True only after
  ``validators.verify_source_evidence_relocatable`` has independently
  re-found the candidate's quoted source snippet inside the actually
  extracted PDF text. NULL means "not checked yet" — this column is never
  set True by anything other than that explicit re-location check, and is
  never read as an implicit pass.

No existing column is altered, renamed, or dropped. No index is added
(these are label/flag columns, not expected to be queried at this
volume). This migration is written but is NOT run against any database by
this task — see docs/quality/neet_mcq_factory_implementation_20261011.md.
"""

from alembic import op
import sqlalchemy as sa

revision = "ee40bf25d73d"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("candidate_kind", sa.String(length=40), nullable=True),
        schema="generation_staging",
    )
    op.add_column(
        "candidates",
        sa.Column("evidence_relocation_confirmed", sa.Boolean(), nullable=True),
        schema="generation_staging",
    )


def downgrade() -> None:
    op.drop_column("candidates", "evidence_relocation_confirmed", schema="generation_staging")
    op.drop_column("candidates", "candidate_kind", schema="generation_staging")
