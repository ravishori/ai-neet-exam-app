"""T6-C: Practice TOPIC scope + Kinematics topic-tree separation (test DB only)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _four_options(stem: str):
    return publishable_question_body(
        stem=stem,
        options=[
            {"label": "A", "text": "One"},
            {"label": "B", "text": "Two"},
            {"label": "C", "text": "Three"},
            {"label": "D", "text": "Four"},
        ],
        explanation="Topic-scope gate explanation.",
    )


async def _as_content_manager(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)


async def _publish_question(client, concept_id: str, stem: str) -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": f"T6 {stem[:40]}",
            "slug": f"t6-topic-{uuid.uuid4().hex[:10]}",
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


async def _kinematics_two_topic_trees(db_session):
    """Ensure one Kinematics chapter with two isolated topic trees (rollback-scoped)."""
    from app.modules.academic.models import Chapter, Concept, Subject, Topic

    subject = (
        await db_session.execute(select(Subject).where(Subject.code == "PHYSICS", Subject.deleted_at.is_(None)))
    ).scalar_one()
    chapter = (
        await db_session.execute(
            select(Chapter).where(
                Chapter.subject_id == subject.id,
                Chapter.code == "kinematics",
                Chapter.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    async def ensure_topic(code: str, name: str, order: int) -> Topic:
        existing = (
            await db_session.execute(
                select(Topic).where(Topic.chapter_id == chapter.id, Topic.code == code, Topic.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        topic = Topic(chapter_id=chapter.id, code=code, name=name, display_order=order)
        db_session.add(topic)
        await db_session.flush()
        return topic

    async def ensure_concept(topic: Topic, code: str, name: str) -> Concept:
        existing = (
            await db_session.execute(
                select(Concept).where(Concept.topic_id == topic.id, Concept.code == code, Concept.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        concept = Concept(topic_id=topic.id, code=code, name=name, display_order=0)
        db_session.add(concept)
        await db_session.flush()
        return concept

    straight = await ensure_topic("motion-in-a-straight-line", "Motion in a Straight Line", 1)
    plane = await ensure_topic("motion-in-a-plane", "Motion in a Plane", 2)
    c_straight = await ensure_concept(straight, "t6-straight-fixture", "T6 Straight Line Fixture")
    c_plane = await ensure_concept(plane, "t6-plane-fixture", "T6 Plane Fixture")
    await db_session.commit()
    return {
        "subject_id": str(subject.id),
        "chapter_id": str(chapter.id),
        "topic_straight_id": str(straight.id),
        "topic_plane_id": str(plane.id),
        "concept_straight_id": str(c_straight.id),
        "concept_plane_id": str(c_plane.id),
    }


async def test_practice_unauthenticated_rejected(client):
    resp = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "FULL", "question_count": 5},
        headers=csrf_headers(client),
    )
    assert resp.status_code in (401, 403)


async def test_practice_full_scope_authenticated(client, register_user):
    await register_user(client)
    resp = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "FULL", "question_count": 5},
        headers=csrf_headers(client),
    )
    # Thin inventory may yield 422; auth path must not be 401.
    assert resp.status_code in (201, 422), resp.text
    if resp.status_code == 422:
        assert resp.json()["errors"][0]["code"] == "NO_QUESTIONS_AVAILABLE"


async def test_practice_topic_empty_pool_explicit(client, db_session, register_user):
    await register_user(client)
    tree = await _kinematics_two_topic_trees(db_session)
    resp = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "TOPIC", "scope_id": tree["topic_straight_id"], "question_count": 10},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["code"] == "NO_QUESTIONS_AVAILABLE"


async def test_practice_topic_rejects_missing_scope_id(client, register_user):
    await register_user(client)
    resp = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "TOPIC", "question_count": 5},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "MISSING_SCOPE_ID"


async def test_practice_invalid_scope_type(client, register_user):
    await register_user(client)
    resp = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "MICROCOMPETENCY", "scope_id": str(uuid.uuid4())},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "INVALID_SCOPE"


async def test_practice_topic_nonexistent_id_empty_or_valid_error(client, register_user):
    """Unknown topic UUID → empty published set → NO_QUESTIONS_AVAILABLE (no silent chapter broaden)."""
    await register_user(client)
    fake = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "TOPIC", "scope_id": fake, "question_count": 5},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["code"] == "NO_QUESTIONS_AVAILABLE"


async def test_kinematics_topic_scopes_do_not_cross_leak(client, db_session, register_user):
    await _as_content_manager(client, db_session, register_user)
    tree = await _kinematics_two_topic_trees(db_session)

    q_straight = await _publish_question(client, tree["concept_straight_id"], f"Straight {uuid.uuid4().hex[:6]}")
    q_plane = await _publish_question(client, tree["concept_plane_id"], f"Plane {uuid.uuid4().hex[:6]}")

    # TOPIC Motion in a Straight Line
    straight_prac = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "TOPIC", "scope_id": tree["topic_straight_id"], "question_count": 90},
        headers=csrf_headers(client),
    )
    assert straight_prac.status_code == 201, straight_prac.text
    attempt = await client.post(
        f"/api/v1/assessments/{straight_prac.json()['data']['id']}/attempts",
        headers=csrf_headers(client),
    )
    detail = await client.get(f"/api/v1/attempts/{attempt.json()['data']['id']}")
    ids = {q["content_item_id"] for q in detail.json()["data"]["questions"]}
    assert q_straight in ids
    assert q_plane not in ids

    # TOPIC Motion in a Plane
    plane_prac = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "TOPIC", "scope_id": tree["topic_plane_id"], "question_count": 90},
        headers=csrf_headers(client),
    )
    assert plane_prac.status_code == 201, plane_prac.text
    attempt2 = await client.post(
        f"/api/v1/assessments/{plane_prac.json()['data']['id']}/attempts",
        headers=csrf_headers(client),
    )
    detail2 = await client.get(f"/api/v1/attempts/{attempt2.json()['data']['id']}")
    ids2 = {q["content_item_id"] for q in detail2.json()["data"]["questions"]}
    assert q_plane in ids2
    assert q_straight not in ids2

    # CHAPTER Kinematics may include both
    chap_prac = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CHAPTER", "scope_id": tree["chapter_id"], "question_count": 90},
        headers=csrf_headers(client),
    )
    assert chap_prac.status_code == 201, chap_prac.text
    attempt3 = await client.post(
        f"/api/v1/assessments/{chap_prac.json()['data']['id']}/attempts",
        headers=csrf_headers(client),
    )
    detail3 = await client.get(f"/api/v1/attempts/{attempt3.json()['data']['id']}")
    ids3 = {q["content_item_id"] for q in detail3.json()["data"]["questions"]}
    assert q_straight in ids3
    assert q_plane in ids3

    # CONCEPT scopes still work
    concept_prac = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CONCEPT", "scope_id": tree["concept_straight_id"], "question_count": 90},
        headers=csrf_headers(client),
    )
    assert concept_prac.status_code == 201, concept_prac.text

    # SUBJECT Physics includes both when published under Physics
    subj_prac = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "SUBJECT", "scope_id": tree["subject_id"], "question_count": 90},
        headers=csrf_headers(client),
    )
    assert subj_prac.status_code == 201, subj_prac.text
    attempt4 = await client.post(
        f"/api/v1/assessments/{subj_prac.json()['data']['id']}/attempts",
        headers=csrf_headers(client),
    )
    detail4 = await client.get(f"/api/v1/attempts/{attempt4.json()['data']['id']}")
    ids4 = {q["content_item_id"] for q in detail4.json()["data"]["questions"]}
    assert q_straight in ids4
    assert q_plane in ids4
