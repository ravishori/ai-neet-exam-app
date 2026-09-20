"""identity.users password_changed_at (90-day password-age reminder).

Adds a nullable ``password_changed_at TIMESTAMPTZ``. NULL means "unknown"
for pre-existing rows — application logic treats NULL as "no reminder",
so existing users are never nagged based on data we do not have. New
registrations and future ``change_password`` / ``reset_password`` flows
write the current timestamp.

Revision ID: a1b2c3d4e5f7
Revises: f7b2c3d4e5f6
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f7"
down_revision = "f7b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        schema="identity",
    )


def downgrade() -> None:
    op.drop_column("users", "password_changed_at", schema="identity")
