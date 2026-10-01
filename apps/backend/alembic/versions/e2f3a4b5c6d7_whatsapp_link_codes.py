"""whatsapp: one-time account-linking codes

Dedicated table for the secure M2-A WhatsApp account-linking flow — see
docs/whatsapp/WHATSAPP_M2A_ACCOUNT_LINKING.md. Additive only: one new
table in the existing whatsapp schema, no change to any existing table.

Revision ID: e2f3a4b5c6d7
Revises: d1a2b3c4e5f6
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "d1a2b3c4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "link_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="5"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "whatsapp_identity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("whatsapp.identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema="whatsapp",
    )
    op.create_index("ix_whatsapp_link_codes_user_id", "link_codes", ["user_id"], schema="whatsapp")


def downgrade() -> None:
    op.drop_index("ix_whatsapp_link_codes_user_id", table_name="link_codes", schema="whatsapp")
    op.drop_table("link_codes", schema="whatsapp")
