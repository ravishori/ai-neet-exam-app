"""ingestion: original_filename on ingestion_jobs (PDF upload PR 1)

Revision ID: 6e2b8d4a1f97
Revises: 3f8a1c6e9b52
Create Date: 2026-08-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6e2b8d4a1f97'
down_revision = '3f8a1c6e9b52'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ingestion_jobs', sa.Column('original_filename', sa.String(length=500), nullable=True), schema='ingestion')


def downgrade() -> None:
    op.drop_column('ingestion_jobs', 'original_filename', schema='ingestion')
