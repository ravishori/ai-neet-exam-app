"""FACTORY-P3.1: generation candidate provider lineage columns

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-01 08:00:00.000000

Adds provider/routing lineage only. Does not modify content_items or ECAEP.
"""

from alembic import op
import sqlalchemy as sa

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_candidates",
        sa.Column("provider", sa.String(length=40), nullable=True),
        schema="cms",
    )
    op.add_column(
        "generation_candidates",
        sa.Column("routing_policy", sa.String(length=120), nullable=True),
        schema="cms",
    )
    op.add_column(
        "generation_candidates",
        sa.Column("provider_attempt_no", sa.Integer(), nullable=True),
        schema="cms",
    )
    op.add_column(
        "generation_candidates",
        sa.Column("cost_status", sa.String(length=20), nullable=True),
        schema="cms",
    )
    op.add_column(
        "generation_candidates",
        sa.Column("provider_request_id", sa.String(length=120), nullable=True),
        schema="cms",
    )
    op.add_column(
        "generation_candidates",
        sa.Column("generator_version", sa.String(length=80), nullable=True),
        schema="cms",
    )
    op.create_index(
        "ix_cms_gen_candidates_provider",
        "generation_candidates",
        ["provider"],
        schema="cms",
    )


def downgrade() -> None:
    op.drop_index("ix_cms_gen_candidates_provider", table_name="generation_candidates", schema="cms")
    op.drop_column("generation_candidates", "generator_version", schema="cms")
    op.drop_column("generation_candidates", "provider_request_id", schema="cms")
    op.drop_column("generation_candidates", "cost_status", schema="cms")
    op.drop_column("generation_candidates", "provider_attempt_no", schema="cms")
    op.drop_column("generation_candidates", "routing_policy", schema="cms")
    op.drop_column("generation_candidates", "provider", schema="cms")
