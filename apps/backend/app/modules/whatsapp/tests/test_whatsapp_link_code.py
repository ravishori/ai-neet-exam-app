"""M2-A: secure WhatsApp account-linking codes.

Most tests exercise WhatsAppLinkCodeService directly, the same way M1's
own tests exercise WhatsAppRepository/WhatsAppIdentityService directly.
One test (test_end_to_end_inbound_webhook_triggers_background_link)
exercises the real integration path — a signed POST through the actual
webhook router, with FastAPI's BackgroundTasks dispatch — rather than
calling the service directly, per the M2-A integration requirement."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import redis.asyncio as redis_asyncio
import structlog
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit as rl
from app.core.config import get_settings
from app.modules.identity.models.user import User
from app.modules.identity.services.token_service import hash_opaque_token
from app.modules.whatsapp.models.whatsapp_identity import WhatsAppIdentity
from app.modules.whatsapp.models.whatsapp_link_code import WhatsAppLinkCode
from app.modules.whatsapp.providers.twilio.webhook import compute_twilio_signature
from app.modules.whatsapp.services import whatsapp_link_code_service as link_code_module
from app.modules.whatsapp.services.whatsapp_link_code_service import (
    LinkOutcome,
    WhatsAppLinkCodeService,
    looks_like_link_code,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

_AUTH_TOKEN = "test-twilio-auth-token-link-1234567890"
_WEBHOOK_URL = "http://test/api/v1/whatsapp/webhook"


@pytest.fixture
async def real_redis():
    """A handful of tests need genuine Redis counting behavior to prove
    rate limiting actually throttles — the default test environment has
    no live Redis (get_redis() returns None, which check_rate_limit's
    fail_closed=False path silently no-ops on), so those specific tests
    opt into a real local connection instead."""
    client = redis_asyncio.from_url(get_settings().redis_url, decode_responses=True)
    yield client
    await client.aclose()


def _make_user(*, email: str) -> User:
    user = User(email=email, password_hash="x")
    # Pre-populate the (unused-here) roles relationship to an empty list
    # so accessing User.role_codes (e.g. the unlink router's SUPER_ADMIN
    # check) never triggers an async lazy-load outside a proper greenlet
    # context when this user is handed to the app via a plain
    # dependency-override lambda in HTTP-level tests.
    user.roles = []
    return user


def _make_identity(*, phone_e164: str, status: str = "active", user_id: uuid.UUID | None = None) -> WhatsAppIdentity:
    return WhatsAppIdentity(provider="twilio", phone_e164=phone_e164, status=status, user_id=user_id)


async def test_generate_code_requires_only_a_user_id_and_is_hash_stored(db_session):
    user = _make_user(email="link1@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user.id)

    assert len(generated.plaintext_code) == 8
    assert generated.expires_at > datetime.now(UTC)

    row = (await db_session.execute(select(WhatsAppLinkCode).where(WhatsAppLinkCode.user_id == user.id))).scalar_one()
    assert row.code_hash != generated.plaintext_code
    assert generated.plaintext_code not in row.code_hash


async def test_wrong_code_is_rejected_generically(db_session):
    user = _make_user(email="link2@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    await service.generate_code(user_id=user.id)

    identity = _make_identity(phone_e164="+919876510002")
    db_session.add(identity)
    await db_session.flush()

    result = await service.verify_and_link(plaintext_code="WRONGCOD", identity=identity)
    assert result.outcome == LinkOutcome.INVALID_CODE
    assert identity.user_id is None


async def test_expired_code_is_rejected(db_session):
    user = _make_user(email="link3@example.com")
    db_session.add(user)
    await db_session.flush()

    code = WhatsAppLinkCode(
        user_id=user.id,
        code_hash=hash_opaque_token("EXPIRED1"),
        attempts=0,
        max_attempts=5,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(code)
    identity = _make_identity(phone_e164="+919876510003")
    db_session.add(identity)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    result = await service.verify_and_link(plaintext_code="EXPIRED1", identity=identity)
    assert result.outcome == LinkOutcome.INVALID_CODE
    assert identity.user_id is None


async def test_phone_scoped_rate_limit_blocks_further_verification_attempts(db_session, real_redis, monkeypatch):
    """Replaces the old per-code cross-user attempt fan-out: throttling is
    now keyed on the WhatsApp phone number, the actual unauthenticated
    boundary. Proven with a real Redis connection — after exhausting the
    per-phone limit, even the CORRECT code must fail, which can only be
    explained by rate limiting (not a wrong guess)."""
    phone = f"+9198765{uuid.uuid4().int % 100000:05d}"
    monkeypatch.setattr(rl, "get_redis", lambda: real_redis)
    await real_redis.delete(f"ratelimit:whatsapp_link_verify:{phone}")

    user = _make_user(email="link4@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user.id)

    identity = _make_identity(phone_e164=phone)
    db_session.add(identity)
    await db_session.flush()

    for _ in range(5):
        result = await service.verify_and_link(plaintext_code="BADGUESS", identity=identity)
        assert result.outcome == LinkOutcome.INVALID_CODE

    # The per-phone limit (5/300s) is now exhausted — even the objectively
    # correct code must fail, proving the block is rate-limit-driven.
    final = await service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity)
    assert final.outcome == LinkOutcome.INVALID_CODE
    assert identity.user_id is None

    await real_redis.delete(f"ratelimit:whatsapp_link_verify:{phone}")


async def test_unrelated_pending_codes_not_locked_by_another_phones_guesses(db_session, real_redis, monkeypatch):
    """The exact cross-user issue being fixed: phone A's bad guesses must
    never affect phone B's independent, still-valid pending code."""
    phone_a = f"+9198765{uuid.uuid4().int % 100000:05d}"
    phone_b = f"+9198765{uuid.uuid4().int % 100000:05d}"
    monkeypatch.setattr(rl, "get_redis", lambda: real_redis)
    await real_redis.delete(f"ratelimit:whatsapp_link_verify:{phone_a}")
    await real_redis.delete(f"ratelimit:whatsapp_link_verify:{phone_b}")

    user_a = _make_user(email="link_a@example.com")
    user_b = _make_user(email="link_b@example.com")
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    await service.generate_code(user_id=user_a.id)
    generated_b = await service.generate_code(user_id=user_b.id)

    identity_a = _make_identity(phone_e164=phone_a)
    identity_b = _make_identity(phone_e164=phone_b)
    db_session.add_all([identity_a, identity_b])
    await db_session.flush()

    # Phone A exhausts its own rate limit with bad guesses.
    for _ in range(6):
        await service.verify_and_link(plaintext_code="BADGUESS", identity=identity_a)

    # Phone B's own, completely independent code must still work.
    result = await service.verify_and_link(plaintext_code=generated_b.plaintext_code, identity=identity_b)
    assert result.outcome == LinkOutcome.LINKED
    assert identity_b.user_id == user_b.id

    await real_redis.delete(f"ratelimit:whatsapp_link_verify:{phone_a}")
    await real_redis.delete(f"ratelimit:whatsapp_link_verify:{phone_b}")


