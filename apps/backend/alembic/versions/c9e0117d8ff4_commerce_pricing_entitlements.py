"""commerce: products, pricing_plans, entitlements + additive Order columns
for the trial/founding-500/annual-access monetization system.

Purely additive — no existing column is dropped or type-changed.
commerce.orders.amount_inr is KEPT (nullable now) for backward compatibility:
inspected before writing this migration (railway ssh, read-only) and found
2 pre-existing rows in production, both status=CREATED, never PAID — no
historical revenue/paid-amount data exists to preserve, but the column is
still not dropped, per the explicit instruction to prefer an additive
migration over a destructive one regardless. New code uses the new
amount_paise (Integer) column as the sole authoritative amount going forward.

Revision ID: c9e0117d8ff4
Revises: c1d2e3f4b5a6
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c9e0117d8ff4"
down_revision = "c1d2e3f4b5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        schema="commerce",
    )

    op.create_table(
        "pricing_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commerce.products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("max_purchases", sa.Integer(), nullable=True),
        sa.Column("purchase_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("max_purchases IS NULL OR purchase_count <= max_purchases", name="ck_pricing_plans_purchase_count_within_max"),
        schema="commerce",
    )
    op.create_index("ix_commerce_pricing_plans_product_id", "pricing_plans", ["product_id"], schema="commerce")

    op.create_table(
        "entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("commerce.products.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        schema="commerce",
    )
    op.create_index("ix_commerce_entitlements_student_id", "entitlements", ["student_id"], schema="commerce")
    op.create_index("ix_commerce_entitlements_expires_at", "entitlements", ["expires_at"], schema="commerce")
    # One trial per (student, product) — the actual idempotency guarantee for
    # TrialService.ensure_trial, enforced at the DB level, not just in Python.
    op.create_index(
        "uq_commerce_entitlements_one_trial_per_student_product",
        "entitlements",
        ["student_id", "product_id"],
        unique=True,
        schema="commerce",
        postgresql_where=sa.text("source_type = 'TRIAL'"),
    )

    # Additive columns on the existing orders table.
    op.add_column("orders", sa.Column("order_number", sa.String(40), nullable=True), schema="commerce")
    op.add_column(
        "orders",
        sa.Column(
            "pricing_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commerce.pricing_plans.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        schema="commerce",
    )
    op.add_column("orders", sa.Column("amount_paise", sa.Integer(), nullable=True), schema="commerce")
    op.add_column("orders", sa.Column("currency", sa.String(3), nullable=False, server_default="INR"), schema="commerce")
    op.add_column("orders", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True), schema="commerce")
    op.add_column("orders", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True), schema="commerce")
    op.alter_column("orders", "amount_inr", nullable=True, schema="commerce")
    op.create_unique_constraint("uq_commerce_orders_order_number", "orders", ["order_number"], schema="commerce")
    op.create_unique_constraint(
        "uq_commerce_orders_razorpay_payment_id", "orders", ["razorpay_payment_id"], schema="commerce"
    )
    op.create_index("ix_commerce_orders_status", "orders", ["status"], schema="commerce")

    # Seed the two pricing plans + the ALL_ACCESS product. Idempotent
    # (ON CONFLICT DO NOTHING) so re-running against an environment that
    # already has them (e.g. a partially-applied prior attempt) is safe.
    conn = op.get_bind()
    product_id = conn.execute(
        sa.text(
            "INSERT INTO commerce.products (code, name, description) "
            "VALUES ('ALL_ACCESS', 'All Access', 'Full NEET platform access') "
            "ON CONFLICT (code) DO UPDATE SET code = EXCLUDED.code "
            "RETURNING id"
        )
    ).scalar_one()
    conn.execute(
        sa.text(
            "INSERT INTO commerce.pricing_plans "
            "(code, product_id, amount_paise, currency, duration_days, max_purchases, purchase_count, is_active) "
            "VALUES ('FOUNDING_500', :pid, 49900, 'INR', 365, 500, 0, true) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        {"pid": product_id},
    )
    conn.execute(
        sa.text(
            "INSERT INTO commerce.pricing_plans "
            "(code, product_id, amount_paise, currency, duration_days, max_purchases, purchase_count, is_active) "
            "VALUES ('STANDARD_ANNUAL', :pid, 99900, 'INR', 365, NULL, 0, true) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        {"pid": product_id},
    )


def downgrade() -> None:
    op.drop_index("ix_commerce_orders_status", table_name="orders", schema="commerce")
    op.drop_constraint("uq_commerce_orders_razorpay_payment_id", "orders", schema="commerce", type_="unique")
    op.drop_constraint("uq_commerce_orders_order_number", "orders", schema="commerce", type_="unique")
    op.drop_column("orders", "paid_at", schema="commerce")
    op.drop_column("orders", "expires_at", schema="commerce")
    op.drop_column("orders", "currency", schema="commerce")
    op.drop_column("orders", "amount_paise", schema="commerce")
    op.drop_column("orders", "pricing_plan_id", schema="commerce")
    op.drop_column("orders", "order_number", schema="commerce")

    op.drop_index("uq_commerce_entitlements_one_trial_per_student_product", table_name="entitlements", schema="commerce")
    op.drop_index("ix_commerce_entitlements_expires_at", table_name="entitlements", schema="commerce")
    op.drop_index("ix_commerce_entitlements_student_id", table_name="entitlements", schema="commerce")
    op.drop_table("entitlements", schema="commerce")

    op.drop_index("ix_commerce_pricing_plans_product_id", table_name="pricing_plans", schema="commerce")
    op.drop_table("pricing_plans", schema="commerce")

    op.drop_table("products", schema="commerce")
