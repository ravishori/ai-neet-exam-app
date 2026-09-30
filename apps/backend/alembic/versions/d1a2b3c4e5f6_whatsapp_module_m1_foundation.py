"""whatsapp module: M1 foundation — identities, messages, study_sessions

New whatsapp schema and three tables only, per
docs/architecture/WHATSAPP_BOT_ARCHITECTURE.md and
docs/decisions/ADR-WHATSAPP-PROVIDER-ABSTRACTION.md. Columns are
provider-neutral (provider/provider_message_id/external_user_id) —
never a provider-specific column name. Does not touch any existing
schema/table.

Revision ID: d1a2b3c4e5f6
Revises: a3f7c8d1e2b4
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d1a2b3c4e5f6"
down_revision = "a3f7c8d1e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS whatsapp")

    op.create_table(
        "identities",
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
            sa.ForeignKey("identity.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("external_user_id", sa.String(120), nullable=True),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        schema="whatsapp",
    )
    op.create_index("ix_whatsapp_identities_user_id", "identities", ["user_id"], schema="whatsapp")
    op.create_index("ix_whatsapp_identities_phone_e164", "identities", ["phone_e164"], schema="whatsapp")
    op.create_unique_constraint(
        "uq_whatsapp_identities_provider_external_user_id",
        "identities",
        ["provider", "external_user_id"],
        schema="whatsapp",
    )
    op.create_unique_constraint(
        "uq_whatsapp_identities_provider_phone_e164",
        "identities",
        ["provider", "phone_e164"],
        schema="whatsapp",
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "whatsapp_identity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("whatsapp.identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_message_id", sa.String(120), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("message_type", sa.String(20), nullable=False, server_default="text"),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("intent", sa.String(30), nullable=True),
        sa.Column("provider_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.CheckConstraint("direction IN ('inbound','outbound')", name="ck_whatsapp_messages_direction"),
        schema="whatsapp",
    )
    op.create_index("ix_whatsapp_messages_whatsapp_identity_id", "messages", ["whatsapp_identity_id"], schema="whatsapp")
    # Durable idempotency guarantee — a redelivered webhook for the same
    # (provider, provider_message_id) must fail this constraint, not
    # silently create a second row.
    op.create_unique_constraint(
        "uq_whatsapp_messages_provider_message_id",
        "messages",
        ["provider", "provider_message_id"],
        schema="whatsapp",
    )

    op.create_table(
        "study_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "whatsapp_identity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("whatsapp.identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment.assessments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "attempt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment.attempts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "current_question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cms.content_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("current_position", sa.Integer, nullable=True),
        sa.Column("context_json", postgresql.JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        schema="whatsapp",
    )
    op.create_index(
        "ix_whatsapp_study_sessions_whatsapp_identity_id",
        "study_sessions",
        ["whatsapp_identity_id"],
        schema="whatsapp",
    )


def downgrade() -> None:
    op.drop_index("ix_whatsapp_study_sessions_whatsapp_identity_id", table_name="study_sessions", schema="whatsapp")
    op.drop_table("study_sessions", schema="whatsapp")

    op.drop_constraint("uq_whatsapp_messages_provider_message_id", "messages", schema="whatsapp", type_="unique")
    op.drop_index("ix_whatsapp_messages_whatsapp_identity_id", table_name="messages", schema="whatsapp")
    op.drop_table("messages", schema="whatsapp")

    op.drop_constraint("uq_whatsapp_identities_provider_phone_e164", "identities", schema="whatsapp", type_="unique")
    op.drop_constraint("uq_whatsapp_identities_provider_external_user_id", "identities", schema="whatsapp", type_="unique")
    op.drop_index("ix_whatsapp_identities_phone_e164", table_name="identities", schema="whatsapp")
    op.drop_index("ix_whatsapp_identities_user_id", table_name="identities", schema="whatsapp")
    op.drop_table("identities", schema="whatsapp")

    op.execute("DROP SCHEMA IF EXISTS whatsapp CASCADE")
