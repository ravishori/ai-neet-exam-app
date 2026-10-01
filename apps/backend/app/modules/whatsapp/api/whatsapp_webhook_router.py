"""Stable, provider-neutral webhook route. What happens inside is entirely
delegated to the configured provider adapter (see providers/__init__.py's
resolver) — this router never imports a provider SDK or references a
provider-specific payload shape.

GET exists for contract stability/provider portability (some providers —
Meta Cloud API, if added later — require a verification handshake before
activating a webhook). Twilio does not require this handshake, so under
the current Twilio-only configuration GET is a stable no-op rather than
implementing any provider-specific verification logic here — per M1
scope, Meta-specific verification (hub.mode/hub.verify_token/
hub.challenge) is explicitly not implemented.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.modules.whatsapp.providers import get_whatsapp_provider
from app.modules.whatsapp.repositories.whatsapp_repository import WhatsAppRepository
from app.modules.whatsapp.services.whatsapp_link_code_service import dispatch_link_code_verification_in_background
from app.modules.whatsapp.services.whatsapp_webhook_service import WebhookValidationError, WhatsAppWebhookService

router = APIRouter(prefix="/api/v1/whatsapp", tags=["whatsapp"])
logger = get_logger("whatsapp.router")


@router.get("/webhook")
async def whatsapp_webhook_verify() -> PlainTextResponse:
    """Stable endpoint for provider webhook-activation checks. No
    provider-specific verification is implemented for the current
    (Twilio) provider — see module docstring."""
    return PlainTextResponse("OK", status_code=200)


_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


@router.post("/webhook")
async def whatsapp_webhook_receive(
    request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)
) -> Response:
    raw_body = await request.body()

    provider = get_whatsapp_provider()
    repository = WhatsAppRepository(db)
    service = WhatsAppWebhookService(provider=provider, repository=repository)

    try:
        result = await service.handle_inbound(request, raw_body)
    except WebhookValidationError:
        # Never expose *why* validation failed (signature detail, provider
        # internals) — a bare 403 is all an unauthenticated caller gets.
        return JSONResponse(status_code=403, content={"error": "invalid_signature"})

    await db.commit()

    # M2-A dispatch only — no linking logic here. Runs strictly after this
    # response is sent (BackgroundTasks semantics), so it can never affect
    # the TwiML response, signature validation, idempotency, or rate-limit
    # behavior above; a duplicate/rate-limited delivery (identity_id/text
    # left None by the service) is never dispatched, preserving replay
    # protection. See whatsapp_link_code_service.py for the actual
    # verification logic.
    if result.whatsapp_identity_id is not None and result.message_text is not None:
        background_tasks.add_task(dispatch_link_code_verification_in_background, result.whatsapp_identity_id, result.message_text)

    # Twilio's messaging webhook parses the response body as TwiML and
    # logs error 12300 ("Invalid Content-Type") for anything else, even
    # on a 2xx status — an empty <Response/> is TwiML's documented way to
    # acknowledge receipt while sending no reply, matching M1's
    # intentional no-auto-reply design.
    return Response(content=_EMPTY_TWIML, status_code=200, media_type="text/xml")
