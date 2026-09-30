"""Twilio request-signature validation.

Twilio signs each webhook request with X-Twilio-Signature: HMAC-SHA1 over
the full request URL with all POST parameters, sorted by key and
concatenated (key+value, no separator) directly onto the URL, keyed with
the Twilio Auth Token, base64-encoded. This is Twilio's own published
algorithm — see Twilio's RequestValidator documentation. Implemented
directly (no vendor SDK dependency), matching the existing
twilio_verify_service.py convention of using httpx/stdlib rather than
the Twilio Python SDK.

F-01 fix: Twilio requires the EXACT URL it was configured to call. Behind
a TLS-terminating reverse proxy, ``request.url`` can report the internal
scheme/host (e.g. plain HTTP) instead of the externally-visible HTTPS URL
Twilio actually signed, causing legitimate signatures to fail validation.
``_canonical_request_url`` rebuilds that externally-visible URL from
``X-Forwarded-Proto``/``X-Forwarded-Host`` when present, falling back to
``request.url`` otherwise. Trusting these headers here does not weaken
the signature check: they only choose which URL string gets hashed, and
an attacker who can set them still cannot produce a valid HMAC without
the secret Twilio auth token, so a forged header can only cause a
legitimate signature to mismatch (fail closed) — never a fake one to
match.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import urlsplit

from starlette.requests import Request


async def compute_twilio_signature(url: str, form_params: dict[str, str], auth_token: str) -> str:
    """Recompute what Twilio's X-Twilio-Signature should be for this exact
    request, per Twilio's documented algorithm."""
    data = url
    for key in sorted(form_params.keys()):
        data += key + form_params[key]
    digest = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def _canonical_request_url(request: Request) -> str:
    """The URL Twilio actually signed: externally-visible scheme/host from
    the reverse proxy's forwarded headers when present, else ``request.url``
    unchanged (identical to pre-fix behavior when no proxy is involved)."""
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if not forwarded_proto or not forwarded_host:
        return str(request.url)

    scheme = forwarded_proto.split(",")[0].strip()
    host = forwarded_host.split(",")[0].strip()

    url = request.url
    path = getattr(url, "path", None)
    query = getattr(url, "query", None)
    if path is None:
        parts = urlsplit(str(url))
        path, query = parts.path, parts.query

    canonical = f"{scheme}://{host}{path}"
    if query:
        canonical += f"?{query}"
    return canonical


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

    expected = await compute_twilio_signature(_canonical_request_url(request), form_params, auth_token)
    return hmac.compare_digest(expected, signature)
