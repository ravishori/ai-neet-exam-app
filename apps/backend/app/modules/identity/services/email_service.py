from app.core.logging import get_logger

logger = get_logger("email")

# No SMTP wired up yet (Mailpit is available via docker-compose for when
# it is — see infrastructure/docker/README.md). Until then, log the link
# so registration/reset flows are fully testable end to end.


def send_verification_email(*, to: str, token: str) -> None:
    link = f"http://localhost:3000/verify-email?token={token}"
    logger.info("email_verification_link", to=to, link=link)


def send_password_reset_email(*, to: str, token: str) -> None:
    link = f"http://localhost:3000/reset-password?token={token}"
    logger.info("password_reset_link", to=to, link=link)
