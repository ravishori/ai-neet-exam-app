"""academic.subjects.neet_weightage_percent + NEET defaults.

Mirrors the existing ``academic.chapters.neet_weightage_percent`` column
one level up so the assessment engine can shape papers by
subject-weightage without hardcoded quotas.

Populates the four seeded NEET subjects with the official 25/25/25/25
percent split (Physics 25, Chemistry 25, Botany 25, Zoology 25 —
Biology bucket = 50). Legacy rows for any other subject remain NULL.

Revision ID: d4e5f7a8b9c0
Revises: c3d4e5f7a8b9
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d4e5f7a8b9c0"
down_revision = "c3d4e5f7a8b9"
branch_labels = None
depends_on = None


DEFAULTS = {
    "PHYSICS": 25.0,
    "CHEMISTRY": 25.0,
    "BOTANY": 25.0,
    "ZOOLOGY": 25.0,
}


def upgrade() -> None:
    op.add_column(
        "subjects",
        sa.Column("neet_weightage_percent", sa.Numeric(4, 1), nullable=True),
        schema="academic",
    )
    for code, pct in DEFAULTS.items():
        op.execute(
            sa.text(
                "UPDATE academic.subjects SET neet_weightage_percent = :pct "
                "WHERE code = :code AND neet_weightage_percent IS NULL"
            ).bindparams(pct=pct, code=code)
        )


def downgrade() -> None:
    op.drop_column("subjects", "neet_weightage_percent", schema="academic")
