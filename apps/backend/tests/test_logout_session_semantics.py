"""Documents the CURRENT logout/session semantics with tests (audit finding
#9). This is deliberately NOT a "logout everywhere" implementation — per the
task, that would be a product decision requiring explicit approval. These
tests establish and pin down today's actual behavior:

- logout revokes only the refresh token bound to the session that logged out
- a second, independent session is unaffected by that logout
- a revoked refresh token cannot be reused
- access tokens are stateless JWTs and are NOT server-side revoked by logout
  (documented via direct decode, not asserted as a "bug")
- password reset/change-password revoke ALL refresh sessions for the user
  (the intentional exception to "this session only")
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    from app.core import rate_limit as rl

    async def no_limit(key: str, *, limit: int, window_seconds: int, fail_closed: bool, log_key: str | None = None) -> None:
        return None

    monkeypatch.setattr(rl, "_check", no_limit)


def _mobile() -> str:
    import random

    return str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))


async def _register_and_login(ac: AsyncClient, email: str, password: str) -> None:
    resp = await ac.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "Sess",
            "last_name": "Test",
            "mobile": _mobile(),
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": password,
        },
    )
    assert resp.status_code == 201, resp.text


@pytest.fixture
async def second_client():
    """An independent AsyncClient with its own cookie jar, hitting the same
    ASGI app (and therefore the same dependency-overridden DB session as the
    `client` fixture) — simulates a second browser/device session."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_logout_revokes_only_the_current_sessions_refresh_token(client, db_session):
    from app.modules.identity.models.refresh_token import RefreshToken
    from app.modules.identity.services.token_service import hash_opaque_token

    email = f"session-a-{uuid.uuid4().hex[:12]}@example.com"
    password = "SessionAPass!42"
    await _register_and_login(client, email, password)

    refresh_cookie = client.cookies.get("refresh_token")
    assert refresh_cookie

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    token_hash = hash_opaque_token(refresh_cookie)
    result = await db_session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    row = result.scalar_one()
    assert row.revoked_at is not None


async def test_second_independent_session_survives_first_sessions_logout(client, second_client, db_session):
    """Session A and session B belong to the SAME user but are independent
    browser sessions (separate cookie jars/refresh tokens). Logging out A
    must not affect B under the current, documented "this session only"
    semantics."""
    email = f"multisession-{uuid.uuid4().hex[:12]}@example.com"
    password = "MultiSessionPass!7"
    await _register_and_login(client, email, password)
    await client.post("/api/v1/auth/logout")

    # Session A: log back in.
    login_a = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_a.status_code == 200

    # Session B: independent login as the same user.
    login_b = await second_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_b.status_code == 200

    me_b_before = await second_client.get("/api/v1/auth/me")
    assert me_b_before.status_code == 200

    # Log out session A only.
    logout_a = await client.post("/api/v1/auth/logout")
    assert logout_a.status_code == 200

    me_a_after = await client.get("/api/v1/auth/me")
    assert me_a_after.status_code == 401, "session A must be ended by its own logout"

    me_b_after = await second_client.get("/api/v1/auth/me")
    assert me_b_after.status_code == 200, (
        "documents CURRENT behavior: session B is unaffected by session A's logout "
        "(logout is per-session, not per-user) — this is the audited gap, not a bug fix"
    )


async def test_revoked_refresh_token_cannot_be_reused(client):
    from conftest import csrf_headers

    email = f"revoke-reuse-{uuid.uuid4().hex[:12]}@example.com"
    password = "RevokeReusePass!3"
    await _register_and_login(client, email, password)

    refresh_cookie = client.cookies.get("refresh_token")
    assert refresh_cookie

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    # Manually re-attach the now-revoked refresh token and attempt to use it.
    client.cookies.set("refresh_token", refresh_cookie)
    resp = await client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert resp.status_code == 401


async def test_access_token_is_stateless_and_not_server_side_revoked_by_logout(client):
    """Documents the current architecture (not a defect): the access_token
    JWT is verified purely by signature + user status, with no server-side
    revocation list. Logout clears the COOKIE; it does not and cannot
    invalidate an already-issued, unexpired JWT if it were replayed
    independently of the cookie jar. This test proves the token remains
    cryptographically valid (decodable, non-expired) immediately after
    logout — it does not attempt to bypass cookie clearing to prove replay
    against the live route, since httpx's cookie jar already deletes the
    cookie the moment logout succeeds (see test_logout_ends_the_session)."""
    from app.modules.identity.services.token_service import decode_access_token

    email = f"stateless-{uuid.uuid4().hex[:12]}@example.com"
    password = "StatelessJwtPass!9"
    await _register_and_login(client, email, password)

    access_token = client.cookies.get("access_token")
    assert access_token

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    # The JWT itself is unaffected by logout — it decodes successfully and
    # is still within its TTL. This is expected, documented behavior: there
    # is no access-token blocklist in this architecture.
    payload = decode_access_token(access_token)
    assert payload["sub"]


async def test_password_reset_revokes_all_sessions_unlike_logout(client, second_client, db_session):
    """The intentional exception: unlike logout (session-scoped), a password
    reset revokes EVERY refresh token for the user, ending all sessions."""
    from app.modules.identity.models.refresh_token import RefreshToken
    from app.modules.identity.models.user import User
    from app.modules.identity.services.auth_service import AuthService

    email = f"reset-kills-all-{uuid.uuid4().hex[:12]}@example.com"
    password = "ResetKillsAllPass!4"
    await _register_and_login(client, email, password)
    await client.post("/api/v1/auth/logout")

    login_a = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_a.status_code == 200
    login_b = await second_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_b.status_code == 200

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()

    service = AuthService(db_session)
    plaintext_token = await service.request_password_reset(email)
    await db_session.commit()

    reset = await client.post(
        "/api/v1/auth/reset-password", json={"token": plaintext_token, "new_password": "AfterResetPass!6"}
    )
    assert reset.status_code == 200

    rows = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
    ).scalars().all()
    assert rows
    assert all(r.revoked_at is not None for r in rows), "password reset must revoke every session, including session B"
