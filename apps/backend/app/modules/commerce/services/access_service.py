import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.models import Entitlement, Product

# Deterministic access states — the ONLY thing any route/frontend should
# branch on. Never inspect Order/Payment status directly for authorization.
TRIAL_ACTIVE = "TRIAL_ACTIVE"
TRIAL_EXPIRING = "TRIAL_EXPIRING"  # active, <= 3 days remaining — display-only, still grants access
TRIAL_EXPIRED = "TRIAL_EXPIRED"
PAID_ACTIVE = "PAID_ACTIVE"
NO_ACCESS = "NO_ACCESS"

TRIAL_EXPIRING_THRESHOLD_DAYS = 3


@dataclass(frozen=True)
class AccessState:
    state: str
    has_access: bool
    trial_expires_at: datetime | None
    entitlement_expires_at: datetime | None


class AccessService:
    """Single source of truth for "can this student use protected NEET
    features right now". Every protected route depends on
    `require_active_access` (identity/dependencies.py) which calls
    `can_access` here — no route re-implements this logic."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _product_id(self, product_code: str) -> uuid.UUID:
        product = (await self.session.execute(select(Product).where(Product.code == product_code))).scalar_one()
        return product.id

    async def get_trial_status(self, student_id: uuid.UUID, product_code: str) -> Entitlement | None:
        product_id = await self._product_id(product_code)
        return (
            await self.session.execute(
                select(Entitlement).where(
                    Entitlement.student_id == student_id,
                    Entitlement.product_id == product_id,
                    Entitlement.source_type == "TRIAL",
                )
            )
        ).scalar_one_or_none()

    async def get_active_entitlement(self, student_id: uuid.UUID, product_code: str) -> Entitlement | None:
        product_id = await self._product_id(product_code)
        now = datetime.now(UTC)
        return (
            await self.session.execute(
                select(Entitlement)
                .where(
                    Entitlement.student_id == student_id,
                    Entitlement.product_id == product_id,
                    Entitlement.source_type == "PURCHASE",
                    Entitlement.status == "ACTIVE",
                    Entitlement.expires_at > now,
                )
                .order_by(Entitlement.expires_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def get_access_state(self, student_id: uuid.UUID, product_code: str = "ALL_ACCESS") -> AccessState:
        now = datetime.now(UTC)
        paid = await self.get_active_entitlement(student_id, product_code)
        if paid:
            return AccessState(PAID_ACTIVE, True, None, paid.expires_at)

        trial = await self.get_trial_status(student_id, product_code)
        if trial and trial.status == "ACTIVE" and trial.expires_at > now:
            days_left = (trial.expires_at - now).days
            state = TRIAL_EXPIRING if days_left <= TRIAL_EXPIRING_THRESHOLD_DAYS else TRIAL_ACTIVE
            return AccessState(state, True, trial.expires_at, None)

        if trial:
            return AccessState(TRIAL_EXPIRED, False, trial.expires_at, None)

        return AccessState(NO_ACCESS, False, None, None)

    async def can_access(self, student_id: uuid.UUID, product_code: str = "ALL_ACCESS") -> bool:
        state = await self.get_access_state(student_id, product_code)
        return state.has_access
