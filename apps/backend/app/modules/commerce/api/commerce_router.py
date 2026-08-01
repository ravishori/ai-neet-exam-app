import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.commerce.models import Order
from app.modules.commerce.schemas.commerce import VerifyPaymentRequest
from app.modules.commerce.services.commerce_service import CommerceService
from app.modules.identity.dependencies import get_current_user, verify_csrf
from app.modules.identity.models.user import User
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/commerce", tags=["commerce"], dependencies=[Depends(get_current_user)])


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


@router.post("/orders", dependencies=[Depends(verify_csrf)])
async def create_order(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    order = await CommerceService(db).create_order(user.id)
    return envelope(success=True, data=_order_response(order), status_code=201)


@router.post("/orders/{order_id}/verify", dependencies=[Depends(verify_csrf)])
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
