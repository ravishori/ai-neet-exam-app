"""commerce module: index on orders.razorpay_order_id

The webhook reconciliation path (CommerceService.apply_webhook_event ->
OrderRepository.get_by_razorpay_order_id) looks up commerce.orders by
razorpay_order_id on every inbound Razorpay webhook delivery. That column
had no index since its introduction in b6accd4cd83f, so this lookup was a
full table scan that gets worse as the orders table grows. Not unique
(a Razorpay order id should only ever belong to one row in practice, but
nothing upstream guarantees that, and this migration only needs to fix the
scan cost) -- plain non-unique index.

Revision ID: d4f5a6b7c8d9
Revises: c7d8e9f0a1b2
Create Date: 2026-10-24 00:00:00.000001

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4f5a6b7c8d9'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_commerce_orders_razorpay_order_id',
        'orders',
        ['razorpay_order_id'],
        unique=False,
        schema='commerce',
    )


def downgrade() -> None:
    op.drop_index(
        'ix_commerce_orders_razorpay_order_id',
        table_name='orders',
        schema='commerce',
    )
