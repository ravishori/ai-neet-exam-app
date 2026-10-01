"""M2-A: secure, one-time WhatsApp account-linking codes.

Security properties (see docs/whatsapp/WHATSAPP_M2A_ACCOUNT_LINKING.md for
the full design):
* A WhatsApp identity is never linked by phone-number match alone — only
  by successful verification of a code generated for a specific,
  already-authenticated user.
* Codes are stored hashed only; the plaintext is returned exactly once,
  at generation, to the authenticated caller.
* Expiry, single-use (atomic consumption), and attempt-limiting all apply.
* Verification failures are deliberately generic (``INVALID_CODE`` covers
  wrong/expired/locked/already-consumed) to avoid giving an attacker a
  signal about *why* a guess failed.
* A blocked WhatsApp identity is rejected before any code comparison runs.
* An identity already correctly linked to the code's user is idempotent
  success; an identity linked to a *different* user is a CONFLICT and is
  never overwritten.
"""

from __future__ import annotations

import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.core.rate_limit import RateLimitExceeded, check_rate_limit
from app.modules.identity.repositories.user_repository import UserRepository
from app.modules.identity.services.token_service import hash_opaque_token
from app.modules.whatsapp.models.whatsapp_identity import WhatsAppIdentity
from app.modules.whatsapp.repositories.whatsapp_link_code_repository import WhatsAppLinkCodeRepository

logger = get_logger("whatsapp.link_code")

CODE_LENGTH = 8
CODE_TTL_MINUTES = 10
MAX_ATTEMPTS = 5

# Verification-attempt throttling boundary. The WhatsApp side of this flow
# is unauthenticated (anyone can message the Twilio number), so there is
# no session to attribute a failed guess to one specific pending code.
# Earlier revision of this service incremented *every* active code's
# per-code `attempts` counter on each unmatched guess — that let one
# phone's bad guesses lock out an unrelated user's pending code, which is
# unacceptable cross-user impact. This is replaced with rate-limiting
# verification attempts per WhatsApp phone number (the actual
# unauthenticated boundary), via the same check_rate_limit() primitive
# M1's own webhook already uses for inbound-message throttling. Per-code
# `attempts`/`max_attempts` remain in the schema as a structural ceiling
# but are no longer incremented on a non-match — see verify_and_link.
_VERIFY_RATE_LIMIT_KEY_PREFIX = "whatsapp_link_verify"
_VERIFY_RATE_LIMIT = 5
_VERIFY_RATE_LIMIT_WINDOW_SECONDS = 300
# Excludes visually ambiguous characters (0/O, 1/I/L) — this code is read
# off a screen and typed into WhatsApp by hand, unlike a numeric OTP
# autofilled from SMS.
_CODE_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "01OIL")


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(CODE_LENGTH))


def looks_like_link_code(text: str | None) -> str | None:
    """Minimal downstream-message recognizer: does an inbound WhatsApp
    message's text look shaped like a link code? Returns the normalized
    (stripped, uppercased) candidate if so, else None.

    This function alone grants nothing — it only decides whether
    verify_and_link's cryptographic hash comparison is worth attempting.
    Called from dispatch_link_code_verification_in_background (below),
    which whatsapp_webhook_router.py invokes via FastAPI BackgroundTasks
    after the frozen M1 webhook response has already been sent — never
    from inside whatsapp_webhook_service.py itself."""
    if not text:
        return None
    candidate = text.strip().upper()
    if len(candidate) != CODE_LENGTH:
        return None
    if any(ch not in _CODE_ALPHABET for ch in candidate):
        return None
    return candidate


class LinkOutcome(str, Enum):
    LINKED = "linked"
    ALREADY_LINKED = "already_linked"
    INVALID_CODE = "invalid_code"
    CONFLICT = "conflict"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class GeneratedLinkCode:
    plaintext_code: str
    expires_at: datetime


@dataclass(frozen=True)
class VerifyResult:
    outcome: LinkOutcome
    user_id: uuid.UUID | None = None


