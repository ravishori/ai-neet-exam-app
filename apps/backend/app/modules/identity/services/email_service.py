"""Outbound email abstraction.

Production: sends via an HTTPS transactional-email provider (Resend today).
Railway production cannot reach outbound SMTP-class ports — confirmed via
direct network diagnostics from the production container (DNS resolves,
but TCP connect to smtp.gmail.com on 587/465/25 all fail with
errno=101 ENETUNREACH, while HTTPS egress on 443 succeeds instantly).
SMTP is therefore never attempted in production, regardless of whether
SMTP_* settings happen to be set.

Development/local: SMTP remains available as an explicit fallback (useful
against a local Mailpit-style catcher), used only when NOT production.
If neither the HTTPS provider nor SMTP is configured, logs a non-secret
notice and (only when not production) the reset/verify link itself, for
local testability — tokens are never logged in production.

Provider/SMTP failures are always caught and logged; they never raise
into the caller, so the enumeration-safe generic response callers already
return is unaffected either way.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("email")

_PROVIDER_TIMEOUT_SECONDS = 8.0


def _app_base_url() -> str:
    return get_settings().web_app_url.rstrip("/")


async def _send_via_resend(*, to: str, subject: str, body: str, settings: Settings) -> None:
    sender = (
        f"{settings.email_from_name} <{settings.email_from}>" if settings.email_from_name else settings.email_from
    )
    async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.email_api_key}", "Content-Type": "application/json"},
            json={"from": sender, "to": [to], "subject": subject, "text": body},
        )
    if resp.status_code >= 400:
        # Never include the response body in the exception/log — provider
        # error payloads can echo back request details we don't want in logs.
        raise RuntimeError(f"resend_api_error status={resp.status_code}")


def _send_via_smtp_blocking(*, to: str, subject: str, body: str, settings: Settings) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=_PROVIDER_TIMEOUT_SECONDS) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)


async def _notify_admin_of_email_failure(*, kind: str, reason: str) -> None:
    """Fire admin-visible alert for a production email-delivery problem.

    Never called for kind == "security_alert": that would recurse back into
    _send() for another security_alert on every failed alert attempt. A
    failure to send the alert itself is already handled safely (logged, not
    retried) by maybe_send_critical_alert's own except block.
    """
    if kind == "security_alert":
        return
    from app.core.alerts import maybe_send_critical_alert

    try:
        await maybe_send_critical_alert(
            subject=f"[NEET APP ERROR] Email delivery failure — {kind}",
            body=(
                "Outbound email delivery failed or is unconfigured in production.\n\n"
                f"Kind: {kind}\nReason: {reason}\n\n"
                "Check EMAIL_PROVIDER / EMAIL_API_KEY / EMAIL_FROM configuration. "
                "Note: if the provider is down entirely, this alert email may also "
                "fail to deliver — check application logs directly in that case."
            ),
            dedupe_key=f"email_delivery_failure:{kind}",
        )
    except Exception:
        logger.warning("email_failure_alert_failed", kind=kind, exc_info=True)


async def _send(*, to: str, subject: str, body: str, kind: str) -> None:
    settings = get_settings()

    if settings.email_provider == "resend" and settings.email_api_key and settings.email_from:
        try:
            await _send_via_resend(to=to, subject=subject, body=body, settings=settings)
            logger.info("email_sent", kind=kind, to=to, provider="resend")
            return
        except Exception:
            logger.error("email_send_failed", kind=kind, to=to, provider="resend", exc_info=True)
            await _notify_admin_of_email_failure(kind=kind, reason="resend_provider_failure")
            return

    # SMTP is a development-only fallback — never attempted in production
    # (see module docstring: Railway blocks outbound SMTP ports).
    if not settings.is_production and settings.smtp_host and settings.smtp_from:
        try:
            await asyncio.to_thread(_send_via_smtp_blocking, to=to, subject=subject, body=body, settings=settings)
            logger.info("email_sent", kind=kind, to=to, provider="smtp")
            return
        except Exception:
            logger.error("email_send_failed", kind=kind, to=to, provider="smtp", exc_info=True)
            return

    if settings.is_production:
        logger.warning("email_not_configured", kind=kind, to=to)
        await _notify_admin_of_email_failure(kind=kind, reason="provider_not_configured")
        return

    # Dev-only: include link so flows are testable. Never do this in production.
    logger.info("email_dev_preview", kind=kind, to=to, body=body)


async def send_verification_email(*, to: str, token: str) -> None:
    link = f"{_app_base_url()}/verify-email?token={token}"
    await _send(
        to=to,
        subject="Verify your Trinetra account",
        body=f"Verify your email by opening this link:\n\n{link}\n\nIf you did not register, ignore this message.",
        kind="verification",
    )


async def send_password_reset_email(*, to: str, token: str) -> None:
    link = f"{_app_base_url()}/reset-password?token={token}"
    await _send(
        to=to,
        subject="Reset your Trinetra password",
        body=f"Reset your password by opening this link (expires soon):\n\n{link}\n\nIf you did not request a reset, ignore this message.",
        kind="password_reset",
    )


async def send_security_alert_email(*, subject: str, body: str) -> None:
    """Ops alert — destination from settings.ops_alert_email; never includes secrets."""
    settings = get_settings()
    to = settings.ops_alert_email
    if not to:
        logger.warning("alert_email_not_configured", subject=subject)
        return
    await _send(to=to, subject=subject, body=body, kind="security_alert")
