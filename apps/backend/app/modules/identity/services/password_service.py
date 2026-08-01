import re

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.exceptions import AppError

_hasher = PasswordHasher()

# BRD Sprint 1 password policy: 12+ chars, upper, lower, number, special.
_MIN_LENGTH = 12
_COMMON_PASSWORDS = {
    "password123!", "qwertyuiop123", "letmein12345!", "admin12345678",
    "welcome123456", "iloveyou12345", "password1234!",
}


class PasswordPolicyError(AppError):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons), code="WEAK_PASSWORD", status_code=400)


def validate_password_policy(password: str) -> None:
    reasons = []
    if len(password) < _MIN_LENGTH:
        reasons.append(f"Must be at least {_MIN_LENGTH} characters")
    if not re.search(r"[A-Z]", password):
        reasons.append("Must include an uppercase letter")
    if not re.search(r"[a-z]", password):
        reasons.append("Must include a lowercase letter")
    if not re.search(r"\d", password):
        reasons.append("Must include a number")
    if not re.search(r"[^\w\s]", password):
        reasons.append("Must include a special character")
    if password.lower() in _COMMON_PASSWORDS:
        reasons.append("This password is too common")

    if reasons:
        raise PasswordPolicyError(reasons)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