class WhatsAppLinkCodeService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._codes = WhatsAppLinkCodeRepository(session)
        self._users = UserRepository(session)

    async def generate_code(self, *, user_id: uuid.UUID) -> GeneratedLinkCode:
        """Caller (the HTTP router) must already have authenticated this
        user_id — this method performs no authentication itself. A fresh
        request supersedes any still-pending codes for the same user, same
        as OtpService's "invalidate prior unused challenges" behavior."""
        await self._codes.invalidate_pending_for_user(user_id)

        plaintext = _generate_code()
        expires_at = datetime.now(UTC) + timedelta(minutes=CODE_TTL_MINUTES)
        await self._codes.create(
            user_id=user_id,
            code_hash=hash_opaque_token(plaintext),
            expires_at=expires_at,
            max_attempts=MAX_ATTEMPTS,
        )
        # Never log the plaintext code.
        logger.info("whatsapp_link_code_generated", user_id=str(user_id))
        return GeneratedLinkCode(plaintext_code=plaintext, expires_at=expires_at)

    async def verify_and_link(self, *, plaintext_code: str, identity: WhatsAppIdentity) -> VerifyResult:
        """Never raises on a bad/expired/guessed-wrong code — always
        returns a VerifyResult, since this runs from a message-processing
        context that must not be able to crash on untrusted input."""
        if identity.status == "blocked":
            logger.warning("whatsapp_link_code_rejected", reason="blocked_identity", whatsapp_identity_id=str(identity.id))
            return VerifyResult(outcome=LinkOutcome.BLOCKED)

        try:
            await check_rate_limit(
                f"ratelimit:{_VERIFY_RATE_LIMIT_KEY_PREFIX}:{identity.phone_e164}",
                limit=_VERIFY_RATE_LIMIT,
                window_seconds=_VERIFY_RATE_LIMIT_WINDOW_SECONDS,
                # fail_closed=False: matches M1's own established
                # convention for this message-processing path (see
                # whatsapp_webhook_service.py's _RATE_LIMIT constants and
                # docstring) rather than auth_router.py's interactive-HTTP
                # OTP endpoints — this runs from a fire-and-forget
                # background task with no user waiting on a response, so a
                # Redis outage degrading to "rate limiting temporarily
                # off" is preferable to silently blocking all WhatsApp
                # linking. The per-code hash comparison (~40 bits of
                # entropy) remains the real security boundary regardless.
                fail_closed=False,
            )
        except RateLimitExceeded:
            logger.warning("whatsapp_link_code_rate_limited", whatsapp_identity_id=str(identity.id))
            # Same generic outcome as any other failure — no distinct
            # signal that rate limiting (vs. a wrong code) was the cause.
            return VerifyResult(outcome=LinkOutcome.INVALID_CODE)

        now = datetime.now(UTC)
        candidates = await self._codes.find_candidates_for_verification(now=now)

        target_hash = hash_opaque_token(plaintext_code)
        matched = None
        for candidate in candidates:
            if secrets.compare_digest(candidate.code_hash, target_hash):
                matched = candidate
                break

        if matched is None:
            # No code matched this guess. The per-phone rate limit above
            # is the active abuse-control boundary for this case — a
            # non-match never mutates any code row, so one phone's bad
            # guesses can never affect another user's pending code.
            logger.info("whatsapp_link_code_failed", reason="no_match", whatsapp_identity_id=str(identity.id))
            return VerifyResult(outcome=LinkOutcome.INVALID_CODE)

        user = await self._users.get_by_id(matched.user_id)
        if user is None:
            # The code's user was deleted/soft-deleted after the code was
            # issued — treat exactly like any other invalid code, no
            # distinct signal.
            logger.info("whatsapp_link_code_failed", reason="user_gone", whatsapp_identity_id=str(identity.id))
            return VerifyResult(outcome=LinkOutcome.INVALID_CODE)

        # Resolve against freshly-committed state, not the possibly-stale
        # in-memory `identity.user_id` — two concurrent verify_and_link
        # calls (e.g. two different valid codes for two different users,
        # both targeting the same still-unlinked identity) must never both
        # conclude "unlinked" and both attempt to set it. See
        # _try_atomic_link's docstring for how this is made race-safe.
        current_user_id = await self._get_current_identity_user_id(identity.id)

        if current_user_id is not None:
            if current_user_id == user.id:
                # Idempotent success — still consume the code (good
                # hygiene, prevents reuse) but no relink needed.
                await self._codes.try_consume(matched.id, whatsapp_identity_id=identity.id)
                identity.user_id = current_user_id
                logger.info("whatsapp_link_code_already_linked", whatsapp_identity_id=str(identity.id), user_id=str(user.id))
                return VerifyResult(outcome=LinkOutcome.ALREADY_LINKED, user_id=user.id)

            # Linked to someone else — never overwrite. Do not consume or
            # penalize the code: the code itself was objectively correct,
            # the conflict is about the identity's existing link, not a
            # guessing attack.
            logger.warning(
                "whatsapp_link_code_conflict", whatsapp_identity_id=str(identity.id), existing_user_id=str(current_user_id)
            )
            return VerifyResult(outcome=LinkOutcome.CONFLICT, user_id=current_user_id)

        # Attempt the atomic link BEFORE consuming the code: if we lose
        # this race, the code must not be burned for nothing.
        linked = await self._try_atomic_link(identity.id, user.id)
        if not linked:
            # Someone else linked this identity between our read above and
            # this UPDATE (Postgres's row-level lock serializes concurrent
            # UPDATEs on the same row, so this reflects real committed
            # state, not a stale read). Re-resolve rather than assume.
            current_user_id = await self._get_current_identity_user_id(identity.id)
            if current_user_id == user.id:
                await self._codes.try_consume(matched.id, whatsapp_identity_id=identity.id)
                identity.user_id = current_user_id
                logger.info("whatsapp_link_code_already_linked", whatsapp_identity_id=str(identity.id), user_id=str(user.id))
                return VerifyResult(outcome=LinkOutcome.ALREADY_LINKED, user_id=user.id)
            logger.warning(
                "whatsapp_link_code_conflict", whatsapp_identity_id=str(identity.id), existing_user_id=str(current_user_id)
            )
            return VerifyResult(outcome=LinkOutcome.CONFLICT, user_id=current_user_id)

        # We atomically won the identity link. Consume the code — if this
        # specific call loses a concurrent race for the SAME code (e.g. a
        # duplicate webhook delivery processed by two overlapping
        # background tasks), the identity link itself is still genuinely
        # established (by us), so this remains a true LINKED outcome.
        await self._codes.try_consume(matched.id, whatsapp_identity_id=identity.id)
        identity.user_id = user.id
        logger.info("whatsapp_link_code_linked", whatsapp_identity_id=str(identity.id), user_id=str(user.id))
        return VerifyResult(outcome=LinkOutcome.LINKED, user_id=user.id)

    async def _get_current_identity_user_id(self, identity_id: uuid.UUID) -> uuid.UUID | None:
        result = await self._session.execute(select(WhatsAppIdentity.user_id).where(WhatsAppIdentity.id == identity_id))
        return result.scalar_one()

    async def _try_atomic_link(self, identity_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Atomically sets WhatsAppIdentity.user_id only if it is still
        NULL — the ``WHERE user_id IS NULL`` guard is what makes two
        concurrent verify_and_link calls for the *same identity* (whether
        from the same code or two different valid codes for different
        users) resolve to exactly one winner, closing the TOCTOU window a
        plain ``identity.user_id = user_id`` attribute assignment would
        leave open. Returns True iff this call was the one that set it."""
        result = await self._session.execute(
            update(WhatsAppIdentity)
            .where(WhatsAppIdentity.id == identity_id, WhatsAppIdentity.user_id.is_(None))
            .values(user_id=user_id)
            .returning(WhatsAppIdentity.id)
        )
        return result.scalar_one_or_none() is not None

    async def unlink(self, *, identity: WhatsAppIdentity, requesting_user_id: uuid.UUID, is_admin: bool = False) -> bool:
        """Only the linked user, or an explicitly-authorized admin caller
        (``is_admin`` — the router/caller is responsible for establishing
        this via the existing role system, never decided here), may
        unlink. Returns False without raising if neither condition holds —
        the router turns that into a 403/404 as it sees fit; this service
        layer stays a plain yes/no."""
        if identity.user_id != requesting_user_id and not is_admin:
            logger.warning(
                "whatsapp_link_unlink_denied", whatsapp_identity_id=str(identity.id), requesting_user_id=str(requesting_user_id)
            )
            return False

        if identity.user_id is None:
            # Nothing to unlink — idempotent no-op, not an error.
            return True

        # Invalidate any still-outstanding codes for this user in the same
        # transaction as the unlink itself, so a stale, not-yet-expired
        # code generated before the unlink can never relink this (or any)
        # identity afterward.
        linked_user_id = identity.user_id
        await self._codes.invalidate_pending_for_user(linked_user_id)

        identity.user_id = None
        logger.info("whatsapp_identity_unlinked", whatsapp_identity_id=str(identity.id))
        return True


async def dispatch_link_code_verification_in_background(whatsapp_identity_id: uuid.UUID, message_text: str) -> None:
    """Downstream M2-A consumer, invoked via FastAPI BackgroundTasks from
    whatsapp_webhook_router.py — see that file's dispatch call. Opens its
    own session (the request-scoped one is torn down once the response is
    sent, long before this runs — same pattern as
    ingestion_router.py's _run_pipeline_in_background).

    Never raises: this is a fire-and-forget background task with no
    caller to report a failure to. looks_like_link_code() only decides
    whether to *attempt* verification — it grants nothing by itself; only
    WhatsAppLinkCodeService.verify_and_link's cryptographic hash
    comparison can establish a link.
    """
    candidate = looks_like_link_code(message_text)
    if candidate is None:
        return

    try:
        async with AsyncSessionLocal() as session:
            identity = (
                await session.execute(select(WhatsAppIdentity).where(WhatsAppIdentity.id == whatsapp_identity_id))
            ).scalar_one_or_none()
            if identity is None:
                return

            service = WhatsAppLinkCodeService(session)
            await service.verify_and_link(plaintext_code=candidate, identity=identity)
            await session.commit()
    except Exception:
        logger.exception("whatsapp_link_code_background_verification_failed", whatsapp_identity_id=str(whatsapp_identity_id))
