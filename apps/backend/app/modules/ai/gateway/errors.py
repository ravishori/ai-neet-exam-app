"""Normalize HTTP/SDK exceptions into ProviderError codes (no secrets)."""

from __future__ import annotations

import httpx

from app.modules.ai.gateway.base import (
    PROVIDER_AUTH_FAILED,
    PROVIDER_BLOCKED,
    PROVIDER_ERROR,
    PROVIDER_INVALID_RESPONSE,
    PROVIDER_RATE_LIMITED,
    PROVIDER_TIMEOUT,
    PROVIDER_UNAVAILABLE,
    ProviderError,
)


def classify_http_error(provider: str, status: int | None, body: str = "", exc: BaseException | None = None) -> ProviderError:
    text = (body or str(exc or "")).lower()
    # Safe excerpt of the PROVIDER'S OWN RESPONSE body (never the outgoing
    # request, so this can never contain the Authorization header/API key).
    detail = (body or str(exc or ""))[:300] or None
    if status in {401, 403} or "invalid api key" in text or "authentication" in text or "unauthorized" in text:
        return ProviderError(PROVIDER_AUTH_FAILED, "Provider authentication failed", provider=provider, retryable=False, http_status=status, provider_detail=detail)
    # Billing / credits must NEVER be treated as retryable 429.
    if (
        ("credit" in text and ("balance" in text or "billing" in text or "too low" in text or "insufficient" in text))
        or ("billing" in text and ("hard limit" in text or "exceeded" in text or "disabled" in text))
        or ("payment" in text and ("required" in text or "failed" in text))
        or ("quota" in text and ("billing" in text or "purchase" in text or "plan" in text))
    ):
        return ProviderError(PROVIDER_BLOCKED, "Provider billing/credits blocked", provider=provider, retryable=False, http_status=status, provider_detail=detail)
    if status == 429 or "rate limit" in text or ("quota" in text and "exceed" in text):
        return ProviderError(PROVIDER_RATE_LIMITED, "Provider rate limited", provider=provider, retryable=True, http_status=status, provider_detail=detail)
    if isinstance(exc, httpx.TimeoutException | TimeoutError) or "timeout" in text:
        return ProviderError(PROVIDER_TIMEOUT, "Provider request timed out", provider=provider, retryable=True, http_status=status, provider_detail=detail)
    # 404 specifically means "this endpoint/route does not exist as configured"
    # (wrong base_url/path, or — for some gateways — a model name the account
    # has no deployment for) — distinct from a 400 (malformed/rejected request
    # the server did understand). Conflating the two previously made a
    # misconfigured endpoint indistinguishable from a bad request body.
    if status == 404:
        return ProviderError(PROVIDER_INVALID_RESPONSE, "Provider endpoint/model not found (check base_url/model configuration)", provider=provider, retryable=False, http_status=status, provider_detail=detail)
    if status == 400 or "invalid" in text:
        return ProviderError(PROVIDER_INVALID_RESPONSE, "Provider rejected request or returned invalid payload", provider=provider, http_status=status, provider_detail=detail)
    if status is not None and status >= 500:
        return ProviderError(PROVIDER_UNAVAILABLE, "Provider unavailable", provider=provider, retryable=True, http_status=status, provider_detail=detail)
    if isinstance(exc, httpx.HTTPError):
        return ProviderError(PROVIDER_UNAVAILABLE, "Provider HTTP error", provider=provider, retryable=True, http_status=status, provider_detail=detail)
    return ProviderError(PROVIDER_ERROR, "Provider error", provider=provider, retryable=False, http_status=status, provider_detail=detail)


def map_exception(provider: str, exc: BaseException) -> ProviderError:
    if isinstance(exc, ProviderError):
        return exc
    status = getattr(exc, "status_code", None)
    body = ""
    if hasattr(exc, "response") and getattr(exc, "response", None) is not None:
        try:
            body = getattr(exc.response, "text", "") or ""
            status = status or getattr(exc.response, "status_code", None)
        except Exception:  # noqa: BLE001
            body = ""
    msg = str(exc)
    # Anthropic SDK often embeds status in message
    if "401" in msg or "403" in msg:
        status = status or 401
    if "429" in msg:
        status = status or 429
    return classify_http_error(provider, status, body or msg, exc)
