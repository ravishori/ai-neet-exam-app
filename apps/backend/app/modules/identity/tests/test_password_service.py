import pytest

from app.modules.identity.services.password_service import (
    PasswordPolicyError,
    hash_password,
    validate_password_policy,
    verify_password,
)


def test_hash_and_verify_roundtrip():
    password = "StrongPass123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword1!", hashed) is False


@pytest.mark.parametrize(
    "password",
    [
        "short1!A",  # too short
        "nouppercase123!",  # no uppercase
        "NOLOWERCASE123!",  # no lowercase
        "NoDigitsHere!!!",  # no digit
        "NoSpecialChar123",  # no special char
    ],
)
def test_rejects_weak_passwords(password):
    with pytest.raises(PasswordPolicyError):
        validate_password_policy(password)


def test_accepts_strong_password():
    validate_password_policy("StrongPass123!")  # should not raise
