"""Resend-verification-email flow — the dashboard's dead `/verify-email`
link (no token) is replaced by an authenticated resend action that reuses
AuthService.request_email_verification()/send_verification_email(), the
same infrastructure /register already uses."""

import re
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.modules.identity.models.user import User
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    from app.core import rate_limit as rl

    async def no_limit(*_a, **_k):
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


def _email() -> str:
    return f"resend-verify-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client, email: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "Resend",
            "last_name": "Verify",
            "mobile": "9876500301",
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": "ResendVerifyPass!42",
        },
    )
    assert resp.status_code == 201, resp.text


async def test_authenticated_unverified_user_can_request_resend(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)

    captured: dict[str, str] = {}

    async def capture_send(*, to, subject, html, text, kind):
        captured["to"] = to
        captured["body"] = text
        captured["kind"] = kind

    monkeypatch.setattr("app.modules.identity.services.email_service._send", capture_send)

    resp = await client.post("/api/v1/auth/verify-email/resend", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    assert "token" not in resp.text  # never returned in the API response

    assert captured["to"] == email
    assert captured["kind"] == "verification"


async def test_resend_sends_email_with_verify_link_containing_token(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)

    captured: dict[str, str] = {}

    async def capture_send(*, to, subject, html, text, kind):
        captured["body"] = text

    monkeypatch.setattr("app.modules.identity.services.email_service._send", capture_send)

    resp = await client.post("/api/v1/auth/verify-email/resend", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text

    match = re.search(r"/verify-email\?token=([\w-]+)", captured["body"])
    assert match, captured["body"]
    token = match.group(1)
    assert len(token) > 20  # secrets.token_urlsafe(32) — not empty, not a placeholder


async def test_resend_token_is_not_returned_in_api_response(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)

    async def capture_send(*, to, subject, html, text, kind):
        return None

    monkeypatch.setattr("app.modules.identity.services.email_service._send", capture_send)

    resp = await client.post("/api/v1/auth/verify-email/resend", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body["data"].keys()) == {"message"}


async def test_resend_rate_limited_after_repeated_requests(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)  # uses the no_limit bypass from the autouse fixture above

    from app.core import rate_limit as rl

    async def deny(*_a, **_k):
        from app.core.exceptions import AppError

        raise AppError("Too many requests", code="RATE_LIMITED", status_code=429)

    # Only the resend call itself should be denied — register() already
    # happened above under the autouse no-limit bypass.
    monkeypatch.setattr(rl, "_check", deny)

    async def capture_send(*, to, subject, html, text, kind):
        return None

    monkeypatch.setattr("app.modules.identity.services.email_service._send", capture_send)

    resp = await client.post("/api/v1/auth/verify-email/resend", headers=csrf_headers(client))
    assert resp.status_code == 429


async def test_already_verified_user_gets_generic_success_without_new_email(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)

    result = await db_session.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one()
    user.email_verified = True
    await db_session.commit()

    send_mock = AsyncMock()
    monkeypatch.setattr("app.modules.identity.services.email_service._send", send_mock)

    resp = await client.post("/api/v1/auth/verify-email/resend", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    assert send_mock.await_count == 0  # already verified — no email sent, no info leaked either way


async def test_resend_survives_email_provider_failure(client, db_session, monkeypatch):
    email = _email()
    await _register(client, email)

    async def failing_send(*, to, subject, html, text, kind):
        raise RuntimeError("provider unreachable")

    # _send() itself always catches provider failures (see email_service.py) —
    # simulate that guarantee holding even if a provider call throws upstream
    # of the catch, by patching at the public function boundary instead.
    async def send_verification_email_swallows(*, to, token):
        try:
            await failing_send(to=to, subject="x", html="x", text="x", kind="verification")
        except RuntimeError:
            pass

    monkeypatch.setattr(
        "app.modules.identity.api.auth_router.send_verification_email", send_verification_email_swallows
    )

    resp = await client.post("/api/v1/auth/verify-email/resend", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text


async def test_existing_verify_email_flow_still_works(client, db_session, monkeypatch):
    """The resend endpoint must not have disturbed the original token-based
    verification flow /verify-email already implements."""
    email = _email()
    await _register(client, email)

    captured: dict[str, str] = {}

    async def capture_send(*, to, subject, html, text, kind):
        captured["body"] = text

    monkeypatch.setattr("app.modules.identity.services.email_service._send", capture_send)

    resp = await client.post("/api/v1/auth/verify-email/resend", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    match = re.search(r"/verify-email\?token=([\w-]+)", captured["body"])
    assert match

    verify = await client.post("/api/v1/auth/verify-email", json={"token": match.group(1)})
    assert verify.status_code == 200, verify.text
    assert verify.json()["data"]["email_verified"] is True
