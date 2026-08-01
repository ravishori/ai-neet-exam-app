import uuid

import jwt
import pytest

from app.modules.identity.services.token_service import (
    create_access_token,
    decode_access_token,
    generate_csrf_token,
    generate_refresh_token,
    hash_opaque_token,
)


def test_access_token_roundtrip():
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role_codes=["STUDENT"])
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["roles"] == ["STUDENT"]
    assert payload["type"] == "access"


def test_decode_rejects_tampered_token():
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role_codes=["STUDENT"])
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)


def test_refresh_token_only_hash_is_deterministic():
    plaintext, token_hash, expires_at = generate_refresh_token()
    assert token_hash == hash_opaque_token(plaintext)
    assert plaintext != token_hash
    assert expires_at is not None


def test_refresh_tokens_are_unique():
    _, hash_a, _ = generate_refresh_token()
    _, hash_b, _ = generate_refresh_token()
    assert hash_a != hash_b


def test_csrf_tokens_are_unique():
    assert generate_csrf_token() != generate_csrf_token()
