"""learning.student_scope_preferences — STRONG/NEUTRAL/WEAK per scope.

One row per (user, scope_type, scope_id). Scope may be SUBJECT, TOPIC,
or CONCEPT — always pointing at an existing row in the academic
hierarchy. This is a preference marker only; mastery calculations are
untouched.

Revision ID: e5f7a8b9c0d1
Revises: d4e5f7a8b9c0
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e5f7a8b9c0d1"
down_revision = "d4e5f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_scope_preferences",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SUBJECT | TOPIC | CONCEPT — validated at service layer against
        # the corresponding academic table.
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("scope_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        # STRONG | NEUTRAL | WEAK
        sa.Column("preference", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("identity.users.id"), nullable=False),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("identity.users.id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("user_id", "scope_type", "scope_id", name="uq_student_scope_pref"),
        sa.CheckConstraint(
            "scope_type IN ('SUBJECT','TOPIC','CONCEPT')", name="ck_student_scope_pref_type"
        ),
        sa.CheckConstraint(
            "preference IN ('STRONG','NEUTRAL','WEAK')", name="ck_student_scope_pref_value"
        ),
        schema="learning",
    )
    op.create_index(
        "ix_student_scope_pref_user",
        "student_scope_preferences",
        ["user_id"],
        schema="learning",
    )


def downgrade() -> None:
    op.drop_index("ix_student_scope_pref_user", table_name="student_scope_preferences", schema="learning")
    op.drop_table("student_scope_preferences", schema="learning")
