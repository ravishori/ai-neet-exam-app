"""Critical error / security alert emails with Redis dedupe + cooldown."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.modules.identity.services.email_service import send_security_alert_email

logger = get_logger("alerts")

DEFAULT_COOLDOWN_SECONDS = 300


async def maybe_send_critical_alert(
    *,
    subject: str,
    body: str,
    dedupe_key: str,
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
) -> bool:
    """Return True if an alert email was attempted (not necessarily delivered)."""
    redis_client = get_redis()
    cache_key = f"alert:dedupe:{dedupe_key}"
    if redis_client is not None:
        try:
            was_set = await redis_client.set(cache_key, "1", nx=True, ex=cooldown_seconds)
            if not was_set:
                logger.info("alert_deduped", dedupe_key=dedupe_key)
                return False
        except Exception:
            logger.warning("alert_dedupe_redis_error", dedupe_key=dedupe_key, exc_info=True)

    send_security_alert_email(subject=subject, body=body)
    return True
