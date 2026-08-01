from fastapi import Depends, Request

from app.core.exceptions import AppError
from app.core.redis import get_redis


class RateLimitExceeded(AppError):
    def __init__(self, retry_after_seconds: int):
        super().__init__(
            "Too many requests — please wait before trying again.",
            code="RATE_LIMITED",
            status_code=429,
        )
        self.retry_after_seconds = retry_after_seconds


async def _check(key: str, *, limit: int, window_seconds: int) -> None:
    redis_client = get_redis()
    if redis_client is None:
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
        return


def rate_limit(key_prefix: str, *, limit: int, window_seconds: int):
    """Fixed-window counter in Redis, keyed on client IP + key_prefix.

    For unauthenticated routes (login/register/refresh) — see rate_limit_per_user
    for authenticated routes where per-user is the fairer key.

    Fails open (no limiting) if Redis isn't reachable — a rate limiter that
    takes the API down when its own dependency is unavailable is worse than
    no rate limiter, see ADR-0018.
    """

    async def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        await _check(f"ratelimit:{key_prefix}:{ip}", limit=limit, window_seconds=window_seconds)

    return dependency


def rate_limit_per_user(key_prefix: str, *, limit: int, window_seconds: int):
    """Same fixed-window limiter, keyed on the authenticated user's id instead
    of IP — fairer for routes behind auth (AI Gateway, commerce) where a
    shared office/NAT IP shouldn't share one budget, and a per-call cost
    (real AI tokens once a key is configured, per ADR-0014) is exactly what
    this is meant to bound.
    """
    from app.modules.identity.dependencies import get_current_user

    async def dependency(request: Request, user=Depends(get_current_user)) -> None:
        await _check(f"ratelimit:{key_prefix}:{user.id}", limit=limit, window_seconds=window_seconds)

    return dependency
