"""Wave C identity security: OTP challenges, TOTP, recovery codes.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret_encrypted", sa.Text(), nullable=True), schema="identity")
    op.add_column(
        "users",
        sa.Column("totp_enabled", sa.Boolean(), server_default="false", nullable=False),
        schema="identity",
    )
    op.add_column(
        "users",
        sa.Column("totp_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        schema="identity",
    )

    op.create_table(
        "otp_challenges",
        sa.Column("destination", sa.String(320), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        schema="identity",
    )
    op.create_index("ix_otp_challenges_destination", "otp_challenges", ["destination"], schema="identity")

    op.create_table(
        "totp_recovery_codes",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        schema="identity",
    )
    op.create_index("ix_totp_recovery_codes_user_id", "totp_recovery_codes", ["user_id"], schema="identity")


def downgrade() -> None:
    op.drop_table("totp_recovery_codes", schema="identity")
    op.drop_table("otp_challenges", schema="identity")
    op.drop_column("users", "totp_confirmed_at", schema="identity")
    op.drop_column("users", "totp_enabled", schema="identity")
    op.drop_column("users", "totp_secret_encrypted", schema="identity")
