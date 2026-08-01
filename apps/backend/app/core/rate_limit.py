from fastapi import Request

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


def rate_limit(key_prefix: str, *, limit: int, window_seconds: int):
    """Fixed-window counter in Redis, keyed on client IP + key_prefix.

    Fails open (no limiting) if Redis isn't reachable — a rate limiter that
    takes the API down when its own dependency is unavailable is worse than
    no rate limiter, see ADR-0018.
    """

    async def dependency(request: Request) -> None:
        redis_client = get_redis()
        if redis_client is None:
            return

        ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{key_prefix}:{ip}"

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

    return dependency
