"""Integration tests: Admin Phase 1 — student detail endpoint (used by
/admin/students), and the SUPER_ADMIN bootstrap script.

No new backend endpoints were required for /admin/students or /admin/roles
themselves — both reuse the existing GET/PATCH /api/v1/users, GET /api/v1/
users/{id}, and /api/v1/roles* endpoints, already covered by
test_admin_portal.py. This file adds only what's genuinely new for Phase 1:
authorization/IDOR coverage for the single-user detail endpoint (the one
piece /admin/students needs that wasn't already tested), and the SUPER_ADMIN
bootstrap script's safety gates.
"""

import sys
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from bootstrap_super_admin import BootstrapError, bootstrap_super_admin  # noqa: E402

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# GET /api/v1/users/{user_id} — permission + IDOR coverage for /admin/students
# ---------------------------------------------------------------------------


async def test_get_user_detail_requires_authentication(client):
    resp = await client.get(f"/api/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 401


async def test_get_user_detail_forbidden_for_student(client, db_session, register_user):
    await register_user(client, db_session=db_session)  # default STUDENT role
    resp = await client.get(f"/api/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 403


async def test_get_user_detail_allowed_for_admin_and_returns_target_not_actor(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other_client:
        target = await register_user(other_client, db_session=db_session)

    resp = await client.get(f"/api/v1/users/{target['id']}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["id"] == target["id"]
    assert resp.json()["data"]["email"] == target["email"]


async def test_get_user_detail_404_for_nonexistent_id_not_500(client, db_session, register_user):
    """IDOR-adjacent: a guessed/incorrect UUID must not error or leak
    anything beyond a plain not-found — same shape whether the id never
    existed or belongs to a soft-deleted account."""
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    resp = await client.get(f"/api/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_user_detail_forbidden_for_teacher(client, db_session, register_user):
    await register_user(client, role_codes=["TEACHER"], db_session=db_session)
    resp = await client.get(f"/api/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# SUPER_ADMIN bootstrap
# ---------------------------------------------------------------------------

_STRONG_PASSWORD = "Correct-Horse-Battery-Staple-9!"


async def test_bootstrap_creates_first_super_admin(db_session):
    user_id, created = await bootstrap_super_admin(
        db_session, email="bootstrap-first@example.com", password=_STRONG_PASSWORD
    )
    assert created is True

    from app.modules.identity.repositories.user_repository import UserRepository

    user = await UserRepository(db_session).get_by_id(uuid.UUID(user_id))
    assert user is not None
    assert "SUPER_ADMIN" in user.role_codes

    from app.modules.identity.services.password_service import verify_password

    assert verify_password(_STRONG_PASSWORD, user.password_hash)
    assert verify_password("wrong-password", user.password_hash) is False


async def test_bootstrap_is_idempotent_for_same_account(db_session):
    user_id_1, created_1 = await bootstrap_super_admin(
        db_session, email="bootstrap-idempotent@example.com", password=_STRONG_PASSWORD
    )
    assert created_1 is True

    user_id_2, created_2 = await bootstrap_super_admin(
        db_session, email="bootstrap-idempotent@example.com", password=_STRONG_PASSWORD
    )
    assert created_2 is False
    assert user_id_2 == user_id_1


async def test_bootstrap_refuses_second_super_admin_without_flag(db_session):
    await bootstrap_super_admin(db_session, email="first-super@example.com", password=_STRONG_PASSWORD)

    with pytest.raises(BootstrapError, match="already exists"):
        await bootstrap_super_admin(db_session, email="second-super@example.com", password=_STRONG_PASSWORD)


async def test_bootstrap_allows_second_super_admin_with_explicit_flag(db_session):
    await bootstrap_super_admin(db_session, email="first-super-2@example.com", password=_STRONG_PASSWORD)

    user_id, created = await bootstrap_super_admin(
        db_session,
        email="second-super-2@example.com",
        password=_STRONG_PASSWORD,
        allow_additional=True,
    )
    assert created is True
    assert user_id is not None


async def test_bootstrap_refuses_to_silently_promote_existing_account(db_session, client, register_user):
    existing = await register_user(client, db_session=db_session)  # default STUDENT

    with pytest.raises(BootstrapError, match="Refusing to silently promote"):
        await bootstrap_super_admin(db_session, email=existing["email"], password=_STRONG_PASSWORD)


async def test_bootstrap_promotes_existing_account_with_explicit_flag(db_session, client, register_user):
    existing = await register_user(client, db_session=db_session)  # default STUDENT

    user_id, created = await bootstrap_super_admin(
        db_session,
        email=existing["email"],
        password=_STRONG_PASSWORD,
        promote_existing=True,
    )
    assert created is False  # promotion of an existing account, not a new row
    assert user_id == existing["id"]

    from app.modules.identity.repositories.user_repository import UserRepository

    user = await UserRepository(db_session).get_by_id(uuid.UUID(user_id))
    assert "SUPER_ADMIN" in user.role_codes


async def test_bootstrap_rejects_weak_password(db_session):
    from app.modules.identity.services.password_service import PasswordPolicyError

    with pytest.raises(PasswordPolicyError):
        await bootstrap_super_admin(db_session, email="weak-pw@example.com", password="short")


async def test_bootstrap_rejects_empty_email(db_session):
    with pytest.raises(BootstrapError, match="Email is required"):
        await bootstrap_super_admin(db_session, email="   ", password=_STRONG_PASSWORD)
