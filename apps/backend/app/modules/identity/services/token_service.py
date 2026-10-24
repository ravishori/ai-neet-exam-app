import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings

settings = get_settings()

ALGORITHM = "HS256"


def create_access_token(*, user_id: uuid.UUID, role_codes: list[str], active_role: str | None = None) -> str:
    """``active_role`` is a display/UX claim only (which of the user's own
    ``role_codes`` they're currently presenting as -- see
    app.modules.identity.role_priority) -- it is never itself a grant.
    Every authorization check still reads the full ``roles`` claim/
    ``user.role_codes``, exactly as before this claim existed."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "roles": role_codes,
        "active_role": active_role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError on any invalid/expired token — callers turn that into 401."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def create_mfa_pending_token(*, user_id: uuid.UUID) -> str:
    """Short-lived token after password OK when TOTP is enabled — not a session."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "type": "mfa_pending",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_mfa_pending_token(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    if payload.get("type") != "mfa_pending":
        raise jwt.InvalidTokenError("Not an MFA pending token")
    return payload


def create_mfa_setup_pending_token(*, user_id: uuid.UUID) -> str:
    """Issued instead of a full session when ENFORCE_MFA_FOR_PRIVILEGED_ROLES
    is on and a SUPER_ADMIN/ADMIN account without TOTP enabled completes
    password/email-OTP/mobile-OTP login -- lets that one account finish TOTP
    enrollment (via /mfa-setup/begin + /mfa-setup/confirm) without ever
    holding a real access/refresh token first. 15 minutes: longer than
    mfa_pending's 5, since this covers scanning a QR code and typing the
    first code into an authenticator app, not just re-entering one."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "type": "mfa_setup_pending",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_mfa_setup_pending_token(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    if payload.get("type") != "mfa_setup_pending":
        raise jwt.InvalidTokenError("Not an MFA setup pending token")
    return payload


def peek_active_role(token: str | None, role_codes: list[str]) -> str:
    """Best-effort read of the ``active_role`` claim from a (possibly
    expired) access-token cookie, WITHOUT verifying its expiry -- used only
    by /refresh to carry a chosen persona across a silent token refresh, so
    switching roles doesn't get reset back to the default just because the
    access token happened to expire first. This is not an authorization
    decision: the claimed role is only ever trusted if it's still in the
    caller's own, freshly-fetched ``role_codes`` (so a role revoked since
    the old token was issued can't be carried forward), and the token's
    signature is still verified -- only the expiry check is skipped, since
    an access token that is merely expired (not forged) is still good
    evidence of what the user was last presenting as."""
    from app.modules.identity.role_priority import default_active_role

    if token:
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"verify_exp": False})
            claimed = payload.get("active_role")
            if claimed in role_codes:
                return claimed
        except jwt.PyJWTError:
            pass
    return default_active_role(role_codes)


def generate_refresh_token() -> tuple[str, str, datetime]:
    """Returns (plaintext_token, token_hash, expires_at). Only the hash is ever stored."""
    plaintext = secrets.token_urlsafe(48)
    token_hash = hash_opaque_token(plaintext)
    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_days)
    return plaintext, token_hash, expires_at


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def generate_verification_token() -> tuple[str, str, datetime]:
    """Email verification / password reset tokens — same shape as refresh tokens, shorter life."""
    plaintext = secrets.token_urlsafe(32)
    token_hash = hash_opaque_token(plaintext)
    expires_at = datetime.now(UTC) + timedelta(hours=24)
    return plaintext, token_hash, expires_at
