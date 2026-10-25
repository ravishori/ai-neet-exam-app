"""Study Plan improvements: is_fallback column + ai_requests index for the
spend-cap query.

Revision ID: b6d8a76b8479
Revises: 9690a6419434
Create Date: 2026-10-25
"""

import sqlalchemy as sa

from alembic import op

revision = "b6d8a76b8479"
down_revision = "9690a6419434"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "study_plans",
        sa.Column("is_fallback", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema="ai",
    )
    # Supports app.modules.ai.spend_guard.reserve_spend's
    # SUM(estimated_cost_usd) WHERE agent_type = ... AND created_at >= ...
    # query, which runs on every Study Planner AI call attempt.
    op.create_index(
        "ix_ai_requests_agent_type_created_at",
        "ai_requests",
        ["agent_type", "created_at"],
        schema="ai",
    )


def downgrade() -> None:
    op.drop_index("ix_ai_requests_agent_type_created_at", table_name="ai_requests", schema="ai")
    op.drop_column("study_plans", "is_fallback", schema="ai")
