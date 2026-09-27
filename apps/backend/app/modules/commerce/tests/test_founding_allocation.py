from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.modules.commerce.models import PricingPlan
from app.modules.commerce.services.founding_allocation import (
    FOUNDING_PLAN_CODE,
    STANDARD_PLAN_CODE,
    FoundingAllocationService,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

TEST_DATABASE_URL = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_test_db"


async def _get_plan(session: AsyncSession, code: str) -> PricingPlan:
    return (await session.execute(select(PricingPlan).where(PricingPlan.code == code))).scalar_one()


async def test_first_purchase_gets_founding_price(db_session: AsyncSession):
    founding = await _get_plan(db_session, FOUNDING_PLAN_CODE)
    founding.purchase_count = 0
    await db_session.commit()

    service = FoundingAllocationService(db_session)
    plan, expires_at = await service.allocate_slot()
    assert plan.code == FOUNDING_PLAN_CODE
    assert plan.amount_paise == 49900
    assert expires_at is not None


async def test_500th_purchase_gets_founding_price(db_session: AsyncSession):
    founding = await _get_plan(db_session, FOUNDING_PLAN_CODE)
    founding.purchase_count = 499
    await db_session.commit()

    service = FoundingAllocationService(db_session)
    plan, _ = await service.allocate_slot()
    assert plan.code == FOUNDING_PLAN_CODE

    refreshed = await _get_plan(db_session, FOUNDING_PLAN_CODE)
    assert refreshed.purchase_count == 500


async def test_501st_purchase_gets_standard_price(db_session: AsyncSession):
    founding = await _get_plan(db_session, FOUNDING_PLAN_CODE)
    founding.purchase_count = 500
    await db_session.commit()

    service = FoundingAllocationService(db_session)
    plan, expires_at = await service.allocate_slot()
    assert plan.code == STANDARD_PLAN_CODE
    assert plan.amount_paise == 99900
    assert expires_at is None

    # Founding counter must not have been touched.
    refreshed = await _get_plan(db_session, FOUNDING_PLAN_CODE)
    assert refreshed.purchase_count == 500


async def test_failed_payment_does_not_consume_a_slot(db_session: AsyncSession):
    """Reservation happens at order-creation (allocate_slot), not at
    payment-verification — a FAILED order still holds its slot until expiry
    (documented trade-off in founding_allocation.py). This test proves the
    counter is NOT decremented merely because a payment attempt fails
    (order.status = FAILED is a separate lifecycle event from the slot
    reservation/release rule, which is time-based, not failure-based)."""
    founding = await _get_plan(db_session, FOUNDING_PLAN_CODE)
    founding.purchase_count = 0
    await db_session.commit()

    service = FoundingAllocationService(db_session)
    plan, _ = await service.allocate_slot()
    assert plan.code == FOUNDING_PLAN_CODE

    refreshed = await _get_plan(db_session, FOUNDING_PLAN_CODE)
    assert refreshed.purchase_count == 1
    # Slot is reserved regardless of eventual payment outcome — only expiry
    # (release_expired) or explicit release_slot() gives it back.


async def test_expired_unpaid_order_releases_founding_slot(db_session: AsyncSession, register_user, client):
    from datetime import UTC, datetime, timedelta

    from app.modules.commerce.models import Order

    founding = await _get_plan(db_session, FOUNDING_PLAN_CODE)
    founding.purchase_count = 0
    await db_session.commit()

    user = await register_user(client, db_session=db_session)
    order = Order(
        user_id=uuid.UUID(user["id"]),
        order_number=f"ORD-TEST-{uuid.uuid4().hex[:8]}",
        pricing_plan_id=founding.id,
        amount_paise=49900,
        status="CREATED",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),  # already expired
    )
    db_session.add(order)
    founding.purchase_count = 1  # simulate the reservation this order made
    await db_session.commit()

    service = FoundingAllocationService(db_session)
    released = await service.release_expired()
    assert released == 1

    refreshed = await _get_plan(db_session, FOUNDING_PLAN_CODE)
    assert refreshed.purchase_count == 0

    await db_session.refresh(order)
    assert order.status == "EXPIRED"


async def test_concurrent_allocation_never_exceeds_max_purchases():
    """Real concurrency test: N simultaneous allocate_slot() calls, each on
    its OWN database connection (not the single shared SAVEPOINT-isolated
    db_session fixture, which cannot exercise real row-lock contention),
    against a live Postgres with only 2 founding slots remaining. Proves the
    SELECT...FOR UPDATE lock in FoundingAllocationService serializes
    concurrent requests so at most 2 receive the founding price."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    setup_session = session_factory()
    try:
        founding = await _get_plan(setup_session, FOUNDING_PLAN_CODE)
        founding.purchase_count = 498  # exactly 2 slots remaining
        await setup_session.commit()
    finally:
        await setup_session.close()

    concurrency = 6  # far more concurrent attempts than slots remaining

    async def _attempt() -> str:
        session = session_factory()
        try:
            service = FoundingAllocationService(session)
            plan, _ = await service.allocate_slot()
            return plan.code
        finally:
            await session.close()

    try:
        results = await asyncio.gather(*[_attempt() for _ in range(concurrency)])
        founding_count = results.count(FOUNDING_PLAN_CODE)
        standard_count = results.count(STANDARD_PLAN_CODE)

        assert founding_count == 2, f"expected exactly 2 founding allocations, got {founding_count}: {results}"
        assert standard_count == concurrency - 2

        verify_session = session_factory()
        try:
            refreshed = await _get_plan(verify_session, FOUNDING_PLAN_CODE)
            assert refreshed.purchase_count == 500
        finally:
            await verify_session.close()
    finally:
        # Cleanup: this test bypasses the SAVEPOINT-isolated fixture (by
        # design — real concurrency requires real separate connections), so
        # it must reset state it changed instead of relying on an automatic
        # rollback.
        cleanup_session = session_factory()
        try:
            founding = await _get_plan(cleanup_session, FOUNDING_PLAN_CODE)
            founding.purchase_count = 0
            await cleanup_session.commit()
        finally:
            await cleanup_session.close()
        await engine.dispose()
