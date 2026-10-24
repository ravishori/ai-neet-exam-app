import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit_per_user
from app.modules.commerce.gateway.razorpay_client import verify_webhook_signature
from app.modules.commerce.models import Order
from app.modules.commerce.schemas.commerce import VerifyPaymentRequest
from app.modules.commerce.services.commerce_service import CommerceService
from app.modules.identity.dependencies import get_current_user, verify_csrf
from app.modules.identity.models.user import User
from app.shared.responses import envelope

logger = get_logger("commerce.webhook")

router = APIRouter(prefix="/api/v1/commerce", tags=["commerce"], dependencies=[Depends(get_current_user)])

# Webhooks are called by Razorpay's servers, not an authenticated browser
# session — no get_current_user/CSRF here. A separate router (no shared
# dependencies) so the auth dependency above never applies to it.
webhook_router = APIRouter(prefix="/api/v1/commerce", tags=["commerce"])

_HANDLED_EVENT_TYPES = {"payment.captured", "payment.failed"}


@webhook_router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # Signature verification is the very first gate — nothing below this
    # point reads or acts on the payload until it passes. Uses the raw
    # body bytes exactly as received, per Razorpay's webhook docs.
    if not verify_webhook_signature(
        raw_body=raw_body, signature=signature, webhook_secret=settings.razorpay_webhook_secret
    ):
        logger.warning("razorpay_webhook_invalid_signature")
        return JSONResponse(status_code=400, content={"error": "invalid_signature"})

    try:
        payload = json.loads(raw_body)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "invalid_payload"})

    event_type = payload.get("event", "")
    # Razorpay's documented dedup key: a unique id per webhook delivery,
    # sent in this header (not a guaranteed body field).
    provider_event_id = request.headers.get("X-Razorpay-Event-Id", "")
    if not provider_event_id:
        logger.warning("razorpay_webhook_missing_event_id", event_type=event_type)
        return JSONResponse(status_code=400, content={"error": "missing_event_id"})

    if event_type not in _HANDLED_EVENT_TYPES:
        # Unhandled event type — acknowledge so Razorpay doesn't retry
        # forever for something we deliberately don't act on.
        return envelope(success=True, data={"handled": False})

    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_order_id = payment_entity.get("order_id")
    razorpay_payment_id = payment_entity.get("id")

    if not razorpay_order_id:
        logger.warning("razorpay_webhook_missing_order_id", event_type=event_type)
        return envelope(success=True, data={"handled": False})

    await CommerceService(db).apply_webhook_event(
        provider_event_id=provider_event_id,
        event_type=event_type,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
    )
    return envelope(success=True, data={"handled": True})


def _order_response(order: Order) -> dict:
    return {
        "id": str(order.id),
        "amount_inr": float(order.amount_inr),
        "status": order.status,
        "razorpay_order_id": order.razorpay_order_id,
        # key_id is Razorpay's publishable key — safe to expose to the client,
        # unlike key_secret which never leaves the server.
        "razorpay_key_id": get_settings().razorpay_key_id,
    }


@router.post(
    "/orders",
    dependencies=[Depends(verify_csrf), Depends(rate_limit_per_user("commerce.create_order", limit=10, window_seconds=600))],
)
async def create_order(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    order = await CommerceService(db).create_order(user.id)
    return envelope(success=True, data=_order_response(order), status_code=201)


@router.post(
    "/orders/{order_id}/verify",
    dependencies=[Depends(verify_csrf), Depends(rate_limit_per_user("commerce.verify_order", limit=10, window_seconds=600))],
)
async def verify_order(
    order_id: uuid.UUID,
    payload: VerifyPaymentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await CommerceService(db).verify_payment(
        order_id,
        user.id,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
    )
    return envelope(success=True, data=_order_response(order))


@router.get("/status")
async def get_commerce_status(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await CommerceService(db).get_status(user.id)
    return envelope(success=True, data=result)