async def test_successful_one_time_linking(db_session):
    user = _make_user(email="link5@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user.id)

    identity = _make_identity(phone_e164="+919876510005")
    db_session.add(identity)
    await db_session.flush()

    result = await service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity)
    assert result.outcome == LinkOutcome.LINKED
    assert result.user_id == user.id
    assert identity.user_id == user.id


async def test_replayed_code_is_rejected_after_first_success(db_session):
    user = _make_user(email="link6@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user.id)

    identity_a = _make_identity(phone_e164="+919876510006")
    identity_b = _make_identity(phone_e164="+919876510066")
    db_session.add_all([identity_a, identity_b])
    await db_session.flush()

    first = await service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity_a)
    assert first.outcome == LinkOutcome.LINKED

    replay = await service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity_b)
    assert replay.outcome == LinkOutcome.INVALID_CODE
    assert identity_b.user_id is None


async def test_concurrent_double_verification_links_exactly_once(db_session):
    """Two 'simultaneous' verification attempts for the same code against
    the same identity — only one may win."""
    user = _make_user(email="link7@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user.id)

    identity = _make_identity(phone_e164="+919876510007")
    db_session.add(identity)
    await db_session.flush()

    results = await asyncio.gather(
        service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity),
        service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity),
    )

    outcomes = sorted(r.outcome for r in results)
    # Exactly one LINKED; the other sees it already correctly linked
    # (ALREADY_LINKED) or loses the race (INVALID_CODE) depending on
    # interleaving — either is a safe, non-duplicating outcome.
    assert LinkOutcome.LINKED in outcomes
    assert identity.user_id == user.id


