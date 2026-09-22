from __future__ import annotations

import hashlib
import hmac
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.services import commerce_service as commerce_service_mod
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")

FAKE_KEY_ID = "rzp_test_fake_key_id"
FAKE_KEY_SECRET = "fake_test_secret_never_real"  # noqa: S105 - test fixture value, not a real secret


def _sign(order_id: str, payment_id: str, secret: str = FAKE_KEY_SECRET) -> str:
    payload = f"{order_id}|{payment_id}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class _FakeSettings:
    razorpay_key_id = FAKE_KEY_ID
    razorpay_key_secret = FAKE_KEY_SECRET


def _stub_razorpay(monkeypatch, *, order_counter: list[int]):
    """No real network call — mirrors the established pattern in this repo
    (e.g. TwilioVerifyStub) of stubbing the external gateway boundary while
    exercising every line of real application logic around it, including
    the real HMAC verification in razorpay_client.verify_payment_signature."""
    monkeypatch.setattr(commerce_service_mod, "get_settings", lambda: _FakeSettings())

    async def _fake_create_order_paise(*, amount_paise, receipt, key_id, key_secret):
        order_counter[0] += 1
        return {"id": f"order_fake_{order_counter[0]}", "amount": amount_paise, "currency": "INR"}

    monkeypatch.setattr(
        "app.modules.commerce.gateway.razorpay_provider.create_razorpay_order_paise", _fake_create_order_paise
    )


async def _create_order(client: AsyncClient) -> dict:
    resp = await client.post("/api/v1/commerce/orders", headers=csrf_headers(client))
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_order_amount_is_locked_at_creation_not_client_supplied(
    client, db_session: AsyncSession, register_user, monkeypatch
):
    _stub_razorpay(monkeypatch, order_counter=[0])
    await register_user(client, db_session=db_session)

    order = await _create_order(client)
    assert order["amountPaise"] == 49900  # server-determined FOUNDING_500 price, ignoring any client input


async def test_client_cannot_choose_another_students_order(client, db_session: AsyncSession, register_user, monkeypatch):
    _stub_razorpay(monkeypatch, order_counter=[0])
    await register_user(client, db_session=db_session)
    order = await _create_order(client)

    # Student B logs in and tries to verify student A's order.
    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)

    resp = await client.post(
        f"/api/v1/commerce/orders/{order['id']}/verify",
        json={"razorpay_payment_id": "pay_x", "razorpay_signature": "sig_x"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 404  # order lookup is scoped to the authenticated user, not just order_id


async def test_tampered_signature_is_rejected(client, db_session: AsyncSession, register_user, monkeypatch):
    _stub_razorpay(monkeypatch, order_counter=[0])
    await register_user(client, db_session=db_session)
    order = await _create_order(client)

    bad_signature = _sign(order["razorpayOrderId"], "pay_123", secret="wrong_secret")
    resp = await client.post(
        f"/api/v1/commerce/orders/{order['id']}/verify",
        json={"razorpay_payment_id": "pay_123", "razorpay_signature": bad_signature},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "INVALID_SIGNATURE"


async def test_valid_signature_verifies_and_grants_entitlement(client, db_session: AsyncSession, register_user, monkeypatch):
    _stub_razorpay(monkeypatch, order_counter=[0])
    user = await register_user(client, db_session=db_session)
    order = await _create_order(client)

    valid_signature = _sign(order["razorpayOrderId"], "pay_123")
    resp = await client.post(
        f"/api/v1/commerce/orders/{order['id']}/verify",
        json={"razorpay_payment_id": "pay_123", "razorpay_signature": valid_signature},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "PAID"

    from app.modules.commerce.services.access_service import PAID_ACTIVE, AccessService

    access = AccessService(db_session)
    state = await access.get_access_state(uuid.UUID(user["id"]))
    assert state.state == PAID_ACTIVE
    assert state.entitlement_expires_at is not None


async def test_duplicate_verification_is_idempotent_no_double_entitlement(
    client, db_session: AsyncSession, register_user, monkeypatch
):
    _stub_razorpay(monkeypatch, order_counter=[0])
    user = await register_user(client, db_session=db_session)
    order = await _create_order(client)

    valid_signature = _sign(order["razorpayOrderId"], "pay_123")
    payload = {"razorpay_payment_id": "pay_123", "razorpay_signature": valid_signature}

    first = await client.post(f"/api/v1/commerce/orders/{order['id']}/verify", json=payload, headers=csrf_headers(client))
    second = await client.post(f"/api/v1/commerce/orders/{order['id']}/verify", json=payload, headers=csrf_headers(client))
    assert first.status_code == 200
    assert second.status_code == 200

    from sqlalchemy import func, select

    from app.modules.commerce.models import Entitlement

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(Entitlement)
            .where(Entitlement.student_id == uuid.UUID(user["id"]), Entitlement.source_type == "PURCHASE")
        )
    ).scalar_one()
    assert count == 1  # exactly one entitlement, not two, despite verifying twice


async def test_same_payment_id_cannot_pay_two_orders(client, db_session: AsyncSession, register_user, monkeypatch):
    _stub_razorpay(monkeypatch, order_counter=[0])
    await register_user(client, db_session=db_session)
    order_a = await _create_order(client)
    order_b = await _create_order(client)

    signature_a = _sign(order_a["razorpayOrderId"], "pay_shared")
    resp_a = await client.post(
        f"/api/v1/commerce/orders/{order_a['id']}/verify",
        json={"razorpay_payment_id": "pay_shared", "razorpay_signature": signature_a},
        headers=csrf_headers(client),
    )
    assert resp_a.status_code == 200

    # Reusing the same razorpay_payment_id on a different order, even with a
    # signature that validates against THAT order's razorpay_order_id, must
    # fail on the DB-level uniqueness guard.
    signature_b = _sign(order_b["razorpayOrderId"], "pay_shared")
    resp_b = await client.post(
        f"/api/v1/commerce/orders/{order_b['id']}/verify",
        json={"razorpay_payment_id": "pay_shared", "razorpay_signature": signature_b},
        headers=csrf_headers(client),
    )
    assert resp_b.status_code == 409
    assert resp_b.json()["errors"][0]["code"] == "DUPLICATE_PAYMENT"


async def test_unverified_payment_does_not_grant_access(client, db_session: AsyncSession, register_user, monkeypatch):
    """Creating an order (even reaching PAYMENT_PENDING) must never itself
    grant access — only a real verified signature does."""
    _stub_razorpay(monkeypatch, order_counter=[0])
    user = await register_user(client, db_session=db_session)
    await _create_order(client)

    from app.modules.commerce.services.access_service import AccessService

    access = AccessService(db_session)
    state = await access.get_access_state(uuid.UUID(user["id"]))
    # Still just on the trial, not PAID_ACTIVE, despite an order existing.
    assert state.state != "PAID_ACTIVE"


async def test_anonymous_user_cannot_create_order(client):
    resp = await client.post("/api/v1/commerce/orders")
    assert resp.status_code == 401


async def test_csrf_required_for_order_creation(client, db_session: AsyncSession, register_user, monkeypatch):
    _stub_razorpay(monkeypatch, order_counter=[0])
    await register_user(client, db_session=db_session)
    resp = await client.post("/api/v1/commerce/orders")  # no CSRF header
    assert resp.status_code == 403
