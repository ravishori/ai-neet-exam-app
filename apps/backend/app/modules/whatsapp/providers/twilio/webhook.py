"""Twilio request-signature validation.

Twilio signs each webhook request with X-Twilio-Signature: HMAC-SHA1 over
the full request URL with all POST parameters, sorted by key and
concatenated (key+value, no separator) directly onto the URL, keyed with
the Twilio Auth Token, base64-encoded. This is Twilio's own published
algorithm — see Twilio's RequestValidator documentation. Implemented
directly (no vendor SDK dependency), matching the existing
twilio_verify_service.py convention of using httpx/stdlib rather than
the Twilio Python SDK.

Caveat (not addressed in M1, noted for later hardening per the
integration spec's "comprehensive observability is a later phase"):
Twilio requires the EXACT URL it was configured to call. Behind a
reverse proxy that terminates TLS and forwards plain HTTP internally,
``request.url`` can report the wrong scheme, causing legitimate
signatures to fail validation. Production deployment must confirm the
app sees (or is told) the correct externally-visible URL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from starlette.requests import Request


async def compute_twilio_signature(url: str, form_params: dict[str, str], auth_token: str) -> str:
    """Recompute what Twilio's X-Twilio-Signature should be for this exact
    request, per Twilio's documented algorithm."""
    data = url
    for key in sorted(form_params.keys()):
        data += key + form_params[key]
    digest = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


async def validate_twilio_signature(request: Request, *, auth_token: str) -> bool:
    """True only if X-Twilio-Signature matches the recomputed signature,
    using constant-time comparison. Never raises — any parsing failure is
    treated as an invalid signature (returns False)."""
    if not auth_token:
        # Unconfigured => fail closed, never silently accept.
        return False

    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        return False

    try:
        form = await request.form()
        form_params = {str(k): str(v) for k, v in form.multi_items()}
    except Exception:
        return False

    expected = await compute_twilio_signature(str(request.url), form_params, auth_token)
    return hmac.compare_digest(expected, signature)