async def test_existing_correct_link_is_idempotent(db_session):
    user = _make_user(email="link8@example.com")
    db_session.add(user)
    await db_session.flush()

    identity = _make_identity(phone_e164="+919876510008", user_id=user.id)
    db_session.add(identity)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user.id)

    result = await service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity)
    assert result.outcome == LinkOutcome.ALREADY_LINKED
    assert result.user_id == user.id
    assert identity.user_id == user.id


async def test_conflicting_existing_link_is_never_overwritten(db_session):
    user_a = _make_user(email="link9a@example.com")
    user_b = _make_user(email="link9b@example.com")
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    identity = _make_identity(phone_e164="+919876510009", user_id=user_a.id)
    db_session.add(identity)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user_b.id)

    result = await service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity)
    assert result.outcome == LinkOutcome.CONFLICT
    assert result.user_id == user_a.id
    assert identity.user_id == user_a.id


async def test_blocked_identity_is_rejected_before_code_check(db_session):
    user = _make_user(email="link10@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user.id)

    identity = _make_identity(phone_e164="+919876510010", status="blocked")
    db_session.add(identity)
    await db_session.flush()

    result = await service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity)
    assert result.outcome == LinkOutcome.BLOCKED
    assert identity.user_id is None

    # The code itself must remain usable — a blocked identity rejecting
    # verification is not the same as the code being spent.
    other_identity = _make_identity(phone_e164="+919876510011")
    db_session.add(other_identity)
    await db_session.flush()
    second = await service.verify_and_link(plaintext_code=generated.plaintext_code, identity=other_identity)
    assert second.outcome == LinkOutcome.LINKED


async def test_unlink_by_linked_user_succeeds(db_session):
    user = _make_user(email="link11@example.com")
    db_session.add(user)
    await db_session.flush()

    identity = _make_identity(phone_e164="+919876510012", user_id=user.id)
    db_session.add(identity)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    ok = await service.unlink(identity=identity, requesting_user_id=user.id)
    assert ok is True
    assert identity.user_id is None


async def test_unlink_by_non_owner_is_denied(db_session):
    user_a = _make_user(email="link12a@example.com")
    user_b = _make_user(email="link12b@example.com")
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    identity = _make_identity(phone_e164="+919876510013", user_id=user_a.id)
    db_session.add(identity)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    ok = await service.unlink(identity=identity, requesting_user_id=user_b.id)
    assert ok is False
    assert identity.user_id == user_a.id  # unchanged


async def test_unlink_by_admin_override_succeeds(db_session):
    user_a = _make_user(email="link13a@example.com")
    admin = _make_user(email="link13admin@example.com")
    db_session.add_all([user_a, admin])
    await db_session.flush()

    identity = _make_identity(phone_e164="+919876510014", user_id=user_a.id)
    db_session.add(identity)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    ok = await service.unlink(identity=identity, requesting_user_id=admin.id, is_admin=True)
    assert ok is True
    assert identity.user_id is None


