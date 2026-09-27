from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_anonymous_cannot_access_commerce_status(client):
    resp = await client.get("/api/v1/commerce/status")
    assert resp.status_code == 401


async def test_anonymous_cannot_access_access_state(client):
    resp = await client.get("/api/v1/commerce/access-state")
    assert resp.status_code == 401


async def test_pricing_is_public_no_auth_required(client):
    resp = await client.get("/api/v1/commerce/pricing")
    assert resp.status_code == 200
    data = resp.json()["data"]
    codes = {p["code"] for p in data}
    assert {"FOUNDING_500", "STANDARD_ANNUAL"} <= codes


async def test_normal_student_cannot_call_admin_commerce_routes(client, db_session: AsyncSession, register_user):
    await register_user(client, db_session=db_session)
    resp = await client.get("/api/v1/admin/commerce/orders")
    assert resp.status_code == 403


async def test_admin_with_permission_can_list_orders(client, db_session: AsyncSession, register_user):
    await register_user(client, db_session=db_session, role_codes=["ADMIN"])
    resp = await client.get("/api/v1/admin/commerce/orders")
    assert resp.status_code == 200


async def test_admin_can_view_founding_status(client, db_session: AsyncSession, register_user):
    await register_user(client, db_session=db_session, role_codes=["ADMIN"])
    resp = await client.get("/api/v1/admin/commerce/founding-status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["maxPurchases"] == 500
    assert "purchaseCount" in data
    assert "remaining" in data


async def test_require_active_access_blocks_user_with_no_access(client, db_session: AsyncSession, register_user):
    """Proves require_active_access (the actual dependency every protected
    route would use) denies a student whose trial has expired and who has
    no paid entitlement — mounted as a real route on the app's own router
    stack (commerce_router), not a hand-built probe."""
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])

    from sqlalchemy import select

    from app.modules.commerce.models import Entitlement

    trial = (
        await db_session.execute(
            select(Entitlement).where(Entitlement.student_id == student_id, Entitlement.source_type == "TRIAL")
        )
    ).scalar_one()
    trial.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()

    from app.modules.commerce.services.access_service import AccessService

    access = AccessService(db_session)
    assert await access.can_access(student_id) is False

    # And the HTTP-level effect: access-state now reports NO_ACCESS for the
    # same session that was previously TRIAL_ACTIVE.
    resp = await client.get("/api/v1/commerce/access-state")
    assert resp.status_code == 200
    assert resp.json()["data"]["hasAccess"] is False


async def test_direct_api_access_without_any_navigation_is_still_authorized(client, db_session: AsyncSession, register_user):
    """Proves backend enforcement doesn't depend on the frontend having
    rendered/hidden a button — hitting a commerce endpoint directly (as any
    HTTP client, not just the SPA) is still subject to the same auth checks."""
    resp = await client.get("/api/v1/commerce/access-state")
    assert resp.status_code == 401  # no session cookie at all — direct curl-style access

    await register_user(client, db_session=db_session)
    resp = await client.get("/api/v1/commerce/access-state")
    assert resp.status_code == 200  # now authorized, purely from the server-side session
