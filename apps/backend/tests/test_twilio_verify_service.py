"""TwilioVerifyService — configuration + fail-closed contract."""

import httpx
import pytest

from app.core.config import get_settings
from app.modules.identity.services.twilio_verify_service import (
    TwilioVerifyError,
    TwilioVerifyService,
    TwilioVerifyStub,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_fails_closed_when_verify_service_sid_missing(monkeypatch):
    # Force the settings singleton to a state with no Verify Service SID.
    settings = get_settings()
    monkeypatch.setattr(settings, "twilio_account_sid", "AC_fake_sid")
    monkeypatch.setattr(settings, "twilio_auth_token", "fake_token")
    monkeypatch.setattr(settings, "twilio_verify_service_sid", "")

    svc = TwilioVerifyService()
    with pytest.raises(TwilioVerifyError) as exc:
        await svc.send("+919876500001")
    assert exc.value.code == "TWILIO_VERIFY_NOT_CONFIGURED"
    assert exc.value.status_code == 503


async def test_fails_closed_when_credentials_missing(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "twilio_account_sid", "")
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(settings, "twilio_verify_service_sid", "VA_fake")

    svc = TwilioVerifyService()
    with pytest.raises(TwilioVerifyError) as exc:
        await svc.check("+919876500001", code="123456")
    assert exc.value.code == "TWILIO_VERIFY_NOT_CONFIGURED"


async def test_twilio_5xx_maps_to_unavailable_and_does_not_leak_body(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "twilio_account_sid", "AC_fake")
    monkeypatch.setattr(settings, "twilio_auth_token", "fake")
    monkeypatch.setattr(settings, "twilio_verify_service_sid", "VA_fake")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"code": 20500, "message": "SECRET_LEAK: internal detail"})

    svc = TwilioVerifyService(transport=httpx.MockTransport(handler))
    with pytest.raises(TwilioVerifyError) as exc:
        await svc.send("+919876500001")
    assert exc.value.code == "TWILIO_VERIFY_UNAVAILABLE"
    # Message is generic — nothing about Twilio's body echoed to caller.
    assert "SECRET_LEAK" not in str(exc.value)


async def test_check_maps_404_to_expired_not_error(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "twilio_account_sid", "AC_fake")
    monkeypatch.setattr(settings, "twilio_auth_token", "fake")
    monkeypatch.setattr(settings, "twilio_verify_service_sid", "VA_fake")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"code": 20404, "message": "Not Found"})

    svc = TwilioVerifyService(transport=httpx.MockTransport(handler))
    result = await svc.check("+919876500001", code="123456")
    assert result.valid is False
    assert result.status == "expired"


async def test_stub_only_approves_seeded_code():
    stub = TwilioVerifyStub()
    stub.seed("+919876500001", "424242")
    assert (await stub.check("+919876500001", code="424242")).valid is True
    assert (await stub.check("+919876500001", code="000000")).valid is False
    # Unknown destination → expired.
    r = await stub.check("+911234567890", code="424242")
    assert r.status == "expired" and r.valid is False
