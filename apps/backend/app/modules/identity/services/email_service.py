from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("email")

# No SMTP wired up yet (Mailpit is available via docker-compose for when
# it is — see infrastructure/docker/README.md). Until then, log the link
# so registration/reset flows are fully testable end to end in dev.
#
# Never log the raw token in production: a password-reset or email-
# verification token is equivalent to a login for that account, and
# application logs are typically readable by more people/systems than the
# email inbox it was meant to reach — logging it there just moves the
# leak surface, it doesn't close it. Once real SMTP exists this whole
# module is replaced; until then, production silently doesn't deliver
# these emails (see docs/deploy/RUNBOOK.md), which is the safe failure
# mode, not the raw-token log line.


def send_verification_email(*, to: str, token: str) -> None:
    if get_settings().is_production:
        logger.warning("email_not_configured", kind="verification", to=to)
        return
    link = f"http://localhost:3000/verify-email?token={token}"
    logger.info("email_verification_link", to=to, link=link)


def send_password_reset_email(*, to: str, token: str) -> None:
    if get_settings().is_production:
        logger.warning("email_not_configured", kind="password_reset", to=to)
        return
    link = f"http://localhost:3000/reset-password?token={token}"
    logger.info("password_reset_link", to=to, link=link)
