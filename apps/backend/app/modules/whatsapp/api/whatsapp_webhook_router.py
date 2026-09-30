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

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.modules.whatsapp.providers import get_whatsapp_provider
from app.modules.whatsapp.repositories.whatsapp_repository import WhatsAppRepository
from app.modules.whatsapp.services.whatsapp_webhook_service import WebhookValidationError, WhatsAppWebhookService

router = APIRouter(prefix="/api/v1/whatsapp", tags=["whatsapp"])
logger = get_logger("whatsapp.router")


@router.get("/webhook")
async def whatsapp_webhook_verify() -> PlainTextResponse:
    """Stable endpoint for provider webhook-activation checks. No
    provider-specific verification is implemented for the current
    (Twilio) provider — see module docstring."""
    return PlainTextResponse("OK", status_code=200)


@router.post("/webhook")
async def whatsapp_webhook_receive(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
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

    # Twilio (and most providers) only need a fast 2xx acknowledgment —
    # this is not the application's own response envelope, since the
    # caller is the provider's webhook delivery system, not a Trinetra
    # API consumer.
    return JSONResponse(status_code=200, content={"status": "accepted", "duplicate": result.duplicate})
