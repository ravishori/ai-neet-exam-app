import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.commerce.models import Entitlement, Product

TRIAL_DURATION_DAYS = 15
TRIAL_SOURCE_TYPE = "TRIAL"

logger = get_logger("commerce.trial")


class TrialService:
    """Grants exactly one 15-day trial entitlement per (student, product).
    Server-side dates only; idempotent by construction (see
    ensure_trial — a DB-level unique index on
    (student_id, product_id) WHERE source_type='TRIAL' is the actual
    correctness guarantee, not this code's own get-then-create check, which
    only avoids a redundant round-trip in the common case).

    Login/logout/re-verification never call this except at the single
    "student became eligible" call site (auth_router.register / email
    verification) — there is deliberately no "refresh trial" or "extend
    trial" entry point anywhere in this service."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_trial(self, *, student_id: uuid.UUID, product_code: str) -> Entitlement:
        product = (
            await self.session.execute(select(Product).where(Product.code == product_code))
        ).scalar_one()

        existing = (
            await self.session.execute(
                select(Entitlement).where(
                    Entitlement.student_id == student_id,
                    Entitlement.product_id == product.id,
                    Entitlement.source_type == TRIAL_SOURCE_TYPE,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing

        now = datetime.now(UTC)
        entitlement = Entitlement(
            student_id=student_id,
            product_id=product.id,
            source_type=TRIAL_SOURCE_TYPE,
            source_id=None,
            status="ACTIVE",
            starts_at=now,
            expires_at=now + timedelta(days=TRIAL_DURATION_DAYS),
        )
        self.session.add(entitlement)
        try:
            await self.session.commit()
        except IntegrityError:
            # Concurrent request already created it (unique partial index) —
            # this is the idempotency guarantee, not the get-then-create above.
            await self.session.rollback()
            existing = (
                await self.session.execute(
                    select(Entitlement).where(
                        Entitlement.student_id == student_id,
                        Entitlement.product_id == product.id,
                        Entitlement.source_type == TRIAL_SOURCE_TYPE,
                    )
                )
            ).scalar_one()
            return existing
        logger.info("trial_created", student_id=str(student_id), product_code=product_code)
        return entitlement
