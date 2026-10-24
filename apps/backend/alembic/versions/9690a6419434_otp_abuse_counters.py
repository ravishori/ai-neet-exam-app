"""OTP abuse counters: persistent, non-resetting verification-attempt
tracking per (destination, purpose) -- closes the gap where requesting a
new OTP code reset the per-challenge attempt counter back to 0.

Revision ID: 9690a6419434
Revises: d4f5a6b7c8d9
Create Date: 2026-10-24
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "9690a6419434"
down_revision = "d4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "otp_abuse_counters",
        sa.Column("destination", sa.String(320), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        schema="identity",
    )
    op.create_index("ix_otp_abuse_counters_destination", "otp_abuse_counters", ["destination"], schema="identity")
    op.create_unique_constraint(
        "uq_otp_abuse_counters_destination_purpose", "otp_abuse_counters", ["destination", "purpose"], schema="identity"
    )


def downgrade() -> None:
    op.drop_table("otp_abuse_counters", schema="identity")
