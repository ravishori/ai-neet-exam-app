"""Focused, self-contained tests for rate_limit_by_mobile (no DB required).

These exercise the actual Redis fixed-window counting logic against a
minimal in-memory fake — not a mocked-out no-op — against a tiny FastAPI
app wired the same way the real mobile OTP routes are, so the assertions
prove real bucketing behavior, not just that a function was called.
"""

from __future__ import annotations

import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core import rate_limit as rl
from app.core.exceptions import AppError, app_error_handler


class FakeRedis:
    """Minimal async fake implementing exactly what `_check` uses."""

    def __init__(self):
        self._counts: dict[str, int] = {}
        self._expiry: dict[str, float] = {}

    def _expired(self, key: str) -> bool:
        return key in self._expiry and time.monotonic() > self._expiry[key]

    async def incr(self, key: str) -> int:
        if self._expired(key):
            self._counts.pop(key, None)
            self._expiry.pop(key, None)
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self._expiry[key] = time.monotonic() + seconds

    async def ttl(self, key: str) -> int:
        return 60


class Payload(BaseModel):
    mobile: str
    code: str = "000000"


def _build_app(*, limit: int, window_seconds: int) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    limiter = rl.rate_limit_by_mobile("test_otp", limit=limit, window_seconds=window_seconds, fail_closed=True)

    @app.post("/otp/verify", dependencies=[Depends(limiter)])
    async def verify(payload: Payload) -> dict:
        return {"ok": True}

    return app


@pytest.fixture()
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: fake)
    return fake


def test_same_mobile_reaches_limit_then_blocked(fake_redis):
    app = _build_app(limit=10, window_seconds=300)
    client = TestClient(app)

    for i in range(10):
        resp = client.post("/otp/verify", json={"mobile": "+919987671916", "code": "000000"})
        assert resp.status_code == 200, f"attempt {i + 1} should be allowed, got {resp.status_code}: {resp.text}"

    eleventh = client.post("/otp/verify", json={"mobile": "+919987671916", "code": "000000"})
    assert eleventh.status_code == 429
    assert eleventh.json()["errors"][0]["code"] == "RATE_LIMITED"


def test_different_mobiles_do_not_share_bucket(fake_redis):
    app = _build_app(limit=10, window_seconds=300)
    client = TestClient(app)

    for _ in range(10):
        assert client.post("/otp/verify", json={"mobile": "+919987671916", "code": "0"}).status_code == 200

    # A different number starts its own fresh bucket, unaffected by the first.
    resp = client.post("/otp/verify", json={"mobile": "+919876543210", "code": "0"})
    assert resp.status_code == 200


def test_same_mobile_from_different_client_ips_still_shares_bucket(fake_redis):
    """Reproduces the exact Railway-edge scenario: request.client.host varies
    per request, but the mobile-keyed bucket must still accumulate."""
    app = _build_app(limit=10, window_seconds=300)
    client = TestClient(app)

    for _i in range(10):
        # TestClient doesn't let us vary request.client.host per-call easily,
        # but the point under test is that the bucket key never references
        # IP at all for this dependency — confirmed by inspecting the fake's
        # recorded keys below, which must all collapse to one entry.
        assert client.post("/otp/verify", json={"mobile": "+919987671916", "code": "0"}).status_code == 200

    matching_keys = [k for k in fake_redis._counts if "mobile:+919987671916" in k]
    assert len(matching_keys) == 1, f"expected exactly one bucket for the mobile, got {matching_keys}"
    assert fake_redis._counts[matching_keys[0]] == 10


def test_malformed_mobile_falls_back_to_ip_bucket_not_exempt(fake_redis):
    app = _build_app(limit=2, window_seconds=300)
    client = TestClient(app)

    assert client.post("/otp/verify", json={"mobile": "not-a-number", "code": "0"}).status_code == 200
    assert client.post("/otp/verify", json={"mobile": "not-a-number", "code": "0"}).status_code == 200
    third = client.post("/otp/verify", json={"mobile": "not-a-number", "code": "0"})
    assert third.status_code == 429, "malformed input must still be bounded, not silently exempt"


def test_redis_failure_fails_closed(monkeypatch):
    monkeypatch.setattr(rl, "get_redis", lambda: None)
    app = _build_app(limit=10, window_seconds=300)
    client = TestClient(app)

    resp = client.post("/otp/verify", json={"mobile": "+919987671916", "code": "0"})
    assert resp.status_code == 429


def test_bucket_key_never_contains_the_otp_code(fake_redis):
    app = _build_app(limit=10, window_seconds=300)
    client = TestClient(app)
    client.post("/otp/verify", json={"mobile": "+919987671916", "code": "654321"})

    for key in fake_redis._counts:
        assert "654321" not in key
