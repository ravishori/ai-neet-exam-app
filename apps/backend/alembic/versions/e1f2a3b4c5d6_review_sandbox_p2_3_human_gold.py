"""P2.3 Human Gold Review Sandbox — isolated review_sandbox schema

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-02 12:00:00.000000

Does NOT modify production MCQ / cms.content_items tables.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS review_sandbox")

    op.create_table(
        "sessions",
        sa.Column("session_name", sa.String(length=200), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviewed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("partial_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_check_status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("protected_checksums", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        schema="review_sandbox",
    )
    op.create_index("ix_review_sandbox_sessions_status", "sessions", ["status"], schema="review_sandbox")
    op.create_index("ix_review_sandbox_sessions_expires_at", "sessions", ["expires_at"], schema="review_sandbox")

    op.create_table(
        "uploads",
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("validation_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["review_sandbox.sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="review_sandbox",
    )

    op.create_table(
        "questions",
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("source_question_id", sa.String(length=80), nullable=False),
        sa.Column("subject", sa.String(length=40), nullable=False),
        sa.Column("class_level", sa.String(length=10), nullable=True),
        sa.Column("chapter", sa.String(length=40), nullable=True),
        sa.Column("topic", sa.String(length=200), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("question_type", sa.String(length=40), nullable=True),
        sa.Column("original_question", sa.Text(), nullable=False),
        sa.Column("original_option_a", sa.Text(), nullable=False),
        sa.Column("original_option_b", sa.Text(), nullable=False),
        sa.Column("original_option_c", sa.Text(), nullable=False),
        sa.Column("original_option_d", sa.Text(), nullable=False),
        sa.Column("original_proposed_answer", sa.String(length=10), nullable=False),
        sa.Column("original_ncert_source", sa.Text(), nullable=True),
        sa.Column("original_validator_verdict", sa.String(length=40), nullable=True),
        sa.Column("original_validation_status_before_r1", sa.String(length=40), nullable=True),
        sa.Column("original_validation_status_after_r1", sa.String(length=40), nullable=True),
        sa.Column("original_r1_validator_provider", sa.String(length=40), nullable=True),
        sa.Column("preaudit_priority", sa.String(length=20), nullable=True),
        sa.Column("preaudit_verdict", sa.String(length=40), nullable=True),
        sa.Column("preaudit_reason", sa.Text(), nullable=True),
        sa.Column("preaudit_recommended_action", sa.String(length=60), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["review_sandbox.sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "source_question_id", name="uq_review_sandbox_questions_session_qid"),
        schema="review_sandbox",
    )
    op.create_index("ix_review_sandbox_questions_session", "questions", ["session_id"], schema="review_sandbox")
    op.create_index("ix_review_sandbox_questions_priority", "questions", ["preaudit_priority"], schema="review_sandbox")

    op.create_table(
        "human_reviews",
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("human_stem", sa.Text(), nullable=True),
        sa.Column("human_option_a", sa.Text(), nullable=True),
        sa.Column("human_option_b", sa.Text(), nullable=True),
        sa.Column("human_option_c", sa.Text(), nullable=True),
        sa.Column("human_option_d", sa.Text(), nullable=True),
        sa.Column("human_answer", sa.String(length=10), nullable=True),
        sa.Column("human_explanation", sa.Text(), nullable=True),
        sa.Column("human_ncert_support", sa.String(length=40), nullable=True),
        sa.Column("human_ambiguity", sa.String(length=20), nullable=True),
        sa.Column("human_duplicate", sa.String(length=30), nullable=True),
        sa.Column("human_difficulty", sa.String(length=20), nullable=True),
        sa.Column("human_neet_suitability", sa.String(length=40), nullable=True),
        sa.Column("human_overall", sa.String(length=20), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("review_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["review_sandbox.questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", name="uq_review_sandbox_human_reviews_question"),
        schema="review_sandbox",
    )

    op.create_table(
        "ai_reviews",
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("ai_answer_check", sa.String(length=30), nullable=True),
        sa.Column("ai_answer_confidence", sa.Float(), nullable=True),
        sa.Column("ai_calculation_check", sa.String(length=30), nullable=True),
        sa.Column("ai_calculated_answer", sa.String(length=10), nullable=True),
        sa.Column("ai_stem_check", sa.Text(), nullable=True),
        sa.Column("ai_option_quality", sa.String(length=20), nullable=True),
        sa.Column("ai_distractor_analysis", sa.Text(), nullable=True),
        sa.Column("ai_ncert_support", sa.String(length=40), nullable=True),
        sa.Column("ai_ncert_evidence", sa.Text(), nullable=True),
        sa.Column("ai_scientific_check", sa.Text(), nullable=True),
        sa.Column("ai_assertion_reason_check", sa.Text(), nullable=True),
        sa.Column("ai_duplicate_check", sa.String(length=40), nullable=True),
        sa.Column("ai_question_type_check", sa.String(length=40), nullable=True),
        sa.Column("ai_difficulty", sa.String(length=20), nullable=True),
        sa.Column("ai_neet_suitability", sa.String(length=40), nullable=True),
        sa.Column("ai_overall", sa.String(length=30), nullable=True),
        sa.Column("ai_reason", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("check_status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["review_sandbox.questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", name="uq_review_sandbox_ai_reviews_question"),
        schema="review_sandbox",
    )

    op.create_table(
        "audit_events",
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("question_id", sa.UUID(), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["review_sandbox.sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["review_sandbox.questions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="review_sandbox",
    )
    op.create_index("ix_review_sandbox_audit_session", "audit_events", ["session_id"], schema="review_sandbox")


def downgrade() -> None:
    op.drop_index("ix_review_sandbox_audit_session", table_name="audit_events", schema="review_sandbox")
    op.drop_table("audit_events", schema="review_sandbox")
    op.drop_table("ai_reviews", schema="review_sandbox")
    op.drop_table("human_reviews", schema="review_sandbox")
    op.drop_index("ix_review_sandbox_questions_priority", table_name="questions", schema="review_sandbox")
    op.drop_index("ix_review_sandbox_questions_session", table_name="questions", schema="review_sandbox")
    op.drop_table("questions", schema="review_sandbox")
    op.drop_table("uploads", schema="review_sandbox")
    op.drop_index("ix_review_sandbox_sessions_expires_at", table_name="sessions", schema="review_sandbox")
    op.drop_index("ix_review_sandbox_sessions_status", table_name="sessions", schema="review_sandbox")
    op.drop_table("sessions", schema="review_sandbox")
    op.execute("DROP SCHEMA IF EXISTS review_sandbox CASCADE")
