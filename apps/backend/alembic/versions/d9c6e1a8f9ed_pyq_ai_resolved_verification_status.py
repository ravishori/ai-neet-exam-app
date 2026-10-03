"""pyq: add AI_RESOLVED to answer_assertions.verification_status

Distinguishes a one-pass Gemini-generated answer (no second AI verification
pass, no routine manual QC — see docs/quality/pyq-gemini-one-pass-resolution-*.md)
from VERIFIED (the existing deterministic NCERT-grounding resolver, and any
future independently-verified answer) and DISPUTED (conflicting evidence).
AI_RESOLVED must never be presented as independently NCERT-verified.

Additive only: existing ASSERTED/VERIFIED/DISPUTED rows and the CHECK
constraint's prior behavior for those three values are unchanged.

Revision ID: d9c6e1a8f9ed
Revises: e2f3a4b5c6d7
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op

revision = "d9c6e1a8f9ed"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None

_OLD_CONSTRAINT = "ck_pyq_answer_assertions_status"
_OLD_VALUES = ("ASSERTED", "VERIFIED", "DISPUTED")
_NEW_VALUES = ("ASSERTED", "VERIFIED", "DISPUTED", "AI_RESOLVED")


def upgrade() -> None:
    op.drop_constraint(_OLD_CONSTRAINT, "answer_assertions", schema="pyq", type_="check")
    op.create_check_constraint(
        _OLD_CONSTRAINT,
        "answer_assertions",
        "verification_status IN ('ASSERTED', 'VERIFIED', 'DISPUTED', 'AI_RESOLVED')",
        schema="pyq",
    )


def downgrade() -> None:
    op.drop_constraint(_OLD_CONSTRAINT, "answer_assertions", schema="pyq", type_="check")
    op.create_check_constraint(
        _OLD_CONSTRAINT,
        "answer_assertions",
        "verification_status IN ('ASSERTED', 'VERIFIED', 'DISPUTED')",
        schema="pyq",
    )
