"""commerce module: webhook_events (Razorpay webhook idempotency)

Revision ID: c7d8e9f0a1b2
Revises: d2e3f4a5b6c7
Create Date: 2026-10-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d8e9f0a1b2'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'webhook_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('provider_event_id', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_event_id', name='uq_commerce_webhook_events_provider_event_id'),
        schema='commerce',
    )


def downgrade() -> None:
    op.drop_table('webhook_events', schema='commerce')
