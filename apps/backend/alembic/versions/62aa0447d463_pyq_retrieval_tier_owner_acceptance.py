"""pyq: add retrieval_match_tier and owner-acceptance fields to pyq.questions

Represents retrieval-context eligibility (measure C: "did a matching NCERT
knowledge unit get found for this question's retrieval context", NOT
measure E: "is the answer independently verified") and the project owner's
explicit launch-prioritization acceptance of the relaxed-threshold
candidate pool. Deliberately separate from pyq.answer_assertions
.verification_status (ASSERTED/VERIFIED/DISPUTED/AI_RESOLVED), which
represents answer-resolution outcomes, not retrieval-context availability
or owner acceptance of a candidate pool -- these must never be conflated
(see docs/quality/pyq-8159-ncert-retrieval-enablement-2026-10-01.md).

Additive only, fully backward compatible:
  - retrieval_match_tier: nullable, defaults to NULL for every existing row
    (meaning "not yet computed"), never retroactively implies anything
    about existing ANSWER_VERIFIED/ANSWER_CONFLICT rows.
  - ncert_owner_accepted: NOT NULL DEFAULT false -- every existing row
    becomes explicitly "not accepted" rather than ambiguous; this is the
    correct default since no prior row was ever marked as part of this new
    acceptance policy.
  - ncert_owner_accepted_at: nullable, set only when ncert_owner_accepted
    is flipped true.

ncert_owner_accepted is NEVER written as a side effect of any answer
resolution step; it is set only by the dedicated, separately-invoked
retrieval-enablement script, independent of pyq.answer_assertions writes.

Revision ID: 62aa0447d463
Revises: d9c6e1a8f9ed
Create Date: 2026-10-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "62aa0447d463"
down_revision = "d9c6e1a8f9ed"
branch_labels = None
depends_on = None

_TIER_VALUES = ("STRICT_MATCH", "RELAXED_MATCH", "NONE")


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("retrieval_match_tier", sa.String(length=32), nullable=True),
        schema="pyq",
    )
    op.create_check_constraint(
        "ck_pyq_questions_retrieval_match_tier",
        "questions",
        f"retrieval_match_tier IS NULL OR retrieval_match_tier IN {_TIER_VALUES}",
        schema="pyq",
    )
    op.add_column(
        "questions",
        sa.Column("ncert_owner_accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="pyq",
    )
    op.add_column(
        "questions",
        sa.Column("ncert_owner_accepted_at", sa.DateTime(timezone=True), nullable=True),
        schema="pyq",
    )


def downgrade() -> None:
    op.drop_column("questions", "ncert_owner_accepted_at", schema="pyq")
    op.drop_column("questions", "ncert_owner_accepted", schema="pyq")
    op.drop_constraint("ck_pyq_questions_retrieval_match_tier", "questions", schema="pyq", type_="check")
    op.drop_column("questions", "retrieval_match_tier", schema="pyq")
