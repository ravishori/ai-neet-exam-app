"""Provider interface. See docs/decisions/ADR-WHATSAPP-PROVIDER-ABSTRACTION.md.

Every provider adapter (providers/twilio/, and any future
providers/<name>/) implements this Protocol. services/, repositories/,
models/, and api/ depend only on this interface and the canonical
schemas in schemas/webhook.py — never on a provider's SDK, payload shape,
or header names directly.

The concrete test of whether this boundary held: switching
``whatsapp_provider`` to a new value and adding a new providers/<name>/
package must require zero changes to services/, repositories/, models/,
or the NEET orchestrator.
"""

from __future__ import annotations

from typing import Protocol

from starlette.requests import Request

from app.modules.whatsapp.schemas.webhook import CanonicalInboundMessage, ProviderSendResult


class WhatsAppProvider(Protocol):
    """Structural interface — no shared base class needed; any object
    with these three async methods satisfies it (including test fakes)."""

    async def send_text(self, to_phone: str, body: str) -> ProviderSendResult:
        """Send a text message. Never raises on provider HTTP/network
        failure — returns ProviderSendResult(success=False, ...) instead,
        so callers always get a provider-agnostic result."""
        ...

    async def parse_inbound(self, request: Request, raw_body: bytes) -> CanonicalInboundMessage:
        """Turn an already-validated inbound webhook request into the
        canonical message shape. Callers must call validate_webhook
        first — this method does not re-validate."""
        ...

    async def validate_webhook(self, request: Request, raw_body: bytes) -> bool:
        """Authenticate that this request genuinely came from the
        configured provider, using the exact raw request (raw body
        and/or raw form parameters/URL per that provider's own scheme —
        never a re-serialized/re-parsed version). Must return False
        (never raise) for a request that fails validation for any
        reason, so callers can uniformly reject on ``False``."""
        ...
