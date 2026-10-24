"""Integration tests for the Razorpay webhook reconciliation path.

Covers: signature verification as the first gate, idempotency via the
commerce.webhook_events unique constraint, the payment.captured ->
PAID / payment.failed -> FAILED state transitions independent of the
client-driven /verify endpoint, unknown-order-id handling, and
concurrent-replay safety.
"""

import asyncio
import hashlib
import hmac
import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.commerce.models import Order
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")

WEBHOOK_SECRET = "test_webhook_secret"


def _sign(raw_body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def _webhook_payload(*, event: str, razorpay_order_id: str, razorpay_payment_id: str) -> bytes:
    return json.dumps(
        {
            "event": event,
            "payload": {
                "payment": {
                    "entity": {
                        "id": razorpay_payment_id,
                        "order_id": razorpay_order_id,
                    }
                }
            },
        }
    ).encode()


async def _make_order(db_session: AsyncSession, *, user_id: uuid.UUID, razorpay_order_id: str) -> Order:
    order = Order(
        user_id=user_id,
        amount_inr=499.00,
        status="CREATED",
        razorpay_order_id=razorpay_order_id,
    )
    db_session.add(order)
    await db_session.commit()
    return order


@pytest.fixture(autouse=True)
def _set_webhook_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "razorpay_webhook_secret", WEBHOOK_SECRET)


