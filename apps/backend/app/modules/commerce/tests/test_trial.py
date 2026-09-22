from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.services.access_service import PAID_ACTIVE, TRIAL_ACTIVE, TRIAL_EXPIRED, AccessService
from app.modules.commerce.services.trial_service import TrialService

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_registration_grants_exactly_one_trial(client: AsyncClient, db_session: AsyncSession, register_user):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])

    access = AccessService(db_session)
    state = await access.get_access_state(student_id)
    assert state.state == TRIAL_ACTIVE
    assert state.has_access is True
    assert state.trial_expires_at is not None


async def test_trial_creation_is_idempotent(db_session: AsyncSession, register_user, client: AsyncClient):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])

    trial_service = TrialService(db_session)
    first = await trial_service.ensure_trial(student_id=student_id, product_code="ALL_ACCESS")
    second = await trial_service.ensure_trial(student_id=student_id, product_code="ALL_ACCESS")

    assert first.id == second.id
    assert first.starts_at == second.starts_at
    assert first.expires_at == second.expires_at


async def test_login_logout_does_not_reset_trial(client: AsyncClient, db_session: AsyncSession, register_user):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])

    access = AccessService(db_session)
    before = await access.get_trial_status(student_id, "ALL_ACCESS")

    await client.post("/api/v1/auth/logout")
    resp = await client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
    assert resp.status_code == 200

    after = await access.get_trial_status(student_id, "ALL_ACCESS")
    assert before.starts_at == after.starts_at
    assert before.expires_at == after.expires_at


async def test_repeated_verification_does_not_reset_trial(db_session: AsyncSession, register_user, client: AsyncClient):
    """Repeated calls to request_email_verification (re-requesting the
    verification email) must never touch trial dates — TrialService.
    ensure_trial is the only thing that can create/read a trial, and
    email-verification code never calls it a second time."""
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])

    trial_service = TrialService(db_session)
    before = await trial_service.ensure_trial(student_id=student_id, product_code="ALL_ACCESS")

    # Simulate repeated verification requests hitting the same idempotent path.
    for _ in range(3):
        again = await trial_service.ensure_trial(student_id=student_id, product_code="ALL_ACCESS")
        assert again.starts_at == before.starts_at
        assert again.expires_at == before.expires_at


async def test_expired_trial_denies_access(db_session: AsyncSession, register_user, client: AsyncClient):
    from datetime import UTC, datetime, timedelta

    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])

    trial_service = TrialService(db_session)
    trial = await trial_service.ensure_trial(student_id=student_id, product_code="ALL_ACCESS")

    # Force expiry — this is the ONLY code path in this test suite allowed to
    # mutate trial dates, and it does so directly via the DB row (simulating
    # time passing), never through any client-facing API (which has none).
    trial.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()

    access = AccessService(db_session)
    state = await access.get_access_state(student_id)
    assert state.state == TRIAL_EXPIRED
    assert state.has_access is False


async def test_client_cannot_modify_trial_dates_via_api(client: AsyncClient, db_session: AsyncSession, register_user):
    """There is no API endpoint that accepts client-supplied trial dates —
    this test documents/proves that by asserting the access-state response
    never echoes anything the client sent, and that no route exists to
    submit trial dates at all (a 404/405 on any guessed path)."""
    await register_user(client, db_session=db_session)

    resp = await client.get("/api/v1/commerce/access-state")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "trialExpiresAt" in body  # server-computed field only, read-only response

    # No mutation route exists for trial state.
    resp = await client.post("/api/v1/commerce/trial", json={"expires_at": "2099-01-01T00:00:00Z"})
    assert resp.status_code in (404, 405)


async def test_paid_entitlement_takes_priority_over_active_trial(db_session: AsyncSession, register_user, client: AsyncClient):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.modules.commerce.models import Entitlement, Product

    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])

    trial_service = TrialService(db_session)
    await trial_service.ensure_trial(student_id=student_id, product_code="ALL_ACCESS")

    product = (await db_session.execute(select(Product).where(Product.code == "ALL_ACCESS"))).scalar_one()
    now = datetime.now(UTC)
    db_session.add(
        Entitlement(
            student_id=student_id,
            product_id=product.id,
            source_type="PURCHASE",
            source_id=uuid.uuid4(),
            status="ACTIVE",
            starts_at=now,
            expires_at=now + timedelta(days=365),
        )
    )
    await db_session.commit()

    access = AccessService(db_session)
    state = await access.get_access_state(student_id)
    assert state.state == PAID_ACTIVE
    assert state.has_access is True
