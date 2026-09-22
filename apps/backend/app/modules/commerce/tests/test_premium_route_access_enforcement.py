"""Representative access-enforcement coverage (Phase 2A).

Deliberately NOT duplicated across every gated router — one representative
premium endpoint (GET /api/v1/attempts, router-level-gated in
assessment_router.py via require_active_access()) stands in for the whole
class of premium routes, since they all share the exact same dependency and
AccessService logic. Testing the dependency's behavior once, thoroughly, is
more valuable than repeating identical assertions per router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.models import Entitlement, Product

pytestmark = pytest.mark.asyncio(loop_scope="session")

PREMIUM_ROUTE = "/api/v1/attempts"


async def _product_id(db_session: AsyncSession) -> uuid.UUID:
    return (await db_session.execute(select(Product).where(Product.code == "ALL_ACCESS"))).scalar_one().id


async def test_anonymous_user_gets_401_on_premium_route(client):
    resp = await client.get(PREMIUM_ROUTE)
    assert resp.status_code == 401


async def test_active_trial_student_can_access_premium_route(client, db_session: AsyncSession, register_user):
    await register_user(client, db_session=db_session)  # registration grants an active trial
    resp = await client.get(PREMIUM_ROUTE)
    assert resp.status_code == 200


async def test_active_paid_entitlement_student_can_access_premium_route(
    client, db_session: AsyncSession, register_user
):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])
    product_id = await _product_id(db_session)

    # Expire the trial so only the paid entitlement can be granting access.
    trial = (
        await db_session.execute(
            select(Entitlement).where(Entitlement.student_id == student_id, Entitlement.source_type == "TRIAL")
        )
    ).scalar_one()
    trial.expires_at = datetime.now(UTC) - timedelta(days=1)

    now = datetime.now(UTC)
    db_session.add(
        Entitlement(
            student_id=student_id,
            product_id=product_id,
            source_type="PURCHASE",
            source_id=uuid.uuid4(),
            status="ACTIVE",
            starts_at=now,
            expires_at=now + timedelta(days=365),
        )
    )
    await db_session.commit()

    resp = await client.get(PREMIUM_ROUTE)
    assert resp.status_code == 200


async def test_expired_trial_with_no_entitlement_gets_403(client, db_session: AsyncSession, register_user):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])

    trial = (
        await db_session.execute(
            select(Entitlement).where(Entitlement.student_id == student_id, Entitlement.source_type == "TRIAL")
        )
    ).scalar_one()
    trial.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()

    resp = await client.get(PREMIUM_ROUTE)
    assert resp.status_code == 403
    assert resp.json()["errors"][0]["code"] == "NO_ACTIVE_ACCESS"


async def test_expired_entitlement_with_no_active_trial_gets_403(client, db_session: AsyncSession, register_user):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])
    product_id = await _product_id(db_session)

    trial = (
        await db_session.execute(
            select(Entitlement).where(Entitlement.student_id == student_id, Entitlement.source_type == "TRIAL")
        )
    ).scalar_one()
    trial.expires_at = datetime.now(UTC) - timedelta(days=1)

    now = datetime.now(UTC)
    db_session.add(
        Entitlement(
            student_id=student_id,
            product_id=product_id,
            source_type="PURCHASE",
            source_id=uuid.uuid4(),
            status="ACTIVE",
            starts_at=now - timedelta(days=400),
            expires_at=now - timedelta(days=35),  # expired
        )
    )
    await db_session.commit()

    resp = await client.get(PREMIUM_ROUTE)
    assert resp.status_code == 403


async def test_unauthorized_student_cannot_call_admin_commerce_endpoint(client, db_session: AsyncSession, register_user):
    """Non-premium boundary: a normal student (with or without active
    access) must still be rejected from admin routes by the existing
    permission system — access-enforcement and admin-authorization are
    separate, independent gates, and this proves neither one substitutes
    for the other."""
    await register_user(client, db_session=db_session)  # active trial, but no admin role/permission
    resp = await client.get("/api/v1/admin/commerce/orders")
    assert resp.status_code == 403


async def test_public_pricing_route_unaffected_by_access_enforcement(client):
    """Non-premium boundary: public routes must remain reachable regardless
    of access state — proves require_active_access was applied selectively,
    not globally."""
    resp = await client.get("/api/v1/commerce/pricing")
    assert resp.status_code == 200


async def test_account_level_route_unaffected_by_access_enforcement(client, db_session: AsyncSession, register_user):
    """Non-premium boundary: authenticated account-level routes (e.g.
    logout) must remain reachable even for a student with no active
    access — access-enforcement must not have been blindly applied
    router-wide to auth_router."""
    await register_user(client, db_session=db_session)
    trial = (await db_session.execute(select(Entitlement).where(Entitlement.source_type == "TRIAL"))).scalar_one()
    trial.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
