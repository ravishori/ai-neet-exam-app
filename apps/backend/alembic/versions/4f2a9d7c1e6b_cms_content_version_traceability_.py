"""cms: content_version traceability columns + knowledge unit lineage (ADR-0025)

Revision ID: 4f2a9d7c1e6b
Revises: 823b50e0e64f
Create Date: 2026-08-02 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f2a9d7c1e6b'
down_revision = '823b50e0e64f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('content_versions', sa.Column('knowledge_unit_id', sa.UUID(), nullable=True), schema='cms')
    op.add_column('content_versions', sa.Column('knowledge_unit_version', sa.Integer(), nullable=True), schema='cms')
    op.add_column('content_versions', sa.Column('model_used', sa.String(length=100), nullable=True), schema='cms')
    op.add_column('content_versions', sa.Column('prompt_version', sa.String(length=20), nullable=True), schema='cms')
    op.add_column('content_versions', sa.Column('confidence_score', sa.Float(), nullable=True), schema='cms')
    op.add_column('content_versions', sa.Column('generation_cost_usd', sa.Float(), nullable=True), schema='cms')
    op.create_foreign_key(
        'fk_content_versions_knowledge_unit_id',
        'content_versions', 'knowledge_units',
        ['knowledge_unit_id'], ['id'],
        source_schema='cms', referent_schema='knowledge',
        ondelete='SET NULL',
    )

    op.add_column(
        'ingestion_jobs',
        sa.Column('generation_skipped_no_knowledge_unit', sa.Integer(), nullable=False, server_default='0'),
        schema='ingestion',
    )
    op.alter_column('ingestion_jobs', 'generation_skipped_no_knowledge_unit', server_default=None, schema='ingestion')

    op.create_table(
        'content_version_knowledge_units',
        sa.Column('content_version_id', sa.UUID(), nullable=False),
        sa.Column('knowledge_unit_id', sa.UUID(), nullable=False),
        sa.Column('knowledge_unit_version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['content_version_id'], ['cms.content_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_unit_id'], ['knowledge.knowledge_units.id']),
        sa.PrimaryKeyConstraint('content_version_id', 'knowledge_unit_id'),
        schema='cms',
    )


def downgrade() -> None:
    op.drop_table('content_version_knowledge_units', schema='cms')
    op.drop_column('ingestion_jobs', 'generation_skipped_no_knowledge_unit', schema='ingestion')
    op.drop_constraint('fk_content_versions_knowledge_unit_id', 'content_versions', schema='cms', type_='foreignkey')
    op.drop_column('content_versions', 'generation_cost_usd', schema='cms')
    op.drop_column('content_versions', 'confidence_score', schema='cms')
    op.drop_column('content_versions', 'prompt_version', schema='cms')
    op.drop_column('content_versions', 'model_used', schema='cms')
    op.drop_column('content_versions', 'knowledge_unit_version', schema='cms')
    op.drop_column('content_versions', 'knowledge_unit_id', schema='cms')
