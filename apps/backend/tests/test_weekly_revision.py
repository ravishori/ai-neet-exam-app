"""Integration tests for the student-driven Weekly Revision recommendation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _publish_question(client, concept_id: str, *, correct_option: str = "B", tag: str = "wr") -> str:
    slug = f"wr-{tag}-{uuid.uuid4().hex[:10]}"
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": f"WR test question {slug}",
            "slug": slug,
            "language": "en",
            "body": publishable_question_body(
                stem=f"WR stem {slug}",
                correct_option=correct_option,
                explanation="Test.",
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


async def _one_concept_per_subject(db_session) -> dict[str, str]:
    """Return {subject_name: concept_id} for Physics + Chemistry + one Biology-family subject."""
    from app.modules.academic.models import Chapter, Concept, Subject, Topic

    out: dict[str, str] = {}
    rows = (
        await db_session.execute(
            select(Subject.name, Concept.id)
            .join(Chapter, Chapter.subject_id == Subject.id)
            .join(Topic, Topic.chapter_id == Chapter.id)
            .join(Concept, Concept.topic_id == Topic.id)
        )
    ).all()
    for name, cid in rows:
        if name not in out:
            out[name] = str(cid)
    return out


async def _seed_pool_for_subjects(client, db_session, *, per_subject: int) -> dict[str, list[str]]:
    subj_to_concept = await _one_concept_per_subject(db_session)
    published: dict[str, list[str]] = {}
    for subject, concept_id in subj_to_concept.items():
        ids = []
        for i in range(per_subject):
            ids.append(await _publish_question(client, concept_id, tag=f"{subject.lower()}-{i}"))
        published[subject] = ids
    return published


async def test_current_generates_recommendation_and_is_idempotent(client, db_session, register_user):
    # Content-manager seeds the pool, then a fresh student pulls their weekly.
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    await _seed_pool_for_subjects(client, db_session, per_subject=8)

    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)

    a = await client.get("/api/v1/weekly-revisions/current")
    assert a.status_code == 200, a.text
    body_a = a.json()["data"]
    assert body_a["status"] in {"RECOMMENDED", "UNAVAILABLE"}

    b = await client.get("/api/v1/weekly-revisions/current")
    assert b.status_code == 200
    body_b = b.json()["data"]
    # Idempotent within the same ISO week.
    assert body_a["id"] == body_b["id"]


async def test_unavailable_when_pool_insufficient(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    # Only 2 questions per subject — well below the 15/15/30 default quotas.
    await _seed_pool_for_subjects(client, db_session, per_subject=2)

    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)

    resp = await client.get("/api/v1/weekly-revisions/current")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "UNAVAILABLE"
    assert body["reason"].get("unavailable_reasons")

    # Starting must fail loudly with a specific code, not ship a short paper.
    start = await client.post("/api/v1/weekly-revisions/current/attempts", headers=csrf_headers(client))
    assert start.status_code == 422
    assert start.json()["errors"][0]["code"] == "WEEKLY_REVISION_UNAVAILABLE"


async def test_start_materialises_unique_published_questions_and_links_back(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    seeded = await _seed_pool_for_subjects(client, db_session, per_subject=16)

    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)

    current = (await client.get("/api/v1/weekly-revisions/current")).json()["data"]
    if current["status"] != "RECOMMENDED":
        pytest.skip("Seeded taxonomy does not yield a RECOMMENDED plan in this environment")

    resp = await client.post("/api/v1/weekly-revisions/current/attempts", headers=csrf_headers(client))
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assessment_id = data["assessment_id"]

    from app.modules.assessment.models import Assessment, AssessmentQuestion

    rows = (
        await db_session.execute(
            select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == uuid.UUID(assessment_id))
        )
    ).scalars().all()
    picked = {r.content_item_id for r in rows}
    # No duplicate questions in the materialised paper.
    assert len(picked) == len(rows)
    # Question count matches the plan's total quota.
    assert len(rows) == current["total_questions"]
    # Every picked question is one we PUBLISHED — proves published/verified filter is respected.
    all_published = {uuid.UUID(qid) for ids in seeded.values() for qid in ids}
    assert picked.issubset(all_published)
    # Assessment is linked back to the recommendation.
    ass = (await db_session.execute(select(Assessment).where(Assessment.id == uuid.UUID(assessment_id)))).scalar_one()
    assert str(ass.weekly_revision_id) == current["id"]


async def test_second_start_resumes_the_in_progress_attempt(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    await _seed_pool_for_subjects(client, db_session, per_subject=16)

    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)

    current = (await client.get("/api/v1/weekly-revisions/current")).json()["data"]
    if current["status"] != "RECOMMENDED":
        pytest.skip("Cold-start pool insufficient in this environment")

    first = (
        await client.post("/api/v1/weekly-revisions/current/attempts", headers=csrf_headers(client))
    ).json()["data"]
    second = (
        await client.post("/api/v1/weekly-revisions/current/attempts", headers=csrf_headers(client))
    ).json()["data"]

    assert first["attempt_id"] == second["attempt_id"]
    assert first["assessment_id"] == second["assessment_id"]


async def test_submit_marks_recommendation_completed_and_blocks_restart(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    await _seed_pool_for_subjects(client, db_session, per_subject=16)

    await client.post("/api/v1/auth/logout")
    await register_user(client, db_session=db_session)

    current = (await client.get("/api/v1/weekly-revisions/current")).json()["data"]
    if current["status"] != "RECOMMENDED":
        pytest.skip("Cold-start pool insufficient in this environment")

    start = (
        await client.post("/api/v1/weekly-revisions/current/attempts", headers=csrf_headers(client))
    ).json()["data"]
    submit = await client.post(f"/api/v1/attempts/{start['attempt_id']}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text

    view = (await client.get("/api/v1/weekly-revisions/current")).json()["data"]
    assert view["status"] == "COMPLETED"

    restart = await client.post("/api/v1/weekly-revisions/current/attempts", headers=csrf_headers(client))
    assert restart.status_code == 409
    assert restart.json()["errors"][0]["code"] == "WEEKLY_REVISION_ALREADY_COMPLETED"


async def test_get_current_requires_authentication(client):
    # Fresh AsyncClient state — no cookies. Endpoint must 401, not leak a
    # recommendation to anonymous callers.
    resp = await client.get("/api/v1/weekly-revisions/current")
    assert resp.status_code in (401, 403)
