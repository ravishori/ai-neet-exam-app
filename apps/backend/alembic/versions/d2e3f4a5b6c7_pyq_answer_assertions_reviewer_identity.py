"""pyq: add reviewer identity to answer_assertions

Additive only, all nullable. Backs the admin individual-question answer
review workflow: when a human reviewer saves a selected option via the
new review API, the written answer_assertions row (assertion_source=
'human_review') now carries who reviewed it, when, and what kind of
evidence backed the decision -- fields resolver/script-written rows
(assertion_source='ncert_grounded_resolver' etc.) simply leave null.

reviewer_user_id follows the same FK convention as pyq.qa_reviews.reviewer_id
(-> identity.users.id, ON DELETE RESTRICT: a reviewer's prior decisions must
not be silently orphaned if their account is later removed).

evidence_source_type is a short controlled vocabulary (not free text) so the
one-pass "unsupported manual pick" case can be distinguished unambiguously
from an identifiable official source, matching the existing ASSERTED vs.
VERIFIED distinction already encoded in verification_status.

Revision ID: d2e3f4a5b6c7
Revises: ee40bf25d73d
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "ee40bf25d73d"
branch_labels = None
depends_on = None

_EVIDENCE_SOURCE_TYPES = (
    "OFFICIAL_ANSWER_KEY",
    "TEXTBOOK_REFERENCE",
    "EXPERT_REVIEW",
    "OTHER",
)


def upgrade() -> None:
    op.add_column(
        "answer_assertions",
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="pyq",
    )
    op.add_column(
        "answer_assertions",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        schema="pyq",
    )
    op.add_column(
        "answer_assertions",
        sa.Column("evidence_source_type", sa.String(30), nullable=True),
        schema="pyq",
    )
    op.add_column(
        "answer_assertions",
        sa.Column("evidence_locator", sa.Text(), nullable=True),
        schema="pyq",
    )
    op.create_foreign_key(
        "fk_pyq_answer_assertions_reviewer_user_id",
        "answer_assertions",
        "users",
        ["reviewer_user_id"],
        ["id"],
        source_schema="pyq",
        referent_schema="identity",
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_pyq_answer_assertions_evidence_source_type",
        "answer_assertions",
        "evidence_source_type IS NULL OR evidence_source_type IN ('"
        + "','".join(_EVIDENCE_SOURCE_TYPES)
        + "')",
        schema="pyq",
    )
    op.create_index(
        "ix_pyq_answer_assertions_reviewer_user_id",
        "answer_assertions",
        ["reviewer_user_id"],
        schema="pyq",
    )


def downgrade() -> None:
    op.drop_index("ix_pyq_answer_assertions_reviewer_user_id", table_name="answer_assertions", schema="pyq")
    op.drop_constraint(
        "ck_pyq_answer_assertions_evidence_source_type", "answer_assertions", schema="pyq", type_="check"
    )
    op.drop_constraint(
        "fk_pyq_answer_assertions_reviewer_user_id", "answer_assertions", schema="pyq", type_="foreignkey"
    )
    op.drop_column("answer_assertions", "evidence_locator", schema="pyq")
    op.drop_column("answer_assertions", "evidence_source_type", schema="pyq")
    op.drop_column("answer_assertions", "reviewed_at", schema="pyq")
    op.drop_column("answer_assertions", "reviewer_user_id", schema="pyq")
