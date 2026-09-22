from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.models import Entitlement, Product
from app.modules.commerce.services.access_service import AccessService
from app.modules.commerce.services.entitlement_service import EntitlementService

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _product_id(db_session: AsyncSession) -> uuid.UUID:
    return (await db_session.execute(select(Product).where(Product.code == "ALL_ACCESS"))).scalar_one().id


async def test_purchase_grants_365_day_entitlement(db_session: AsyncSession, register_user, client):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])
    product_id = await _product_id(db_session)

    service = EntitlementService(db_session)
    entitlement = await service.grant_or_extend(
        student_id=student_id, product_id=product_id, source_id=uuid.uuid4(), duration_days=365
    )
    delta = entitlement.expires_at - entitlement.starts_at
    assert 364 <= delta.days <= 365


async def test_second_purchase_extends_not_overwrites(db_session: AsyncSession, register_user, client):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])
    product_id = await _product_id(db_session)

    service = EntitlementService(db_session)
    first = await service.grant_or_extend(
        student_id=student_id, product_id=product_id, source_id=uuid.uuid4(), duration_days=365
    )
    first_expiry = first.expires_at

    second = await service.grant_or_extend(
        student_id=student_id, product_id=product_id, source_id=uuid.uuid4(), duration_days=365
    )
    assert second.id == first.id  # same row, extended — not a second overlapping entitlement
    assert second.expires_at == first_expiry + timedelta(days=365)


async def test_grant_is_idempotent_per_source_id(db_session: AsyncSession, register_user, client):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])
    product_id = await _product_id(db_session)
    source_id = uuid.uuid4()

    service = EntitlementService(db_session)
    first = await service.grant_or_extend(
        student_id=student_id, product_id=product_id, source_id=source_id, duration_days=365
    )
    second = await service.grant_or_extend(
        student_id=student_id, product_id=product_id, source_id=source_id, duration_days=365
    )
    assert first.id == second.id
    assert first.expires_at == second.expires_at  # not extended twice for the same order


async def test_expired_entitlement_denies_access(db_session: AsyncSession, register_user, client):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])
    product_id = await _product_id(db_session)

    now = datetime.now(UTC)
    db_session.add(
        Entitlement(
            student_id=student_id,
            product_id=product_id,
            source_type="PURCHASE",
            source_id=uuid.uuid4(),
            status="ACTIVE",
            starts_at=now - timedelta(days=400),
            expires_at=now - timedelta(days=35),  # expired 35 days ago
        )
    )
    # Also expire the trial so it doesn't mask the expired-entitlement result.
    from app.modules.commerce.services.trial_service import TrialService

    trial = await TrialService(db_session).ensure_trial(student_id=student_id, product_code="ALL_ACCESS")
    trial.expires_at = now - timedelta(days=1)
    await db_session.commit()

    access = AccessService(db_session)
    state = await access.get_access_state(student_id)
    assert state.has_access is False


async def test_revoked_entitlement_denies_access(db_session: AsyncSession, register_user, client):
    user = await register_user(client, db_session=db_session)
    student_id = uuid.UUID(user["id"])
    product_id = await _product_id(db_session)

    now = datetime.now(UTC)
    db_session.add(
        Entitlement(
            student_id=student_id,
            product_id=product_id,
            source_type="PURCHASE",
            source_id=uuid.uuid4(),
            status="REVOKED",
            starts_at=now,
            expires_at=now + timedelta(days=365),
        )
    )
    from app.modules.commerce.services.trial_service import TrialService

    trial = await TrialService(db_session).ensure_trial(student_id=student_id, product_code="ALL_ACCESS")
    trial.expires_at = now - timedelta(days=1)
    await db_session.commit()

    access = AccessService(db_session)
    state = await access.get_access_state(student_id)
    # A revoked (inactive) entitlement never counts toward access; with an
    # expired trial also on record, TRIAL_EXPIRED is the accurate state
    # (distinct from NO_ACCESS, which means "no trial history at all") —
    # either way, the important assertion is has_access is False.
    assert state.state == "TRIAL_EXPIRED"
    assert state.has_access is False


async def test_money_amounts_are_integer_paise_no_float(db_session: AsyncSession):
    from app.modules.commerce.models import PricingPlan

    founding = (
        await db_session.execute(select(PricingPlan).where(PricingPlan.code == "FOUNDING_500"))
    ).scalar_one()
    standard = (
        await db_session.execute(select(PricingPlan).where(PricingPlan.code == "STANDARD_ANNUAL"))
    ).scalar_one()

    assert founding.amount_paise == 49900
    assert standard.amount_paise == 99900
    assert isinstance(founding.amount_paise, int)
    assert isinstance(standard.amount_paise, int)
