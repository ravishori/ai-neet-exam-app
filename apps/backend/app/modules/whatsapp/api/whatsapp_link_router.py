"""Authenticated WhatsApp account-linking endpoints — M2-A.

Deliberately separate from whatsapp_webhook_router.py: that router is the
frozen, unauthenticated M1 transport surface Twilio calls directly. This
router requires a logged-in NEET session (cookie auth, same as the rest of
the identity module) and is never reachable from Twilio.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.rate_limit import rate_limit_per_user
from app.modules.identity.dependencies import get_current_user, verify_csrf
from app.modules.identity.models.user import User
from app.modules.whatsapp.repositories.whatsapp_repository import WhatsAppRepository
from app.modules.whatsapp.schemas.link import UnlinkRequest
from app.modules.whatsapp.services.whatsapp_link_code_service import WhatsAppLinkCodeService
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/whatsapp/link", tags=["whatsapp"])


@router.post(
    "/request",
    dependencies=[Depends(verify_csrf), Depends(rate_limit_per_user("whatsapp_link_request", limit=5, window_seconds=300))],
)
async def request_link_code(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = WhatsAppLinkCodeService(db)
    generated = await service.generate_code(user_id=user.id)
    await db.commit()
    # The plaintext code is returned exactly once, here, to the already-
    # authenticated caller — never stored, never logged, never returned
    # again by any other endpoint.
    return envelope(
        success=True,
        data={"code": generated.plaintext_code, "expires_at": generated.expires_at.isoformat()},
    )


@router.post(
    "/unlink",
    dependencies=[Depends(verify_csrf), Depends(rate_limit_per_user("whatsapp_unlink", limit=5, window_seconds=300))],
)
async def unlink_whatsapp_identity(
    payload: UnlinkRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    # Enumeration-safe by design: "no such identity" and "identity exists
    # but you're not authorized to unlink it" must be indistinguishable to
    # the caller — both raise the exact same error, same status code, same
    # message. Do not special-case the not-found path differently.
    repository = WhatsAppRepository(db)
    identity = await repository.get_identity_by_provider_phone("twilio", payload.phone_e164)

    is_admin = "SUPER_ADMIN" in user.role_codes
    unlinked = False
    if identity is not None:
        service = WhatsAppLinkCodeService(db)
        unlinked = await service.unlink(identity=identity, requesting_user_id=user.id, is_admin=is_admin)

    if not unlinked:
        raise AppError("Not authorized to unlink this WhatsApp identity", code="WHATSAPP_UNLINK_FORBIDDEN", status_code=403)

    await db.commit()
    return envelope(success=True, data={"message": "WhatsApp identity unlinked."})
