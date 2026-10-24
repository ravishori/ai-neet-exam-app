"""Mobile OTP login is disabled by default (settings.mobile_otp_login_
enabled=False) -- Password and Email OTP are unaffected. Covers both
halves of "disable in frontend and backend": /methods reports mobileOtp:
false (which the frontend's existing conditional rendering already keys
off of -- see login-form.tsx's `showMobileOtp = methods?.mobileOtp ===
true`, no frontend code change needed), and the backend routes
themselves reject directly, so hiding the UI tab isn't the only thing
standing between a caller and the feature."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    """ASGITransport does not run FastAPI's lifespan, so init_redis() never
    fires and every fail_closed=True endpoint would return 429 before ever
    reaching the disabled-feature check this file actually tests. Same
    pattern as test_mobile_otp_login.py."""
    from app.core import rate_limit as rl

    async def no_limit(key: str, *, limit: int, window_seconds: int, fail_closed: bool, log_key: str | None = None) -> None:
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


async def test_methods_reports_mobile_otp_disabled(client):
    resp = await client.get("/api/v1/auth/methods")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["mobileOtp"] is False
    # Unaffected: Password and Email OTP stay reported per their own
    # independent config checks.
    assert data["emailPassword"] is True


async def test_mobile_otp_send_route_rejects_when_disabled(client):
    resp = await client.post("/api/v1/auth/mobile/otp/send", json={"mobile": "9876500101"})
    assert resp.status_code == 404, resp.text
    assert resp.json()["errors"][0]["code"] == "FEATURE_DISABLED"


async def test_mobile_otp_verify_route_rejects_when_disabled(client):
    resp = await client.post(
        "/api/v1/auth/mobile/otp/verify", json={"mobile": "9876500101", "code": "123456"}
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["errors"][0]["code"] == "FEATURE_DISABLED"


async def test_methods_reports_mobile_otp_enabled_when_toggled_on(client, monkeypatch):
    """Confirms this is a real toggle, not effectively a permanent removal
    -- re-enabling the setting (even with no Twilio credentials configured
    in this test environment) changes /methods' report back, proving the
    flag is actually what /methods reads, not a hardcoded False."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "mobile_otp_login_enabled", True)
    monkeypatch.setattr(settings, "twilio_account_sid", "ACtest")
    monkeypatch.setattr(settings, "twilio_auth_token", "test-token")
    monkeypatch.setattr(settings, "twilio_verify_service_sid", "VAtest")

    resp = await client.get("/api/v1/auth/methods")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["mobileOtp"] is True
