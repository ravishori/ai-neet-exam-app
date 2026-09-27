import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.modules.commerce.gateway.base import PaymentProviderError, PaymentProviderNotConfiguredError
from app.modules.commerce.gateway.razorpay_provider import RazorpayProvider
from app.modules.commerce.models import Order, PricingPlan, Product
from app.modules.commerce.repositories.order_repository import OrderRepository
from app.modules.commerce.services.access_service import AccessService
from app.modules.commerce.services.entitlement_service import EntitlementService
from app.modules.commerce.services.founding_allocation import FoundingAllocationService

ALL_ACCESS_PRODUCT_CODE = "ALL_ACCESS"


class CommerceError(AppError):
    def __init__(self, message: str, *, code: str = "COMMERCE_ERROR", status_code: int = 409):
        super().__init__(message, code=code, status_code=status_code)


def _generate_order_number() -> str:
    # Not a secret — just a short, human-shareable reference. Uniqueness is
    # enforced by the DB unique constraint on orders.order_number regardless.
    return f"ORD-{secrets.token_hex(6).upper()}"


class CommerceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OrderRepository(session)
        self.founding = FoundingAllocationService(session)
        self.entitlements = EntitlementService(session)

    async def create_order(self, user_id: uuid.UUID) -> Order:
        settings = get_settings()

        # Price is determined HERE, server-side, and locked onto the order —
        # never recalculated from the "current" plan later.
        plan, reservation_expires_at = await self.founding.allocate_slot()

        order = Order(
            user_id=user_id,
            order_number=_generate_order_number(),
            pricing_plan_id=plan.id,
            amount_paise=plan.amount_paise,
            amount_inr=plan.amount_paise / 100,  # display/back-compat only — amount_paise is authoritative
            currency=plan.currency,
            status="CREATED",
            expires_at=reservation_expires_at,
        )
        self.repo.add(order)
        await self.repo.commit()

        provider = RazorpayProvider(key_id=settings.razorpay_key_id, key_secret=settings.razorpay_key_secret)
        try:
            provider_order = await provider.create_order(amount_paise=plan.amount_paise, receipt=str(order.id))
        except PaymentProviderNotConfiguredError as exc:
            raise CommerceError(
                "Payment gateway is not configured yet — set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.",
                code="PAYMENT_GATEWAY_NOT_CONFIGURED",
                status_code=503,
            ) from exc
        except PaymentProviderError as exc:
            order.status = "FAILED"
            if order.pricing_plan_id:
                await self.founding.release_slot(order.pricing_plan_id)
            await self.repo.commit()
            raise CommerceError(str(exc), code="PAYMENT_GATEWAY_ERROR", status_code=502) from exc

        order.razorpay_order_id = provider_order.provider_order_id
        order.status = "PAYMENT_PENDING"
        await self.repo.commit()
        return order

    async def verify_payment(
        self, order_id: uuid.UUID, user_id: uuid.UUID, *, razorpay_payment_id: str, razorpay_signature: str
    ) -> Order:
        settings = get_settings()
        order = await self.repo.get(order_id)
        if not order or order.user_id != user_id:
            raise CommerceError("Order not found", code="NOT_FOUND", status_code=404)
        if not order.razorpay_order_id:
            raise CommerceError("Order was never sent to the payment gateway", code="INVALID_ORDER_STATE")
        if order.status == "PAID":
            # Idempotent: verifying an already-paid order is a safe no-op,
            # never a second entitlement grant (grant_or_extend is also
            # independently idempotent on source_id, belt-and-braces).
            return order

        provider = RazorpayProvider(key_id=settings.razorpay_key_id, key_secret=settings.razorpay_key_secret)
        is_valid = provider.verify_payment(
            provider_order_id=order.razorpay_order_id,
            provider_payment_id=razorpay_payment_id,
            signature=razorpay_signature,
        )
        if not is_valid:
            order.status = "FAILED"
            await self.repo.commit()
            raise CommerceError("Payment signature verification failed", code="INVALID_SIGNATURE", status_code=400)

        # DB-level duplicate-payment guard: razorpay_payment_id is UNIQUE on
        # orders. If another order already recorded this exact payment id,
        # this commit will fail — caught explicitly for a clean error instead
        # of a raw IntegrityError leaking out.
        order.status = "PAID"
        order.razorpay_payment_id = razorpay_payment_id
        order.razorpay_signature = razorpay_signature
        order.paid_at = datetime.now(UTC)
        try:
            await self.repo.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise CommerceError(
                "This payment reference has already been used on another order.",
                code="DUPLICATE_PAYMENT",
                status_code=409,
            ) from exc

        product = (
            await self.session.execute(select(Product).where(Product.code == ALL_ACCESS_PRODUCT_CODE))
        ).scalar_one()
        pricing_plan_id = order.pricing_plan_id
        duration_days = None
        if pricing_plan_id:
            plan = await self.session.get(PricingPlan, pricing_plan_id)
            duration_days = plan.duration_days if plan else 365
        await self.entitlements.grant_or_extend(
            student_id=user_id,
            product_id=product.id,
            source_id=order.id,
            duration_days=duration_days or 365,
        )
        return order

    async def get_status(self, user_id: uuid.UUID) -> dict:
        access = AccessService(self.session)
        state = await access.get_access_state(user_id, ALL_ACCESS_PRODUCT_CODE)
        return {
            "state": state.state,
            "has_access": state.has_access,
            "trial_expires_at": state.trial_expires_at.isoformat() if state.trial_expires_at else None,
            "entitlement_expires_at": state.entitlement_expires_at.isoformat() if state.entitlement_expires_at else None,
        }
