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
notice and (only when not production) the rendered text body itself, for
local testability — plaintext OTPs/tokens are never logged in production.

Provider/SMTP failures are always caught and logged; they never raise into
the caller, so the enumeration-safe generic response callers already return
is unaffected either way. A production delivery failure additionally pages
via _notify_admin_of_email_failure.

All sends go through ``_send``, which builds both an html and a plaintext
body from email_templates.py and is async throughout — the only blocking
call (SMTP, dev-only) is off-loaded via asyncio.to_thread.

Reply-To is set to settings.support_email — the public-facing student
support/contact address. That address is an existing forwarding alias onto
the real configured mailbox, not a separate dedicated inbox; this module
never exposes the real underlying mailbox address to students.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.modules.identity.services import email_templates as tpl

logger = get_logger("email")

_PROVIDER_TIMEOUT_SECONDS = 8.0


def _app_base_url() -> str:
    return get_settings().web_app_url.rstrip("/")


def _sender_header(settings: Settings, from_addr: str) -> str:
    return f"{settings.email_from_name} <{from_addr}>" if settings.email_from_name else from_addr


async def _send_via_resend(*, to: str, subject: str, html: str, text: str, settings: Settings) -> None:
    sender = _sender_header(settings, settings.email_from)
    payload = {"from": sender, "to": [to], "subject": subject, "html": html, "text": text}
    if settings.support_email:
        payload["reply_to"] = settings.support_email
    async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.email_api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    if resp.status_code >= 400:
        # Never include the response body in the exception/log — provider
        # error payloads can echo back request details we don't want in logs.
        raise RuntimeError(f"resend_api_error status={resp.status_code}")


def _send_via_smtp_blocking(*, to: str, subject: str, html: str, text: str, settings: Settings) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _sender_header(settings, settings.smtp_from)
    msg["To"] = to
    if settings.support_email:
        msg["Reply-To"] = settings.support_email
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
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


async def _send(*, to: str, subject: str, html: str, text: str, kind: str) -> None:
    settings = get_settings()

    if settings.email_provider == "resend" and settings.email_api_key and settings.email_from:
        try:
            await _send_via_resend(to=to, subject=subject, html=html, text=text, settings=settings)
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
            await asyncio.to_thread(
                _send_via_smtp_blocking, to=to, subject=subject, html=html, text=text, settings=settings
            )
            logger.info("email_sent", kind=kind, to=to, provider="smtp")
            return
        except Exception:
            logger.error("email_send_failed", kind=kind, to=to, provider="smtp", exc_info=True)
            return

    if settings.is_production:
        logger.warning("email_not_configured", kind=kind, to=to)
        await _notify_admin_of_email_failure(kind=kind, reason="provider_not_configured")
        return

    # Dev-only: log the rendered text body so flows are testable locally.
    # Subject is never sensitive; never do the body-logging in production
    # (guarded above).
    logger.info("email_dev_preview", kind=kind, to=to, subject=subject, body=text)


async def send_welcome_email(*, to: str, first_name: str, email_verified: bool) -> None:
    settings = get_settings()
    subject, html, text = tpl.welcome_email(
        first_name=first_name,
        dashboard_url=f"{_app_base_url()}/student/dashboard",
        email_verified=email_verified,
        support_email=settings.support_email,
    )
    await _send(to=to, subject=subject, html=html, text=text, kind="welcome")


async def send_verification_email(*, to: str, token: str) -> None:
    settings = get_settings()
    link = f"{_app_base_url()}/verify-email?token={token}"
    subject, html, text = tpl.email_verification_email(
        verify_url=link, expires_in_hours=24, support_email=settings.support_email
    )
    await _send(to=to, subject=subject, html=html, text=text, kind="verification")


async def send_email_verification_otp_email(*, to: str, code: str) -> None:
    from app.modules.identity.services.otp_service import OTP_TTL_MINUTES

    settings = get_settings()
    subject, html, text = tpl.email_verification_otp_email(
        code=code, expires_in_minutes=OTP_TTL_MINUTES, support_email=settings.support_email
    )
    await _send(to=to, subject=subject, html=html, text=text, kind="email_verification_otp")


async def send_login_otp_email(*, to: str, code: str) -> None:
    from app.modules.identity.services.otp_service import OTP_TTL_MINUTES

    settings = get_settings()
    subject, html, text = tpl.login_otp_email(
        code=code, expires_in_minutes=OTP_TTL_MINUTES, support_email=settings.support_email
    )
    await _send(to=to, subject=subject, html=html, text=text, kind="login_otp")


async def send_password_reset_email(*, to: str, token: str) -> None:
    settings = get_settings()
    link = f"{_app_base_url()}/reset-password?token={token}"
    subject, html, text = tpl.password_reset_email(
        reset_url=link, expires_in_hours=24, support_email=settings.support_email
    )
    await _send(to=to, subject=subject, html=html, text=text, kind="password_reset")


async def send_password_changed_email(*, to: str, when_text: str) -> None:
    settings = get_settings()
    subject, html, text = tpl.password_changed_email(when_text=when_text, support_email=settings.support_email)
    await _send(to=to, subject=subject, html=html, text=text, kind="password_changed")


async def send_new_login_alert_email(*, to: str, when_text: str, ip_address: str | None, device_text: str | None) -> None:
    """Template/service kept ready, but NOT wired to fire automatically on
    every login — see auth_service.authenticate. No known-device/anomaly
    detection exists yet, so sending this on every password login would be
    noise, not a security signal. Call this once real new/unrecognized-login
    detection exists."""
    settings = get_settings()
    subject, html, text = tpl.new_login_alert_email(
        when_text=when_text, ip_address=ip_address, device_text=device_text, support_email=settings.support_email
    )
    await _send(to=to, subject=subject, html=html, text=text, kind="new_login_alert")


async def send_email_changed_email(*, to: str, new_email_masked: str, when_text: str) -> None:
    """Net-new template. No existing endpoint changes a user's email today —
    call this once such a flow exists; kept ready so the template isn't
    built twice."""
    settings = get_settings()
    subject, html, text = tpl.email_changed_email(
        new_email_masked=new_email_masked, when_text=when_text, support_email=settings.support_email
    )
    await _send(to=to, subject=subject, html=html, text=text, kind="email_changed")


async def send_mobile_changed_email(*, to: str, new_mobile_masked: str, when_text: str) -> None:
    settings = get_settings()
    subject, html, text = tpl.mobile_changed_email(
        new_mobile_masked=new_mobile_masked, when_text=when_text, support_email=settings.support_email
    )
    await _send(to=to, subject=subject, html=html, text=text, kind="mobile_changed")


async def send_security_alert_email(*, subject: str, body: str) -> None:
    """Ops alert — destination from settings.ops_alert_email; never includes secrets."""
    settings = get_settings()
    to = settings.ops_alert_email
    if not to:
        logger.warning("alert_email_not_configured", subject=subject)
        return
    await _send(to=to, subject=subject, html=f"<pre>{body}</pre>", text=body, kind="security_alert")
