import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.modules.commerce.gateway.razorpay_client import (
    RazorpayApiError,
    RazorpayNotConfiguredError,
    create_razorpay_order,
    verify_payment_signature,
)
from app.modules.commerce.models import Order
from app.modules.commerce.repositories.order_repository import OrderRepository

PREMIUM_PRICE_INR = 499.00


class CommerceError(AppError):
    def __init__(self, message: str, *, code: str = "COMMERCE_ERROR", status_code: int = 409):
        super().__init__(message, code=code, status_code=status_code)


class CommerceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OrderRepository(session)

    async def create_order(self, user_id: uuid.UUID) -> Order:
        settings = get_settings()
        order = Order(user_id=user_id, amount_inr=PREMIUM_PRICE_INR, status="CREATED")
        self.repo.add(order)
        await self.repo.commit()

        try:
            razorpay_order = await create_razorpay_order(
                amount_inr=PREMIUM_PRICE_INR,
                receipt=str(order.id),
                key_id=settings.razorpay_key_id,
                key_secret=settings.razorpay_key_secret,
            )
        except RazorpayNotConfiguredError as exc:
            raise CommerceError(
                "Payment gateway is not configured yet — set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.",
                code="PAYMENT_GATEWAY_NOT_CONFIGURED",
                status_code=503,
            ) from exc
        except RazorpayApiError as exc:
            order.status = "FAILED"
            await self.repo.commit()
            raise CommerceError(str(exc), code="PAYMENT_GATEWAY_ERROR", status_code=502) from exc

        order.razorpay_order_id = razorpay_order["id"]
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
            return order

        is_valid = verify_payment_signature(
            razorpay_order_id=order.razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
            key_secret=settings.razorpay_key_secret,
        )
        if not is_valid:
            order.status = "FAILED"
            await self.repo.commit()
            raise CommerceError("Payment signature verification failed", code="INVALID_SIGNATURE", status_code=400)

        order.status = "PAID"
        order.razorpay_payment_id = razorpay_payment_id
        order.razorpay_signature = razorpay_signature
        await self.repo.commit()
        return order

    async def get_status(self, user_id: uuid.UUID) -> dict:
        return {"is_premium": await self.repo.has_paid_order(user_id)}

    async def apply_webhook_event(
        self,
        *,
        provider_event_id: str,
        event_type: str,
        razorpay_order_id: str,
        razorpay_payment_id: str | None,
    ) -> None:
        """Webhook reconciliation path — no authenticated user, order is
        looked up by razorpay_order_id (never by session/user_id). Caller
        (the router) MUST have already verified the webhook signature
        before this is called; this method never re-checks it.

        Idempotency + the order-status update happen inside one DB
        transaction via this single commit: record_webhook_event() only
        flushes (no commit), so if this method raises before the final
        commit, nothing — neither the dedup row nor the order mutation —
        is persisted. A crash between flush and commit rolls back both,
        never leaving the event marked-processed without the order update.

        Unknown/unmatched razorpay_order_id: logged by the caller and
        treated as a no-op here (never invents a new Order row).
        """
        is_new_event = await self.repo.record_webhook_event(
            provider="razorpay", provider_event_id=provider_event_id, event_type=event_type
        )
        if not is_new_event:
            # Replay of an already-processed (or concurrently-being-processed)
            # event — safe no-op, never double-apply the state transition.
            return

        order = await self.repo.get_by_razorpay_order_id(razorpay_order_id)
        if not order:
            await self.repo.commit()
            return

        if event_type == "payment.captured":
            if order.status != "PAID":
                order.status = "PAID"
                if razorpay_payment_id:
                    order.razorpay_payment_id = razorpay_payment_id
        elif event_type == "payment.failed":
            if order.status != "PAID":
                order.status = "FAILED"

        await self.repo.commit()
