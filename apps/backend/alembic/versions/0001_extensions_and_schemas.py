"""Extensions and schemas foundation

Revision ID: 0001
Revises:
Create Date: 2026-08-01

"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = ["identity", "academic", "cms", "assessment", "ai", "analytics", "commerce", "system"]


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    # pgcrypto / vector are enabled separately once the local Postgres install
    # supports them (see database/setup.md) — not required for Sprint 0-2.

    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")


def downgrade() -> None:
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
