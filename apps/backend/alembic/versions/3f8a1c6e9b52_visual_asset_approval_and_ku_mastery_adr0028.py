"""visual asset approval timestamps + knowledge_unit_mastery (ADR-0028 Phase C/D)

Revision ID: 3f8a1c6e9b52
Revises: 9b4f6d2c8a71
Create Date: 2026-08-03 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f8a1c6e9b52'
down_revision = '9b4f6d2c8a71'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase C: approval timestamps on the EXISTING review_status workflow —
    # not a second, parallel status enum. See VisualAsset model docstring.
    op.add_column('visual_assets', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True), schema='ingestion')
    op.add_column('visual_assets', sa.Column('approved_by', sa.UUID(), nullable=True), schema='ingestion')
    op.add_column('visual_assets', sa.Column('rejection_reason', sa.Text(), nullable=True), schema='ingestion')
    op.create_foreign_key(
        'fk_visual_assets_approved_by',
        'visual_assets', 'users',
        ['approved_by'], ['id'],
        source_schema='ingestion', referent_schema='identity',
        ondelete='SET NULL',
    )

    # Phase D: knowledge_unit_mastery, mirroring ConceptMastery's exact,
    # real, populated shape.
    op.create_table(
        'knowledge_unit_mastery',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('knowledge_unit_id', sa.UUID(), nullable=False),
        sa.Column('attempts_count', sa.Integer(), nullable=False),
        sa.Column('correct_count', sa.Integer(), nullable=False),
        sa.Column('mastery_score', sa.Integer(), nullable=False),
        sa.Column('mastery_level', sa.String(length=20), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_review_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['identity.users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_unit_id'], ['knowledge.knowledge_units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'knowledge_unit_id', name='uq_knowledge_unit_mastery_user_unit'),
        schema='learning',
    )
    op.create_index(
        'ix_knowledge_unit_mastery_knowledge_unit', 'knowledge_unit_mastery', ['knowledge_unit_id'],
        unique=False, schema='learning',
    )


def downgrade() -> None:
    op.drop_index('ix_knowledge_unit_mastery_knowledge_unit', table_name='knowledge_unit_mastery', schema='learning')
    op.drop_table('knowledge_unit_mastery', schema='learning')

    op.drop_constraint('fk_visual_assets_approved_by', 'visual_assets', schema='ingestion', type_='foreignkey')
    op.drop_column('visual_assets', 'rejection_reason', schema='ingestion')
    op.drop_column('visual_assets', 'approved_by', schema='ingestion')
    op.drop_column('visual_assets', 'approved_at', schema='ingestion')
