"""Identity profile: mobile (E.164), state, city, must_change_password.

Revision ID: e6a1b2c3d4e5
Revises: c1d2e3f4a5b6
Create Date: 2026-09-15

Adds the columns required for mobile-OTP login and the mandatory
State/City fields, plus the ``must_change_password`` gate for the
auto-issued initial credential.

All new columns are nullable and default to null / false so existing rows
migrate without an explicit backfill. Enforcement of "required" for new
registrations and profile updates happens at the service layer — the DB
does NOT hard-require the fields, which keeps historical users usable
until they complete their profile.

The uniqueness contract is expressed as a partial unique index on
``lower(mobile_e164)`` restricted to non-deleted rows; NULL values do not
collide, so unfinished profiles remain writeable.
"""

import sqlalchemy as sa

from alembic import op

revision = "e6a1b2c3d4e5"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("mobile_e164", sa.String(length=20), nullable=True),
        schema="identity",
    )
    op.add_column(
        "users",
        sa.Column("state_code", sa.String(length=4), nullable=True),
        schema="identity",
    )
    op.add_column(
        "users",
        sa.Column("city_name", sa.String(length=120), nullable=True),
        schema="identity",
    )
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        schema="identity",
    )

    # Partial unique index — enforces one active user per mobile number,
    # ignoring soft-deleted rows and null values. Case-insensitive to prevent
    # e.g. "+91..." variants smuggling through when combined with dial-in codes.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_identity_users_mobile_e164_active
        ON identity.users (lower(mobile_e164))
        WHERE mobile_e164 IS NOT NULL AND deleted_at IS NULL
        """
    )
    op.create_index(
        "ix_identity_users_state_city",
        "users",
        ["state_code", "city_name"],
        schema="identity",
    )


def downgrade() -> None:
    op.drop_index("ix_identity_users_state_city", table_name="users", schema="identity")
    op.execute("DROP INDEX IF EXISTS identity.uq_identity_users_mobile_e164_active")
    op.drop_column("users", "must_change_password", schema="identity")
    op.drop_column("users", "city_name", schema="identity")
    op.drop_column("users", "state_code", schema="identity")
    op.drop_column("users", "mobile_e164", schema="identity")
