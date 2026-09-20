"""Wave A security unit tests: redaction, integrity mapping, sanitized errors."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import map_integrity_error
from app.core.logging import REDACTED, redact_event_dict

pytestmark = pytest.mark.asyncio(loop_scope="session")


def test_redact_event_dict_masks_sensitive_keys():
    event = redact_event_dict(
        None,
        "info",
        {
            "event": "login",
            "password": "super-secret",
            "otp": "123456",
            "access_token": "aaa.bbb.ccc",
            "user_id": "ok-to-keep",
            "nested": {"refresh_token": "raw-refresh", "count": 1},
        },
    )
    assert event["password"] == REDACTED
    assert event["otp"] == REDACTED
    assert event["access_token"] == REDACTED
    assert event["user_id"] == "ok-to-keep"
    assert event["nested"]["refresh_token"] == REDACTED
    assert event["nested"]["count"] == 1


def test_map_integrity_error_unique():
    exc = IntegrityError("INSERT", {}, Exception("duplicate key value violates unique constraint"))
    mapped = map_integrity_error(exc)
    assert mapped.code == "CONFLICT"
    assert mapped.status_code == 409
    assert "duplicate key" not in mapped.message.lower()
    assert "unique constraint" not in mapped.message.lower()


def test_map_integrity_error_fk():
    exc = IntegrityError("INSERT", {}, Exception("violates foreign key constraint fk_example"))
    mapped = map_integrity_error(exc)
    assert mapped.code == "INVALID_REFERENCE"
    assert "fk_example" not in mapped.message


async def test_unhandled_error_response_is_sanitized(client):
    resp = await client.get("/api/v1/does-not-exist-wave-a")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert "traceId" in body
    text = resp.text.lower()
    assert "traceback" not in text
    assert "sqlalchemy" not in text


async def test_forgot_password_is_rate_limited(client, monkeypatch):
    """Recovery endpoints must throttle; uses fail_closed path with Redis when available.

    Without Redis in unit transport, fail_closed raises RATE_LIMITED immediately
    when redis client is None — assert that contract for forgot-password.
    """
    from app.core import rate_limit as rl

    async def always_none():
        return None

    monkeypatch.setattr(rl, "get_redis", lambda: None)

    resp = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    # fail_closed=True + redis None → 429
    assert resp.status_code == 429
    body = resp.json()
    assert body["errors"][0]["code"] == "RATE_LIMITED"
    assert "password" not in resp.text.lower() or "reset" in body["errors"][0]["message"].lower()
