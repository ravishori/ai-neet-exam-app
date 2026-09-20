"""Identity geo master: states + cities + user FKs; widen state_code.

Revision ID: f7b2c3d4e5f6
Revises: e6a1b2c3d4e5
Create Date: 2026-09-15

Creates normalized State/City master tables and the two FK columns on
``identity.users`` that reference them. Data population lives in
``app.modules.identity.geo_seed.seed_geo_master`` (invoked from
``seed_identity`` on fresh test databases, and can be run standalone via
``python -m app.modules.identity.geo_seed`` on dev/prod). Keeping the
~300-row seed out of the migration file keeps the migration lean and lets
the source-of-truth JSON be regenerated from Cities-List.xlsx without a
new Alembic revision.

Also widens ``users.state_code`` from VARCHAR(4) to VARCHAR(64) because the
authoritative source uses full-name-derived slugs (e.g. ``ANDHRA_PRADESH``)
rather than ISO 3166-2:IN 2-letter codes. Existing rows with values like
``"KA"`` still fit and are not rewritten by this migration.
"""

import sqlalchemy as sa

from alembic import op

revision = "f7b2c3d4e5f6"
down_revision = "e6a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "states",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("code", name="uq_identity_states_code"),
        sa.UniqueConstraint("name", name="uq_identity_states_name"),
        schema="identity",
    )
    op.create_table(
        "cities",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "state_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.states.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("state_id", "name", name="uq_identity_cities_state_name"),
        schema="identity",
    )
    op.create_index("ix_identity_cities_state_id", "cities", ["state_id"], schema="identity")
    op.create_index("ix_identity_cities_name", "cities", ["name"], schema="identity")

    # Widen state_code so the new master-derived slugs fit. Existing 2-letter
    # values (from prior task) still validate; no rewrite required.
    op.alter_column(
        "users",
        "state_code",
        existing_type=sa.String(length=4),
        type_=sa.String(length=64),
        existing_nullable=True,
        schema="identity",
    )

    op.add_column(
        "users",
        sa.Column(
            "state_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.states.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        schema="identity",
    )
    op.add_column(
        "users",
        sa.Column(
            "city_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.cities.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        schema="identity",
    )
    op.create_index("ix_identity_users_state_id", "users", ["state_id"], schema="identity")
    op.create_index("ix_identity_users_city_id", "users", ["city_id"], schema="identity")


def downgrade() -> None:
    op.drop_index("ix_identity_users_city_id", table_name="users", schema="identity")
    op.drop_index("ix_identity_users_state_id", table_name="users", schema="identity")
    op.drop_column("users", "city_id", schema="identity")
    op.drop_column("users", "state_id", schema="identity")
    op.alter_column(
        "users",
        "state_code",
        existing_type=sa.String(length=64),
        type_=sa.String(length=4),
        existing_nullable=True,
        schema="identity",
    )
    op.drop_index("ix_identity_cities_name", table_name="cities", schema="identity")
    op.drop_index("ix_identity_cities_state_id", table_name="cities", schema="identity")
    op.drop_table("cities", schema="identity")
    op.drop_table("states", schema="identity")
