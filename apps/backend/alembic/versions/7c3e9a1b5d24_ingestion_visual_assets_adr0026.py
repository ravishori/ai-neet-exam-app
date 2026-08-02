"""ingestion: visual_assets table + job counters (ADR-0026)

Revision ID: 7c3e9a1b5d24
Revises: 4f2a9d7c1e6b
Create Date: 2026-08-02 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '7c3e9a1b5d24'
down_revision = '4f2a9d7c1e6b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'visual_assets',
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('section_id', sa.UUID(), nullable=True),
        sa.Column('knowledge_unit_id', sa.UUID(), nullable=True),
        sa.Column('source_page', sa.Integer(), nullable=False),
        sa.Column('bounding_box', postgresql.JSONB(), nullable=True),
        sa.Column('render_dpi', sa.Integer(), nullable=True),
        sa.Column('width_px', sa.Integer(), nullable=True),
        sa.Column('height_px', sa.Integer(), nullable=True),
        sa.Column('asset_type', sa.String(length=30), nullable=False),
        sa.Column('detection_method', sa.String(length=20), nullable=False),
        sa.Column('review_status', sa.String(length=20), nullable=False),
        sa.Column('storage_path', sa.String(length=1000), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('vision_description', sa.Text(), nullable=True),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['ingestion.ingestion_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['section_id'], ['ingestion.ingestion_sections.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['knowledge_unit_id'], ['knowledge.knowledge_units.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        schema='ingestion',
    )
    op.create_index('ix_visual_assets_job', 'visual_assets', ['job_id'], unique=False, schema='ingestion')
    op.create_index('ix_visual_assets_review_status', 'visual_assets', ['review_status'], unique=False, schema='ingestion')

    op.add_column(
        'ingestion_jobs',
        sa.Column('visual_assets_detected', sa.Integer(), nullable=False, server_default='0'),
        schema='ingestion',
    )
    op.add_column(
        'ingestion_jobs',
        sa.Column('visual_assets_needing_review', sa.Integer(), nullable=False, server_default='0'),
        schema='ingestion',
    )
    op.alter_column('ingestion_jobs', 'visual_assets_detected', server_default=None, schema='ingestion')
    op.alter_column('ingestion_jobs', 'visual_assets_needing_review', server_default=None, schema='ingestion')


def downgrade() -> None:
    op.drop_column('ingestion_jobs', 'visual_assets_needing_review', schema='ingestion')
    op.drop_column('ingestion_jobs', 'visual_assets_detected', schema='ingestion')
    op.drop_index('ix_visual_assets_review_status', table_name='visual_assets', schema='ingestion')
    op.drop_index('ix_visual_assets_job', table_name='visual_assets', schema='ingestion')
    op.drop_table('visual_assets', schema='ingestion')
