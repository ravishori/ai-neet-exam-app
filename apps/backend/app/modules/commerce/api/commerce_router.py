import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import rate_limit_per_user
from app.modules.commerce.models import Order
from app.modules.commerce.schemas.commerce import VerifyPaymentRequest
from app.modules.commerce.services.access_service import AccessService
from app.modules.commerce.services.commerce_service import CommerceService
from app.modules.identity.dependencies import get_current_user, verify_csrf
from app.modules.identity.models.user import User
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/commerce", tags=["commerce"], dependencies=[Depends(get_current_user)])
# Separate router with NO auth dependency — pricing must be visible to
# anonymous visitors on the public landing/pricing page, per spec ("Public:
# pricing information ... Do not expose protected student functionality" —
# pricing itself is explicitly public, everything else on `router` is not).
public_router = APIRouter(prefix="/api/v1/commerce", tags=["commerce"])


def _order_response(order: Order, *, razorpay_key_id: str | None = None) -> dict:
    return {
        "id": str(order.id),
        "orderNumber": order.order_number,
        "amountPaise": order.amount_paise,
        "currency": order.currency,
        "status": order.status,
        "razorpayOrderId": order.razorpay_order_id,
        # key_id is Razorpay's publishable key — safe to expose to the client,
        # unlike key_secret which never leaves the server. Only included on
        # the create-order response (checkout needs it); omitted elsewhere.
        **({"razorpayKeyId": razorpay_key_id} if razorpay_key_id is not None else {}),
    }


@router.post(
    "/orders",
    dependencies=[Depends(verify_csrf), Depends(rate_limit_per_user("commerce.create_order", limit=10, window_seconds=600))],
)
async def create_order(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.core.config import get_settings

    order = await CommerceService(db).create_order(user.id)
    return envelope(
        success=True, data=_order_response(order, razorpay_key_id=get_settings().razorpay_key_id), status_code=201
    )


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


@router.get("/access-state")
async def get_access_state(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Canonical access-state read for the frontend (trial banner, pricing
    page, etc). Deliberately identical logic path to what
    require_active_access uses for enforcement — the frontend never
    computes access itself, it only displays what this endpoint returns."""
    state = await AccessService(db).get_access_state(user.id)
    return envelope(
        success=True,
        data={
            "state": state.state,
            "hasAccess": state.has_access,
            "trialExpiresAt": state.trial_expires_at.isoformat() if state.trial_expires_at else None,
            "entitlementExpiresAt": state.entitlement_expires_at.isoformat() if state.entitlement_expires_at else None,
        },
    )


@public_router.get("/pricing")
async def get_pricing(db: AsyncSession = Depends(get_db)):
    """Public-facing pricing display data — current founding-slot
    availability comes from the DB, never a frontend-guessed counter."""
    from sqlalchemy import select

    from app.modules.commerce.models import PricingPlan

    plans = (await db.execute(select(PricingPlan).where(PricingPlan.is_active.is_(True)))).scalars().all()
    return envelope(
        success=True,
        data=[
            {
                "code": p.code,
                "amountPaise": p.amount_paise,
                "currency": p.currency,
                "durationDays": p.duration_days,
                "maxPurchases": p.max_purchases,
                "remaining": (p.max_purchases - p.purchase_count) if p.max_purchases is not None else None,
            }
            for p in plans
        ],
    )
