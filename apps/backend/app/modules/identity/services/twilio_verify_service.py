"""Twilio Verify wrapper for mobile OTP login.

Uses Twilio Verify's HTTP API directly via httpx (no vendor SDK dependency).
Twilio Verify generates, delivers, and validates the OTP itself — this
service NEVER stores, logs, or returns the OTP code.

Fails closed:
* if TWILIO_VERIFY_SERVICE_SID / SID / TOKEN are unset →
  TWILIO_VERIFY_NOT_CONFIGURED (503, retryable=false).
* if Twilio returns any non-2xx →
  TWILIO_VERIFY_UNAVAILABLE (503, retryable=true) with a scrubbed detail.

The service is instance-based so tests can inject an ``httpx.AsyncClient``
transport (see ``TwilioVerifyStubTransport``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError

logger = logging.getLogger("identity.twilio_verify")

_BASE_URL = "https://verify.twilio.com/v2"


class TwilioVerifyError(AppError):
    """Typed failure — the code identifies the class, message stays generic
    so nothing leaks to the client (e.g. we do not repeat what Twilio said)."""

    def __init__(self, message: str, *, code: str, status_code: int = 503):
        super().__init__(message, code=code, status_code=status_code)


@dataclass(frozen=True)
class VerifySendResult:
    sid: str  # Twilio Verification SID (VE…) — safe to log; no PII/OTP inside.
    status: str  # pending | approved | canceled — Twilio-controlled.


@dataclass(frozen=True)
class VerifyCheckResult:
    status: str  # approved | pending | canceled
    valid: bool


class TwilioVerifyClient(Protocol):  # pragma: no cover — structural
    async def send(self, mobile_e164: str, *, channel: str = "sms") -> VerifySendResult: ...
    async def check(self, mobile_e164: str, *, code: str) -> VerifyCheckResult: ...


class TwilioVerifyService:
    """Production adapter. Reads settings on each call so hot-swap of env
    (e.g. via a test-time monkeypatch) is picked up without process restart."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        # ``transport`` is injected only in tests; production leaves it None.
        self._transport = transport

    def _cfg(self) -> tuple[str, str, str]:
        s: Settings = get_settings()
        sid = (s.twilio_account_sid or "").strip()
        token = (s.twilio_auth_token or "").strip()
        service = (s.twilio_verify_service_sid or "").strip()
        if not sid or not token or not service:
            raise TwilioVerifyError(
                "Mobile OTP service is not configured",
                code="TWILIO_VERIFY_NOT_CONFIGURED",
            )
        return sid, token, service

    async def send(self, mobile_e164: str, *, channel: str = "sms") -> VerifySendResult:
        sid, token, service = self._cfg()
        url = f"{_BASE_URL}/Services/{service}/Verifications"
        try:
            async with httpx.AsyncClient(timeout=15.0, transport=self._transport) as client:
                resp = await client.post(
                    url,
                    data={"To": mobile_e164, "Channel": channel},
                    auth=(sid, token),
                )
        except httpx.HTTPError as exc:  # network / DNS / TLS
            logger.warning("twilio_verify_send_network_error kind=%s", type(exc).__name__)
            raise TwilioVerifyError("Could not send OTP", code="TWILIO_VERIFY_UNAVAILABLE") from exc

        if resp.status_code >= 400:
            # Do not include Twilio's response text — some error responses echo
            # the destination number back. Log only status + Twilio error code.
            twilio_code = _safe_error_code(resp)
            logger.warning("twilio_verify_send_failed status=%s twilio_code=%s", resp.status_code, twilio_code)
            raise TwilioVerifyError("Could not send OTP", code="TWILIO_VERIFY_UNAVAILABLE")

        body = resp.json()
        return VerifySendResult(sid=str(body.get("sid", "")), status=str(body.get("status", "pending")))

    async def check(self, mobile_e164: str, *, code: str) -> VerifyCheckResult:
        sid, token, service = self._cfg()
        url = f"{_BASE_URL}/Services/{service}/VerificationCheck"
        try:
            async with httpx.AsyncClient(timeout=15.0, transport=self._transport) as client:
                resp = await client.post(
                    url,
                    data={"To": mobile_e164, "Code": code},
                    auth=(sid, token),
                )
        except httpx.HTTPError as exc:
            logger.warning("twilio_verify_check_network_error kind=%s", type(exc).__name__)
            raise TwilioVerifyError("Could not verify OTP", code="TWILIO_VERIFY_UNAVAILABLE") from exc

        # Twilio Verify returns 404 when the verification is expired/consumed
        # and 200 with status="pending" when the code is wrong but still open.
        if resp.status_code == 404:
            return VerifyCheckResult(status="expired", valid=False)
        if resp.status_code >= 400:
            twilio_code = _safe_error_code(resp)
            logger.warning("twilio_verify_check_failed status=%s twilio_code=%s", resp.status_code, twilio_code)
            raise TwilioVerifyError("Could not verify OTP", code="TWILIO_VERIFY_UNAVAILABLE")

        body = resp.json()
        status = str(body.get("status", "pending"))
        return VerifyCheckResult(status=status, valid=status == "approved")


def _safe_error_code(resp: httpx.Response) -> str:
    """Extract Twilio's numeric error code without echoing the message body."""
    try:
        payload = resp.json()
        return str(payload.get("code", ""))
    except Exception:  # noqa: BLE001
        return ""


class TwilioVerifyStub:
    """In-memory test double implementing the same shape as TwilioVerifyService.

    * ``send`` always accepts and records the destination.
    * ``check`` approves only the exact code passed to the last ``send`` (or
      one seeded by tests via ``seed``); rejects everything else with
      status='pending' and valid=False. Never talks to the network.

    Configured by the test to preload the "correct" code for a given number.
    """

    def __init__(self, *, seeded_code: str = "123456"):
        self._codes: dict[str, str] = {}
        self._seeded_code = seeded_code
        self.send_calls: list[tuple[str, str]] = []
        self.check_calls: list[tuple[str, str]] = []

    def seed(self, mobile_e164: str, code: str) -> None:
        self._codes[mobile_e164] = code

    async def send(self, mobile_e164: str, *, channel: str = "sms") -> VerifySendResult:
        self.send_calls.append((mobile_e164, channel))
        self._codes.setdefault(mobile_e164, self._seeded_code)
        return VerifySendResult(sid="VE_stub_" + mobile_e164[-4:], status="pending")

    async def check(self, mobile_e164: str, *, code: str) -> VerifyCheckResult:
        self.check_calls.append((mobile_e164, "***"))
        expected = self._codes.get(mobile_e164)
        if expected is None:
            return VerifyCheckResult(status="expired", valid=False)
        return VerifyCheckResult(status="approved", valid=True) if code == expected else VerifyCheckResult(
            status="pending", valid=False
        )
