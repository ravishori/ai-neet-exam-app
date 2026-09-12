"""Outbound email abstraction.

Development: logs a non-secret notice and (only when not production) the
reset/verify link for local Mailpit testing — tokens are never logged in
production.

Production: if SMTP_* settings are configured, sends via smtplib. If not,
logs email_not_configured and returns without raising (callers already use
enumeration-safe responses).
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("email")


def _app_base_url() -> str:
    return get_settings().web_app_url.rstrip("/")


def _send(*, to: str, subject: str, body: str, kind: str) -> None:
    settings = get_settings()
    if settings.smtp_host and settings.smtp_from:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = settings.smtp_from
            msg["To"] = to
            msg.set_content(body)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
            logger.info("email_sent", kind=kind, to=to)
            return
        except Exception:
            logger.error("email_send_failed", kind=kind, to=to, exc_info=True)
            return

    if settings.is_production:
        logger.warning("email_not_configured", kind=kind, to=to)
        return

    # Dev-only: include link so flows are testable. Never do this in production.
    logger.info("email_dev_preview", kind=kind, to=to, body=body)


def send_verification_email(*, to: str, token: str) -> None:
    link = f"{_app_base_url()}/verify-email?token={token}"
    _send(
        to=to,
        subject="Verify your Trinetra account",
        body=f"Verify your email by opening this link:\n\n{link}\n\nIf you did not register, ignore this message.",
        kind="verification",
    )


def send_password_reset_email(*, to: str, token: str) -> None:
    link = f"{_app_base_url()}/reset-password?token={token}"
    _send(
        to=to,
        subject="Reset your Trinetra password",
        body=f"Reset your password by opening this link (expires soon):\n\n{link}\n\nIf you did not request a reset, ignore this message.",
        kind="password_reset",
    )


def send_security_alert_email(*, subject: str, body: str) -> None:
    """Ops alert — destination from settings.alert_email; never includes secrets."""
    settings = get_settings()
    to = settings.alert_email
    if not to:
        logger.warning("alert_email_not_configured", subject=subject)
        return
    _send(to=to, subject=subject, body=body, kind="security_alert")
