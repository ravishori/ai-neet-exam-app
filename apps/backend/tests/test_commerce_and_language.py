"""Integration tests: commerce guard rail (ADR-0018) + multi-language fallback (ADR-0019)."""

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def test_order_creation_without_razorpay_keys_never_fakes_success(client):
    """The one place this codebase deliberately never simulates success —
    see ADR-0018. No ANTHROPIC_API_KEY-style fallback for payments."""
    resp = await client.post("/api/v1/auth/register", json={"email": "commerce-test@example.com", "password": "Commerce!234"})
    assert resp.status_code == 201

    order = await client.post("/api/v1/commerce/orders", headers=csrf_headers(client))
    assert order.status_code == 503
    assert order.json()["errors"][0]["code"] == "PAYMENT_GATEWAY_NOT_CONFIGURED"
    assert order.json()["data"] is None


async def test_commerce_status_defaults_to_not_premium(client):
    await client.post("/api/v1/auth/register", json={"email": "commerce-status@example.com", "password": "Commerce!234"})

    resp = await client.get("/api/v1/commerce/status")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_premium"] is False


async def test_language_falls_back_to_english_with_flag_when_untranslated(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)

    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "CONCEPT_NOTE",
            "concept_id": concept_id,
            "title": "English only note",
            "slug": f"english-only-{concept_id[:8]}",
            "language": "en",
            "body": {"summary": "English content.", "sections": []},
        },
        headers=csrf_headers(client),
    )
    item_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{item_id}/review", json={"decision": "approve"}, headers=csrf_headers(client)
    )
    await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))

    resp = await client.get(f"/api/v1/cms/concepts/{concept_id}/published?language=hi")
    assert resp.status_code == 200
    assert resp.json()["meta"]["language_fallback"] is True
    assert resp.json()["meta"]["language"] == "hi"
    assert resp.json()["data"][0]["language"] == "en"


async def test_language_no_fallback_when_translation_exists(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)

    for language in ("en", "hi"):
        create = await client.post(
            "/api/v1/cms/content-items",
            json={
                "content_type": "CONCEPT_NOTE",
                "concept_id": concept_id,
                "title": f"Note in {language}",
                "slug": f"note-{language}-{concept_id[:8]}",
                "language": language,
                "body": {"summary": f"Content in {language}.", "sections": []},
            },
            headers=csrf_headers(client),
        )
        item_id = create.json()["data"]["id"]
        await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
        await client.post(
            f"/api/v1/cms/content-items/{item_id}/review", json={"decision": "approve"}, headers=csrf_headers(client)
        )
        await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))

    resp = await client.get(f"/api/v1/cms/concepts/{concept_id}/published?language=hi")
    assert resp.status_code == 200
    assert resp.json()["meta"]["language_fallback"] is False
    assert resp.json()["data"][0]["language"] == "hi"