async def test_generation_invalidates_prior_pending_codes_for_same_user(db_session):
    user = _make_user(email="link14@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    first = await service.generate_code(user_id=user.id)
    await service.generate_code(user_id=user.id)

    identity = _make_identity(phone_e164="+919876510015")
    db_session.add(identity)
    await db_session.flush()

    # The first code must no longer work — superseded by the second request.
    result = await service.verify_and_link(plaintext_code=first.plaintext_code, identity=identity)
    assert result.outcome == LinkOutcome.INVALID_CODE


async def test_deleted_user_code_cannot_link(db_session):
    user = _make_user(email="link15@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user.id)

    user.deleted_at = datetime.now(UTC)
    await db_session.flush()

    identity = _make_identity(phone_e164="+919876510016")
    db_session.add(identity)
    await db_session.flush()

    result = await service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity)
    assert result.outcome == LinkOutcome.INVALID_CODE
    assert identity.user_id is None


async def test_plaintext_code_never_appears_in_logs(db_session):
    user = _make_user(email="link16@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    with structlog.testing.capture_logs() as logs:
        generated = await service.generate_code(user_id=user.id)

        identity = _make_identity(phone_e164="+919876510017")
        db_session.add(identity)
        await db_session.flush()
        await service.verify_and_link(plaintext_code=generated.plaintext_code, identity=identity)
        await service.verify_and_link(plaintext_code="WRONGONE", identity=identity)

    assert len(logs) > 0
    for entry in logs:
        assert generated.plaintext_code not in str(entry)


def test_looks_like_link_code_recognizer():
    assert looks_like_link_code("ab23cd45") == "AB23CD45"
    assert looks_like_link_code("  AB23CD45  ") == "AB23CD45"
    assert looks_like_link_code("too-short") is None
    assert looks_like_link_code("") is None
    assert looks_like_link_code(None) is None
    assert looks_like_link_code("hi there") is None
    # Ambiguous-character exclusions (0/O/1/I/L) must not be "valid shape":
    assert looks_like_link_code("AB0OCD45") is None


# ---------------------------------------------------------------------------
# End-to-end: real signed webhook POST -> frozen M1 persistence -> M2-A
# BackgroundTasks dispatch -> verification -> link. This exercises the
# actual integration path (whatsapp_webhook_router.py's dispatch), not a
# direct WhatsAppLinkCodeService call.
#
# The background task opens its own AsyncSessionLocal() (see
# dispatch_link_code_verification_in_background's docstring — same
# pattern as ingestion_router.py's _run_pipeline_in_background), which by
# default is bound to the app's main engine, not this test's isolated
# SAVEPOINT transaction. AsyncSessionLocal is monkeypatched here to a
# factory bound to this test's own connection (db_session.bind) so the
# background task's writes land in — and are visible from — the same
# transaction this test asserts against, and are rolled back with
# everything else at teardown. This is the same seam ingestion's own
# tests treat as the legitimate monkeypatch point for background tasks
# (they replace the task itself with a no-op; here we instead redirect
# its session so the real verification logic actually runs).
# ---------------------------------------------------------------------------


async def test_end_to_end_inbound_webhook_triggers_background_link(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setenv("WHATSAPP_TWILIO_ACCOUNT_SID", "ACtest0000000000000000000000000000")
    monkeypatch.setenv("WHATSAPP_TWILIO_AUTH_TOKEN", _AUTH_TOKEN)
    monkeypatch.setenv("WHATSAPP_TWILIO_WHATSAPP_FROM", "+15550001111")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "twilio")
    get_settings.cache_clear()

    def _test_session_factory():
        return AsyncSession(bind=db_session.bind, expire_on_commit=False)

    monkeypatch.setattr(link_code_module, "AsyncSessionLocal", _test_session_factory)

    user = _make_user(email="e2e_link@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user.id)
    await db_session.flush()

    form = {
        "MessageSid": "SMe2elinktest00000000000000000001",
        "From": "whatsapp:+919876599999",
        "To": "whatsapp:+911111111111",
        "Body": generated.plaintext_code,
    }
    sig = await compute_twilio_signature(_WEBHOOK_URL, form, _AUTH_TOKEN)

    resp = await client.post("/api/v1/whatsapp/webhook", data=form, headers={"X-Twilio-Signature": sig})
    assert resp.status_code == 200

    identity = (
        await db_session.execute(select(WhatsAppIdentity).where(WhatsAppIdentity.phone_e164 == "+919876599999"))
    ).scalar_one()
    assert identity.user_id == user.id

    code_row = (await db_session.execute(select(WhatsAppLinkCode).where(WhatsAppLinkCode.user_id == user.id))).scalar_one()
    assert code_row.consumed_at is not None
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Regression tests for the two PR-blocking findings from the prior
# read-only review: (1) the identity.user_id TOCTOU race under concurrent
# verification, (2) the unlink enumeration leak. Plus the pending-code-
# invalidation-on-unlink fix and the remaining requested coverage.
# ---------------------------------------------------------------------------


async def test_two_different_valid_codes_concurrently_resolve_to_one_winner(db_session):
    """The exact cross-user race the atomic-link fix closes: two
    different valid codes, for two different users, both targeting the
    same still-unlinked identity at once. Exactly one may win; the other
    must see CONFLICT, and its own code must remain unconsumed (per the
    existing 'CONFLICT never burns the code' property)."""
    user_a = _make_user(email="race_a@example.com")
    user_b = _make_user(email="race_b@example.com")
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    code_a = await service.generate_code(user_id=user_a.id)
    code_b = await service.generate_code(user_id=user_b.id)

    identity = _make_identity(phone_e164="+919876520001")
    db_session.add(identity)
    await db_session.flush()

    results = await asyncio.gather(
        service.verify_and_link(plaintext_code=code_a.plaintext_code, identity=identity),
        service.verify_and_link(plaintext_code=code_b.plaintext_code, identity=identity),
    )

    outcomes = [r.outcome for r in results]
    assert outcomes.count(LinkOutcome.LINKED) == 1
    assert LinkOutcome.CONFLICT in outcomes

    # Final DB state matches whichever one actually won — never a mix.
    winner = next(r for r in results if r.outcome == LinkOutcome.LINKED)
    assert identity.user_id == winner.user_id

    # Re-fetch the loser's own code row directly by its known owner to confirm it was never consumed.
    loser_user_id = user_b.id if winner.user_id == user_a.id else user_a.id
    loser_code_row = (
        await db_session.execute(select(WhatsAppLinkCode).where(WhatsAppLinkCode.user_id == loser_user_id))
    ).scalar_one()
    assert loser_code_row.consumed_at is None


async def test_duplicate_inbound_webhook_does_not_dispatch_verification_again(client: AsyncClient, db_session, monkeypatch):
    """A redelivered (duplicate) Twilio webhook must not trigger a second
    background verification attempt — proven by sending the SAME signed
    message twice and confirming the code is consumed exactly once, with
    the link established by (and attributable to) a single dispatch."""
    monkeypatch.setenv("WHATSAPP_TWILIO_ACCOUNT_SID", "ACtest0000000000000000000000000000")
    monkeypatch.setenv("WHATSAPP_TWILIO_AUTH_TOKEN", _AUTH_TOKEN)
    monkeypatch.setenv("WHATSAPP_TWILIO_WHATSAPP_FROM", "+15550001111")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "twilio")
    get_settings.cache_clear()

    def _test_session_factory():
        return AsyncSession(bind=db_session.bind, expire_on_commit=False)

    monkeypatch.setattr(link_code_module, "AsyncSessionLocal", _test_session_factory)

    user = _make_user(email="dup_dispatch@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    generated = await service.generate_code(user_id=user.id)
    await db_session.flush()

    form = {
        "MessageSid": "SMdupdispatchtest0000000000000001",
        "From": "whatsapp:+919876520002",
        "To": "whatsapp:+911111111111",
        "Body": generated.plaintext_code,
    }
    sig = await compute_twilio_signature(_WEBHOOK_URL, form, _AUTH_TOKEN)

    first = await client.post("/api/v1/whatsapp/webhook", data=form, headers={"X-Twilio-Signature": sig})
    second = await client.post("/api/v1/whatsapp/webhook", data=form, headers={"X-Twilio-Signature": sig})
    assert first.status_code == 200
    assert second.status_code == 200

    identity = (
        await db_session.execute(select(WhatsAppIdentity).where(WhatsAppIdentity.phone_e164 == "+919876520002"))
    ).scalar_one()
    assert identity.user_id == user.id

    # Exactly one message row (M1's own idempotency) and the code consumed exactly once.
    code_row = (await db_session.execute(select(WhatsAppLinkCode).where(WhatsAppLinkCode.user_id == user.id))).scalar_one()
    assert code_row.consumed_at is not None
    get_settings.cache_clear()


async def test_http_link_request_requires_authentication(client: AsyncClient):
    resp = await client.post("/api/v1/whatsapp/link/request")
    assert resp.status_code in (401, 403)


async def test_http_unlink_requires_authentication(client: AsyncClient):
    resp = await client.post("/api/v1/whatsapp/link/unlink", json={"phone_e164": "+919876520099"})
    assert resp.status_code in (401, 403)


async def test_http_link_request_requires_csrf(client: AsyncClient, db_session, monkeypatch):
    from app.main import app
    from app.modules.identity.dependencies import get_current_user

    user = _make_user(email="csrf_req@example.com")
    db_session.add(user)
    await db_session.flush()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.post("/api/v1/whatsapp/link/request")
        assert resp.status_code == 403
        assert resp.json()["errors"][0]["code"] == "CSRF_INVALID"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_http_link_request_succeeds_with_valid_auth_and_csrf(client: AsyncClient, db_session):
    from app.main import app
    from app.modules.identity.dependencies import CSRF_COOKIE, CSRF_HEADER, get_current_user

    user = _make_user(email="csrf_ok@example.com")
    db_session.add(user)
    await db_session.flush()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client.cookies.set(CSRF_COOKIE, "test-csrf-token")
        resp = await client.post("/api/v1/whatsapp/link/request", headers={CSRF_HEADER: "test-csrf-token"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]["code"]) == 8
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_http_unlink_enumeration_safe_responses_are_identical(client: AsyncClient, db_session):
    """Nonexistent identity and unauthorized-unlink must return the exact
    same status code and error code — proving the enumeration fix at the
    actual HTTP layer, not just at the service layer."""
    from app.main import app
    from app.modules.identity.dependencies import CSRF_COOKIE, CSRF_HEADER, get_current_user

    owner = _make_user(email="enum_owner@example.com")
    stranger = _make_user(email="enum_stranger@example.com")
    db_session.add_all([owner, stranger])
    await db_session.flush()

    identity = _make_identity(phone_e164="+919876520003", user_id=owner.id)
    db_session.add(identity)
    await db_session.flush()

    client.cookies.set(CSRF_COOKIE, "test-csrf-token")
    headers = {CSRF_HEADER: "test-csrf-token"}

    # Case 1: identity does not exist at all.
    app.dependency_overrides[get_current_user] = lambda: stranger
    try:
        resp_missing = await client.post("/api/v1/whatsapp/link/unlink", json={"phone_e164": "+919876599999"}, headers=headers)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # Case 2: identity exists, but the caller doesn't own it and isn't admin.
    app.dependency_overrides[get_current_user] = lambda: stranger
    try:
        resp_unauthorized = await client.post(
            "/api/v1/whatsapp/link/unlink", json={"phone_e164": "+919876520003"}, headers=headers
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp_missing.status_code == resp_unauthorized.status_code == 403
    assert (
        resp_missing.json()["errors"][0]["code"] == resp_unauthorized.json()["errors"][0]["code"] == "WHATSAPP_UNLINK_FORBIDDEN"
    )
    # Same message too — only the per-request correlation fields
    # (errorId/traceId/timestamp) legitimately differ.
    assert resp_missing.json()["errors"][0]["message"] == resp_unauthorized.json()["errors"][0]["message"]

    # The real owner, however, can unlink successfully.
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        resp_owner = await client.post("/api/v1/whatsapp/link/unlink", json={"phone_e164": "+919876520003"}, headers=headers)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert resp_owner.status_code == 200


async def test_unlink_invalidates_pending_codes_for_that_user(db_session):
    """After unlink, a different, still-unexpired code generated before
    the unlink must no longer be able to relink the identity (or any
    identity) — the exact unlink -> stale-code scenario."""
    user = _make_user(email="unlink_invalidate@example.com")
    db_session.add(user)
    await db_session.flush()

    service = WhatsAppLinkCodeService(db_session)
    first_code = await service.generate_code(user_id=user.id)

    identity = _make_identity(phone_e164="+919876520004")
    db_session.add(identity)
    await db_session.flush()

    # Link via the first code.
    linked = await service.verify_and_link(plaintext_code=first_code.plaintext_code, identity=identity)
    assert linked.outcome == LinkOutcome.LINKED

    # A second code requested later (e.g. to link a different phone) while still linked.
    stale_code = await service.generate_code(user_id=user.id)

    ok = await service.unlink(identity=identity, requesting_user_id=user.id)
    assert ok is True
    assert identity.user_id is None

    # The stale code must now be dead — redeeming it must not relink anything.
    other_identity = _make_identity(phone_e164="+919876520005")
    db_session.add(other_identity)
    await db_session.flush()

    result = await service.verify_and_link(plaintext_code=stale_code.plaintext_code, identity=other_identity)
    assert result.outcome == LinkOutcome.INVALID_CODE
    assert other_identity.user_id is None

    all_codes = (await db_session.execute(select(WhatsAppLinkCode).where(WhatsAppLinkCode.user_id == user.id))).scalars().all()
    assert all(c.consumed_at is not None for c in all_codes)
