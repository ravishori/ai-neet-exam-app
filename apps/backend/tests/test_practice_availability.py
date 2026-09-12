"""WAVE-P0-5: published-only practice pool + recommendations skip empty concepts."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _four_options(stem: str = "Practice gate question?"):
    return publishable_question_body(
        stem=stem,
        options=[
            {"label": "A", "text": "One"},
            {"label": "B", "text": "Two"},
            {"label": "C", "text": "Three"},
            {"label": "D", "text": "Four"},
        ],
        explanation="Gate explanation.",
    )


async def _concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _concept_without_published(db_session) -> str:
    """Pick a concept that has no PUBLISHED questions (prefer unused syllabus concepts)."""
    from app.modules.academic.models import Concept
    from app.modules.cms.models import ContentItem

    published = select(ContentItem.concept_id).where(
        ContentItem.content_type == "QUESTION",
        ContentItem.status == "PUBLISHED",
        ContentItem.concept_id.is_not(None),
        ContentItem.deleted_at.is_(None),
    )
    result = await db_session.execute(select(Concept.id).where(Concept.id.not_in(published)).limit(1))
    concept_id = result.scalar_one_or_none()
    assert concept_id is not None, "Need at least one concept without published questions for this test"
    return str(concept_id)


async def _as_content_manager(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)


async def _publish_question(client, concept_id: str, stem: str) -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": f"P05 {stem[:40]}",
            "slug": f"p05-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": _four_options(stem),
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{item_id}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    pub = await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    assert pub.status_code == 200, pub.text
    return item_id


async def test_practice_rejects_empty_concept_with_no_questions_code(client, db_session, register_user):
    await register_user(client)
    empty_concept = await _concept_without_published(db_session)
    resp = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CONCEPT", "scope_id": empty_concept, "question_count": 10},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422
    err = resp.json()["errors"][0]
    assert err["code"] == "NO_QUESTIONS_AVAILABLE"
    assert "published" in err["message"].lower()


async def test_practice_only_includes_published_not_draft(client, db_session, register_user):
    await _as_content_manager(client, db_session, register_user)
    concept_id = await _concept_id(db_session)

    # Draft only — must not become practice pool
    draft = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "Draft only",
            "slug": f"p05-draft-{uuid.uuid4().hex[:8]}",
            "language": "en",
            "body": _four_options("Draft stem only"),
        },
        headers=csrf_headers(client),
    )
    assert draft.status_code == 201
    draft_id = draft.json()["data"]["id"]

    # If this concept already has other published items, practice may succeed —
    # assert the draft id is never in the assessment questions.
    published_id = await _publish_question(client, concept_id, f"Published stem {uuid.uuid4().hex[:6]}")

    practice = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CONCEPT", "scope_id": concept_id, "question_count": 90},
        headers=csrf_headers(client),
    )
    assert practice.status_code == 201, practice.text
    assessment_id = practice.json()["data"]["id"]
    meta = practice.json().get("meta") or {}
    assert "available_count" in meta
    assert meta["delivered_count"] <= meta["available_count"]

    attempt = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    assert attempt.status_code == 201
    detail = await client.get(f"/api/v1/attempts/{attempt.json()['data']['id']}")
    assert detail.status_code == 200
    questions = detail.json()["data"]["questions"]
    qids = [q.get("content_item_id") or q.get("id") for q in questions]
    assert published_id in qids
    assert draft_id not in qids


async def test_recommendations_exclude_concepts_without_published_questions(client, db_session, register_user):
    await register_user(client)
    empty_concept = await _concept_without_published(db_session)

    resp = await client.get("/api/v1/learning/recommendations")
    assert resp.status_code == 200
    ids = {item["concept_id"] for item in resp.json()["data"]}
    assert empty_concept not in ids
    for item in resp.json()["data"]:
        assert item.get("published_question_count", 0) >= 1


async def test_revision_due_includes_published_count_when_present(client, db_session, register_user):
    await register_user(client)
    resp = await client.get("/api/v1/learning/revision/due")
    assert resp.status_code == 200
    for item in resp.json()["data"]:
        assert "published_question_count" in item
        assert item["published_question_count"] >= 1
