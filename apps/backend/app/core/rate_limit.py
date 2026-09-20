from fastapi import Depends, Request

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger("rate_limit")


class RateLimitExceeded(AppError):
    def __init__(self, retry_after_seconds: int):
        super().__init__(
            "Too many requests — please wait before trying again.",
            code="RATE_LIMITED",
            status_code=429,
        )
        self.retry_after_seconds = retry_after_seconds


def _client_ip(request: Request) -> str:
    """Prefer direct ASGI client host. If TRUST_PROXY_HEADERS is ever enabled
    via settings, X-Forwarded-For could be consulted — left off by default to
    prevent spoofed client IPs from bypassing buckets.
    """
    return request.client.host if request.client else "unknown"


async def _check(key: str, *, limit: int, window_seconds: int, fail_closed: bool) -> None:
    redis_client = get_redis()
    if redis_client is None:
        if fail_closed:
            logger.warning("rate_limit_redis_unavailable", key_prefix=key, fail_closed=True)
            raise RateLimitExceeded(retry_after_seconds=window_seconds)
        return

    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, window_seconds)
        if count > limit:
            ttl = await redis_client.ttl(key)
            raise RateLimitExceeded(retry_after_seconds=max(ttl, 1))
    except RateLimitExceeded:
        raise
    except Exception:
        if fail_closed:
            logger.warning("rate_limit_redis_error", key_prefix=key, fail_closed=True, exc_info=True)
            raise RateLimitExceeded(retry_after_seconds=window_seconds)
        logger.warning("rate_limit_fail_open", key_prefix=key)
        return


def rate_limit(key_prefix: str, *, limit: int, window_seconds: int, fail_closed: bool = False):
    """Fixed-window counter in Redis, keyed on client IP + key_prefix.

    For unauthenticated routes (login/register/refresh). Auth-sensitive
    recovery endpoints should pass fail_closed=True so Redis outages do not
    silently remove protection.

    Default remains fail-open for login/register (ADR-0018) so a Redis blip
    does not take down the whole auth surface.
    """

    async def dependency(request: Request) -> None:
        ip = _client_ip(request)
        await _check(
            f"ratelimit:{key_prefix}:{ip}",
            limit=limit,
            window_seconds=window_seconds,
            fail_closed=fail_closed,
        )

    return dependency


def rate_limit_per_user(key_prefix: str, *, limit: int, window_seconds: int, fail_closed: bool = False):
    """Same fixed-window limiter, keyed on the authenticated user's id."""
    from app.modules.identity.dependencies import get_current_user

    async def dependency(request: Request, user=Depends(get_current_user)) -> None:
        await _check(
            f"ratelimit:{key_prefix}:{user.id}",
            limit=limit,
            window_seconds=window_seconds,
            fail_closed=fail_closed,
        )

    return dependency