async def test_valid_signature_payment_captured_marks_order_paid(client, db_session, register_user):
    user = await register_user(client)
    order = await _make_order(db_session, user_id=uuid.UUID(user["id"]), razorpay_order_id="order_capture_1")

    body = _webhook_payload(event="payment.captured", razorpay_order_id="order_capture_1", razorpay_payment_id="pay_1")
    resp = await client.post(
        "/api/v1/commerce/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "X-Razorpay-Event-Id": "evt_1", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    await db_session.refresh(order)
    assert order.status == "PAID"
    assert order.razorpay_payment_id == "pay_1"


async def test_invalid_signature_rejected_order_untouched(client, db_session, register_user):
    user = await register_user(client)
    order = await _make_order(db_session, user_id=uuid.UUID(user["id"]), razorpay_order_id="order_badsig_1")

    body = _webhook_payload(event="payment.captured", razorpay_order_id="order_badsig_1", razorpay_payment_id="pay_x")
    resp = await client.post(
        "/api/v1/commerce/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": "not-a-real-signature", "X-Razorpay-Event-Id": "evt_bad", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400

    await db_session.refresh(order)
    assert order.status == "CREATED"


async def test_missing_signature_rejected(client, db_session, register_user):
    user = await register_user(client)
    order = await _make_order(db_session, user_id=uuid.UUID(user["id"]), razorpay_order_id="order_nosig_1")

    body = _webhook_payload(event="payment.captured", razorpay_order_id="order_nosig_1", razorpay_payment_id="pay_x")
    resp = await client.post(
        "/api/v1/commerce/webhooks/razorpay", content=body, headers={"X-Razorpay-Event-Id": "evt_nosig", "Content-Type": "application/json"}
    )
    assert resp.status_code == 400

    await db_session.refresh(order)
    assert order.status == "CREATED"


async def test_duplicate_event_id_replay_is_safe_noop(client, db_session, register_user):
    user = await register_user(client)
    order = await _make_order(db_session, user_id=uuid.UUID(user["id"]), razorpay_order_id="order_dup_1")

    body = _webhook_payload(event="payment.captured", razorpay_order_id="order_dup_1", razorpay_payment_id="pay_dup")
    headers = {"X-Razorpay-Signature": _sign(body), "X-Razorpay-Event-Id": "evt_dup", "Content-Type": "application/json"}

    first = await client.post("/api/v1/commerce/webhooks/razorpay", content=body, headers=headers)
    second = await client.post("/api/v1/commerce/webhooks/razorpay", content=body, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200

    await db_session.refresh(order)
    assert order.status == "PAID"

    from sqlalchemy import func, select

    from app.modules.commerce.models import WebhookEvent

    count = await db_session.execute(
        select(func.count()).select_from(WebhookEvent).where(WebhookEvent.provider_event_id == "evt_dup")
    )
    assert count.scalar_one() == 1


async def test_unrelated_order_id_does_not_crash_or_touch_other_orders(client, db_session, register_user):
    user = await register_user(client)
    order = await _make_order(db_session, user_id=uuid.UUID(user["id"]), razorpay_order_id="order_real_1")

    body = _webhook_payload(
        event="payment.captured", razorpay_order_id="order_does_not_exist_999", razorpay_payment_id="pay_ghost"
    )
    resp = await client.post(
        "/api/v1/commerce/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "X-Razorpay-Event-Id": "evt_ghost", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    await db_session.refresh(order)
    assert order.status == "CREATED"


async def test_payment_captured_without_prior_verify_call_still_reaches_paid(client, db_session, register_user):
    """The core reconciliation guarantee: the client never calls /verify
    (tab closed, crash, network drop) but the webhook alone must still
    transition CREATED -> PAID."""
    user = await register_user(client)
    order = await _make_order(db_session, user_id=uuid.UUID(user["id"]), razorpay_order_id="order_recon_1")
    assert order.status == "CREATED"

    body = _webhook_payload(event="payment.captured", razorpay_order_id="order_recon_1", razorpay_payment_id="pay_recon")
    resp = await client.post(
        "/api/v1/commerce/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "X-Razorpay-Event-Id": "evt_recon", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    await db_session.refresh(order)
    assert order.status == "PAID"


async def test_payment_failed_marks_order_failed_never_paid(client, db_session, register_user):
    user = await register_user(client)
    order = await _make_order(db_session, user_id=uuid.UUID(user["id"]), razorpay_order_id="order_fail_1")

    body = _webhook_payload(event="payment.failed", razorpay_order_id="order_fail_1", razorpay_payment_id="pay_fail")
    resp = await client.post(
        "/api/v1/commerce/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "X-Razorpay-Event-Id": "evt_fail", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    await db_session.refresh(order)
    assert order.status == "FAILED"
    assert order.status != "PAID"


async def test_concurrent_duplicate_delivery_processed_only_once(client, db_session, register_user):
    """Two near-simultaneous deliveries of the same event id must still
    result in exactly one dedup row and one state transition."""
    user = await register_user(client)
    order = await _make_order(db_session, user_id=uuid.UUID(user["id"]), razorpay_order_id="order_concurrent_1")

    body = _webhook_payload(
        event="payment.captured", razorpay_order_id="order_concurrent_1", razorpay_payment_id="pay_concurrent"
    )
    headers = {
        "X-Razorpay-Signature": _sign(body),
        "X-Razorpay-Event-Id": "evt_concurrent",
        "Content-Type": "application/json",
    }

    results = await asyncio.gather(
        client.post("/api/v1/commerce/webhooks/razorpay", content=body, headers=headers),
        client.post("/api/v1/commerce/webhooks/razorpay", content=body, headers=headers),
    )
    for resp in results:
        assert resp.status_code == 200

    await db_session.refresh(order)
    assert order.status == "PAID"

    from sqlalchemy import func, select

    from app.modules.commerce.models import WebhookEvent

    count = await db_session.execute(
        select(func.count()).select_from(WebhookEvent).where(WebhookEvent.provider_event_id == "evt_concurrent")
    )
    assert count.scalar_one() == 1


async def test_webhook_driven_paid_order_activates_entitlement(client, db_session, register_user):
    """Proves the entitlement check (OrderRepository.has_paid_order, which
    backs GET /commerce/status) flips to true via the webhook-driven PAID
    transition alone -- not just via the client-driven /verify endpoint."""
    from app.modules.commerce.repositories.order_repository import OrderRepository

    user = await register_user(client)
    user_id = uuid.UUID(user["id"])
    await _make_order(db_session, user_id=user_id, razorpay_order_id="order_entitlement_1")

    repo = OrderRepository(db_session)
    assert await repo.has_paid_order(user_id) is False

    body = _webhook_payload(
        event="payment.captured", razorpay_order_id="order_entitlement_1", razorpay_payment_id="pay_entitlement"
    )
    resp = await client.post(
        "/api/v1/commerce/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "X-Razorpay-Event-Id": "evt_entitlement", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    assert await repo.has_paid_order(user_id) is True

    status_resp = await client.get("/api/v1/commerce/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["is_premium"] is True


async def test_verify_rejects_order_belonging_to_another_user(client, db_session, register_user):
    """Cross-user ownership check on the existing /orders/{id}/verify
    endpoint (commerce_service.py: verify_payment, `order.user_id !=
    user_id` branch). Flagged by the original audit as missing test
    coverage, not missing implementation -- this is that coverage."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    # orders.user_id is FK-constrained to identity.users.id, so "the other
    # user" must be a real registered user, not an arbitrary UUID. Use a
    # second client (separate cookie jar, same overridden db_session) so
    # registering them doesn't clobber the primary client's session.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other_client:
        other_user = await register_user(other_client)
    other_user_id = uuid.UUID(other_user["id"])

    others_order = await _make_order(db_session, user_id=other_user_id, razorpay_order_id="order_not_mine")

    # The authenticated caller on `client` is a different, freshly
    # registered user.
    await register_user(client)

    resp = await client.post(
        f"/api/v1/commerce/orders/{others_order.id}/verify",
        json={"razorpay_payment_id": "pay_x", "razorpay_signature": "sig_x"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 404
    assert resp.json()["errors"][0]["code"] == "NOT_FOUND"

    await db_session.refresh(others_order)
    assert others_order.status == "CREATED"
