"""Field encryption helpers (TOTP secrets). Requires ENCRYPTION_KEY (Fernet)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.exceptions import AppError


def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise AppError(
            "Encryption is not configured on this server.",
            code="ENCRYPTION_NOT_CONFIGURED",
            status_code=503,
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        raise AppError(
            "Encryption is misconfigured on this server.",
            code="ENCRYPTION_NOT_CONFIGURED",
            status_code=503,
        ) from exc


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise AppError("Unable to decrypt credential", code="DECRYPT_FAILED", status_code=500) from exc
