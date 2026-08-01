import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings

settings = get_settings()

ALGORITHM = "HS256"


def create_access_token(*, user_id: uuid.UUID, role_codes: list[str]) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "roles": role_codes,
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
