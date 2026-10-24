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


async def check_rate_limit(key: str, *, limit: int, window_seconds: int, fail_closed: bool = False) -> None:
    """Public entry point to the same Redis-backed fixed-window limiter
    used by the ``rate_limit``/``rate_limit_per_user``/``rate_limit_by_mobile``
    FastAPI dependencies below, for callers that aren't a route dependency
    (e.g. a webhook service rate-limiting per external identity rather
    than per authenticated user). Raises RateLimitExceeded exactly like
    those dependencies do; same fail-open/fail-closed semantics."""
    await _check(key, limit=limit, window_seconds=window_seconds, fail_closed=fail_closed)


def _client_ip(request: Request) -> str:
    """Prefer direct ASGI client host. If TRUST_PROXY_HEADERS is ever enabled
    via settings, X-Forwarded-For could be consulted — left off by default to
    prevent spoofed client IPs from bypassing buckets.
    """
    return request.client.host if request.client else "unknown"


async def _check(key: str, *, limit: int, window_seconds: int, fail_closed: bool, log_key: str | None = None) -> None:
    """``log_key`` is what appears in warning logs — defaults to ``key`` so
    existing callers (IP/user-id keyed, not considered sensitive enough to
    warrant a separate identifier) are unaffected. Callers whose key embeds
    PII (e.g. a phone number) should pass a redacted ``log_key`` instead;
    ``key`` itself is never touched, so the actual rate-limit bucket and its
    collision-safety are unchanged."""
    if log_key is None:
        log_key = key
    redis_client = get_redis()
    if redis_client is None:
        if fail_closed:
            logger.warning("rate_limit_redis_unavailable", key_prefix=log_key, fail_closed=True)
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
            logger.warning("rate_limit_redis_error", key_prefix=log_key, fail_closed=True, exc_info=True)
            # The original Redis error is already fully logged above (exc_info=True);
            # deliberately not chaining it here so the raw infra exception/traceback
            # doesn't propagate into whatever handles RateLimitExceeded downstream.
            raise RateLimitExceeded(retry_after_seconds=window_seconds) from None
        logger.warning("rate_limit_fail_open", key_prefix=log_key)
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


def rate_limit_by_email(key_prefix: str, *, limit: int, window_seconds: int, fail_closed: bool = False):
    """Fixed-window limiter keyed on the request's normalized (lowercased,
    stripped) login email, not the caller's IP.

    Added for /auth/login specifically (docs/audits/auth-otp-feature-audit.md
    "Login rate-limit follow-up"): the existing IP-keyed ``rate_limit`` on
    that route shares exactly the problem ``rate_limit_by_mobile`` above was
    already built to work around -- behind Railway's edge, ``request.client.
    host`` does not give a stable per-external-caller identity (see that
    function's own docstring, written by an earlier session with direct
    knowledge of this). For login specifically this is worse than merely
    "ineffective": it can make genuine, correctly-credentialed logins from
    unrelated users collide into one shared bucket and get 429'd together.

    This does NOT replace the IP-keyed layer (kept in place, unchanged, as a
    coarse volumetric backstop) and does NOT touch the existing per-account
    failed-password lockout in AuthService.authenticate (MAX_FAILED_ATTEMPTS/
    LOCKOUT_MINUTES) -- that is a separate, already-correct, IP-independent
    protection against credential guessing on one account. This dependency
    adds a THIRD, additive layer: a per-email ceiling on login *attempts*
    (successful or not), so a flood of attempts against other people's
    emails can never consume a legitimate user's own budget, regardless of
    what request.client.host resolves to for either of them. Trusts no
    client-supplied header (no X-Forwarded-For) -- the identity here is the
    login request's own submitted email, already required to reach the
    database lookup downstream, so this adds no new spoofing surface: an
    attacker can already submit any email; they just get their own bucket
    for it, never anyone else's.

    Falls back to the IP-based key if the email is missing/malformed, so
    those requests stay bounded rather than silently exempt. The Redis key
    embeds a salted hash of the email (never the plaintext) so a Redis
    failure's warning log never puts an email address in cleartext logs --
    same convention as rate_limit_by_mobile's phone-number hashing.

    Known, accepted trade-off (reviewed explicitly, not overlooked -- see
    docs/audits/auth-otp-feature-audit.md "rate_limit_by_email review"):
    because this counts every attempt against an email regardless of
    outcome, anyone who knows (or guesses) a target's login email can
    submit `limit` requests for it within `window_seconds` and cause that
    target's own, correctly-credentialed next login attempt to receive a
    429 until the window rolls over -- a small, bounded, single-account
    denial-of-service window, not an account takeover or credential
    exposure. This is the exact same shape of trade-off already present,
    unmodified, in `rate_limit_by_mobile` above (a known phone number lets
    an attacker exhaust that OTP-request bucket the same way) -- extending
    an already-accepted pattern to login, not introducing a new category
    of risk. `window_seconds`/`limit` should be tuned generous enough that
    legitimate retry bursts never hit it while keeping the window short
    enough that the DoS is self-resolving in under a minute; see
    test_login_rate_limit_shared_proxy_mitigation.py's
    `test_rate_limit_by_email_creates_a_bounded_targeted_dos_window` for a
    concrete demonstration of this exact trade-off, not just a description
    of it.
    """
    from app.modules.identity.services.token_service import hash_opaque_token

    async def dependency(request: Request) -> None:
        try:
            body = await request.json()
            raw_email = str(body.get("email") or "").strip().lower()
        except Exception:
            raw_email = ""

        if raw_email:
            identity = f"email:{hash_opaque_token(raw_email)[:16]}"
            log_identity = identity  # already non-reversible; safe to log as-is
        else:
            ip = _client_ip(request)
            identity = f"ip:{ip}"
            log_identity = identity

        await _check(
            f"ratelimit:{key_prefix}:{identity}",
            limit=limit,
            window_seconds=window_seconds,
            fail_closed=fail_closed,
            log_key=f"ratelimit:{key_prefix}:{log_identity}",
        )

    return dependency


