"""ingestion: section language metadata (ADR-0027)

Revision ID: 9b4f6d2c8a71
Revises: 7c3e9a1b5d24
Create Date: 2026-08-02 20:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b4f6d2c8a71'
down_revision = '7c3e9a1b5d24'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ingestion_sections', sa.Column('language_code', sa.String(length=10), nullable=True), schema='ingestion')
    op.add_column('ingestion_sections', sa.Column('language_name', sa.String(length=20), nullable=True), schema='ingestion')
    op.add_column('ingestion_sections', sa.Column('language_confidence', sa.Float(), nullable=True), schema='ingestion')


def downgrade() -> None:
    op.drop_column('ingestion_sections', 'language_confidence', schema='ingestion')
    op.drop_column('ingestion_sections', 'language_name', schema='ingestion')
    op.drop_column('ingestion_sections', 'language_code', schema='ingestion')
