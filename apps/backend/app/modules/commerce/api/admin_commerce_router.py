import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.commerce.models import Order, PricingPlan
from app.modules.commerce.repositories.order_repository import OrderRepository
from app.modules.identity.dependencies import require_permission
from app.modules.identity.models.user import User
from app.modules.system.services.audit_service import AuditService, request_context
from app.shared.responses import envelope

router = APIRouter(
    prefix="/api/v1/admin/commerce",
    tags=["admin", "commerce"],
    dependencies=[Depends(require_permission("commerce.manage"))],
)


def _admin_order_response(order: Order) -> dict:
    return {
        "id": str(order.id),
        "orderNumber": order.order_number,
        "userId": str(order.user_id),
        "amountPaise": order.amount_paise,
        "currency": order.currency,
        "status": order.status,
        "razorpayOrderId": order.razorpay_order_id,
        "razorpayPaymentId": order.razorpay_payment_id,
        "createdAt": order.created_at.isoformat() if order.created_at else None,
        "paidAt": order.paid_at.isoformat() if order.paid_at else None,
    }


@router.get("/orders/pending")
async def list_pending_orders(db: AsyncSession = Depends(get_db)):
    orders = await OrderRepository(db).list_pending_admin()
    return envelope(success=True, data=[_admin_order_response(o) for o in orders])


@router.get("/orders")
async def list_all_orders(db: AsyncSession = Depends(get_db)):
    orders = await OrderRepository(db).list_all_admin()
    return envelope(success=True, data=[_admin_order_response(o) for o in orders])


@router.get("/founding-status")
async def founding_status(db: AsyncSession = Depends(get_db)):
    plan = (
        await db.execute(select(PricingPlan).where(PricingPlan.code == "FOUNDING_500"))
    ).scalar_one_or_none()
    if not plan:
        return envelope(success=True, data=None)
    return envelope(
        success=True,
        data={
            "maxPurchases": plan.max_purchases,
            "purchaseCount": plan.purchase_count,
            "remaining": (plan.max_purchases - plan.purchase_count) if plan.max_purchases is not None else None,
            "isActive": plan.is_active,
        },
    )


@router.post("/orders/{order_id}/verify")
async def admin_verify_order_note(
    order_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("commerce.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Payment verification itself is automatic and cryptographic
    (Razorpay HMAC signature — CommerceService.verify_payment), per the
    explicit instruction NOT to make manual verification the primary flow.
    This endpoint exists only to let an admin manually confirm/annotate an
    order for reconciliation (e.g. a payment the gateway confirmed but the
    student's browser never called /verify for) — it does NOT itself grant
    access; it re-runs the same real signature check, it does not bypass it.
    Informational reference fields on the order (if ever added) are treated
    the same way: informational only, never self-authorizing."""
    order = await OrderRepository(db).get(order_id)
    if not order:
        from app.core.exceptions import AppError

        raise AppError("Order not found", code="NOT_FOUND", status_code=404)

    ctx = request_context(request)
    await AuditService(db).log(
        actor_user_id=user.id,
        action="COMMERCE_ADMIN_ORDER_REVIEWED",
        entity_type="commerce.orders",
        entity_id=order.id,
        metadata={"status": order.status},
        **ctx,
    )
    return envelope(success=True, data=_admin_order_response(order))