def rate_limit_by_mobile(key_prefix: str, *, limit: int, window_seconds: int, fail_closed: bool = False):
    """Fixed-window limiter keyed on the request's normalized mobile number,
    not the caller's IP.

    Behind Railway's edge, ``request.client.host`` is the address of whichever
    internal proxy instance happened to terminate that connection — it
    rotates across requests from the same external caller, so the IP-keyed
    ``rate_limit`` above never accumulates a meaningful count for OTP abuse
    from a single phone number. Keying on the (normalized) target mobile
    number instead gives a stable identity regardless of which edge IP the
    request lands on, without weakening the existing IP-based layer, which
    stays in place as an additional dependency on the same route.

    The request body is read once via ``request.json()``; Starlette caches
    the parsed body, so the route's own Pydantic body parameter still reads
    the identical bytes — no double-consumption of the ASGI stream.

    If the mobile can't be normalized (malformed input), falls back to the
    IP-based key so those requests are still bounded rather than silently
    exempt from this layer.

    The Redis key itself still embeds the normalized mobile number (needed
    for correct, collision-safe bucketing) — but on a Redis failure, `_check`
    would otherwise log that key verbatim, putting a phone number in
    cleartext logs. A hashed stand-in (same `hash_opaque_token` SHA-256
    convention already used for recovery codes) is passed as `log_key` so
    logs only ever see a non-reversible identifier, never the number.
    """
    from app.core.exceptions import AppError as _AppError
    from app.modules.identity.services.profile_validation import normalize_indian_mobile
    from app.modules.identity.services.token_service import hash_opaque_token

    async def dependency(request: Request) -> None:
        try:
            body = await request.json()
            raw_mobile = str(body.get("mobile") or "")
        except Exception:
            raw_mobile = ""

        try:
            mobile = normalize_indian_mobile(raw_mobile)
            identity = f"mobile:{mobile}"
            log_identity = f"mobile:{hash_opaque_token(mobile)[:12]}"
        except _AppError:
            ip = _client_ip(request)
            identity = f"ip:{ip}"
            log_identity = identity

        await _check(
            f"ratelimit:{key_prefix}:{identity}",
            limit=limit,
            window_seconds=window_seconds,
            fail_closed=fail_closed,
            log_key=f"ratelimit:{key_prefix}:{log_identity}",
        )

    return dependency
