"""pyq: subject_classification_audit — minimal audit trail for the local
deterministic NCERT subject classifier (pyq_subject_classifier). Additive
only; no existing pyq.* objects are touched.

Revision ID: c1d2e3f4b5a6
Revises: b7c8d9e0f1a2
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4b5a6"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subject_classification_audit",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("question_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_subject", sa.String(30), nullable=True),
        sa.Column("new_subject", sa.String(30), nullable=True),
        sa.Column("classification_status", sa.String(20), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("classification_method", sa.String(40), nullable=False),
        sa.Column("ncert_source", sa.Text(), nullable=True),
        sa.Column("classifier_version", sa.String(40), nullable=False),
        sa.Column("classified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["pyq.questions.id"], ondelete="CASCADE"),
        schema="pyq",
    )
    op.create_index(
        "ix_pyq_subject_audit_question_id", "subject_classification_audit", ["question_id"], schema="pyq"
    )


def downgrade() -> None:
    op.drop_index("ix_pyq_subject_audit_question_id", table_name="subject_classification_audit", schema="pyq")
    op.drop_table("subject_classification_audit", schema="pyq")
