import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.commerce.models import Entitlement

logger = get_logger("commerce.entitlement")

PURCHASE_SOURCE_TYPE = "PURCHASE"


class EntitlementService:
    """Grants/extends the PURCHASE-type entitlement after a verified payment.
    Idempotent: called twice for the same order_id (e.g. a retried webhook)
    must not create two entitlements or double-extend — guarded by the
    caller (CommerceService.verify_payment) checking order.status == "PAID"
    before ever calling this, plus source_id-based lookup here."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def grant_or_extend(
        self, *, student_id: uuid.UUID, product_id: uuid.UUID, source_id: uuid.UUID, duration_days: int
    ) -> Entitlement:
        # Idempotency: if this exact order already granted an entitlement
        # (source_id match), return it unchanged rather than extending again.
        existing_for_order = (
            await self.session.execute(
                select(Entitlement).where(
                    Entitlement.source_type == PURCHASE_SOURCE_TYPE, Entitlement.source_id == source_id
                )
            )
        ).scalar_one_or_none()
        if existing_for_order:
            return existing_for_order

        now = datetime.now(UTC)
        current = (
            await self.session.execute(
                select(Entitlement)
                .where(
                    Entitlement.student_id == student_id,
                    Entitlement.product_id == product_id,
                    Entitlement.source_type == PURCHASE_SOURCE_TYPE,
                    Entitlement.status == "ACTIVE",
                )
                .order_by(Entitlement.expires_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if current and current.expires_at > now:
            # Extend from existing expiry — never overwrite remaining paid time.
            current.expires_at = current.expires_at + timedelta(days=duration_days)
            current.source_id = source_id
            await self.session.commit()
            logger.info("entitlement_extended", student_id=str(student_id), new_expiry=current.expires_at.isoformat())
            return current

        entitlement = Entitlement(
            student_id=student_id,
            product_id=product_id,
            source_type=PURCHASE_SOURCE_TYPE,
            source_id=source_id,
            status="ACTIVE",
            starts_at=now,
            expires_at=now + timedelta(days=duration_days),
        )
        self.session.add(entitlement)
        await self.session.commit()
        logger.info("entitlement_granted", student_id=str(student_id), expires_at=entitlement.expires_at.isoformat())
        return entitlement
