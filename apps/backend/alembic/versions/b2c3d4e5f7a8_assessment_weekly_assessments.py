"""Weekly Assessment scheduling + blueprint.

Adds:
- ``assessment.weekly_assessments`` — the recurring, scheduled paper.
- ``assessment.weekly_assessment_blueprints`` — subject × quota rows.
- ``assessment.assessments.weekly_assessment_id`` — nullable FK linking a
  generated assessment back to the weekly it was materialised for.

The engine still lives in ``AssessmentService``; a weekly assessment is a
scheduling + blueprint envelope, not a second exam engine.

Revision ID: b2c3d4e5f7a8
Revises: a1b2c3d4e5f7
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f7a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_assessments",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("assessment_key", sa.String(80), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("marks_per_question", sa.Numeric(5, 2), nullable=False, server_default="4"),
        sa.Column("negative_marks_per_question", sa.Numeric(5, 2), nullable=False, server_default="1"),
        sa.Column("attempt_limit", sa.Integer, nullable=False, server_default="1"),
        # cumulative_weight: {"current_syllabus_pct": 75, "previous_syllabus_pct": 25}
        sa.Column("cumulative_weight", sa.dialects.postgresql.JSONB, nullable=True),
        # difficulty_distribution: {"easy": 0.3, "medium": 0.5, "hard": 0.2}
        sa.Column("difficulty_distribution", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("published", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("identity.users.id"), nullable=False),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("identity.users.id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_weekly_window_valid"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_weekly_duration_positive"),
        sa.CheckConstraint("attempt_limit >= 1", name="ck_weekly_attempt_limit_positive"),
        schema="assessment",
    )
    op.create_index(
        "ix_weekly_assessments_published_starts_at",
        "weekly_assessments",
        ["published", "starts_at"],
        schema="assessment",
    )

    op.create_table(
        "weekly_assessment_blueprints",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "weekly_assessment_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment.weekly_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("academic.subjects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("question_count", sa.Integer, nullable=False),
        # Optional scope narrowing: list of chapter/topic IDs to constrain the
        # subject-level pool. Empty/null => whole subject.
        sa.Column("chapter_ids", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("topic_ids", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("order_no", sa.Integer, nullable=False),
        sa.CheckConstraint("question_count >= 1", name="ck_weekly_bp_count_positive"),
        sa.UniqueConstraint("weekly_assessment_id", "subject_id", name="uq_weekly_bp_subject"),
        schema="assessment",
    )

    # Link a materialised assessment back to its weekly.
    op.add_column(
        "assessments",
        sa.Column(
            "weekly_assessment_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment.weekly_assessments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema="assessment",
    )
    op.create_index(
        "ix_assessments_weekly_assessment_id",
        "assessments",
        ["weekly_assessment_id"],
        schema="assessment",
    )


def downgrade() -> None:
    op.drop_index("ix_assessments_weekly_assessment_id", table_name="assessments", schema="assessment")
    op.drop_column("assessments", "weekly_assessment_id", schema="assessment")
    op.drop_table("weekly_assessment_blueprints", schema="assessment")
    op.drop_index("ix_weekly_assessments_published_starts_at", table_name="weekly_assessments", schema="assessment")
    op.drop_table("weekly_assessments", schema="assessment")
