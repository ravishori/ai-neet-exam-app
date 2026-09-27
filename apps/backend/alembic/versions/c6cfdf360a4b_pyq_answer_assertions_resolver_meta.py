"""pyq: add resolver_version + explanation to answer_assertions

Additive only, both nullable. Backs the background NCERT-grounded PYQ
answer resolver: every row it inserts now records which resolver build
produced it (resolver_version) and a concise, evidence-derived explanation
(explanation) alongside the existing evidence_note provenance blob.

Revision ID: c6cfdf360a4b
Revises: c1d2e3f4b5a6

NOTE: chained onto c1d2e3f4b5a6, not the (still uncommitted, unrelated)
d3e4f5a6b7c8 PYQ-conflict-review migration — this migration must not
depend on work that isn't committed to this branch.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "c6cfdf360a4b"
down_revision = "c1d2e3f4b5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("answer_assertions", sa.Column("resolver_version", sa.String(40), nullable=True), schema="pyq")
    op.add_column("answer_assertions", sa.Column("explanation", sa.Text(), nullable=True), schema="pyq")


def downgrade() -> None:
    op.drop_column("answer_assertions", "explanation", schema="pyq")
    op.drop_column("answer_assertions", "resolver_version", schema="pyq")
