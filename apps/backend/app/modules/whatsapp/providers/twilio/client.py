"""Twilio WhatsApp adapter — implements providers.base.WhatsAppProvider.

No Twilio SDK object or Twilio payload shape crosses out of this module;
callers only ever see CanonicalInboundMessage / ProviderSendResult (see
schemas/webhook.py). Uses httpx directly, matching the existing
twilio_verify_service.py convention (no vendor SDK dependency).
"""

from __future__ import annotations

import httpx
import pydantic
from starlette.requests import Request

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.whatsapp.providers.twilio.schemas import (
    TwilioInboundForm,
    add_whatsapp_prefix,
    strip_whatsapp_prefix,
)
from app.modules.whatsapp.providers.twilio.webhook import validate_twilio_signature
from app.modules.whatsapp.schemas.webhook import CanonicalInboundMessage, ProviderSendResult

logger = get_logger("whatsapp.providers.twilio")

_PROVIDER_NAME = "twilio"
_MESSAGES_URL_TEMPLATE = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"


class WhatsAppMalformedPayloadError(AppError):
    """A signature-valid webhook whose form payload doesn't match the
    expected Twilio shape (missing/malformed required fields). Mapped to
    a safe, generic application error — never a raw pydantic
    ValidationError, which would otherwise propagate as an unhandled
    exception and risk leaking field-level internals."""

    def __init__(self):
        super().__init__(
            "Malformed webhook payload",
            code="WHATSAPP_MALFORMED_PAYLOAD",
            status_code=400,
        )


class TwilioWhatsAppProvider:
    """Production adapter. Reads settings per-call, like
    TwilioVerifyService, so env changes (e.g. test-time monkeypatch) are
    picked up without a process restart."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        # transport is injected only in tests; production leaves it None.
        self._transport = transport

    def _cfg(self) -> tuple[str, str, str]:
        s = get_settings()
        sid = (s.whatsapp_twilio_account_sid or "").strip()
        token = (s.whatsapp_twilio_auth_token or "").strip()
        from_number = (s.whatsapp_twilio_whatsapp_from or "").strip()
        return sid, token, from_number

    async def send_text(self, to_phone: str, body: str) -> ProviderSendResult:
        sid, token, from_number = self._cfg()
        if not sid or not token or not from_number:
            logger.warning("whatsapp_twilio_send_not_configured")
            return ProviderSendResult(success=False, provider=_PROVIDER_NAME, error_code="WHATSAPP_PROVIDER_NOT_CONFIGURED")

        url = _MESSAGES_URL_TEMPLATE.format(account_sid=sid)
        try:
            async with httpx.AsyncClient(timeout=15.0, transport=self._transport) as client:
                resp = await client.post(
                    url,
                    data={
                        "From": add_whatsapp_prefix(from_number),
                        "To": add_whatsapp_prefix(to_phone),
                        "Body": body,
                    },
                    auth=(sid, token),
                )
        except httpx.HTTPError as exc:
            logger.warning("whatsapp_twilio_send_network_error", kind=type(exc).__name__)
            return ProviderSendResult(success=False, provider=_PROVIDER_NAME, error_code="WHATSAPP_PROVIDER_UNAVAILABLE")

        if resp.status_code >= 400:
            # Never forward Twilio's raw response text to callers — some
            # error bodies echo the destination number back.
            twilio_code = _safe_error_code(resp)
            logger.warning("whatsapp_twilio_send_failed", status=resp.status_code, twilio_code=twilio_code)
            return ProviderSendResult(success=False, provider=_PROVIDER_NAME, error_code="WHATSAPP_PROVIDER_SEND_FAILED")

        # F-02: a 2xx response is still not guaranteed to carry a valid JSON
        # body (proxy glitch, unexpected empty 200) — send_text's own
        # interface contract (providers/base.py) promises it never raises
        # on provider failure, so this must degrade to the same safe
        # ProviderSendResult(success=False, ...) shape as every other
        # failure path above, not propagate a raw JSONDecodeError.
        try:
            body_json = resp.json()
        except ValueError:
            logger.warning("whatsapp_twilio_send_invalid_response", status=resp.status_code)
            return ProviderSendResult(success=False, provider=_PROVIDER_NAME, error_code="WHATSAPP_PROVIDER_INVALID_RESPONSE")

        return ProviderSendResult(success=True, provider=_PROVIDER_NAME, provider_message_id=str(body_json.get("sid", "")))

    async def validate_webhook(self, request: Request, raw_body: bytes) -> bool:
        _sid, token, _from = self._cfg()
        return await validate_twilio_signature(request, auth_token=token)

    async def parse_inbound(self, request: Request, raw_body: bytes) -> CanonicalInboundMessage:
        # request.form() is cached by Starlette after validate_webhook's
        # own call, so this does not re-read the raw ASGI stream.
        form = await request.form()
        try:
            parsed = TwilioInboundForm.model_validate({str(k): v for k, v in form.multi_items()})
        except pydantic.ValidationError as exc:
            logger.warning("whatsapp_twilio_malformed_payload", field_count=len(exc.errors()))
            raise WhatsAppMalformedPayloadError() from exc
        return CanonicalInboundMessage(
            provider=_PROVIDER_NAME,
            provider_message_id=parsed.MessageSid,
            from_phone=strip_whatsapp_prefix(parsed.From),
            to_phone=strip_whatsapp_prefix(parsed.To),
            message_type="text",
            text=parsed.Body,
            provider_timestamp=None,  # Twilio's inbound webhook does not include one
        )


def _safe_error_code(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
        return str(payload.get("code", ""))
    except Exception:  # noqa: BLE001
        return ""
