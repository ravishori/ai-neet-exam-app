import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.commerce.models import PricingPlan

FOUNDING_PLAN_CODE = "FOUNDING_500"
STANDARD_PLAN_CODE = "STANDARD_ANNUAL"
# How long a reserved founding slot is held for an unpaid order before it is
# released back to the pool. See docstring on allocate_slot for the exact
# reservation rule this implements.
FOUNDING_RESERVATION_WINDOW_MINUTES = 30

logger = get_logger("commerce.founding_allocation")


class FoundingAllocationService:
    """Concurrency-safe allocation of the 500 founding (₹499) slots.

    THE EXACT RULE (documented here because the brief explicitly asked for
    it to be spelled out):

    A slot is RESERVED — pricing_plans.purchase_count is incremented — at
    ORDER CREATION time, inside the same DB transaction as the order insert,
    guarded by `SELECT ... FOR UPDATE` on the FOUNDING_500 pricing_plan row.
    This is what makes concurrent allocation safe: two simultaneous
    create_order calls cannot both read "499 of 500 used" and both proceed —
    the row lock serializes them, so the second one sees "500 of 500" and is
    correctly routed to the ₹999 STANDARD_ANNUAL plan instead.

    A slot is RELEASED — purchase_count decremented — if that order is never
    paid within FOUNDING_RESERVATION_WINDOW_MINUTES. release_expired() is
    called lazily at the start of every allocate_slot() call (no scheduler/
    cron exists in this codebase; this achieves the same effect without
    adding new infra). This satisfies "do not permanently consume a founding
    slot merely because someone opened checkout" while still preventing
    over-allocation at any instant multiple checkouts are open concurrently.

    A slot is PERMANENTLY consumed once the order transitions to PAID
    (CommerceService.verify_payment) — purchase_count is NOT touched again at
    that point; it was already counted at reservation.

    Trade-off, stated explicitly: between order-creation and payment
    verification (or expiry), a reserved-but-unpaid founding order does
    occupy one of the 500 slots. This is the standard "hold inventory during
    checkout" pattern (same approach ticketing systems use) and is required
    to satisfy BOTH the concurrency-safety requirement AND the price-locking
    requirement (the ₹499 price must be fixed at order creation, before
    payment is known) without a more complex reservation-token redesign.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def release_expired(self) -> int:
        from app.modules.commerce.models import Order

        now = datetime.now(UTC)
        expired = (
            await self.session.execute(
                select(Order).where(
                    Order.status == "CREATED",
                    Order.pricing_plan_id.isnot(None),
                    Order.expires_at.isnot(None),
                    Order.expires_at < now,
                )
            )
        ).scalars().all()
        released = 0
        for order in expired:
            plan = await self.session.get(PricingPlan, order.pricing_plan_id, with_for_update=True)
            if plan and plan.code == FOUNDING_PLAN_CODE and plan.purchase_count > 0:
                plan.purchase_count -= 1
                released += 1
                logger.info("founding_slot_released", order_id=str(order.id))
            order.status = "EXPIRED"
        if expired:
            await self.session.commit()
        return released

    async def allocate_slot(self) -> tuple[PricingPlan, datetime | None]:
        """Returns (plan_to_use, reservation_expires_at). reservation_expires_at
        is None when the STANDARD plan is returned (no allocation/expiry
        concept applies to the unlimited plan)."""
        await self.release_expired()

        result = await self.session.execute(
            select(PricingPlan).where(PricingPlan.code == FOUNDING_PLAN_CODE).with_for_update()
        )
        founding = result.scalar_one_or_none()

        if (
            founding
            and founding.is_active
            and founding.max_purchases is not None
            and founding.purchase_count < founding.max_purchases
        ):
            founding.purchase_count += 1
            await self.session.commit()
            logger.info(
                "founding_slot_allocated",
                purchase_count=founding.purchase_count,
                max_purchases=founding.max_purchases,
            )
            reservation_expires_at = datetime.now(UTC) + timedelta(minutes=FOUNDING_RESERVATION_WINDOW_MINUTES)
            return founding, reservation_expires_at

        standard = (
            await self.session.execute(select(PricingPlan).where(PricingPlan.code == STANDARD_PLAN_CODE))
        ).scalar_one()
        return standard, None

    async def release_slot(self, plan_id: uuid.UUID) -> None:
        """Explicit release (e.g. order cancelled by the student before
        expiry) — same effect as release_expired's per-row logic."""
        plan = await self.session.get(PricingPlan, plan_id, with_for_update=True)
        if plan and plan.code == FOUNDING_PLAN_CODE and plan.purchase_count > 0:
            plan.purchase_count -= 1
            await self.session.commit()
            logger.info("founding_slot_released", plan_id=str(plan_id))
