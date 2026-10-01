"""Orchestrates the inbound webhook flow. M1 scope: validate -> parse ->
rate limit -> idempotency -> persist -> resolve identity. No intent
resolution or learning-service dispatch (that's a later milestone's
orchestrator) — this service's job ends at "the message is durably,
safely, idempotently on record."
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from starlette.requests import Request

from app.core.logging import get_logger
from app.core.rate_limit import RateLimitExceeded, check_rate_limit
from app.modules.whatsapp.providers.base import WhatsAppProvider
from app.modules.whatsapp.repositories.whatsapp_repository import WhatsAppRepository
from app.modules.whatsapp.services.whatsapp_identity_service import WhatsAppIdentityService
from app.modules.whatsapp.services.whatsapp_message_service import WhatsAppMessageService

logger = get_logger("whatsapp.webhook")

# Inbound webhook rate limit — protects webhook processing and (once wired
# in a later milestone) downstream outbound/AI usage, per a single WhatsApp
# identity rather than IP (Meta/Twilio's own infra is the request's
# apparent IP, not the student's). Fail-open by default, matching this
# codebase's established default for non-recovery-sensitive limits (see
# app/core/rate_limit.py's rate_limit() docstring) — a Redis blip must not
# silently stop students' messages from being received at all.
_RATE_LIMIT_KEY_PREFIX = "whatsapp_inbound"
_RATE_LIMIT = 30
_RATE_LIMIT_WINDOW_SECONDS = 60


class WebhookValidationError(Exception):
    """Signature/authenticity validation failed — caller must respond
    403, never process the payload."""


@dataclass(frozen=True)
class WebhookProcessResult:
    accepted: bool
    duplicate: bool = False
    # Additive, M2-A-only fields — surface already-computed data for a
    # downstream, out-of-process consumer (see whatsapp_webhook_router.py's
    # BackgroundTasks dispatch) without adding any linking logic here.
    # Populated only on the newly-persisted, non-duplicate, non-rate-
    # limited path — a redelivered/duplicate webhook must never re-trigger
    # downstream processing.
    whatsapp_identity_id: uuid.UUID | None = None
    message_text: str | None = None


class WhatsAppWebhookService:
    def __init__(
        self,
        *,
        provider: WhatsAppProvider,
        repository: WhatsAppRepository,
    ):
        self._provider = provider
        self._repository = repository
        self._identity_service = WhatsAppIdentityService(repository)
        self._message_service = WhatsAppMessageService(repository)

    async def handle_inbound(self, request: Request, raw_body: bytes) -> WebhookProcessResult:
        is_valid = await self._provider.validate_webhook(request, raw_body)
        if not is_valid:
            logger.warning("whatsapp_webhook_invalid_signature")
            raise WebhookValidationError("Invalid webhook signature")

        canonical = await self._provider.parse_inbound(request, raw_body)

        try:
            await check_rate_limit(
                f"ratelimit:{_RATE_LIMIT_KEY_PREFIX}:{canonical.provider}:{canonical.from_phone}",
                limit=_RATE_LIMIT,
                window_seconds=_RATE_LIMIT_WINDOW_SECONDS,
                fail_closed=False,
            )
        except RateLimitExceeded:
            logger.warning("whatsapp_webhook_rate_limited", provider=canonical.provider)
            # Still record nothing and return "accepted" to the HTTP layer
            # (Twilio should not be told to retry a rate-limited request —
            # that would just cause more redeliveries) but do not process
            # further.
            return WebhookProcessResult(accepted=True, duplicate=False)

        identity = await self._identity_service.resolve_identity(provider=canonical.provider, phone_e164=canonical.from_phone)

        _message, created = await self._message_service.persist_inbound(
            whatsapp_identity_id=identity.id,
            provider=canonical.provider,
            provider_message_id=canonical.provider_message_id,
            message_type=canonical.message_type,
            text=canonical.text,
            provider_timestamp=canonical.provider_timestamp,
        )

        if not created:
            logger.info(
                "whatsapp_webhook_duplicate_ignored",
                provider=canonical.provider,
                provider_message_id=canonical.provider_message_id,
            )
            return WebhookProcessResult(accepted=True, duplicate=True)

        logger.info(
            "whatsapp_webhook_message_persisted",
            provider=canonical.provider,
            provider_message_id=canonical.provider_message_id,
            whatsapp_identity_id=str(identity.id),
        )
        # M1 foundation ends here — no intent resolution/reply is sent yet;
        # that belongs to a later milestone's orchestrator.
        return WebhookProcessResult(accepted=True, duplicate=False, whatsapp_identity_id=identity.id, message_text=canonical.text)
