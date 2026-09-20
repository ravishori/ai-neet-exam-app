"""Weekly Revision — student-driven recommendation.

Adds ``assessment.weekly_revision_recommendations`` (idempotent per user
per ISO week) and a nullable FK ``assessment.assessments.weekly_revision_id``
so materialised attempts link back to the recommendation.

Institutional-mode ``weekly_assessments`` tables remain untouched.

Revision ID: c3d4e5f7a8b9
Revises: b2c3d4e5f7a8
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f7a8b9"
down_revision = "b2c3d4e5f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_revision_recommendations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("iso_year", sa.Integer, nullable=False),
        sa.Column("iso_week", sa.Integer, nullable=False),
        # Per-subject blueprint the recommender picked, e.g. [{"subject_id":..., "quota":15, "recent_chapter_ids":[...], "previous_chapter_ids":[...]}]
        sa.Column("blueprint", sa.dialects.postgresql.JSONB, nullable=False),
        # Human-facing rationale ("recent_chapters":[...], "weak_topics":[...], "cold_start":bool)
        sa.Column("reason", sa.dialects.postgresql.JSONB, nullable=False),
        # RECOMMENDED | IN_PROGRESS | COMPLETED | UNAVAILABLE
        sa.Column("status", sa.String(20), nullable=False, server_default="RECOMMENDED"),
        sa.Column("estimated_duration_minutes", sa.Integer, nullable=False, server_default="60"),
        sa.Column("marks_per_question", sa.Numeric(5, 2), nullable=False, server_default="4"),
        sa.Column("negative_marks_per_question", sa.Numeric(5, 2), nullable=False, server_default="1"),
        sa.Column("attempt_limit", sa.Integer, nullable=False, server_default="1"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("identity.users.id"), nullable=False),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("identity.users.id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("user_id", "iso_year", "iso_week", name="uq_weekly_revision_per_week"),
        schema="assessment",
    )

    op.add_column(
        "assessments",
        sa.Column(
            "weekly_revision_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment.weekly_revision_recommendations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema="assessment",
    )
    op.create_index(
        "ix_assessments_weekly_revision_id",
        "assessments",
        ["weekly_revision_id"],
        schema="assessment",
    )


def downgrade() -> None:
    op.drop_index("ix_assessments_weekly_revision_id", table_name="assessments", schema="assessment")
    op.drop_column("assessments", "weekly_revision_id", schema="assessment")
    op.drop_table("weekly_revision_recommendations", schema="assessment")
