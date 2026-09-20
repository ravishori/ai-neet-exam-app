"""Integration tests for the Weekly Assessment feature."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _publish_question(client, concept_id: str, *, correct_option: str = "B", tag: str = "wa") -> str:
    slug = f"wa-{tag}-{uuid.uuid4().hex[:10]}"
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": f"WA test question {slug}",
            "slug": slug,
            "language": "en",
            "body": publishable_question_body(
                stem=f"WA question {slug}",
                correct_option=correct_option,
                explanation="Test question.",
                options=[
                    {"label": "A", "text": "3"},
                    {"label": "B", "text": "4"},
                    {"label": "C", "text": "5"},
                    {"label": "D", "text": "22"},
                ],
            ),
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{item_id}/review", json={"decision": "approve"}, headers=csrf_headers(client)
    )
    await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    return item_id


async def _first_subject_id_and_concept_id(db_session) -> tuple[str, str]:
    from app.modules.academic.models import Chapter, Concept, Subject, Topic

    row = (
        await db_session.execute(
            select(Subject.id, Concept.id)
            .join(Chapter, Chapter.subject_id == Subject.id)
            .join(Topic, Topic.chapter_id == Chapter.id)
            .join(Concept, Concept.topic_id == Topic.id)
            .limit(1)
        )
    ).first()
    assert row is not None, "no seeded Subject/Concept row present"
    return str(row[0]), str(row[1])


async def _seed_subject_pool(client, db_session, *, count: int) -> tuple[str, list[str]]:
    subject_id, concept_id = await _first_subject_id_and_concept_id(db_session)
    ids = []
    for i in range(count):
        ids.append(await _publish_question(client, concept_id, correct_option="B", tag=f"pool{i}"))
    return subject_id, ids


def _future_window() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return now + timedelta(days=1), now + timedelta(days=2)


def _open_window() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return now - timedelta(minutes=5), now + timedelta(hours=2)


async def _make_admin(client, db_session, register_user):
    return await register_user(client, role_codes=["ADMIN", "CONTENT_MANAGER"], db_session=db_session)


async def test_admin_can_create_weekly_and_student_sees_it_when_published(client, db_session, register_user):
    await _make_admin(client, db_session, register_user)
    subject_id, _ = await _seed_subject_pool(client, db_session, count=3)

    starts, ends = _open_window()
    create = await client.post(
        "/api/v1/weekly-assessments",
        json={
            "assessment_key": f"wa-{uuid.uuid4().hex[:8]}",
            "title": "Weekly Assessment #1",
            "description": "Test weekly",
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "duration_minutes": 90,
            "marks_per_question": 4,
            "negative_marks_per_question": 1,
            "attempt_limit": 1,
            "blueprint": [{"subject_id": subject_id, "question_count": 3}],
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    weekly_id = create.json()["data"]["id"]
    assert create.json()["data"]["published"] is False

    publish = await client.post(
        f"/api/v1/weekly-assessments/{weekly_id}/publish", headers=csrf_headers(client)
    )
    assert publish.status_code == 200, publish.text
    assert publish.json()["data"]["published"] is True

    # Student flow: log out admin, register student, list.
    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)
    listed = await client.get("/api/v1/weekly-assessments")
    assert listed.status_code == 200
    items = listed.json()["data"]
    assert any(w["id"] == weekly_id for w in items)


async def test_publish_fails_when_pool_insufficient(client, db_session, register_user):
    await _make_admin(client, db_session, register_user)
    subject_id, _ = await _seed_subject_pool(client, db_session, count=2)

    starts, ends = _future_window()
    create = await client.post(
        "/api/v1/weekly-assessments",
        json={
            "assessment_key": f"wa-{uuid.uuid4().hex[:8]}",
            "title": "Weekly Assessment insufficient",
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "duration_minutes": 60,
            "attempt_limit": 1,
            "blueprint": [{"subject_id": subject_id, "question_count": 20}],
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    weekly_id = create.json()["data"]["id"]

    publish = await client.post(
        f"/api/v1/weekly-assessments/{weekly_id}/publish", headers=csrf_headers(client)
    )
    assert publish.status_code == 422
    assert publish.json()["errors"][0]["code"] == "WEEKLY_POOL_INSUFFICIENT"


async def test_student_start_attempt_selects_only_published_questions_no_duplicates(client, db_session, register_user):
    await _make_admin(client, db_session, register_user)
    subject_id, published_ids = await _seed_subject_pool(client, db_session, count=5)

    starts, ends = _open_window()
    create = await client.post(
        "/api/v1/weekly-assessments",
        json={
            "assessment_key": f"wa-{uuid.uuid4().hex[:8]}",
            "title": "Weekly Assessment attempt",
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "duration_minutes": 60,
            "attempt_limit": 1,
            "blueprint": [{"subject_id": subject_id, "question_count": 4}],
        },
        headers=csrf_headers(client),
    )
    weekly_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/weekly-assessments/{weekly_id}/publish", headers=csrf_headers(client))

    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)

    start = await client.post(
        f"/api/v1/weekly-assessments/{weekly_id}/attempts", headers=csrf_headers(client)
    )
    assert start.status_code == 201, start.text
    data = start.json()["data"]
    assessment_id = data["assessment_id"]

    from app.modules.assessment.models import Assessment, AssessmentQuestion

    q_rows = (
        await db_session.execute(
            select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == uuid.UUID(assessment_id))
        )
    ).scalars().all()
    assert len(q_rows) == 4
    picked_ids = {r.content_item_id for r in q_rows}
    assert len(picked_ids) == 4  # no duplicates
    assert picked_ids.issubset({uuid.UUID(x) for x in published_ids})

    ass = (
        await db_session.execute(select(Assessment).where(Assessment.id == uuid.UUID(assessment_id)))
    ).scalar_one()
    assert str(ass.weekly_assessment_id) == weekly_id


async def test_start_before_window_is_blocked(client, db_session, register_user):
    await _make_admin(client, db_session, register_user)
    subject_id, _ = await _seed_subject_pool(client, db_session, count=3)

    starts, ends = _future_window()
    create = await client.post(
        "/api/v1/weekly-assessments",
        json={
            "assessment_key": f"wa-{uuid.uuid4().hex[:8]}",
            "title": "Weekly Assessment future",
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "duration_minutes": 60,
            "attempt_limit": 1,
            "blueprint": [{"subject_id": subject_id, "question_count": 2}],
        },
        headers=csrf_headers(client),
    )
    weekly_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/weekly-assessments/{weekly_id}/publish", headers=csrf_headers(client))

    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)
    resp = await client.post(
        f"/api/v1/weekly-assessments/{weekly_id}/attempts", headers=csrf_headers(client)
    )
    assert resp.status_code == 409
    assert resp.json()["errors"][0]["code"] == "WEEKLY_NOT_OPEN"


async def test_attempt_limit_enforced(client, db_session, register_user):
    await _make_admin(client, db_session, register_user)
    subject_id, _ = await _seed_subject_pool(client, db_session, count=3)

    starts, ends = _open_window()
    create = await client.post(
        "/api/v1/weekly-assessments",
        json={
            "assessment_key": f"wa-{uuid.uuid4().hex[:8]}",
            "title": "Weekly Assessment attempt-limit",
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "duration_minutes": 60,
            "attempt_limit": 1,
            "blueprint": [{"subject_id": subject_id, "question_count": 2}],
        },
        headers=csrf_headers(client),
    )
    weekly_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/weekly-assessments/{weekly_id}/publish", headers=csrf_headers(client))

    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)
    first = await client.post(
        f"/api/v1/weekly-assessments/{weekly_id}/attempts", headers=csrf_headers(client)
    )
    assert first.status_code == 201
    second = await client.post(
        f"/api/v1/weekly-assessments/{weekly_id}/attempts", headers=csrf_headers(client)
    )
    assert second.status_code == 409
    assert second.json()["errors"][0]["code"] == "WEEKLY_ATTEMPT_LIMIT_REACHED"


async def test_non_admin_cannot_create(client, db_session, register_user):
    # Register plain student (no ADMIN)
    await register_user(client, db_session=db_session)
    subject_id, _ = await _first_subject_id_and_concept_id(db_session)
    starts, ends = _open_window()
    resp = await client.post(
        "/api/v1/weekly-assessments",
        json={
            "assessment_key": f"wa-{uuid.uuid4().hex[:8]}",
            "title": "Should be forbidden",
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "duration_minutes": 60,
            "attempt_limit": 1,
            "blueprint": [{"subject_id": subject_id, "question_count": 1}],
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 403
    assert resp.json()["errors"][0]["code"] == "FORBIDDEN"


async def test_unpublished_weekly_not_visible_to_student(client, db_session, register_user):
    await _make_admin(client, db_session, register_user)
    subject_id, _ = await _seed_subject_pool(client, db_session, count=2)
    starts, ends = _open_window()
    create = await client.post(
        "/api/v1/weekly-assessments",
        json={
            "assessment_key": f"wa-{uuid.uuid4().hex[:8]}",
            "title": "Hidden weekly",
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "duration_minutes": 60,
            "attempt_limit": 1,
            "blueprint": [{"subject_id": subject_id, "question_count": 1}],
        },
        headers=csrf_headers(client),
    )
    hidden_id = create.json()["data"]["id"]

    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)
    listed = await client.get("/api/v1/weekly-assessments")
    assert listed.status_code == 200
    assert not any(w["id"] == hidden_id for w in listed.json()["data"])

    start = await client.post(
        f"/api/v1/weekly-assessments/{hidden_id}/attempts", headers=csrf_headers(client)
    )
    assert start.status_code == 409
    assert start.json()["errors"][0]["code"] == "WEEKLY_NOT_PUBLISHED"


async def test_duplicate_key_conflict(client, db_session, register_user):
    await _make_admin(client, db_session, register_user)
    subject_id, _ = await _seed_subject_pool(client, db_session, count=2)
    starts, ends = _open_window()
    key = f"wa-dup-{uuid.uuid4().hex[:8]}"
    payload = {
        "assessment_key": key,
        "title": "Dup",
        "starts_at": starts.isoformat(),
        "ends_at": ends.isoformat(),
        "duration_minutes": 60,
        "attempt_limit": 1,
        "blueprint": [{"subject_id": subject_id, "question_count": 1}],
    }
    a = await client.post("/api/v1/weekly-assessments", json=payload, headers=csrf_headers(client))
    assert a.status_code == 201
    b = await client.post("/api/v1/weekly-assessments", json=payload, headers=csrf_headers(client))
    assert b.status_code == 409
    assert b.json()["errors"][0]["code"] == "WEEKLY_KEY_TAKEN"


async def test_invalid_window_rejected(client, db_session, register_user):
    await _make_admin(client, db_session, register_user)
    subject_id, _ = await _first_subject_id_and_concept_id(db_session)
    now = datetime.now(UTC)
    payload = {
        "assessment_key": f"wa-{uuid.uuid4().hex[:8]}",
        "title": "Bad window",
        "starts_at": (now + timedelta(hours=2)).isoformat(),
        "ends_at": (now + timedelta(hours=1)).isoformat(),
        "duration_minutes": 60,
        "attempt_limit": 1,
        "blueprint": [{"subject_id": subject_id, "question_count": 1}],
    }
    resp = await client.post("/api/v1/weekly-assessments", json=payload, headers=csrf_headers(client))
    assert resp.status_code == 422
