"""Phase 3.3 — Zoology IN_REVIEW campaign preparation (read-only safety).

Uses isolated test fixtures only. Does not mutate the live content inventory.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

asyncio_mark = pytest.mark.asyncio(loop_scope="session")


async def _concept_with_class(db_session, *, subject_name: str = "Zoology"):
    from app.modules.academic.models import Chapter, Concept, Subject, Topic

    subj = (
        await db_session.execute(select(Subject).where(Subject.name == subject_name, Subject.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if not subj:
        subj = Subject(name=subject_name, code=f"ZOO-TEST-{uuid.uuid4().hex[:6]}", display_order=99)
        db_session.add(subj)
        await db_session.flush()
    ch = (
        await db_session.execute(
            select(Chapter).where(Chapter.subject_id == subj.id, Chapter.deleted_at.is_(None)).limit(1)
        )
    ).scalar_one_or_none()
    if not ch:
        ch = Chapter(subject_id=subj.id, name="Animal Kingdom", code=f"ak-{uuid.uuid4().hex[:6]}", display_order=1)
        db_session.add(ch)
        await db_session.flush()
    if getattr(ch, "class_level", None) != "11":
        ch.class_level = "11"
        await db_session.flush()
    topic = (
        await db_session.execute(select(Topic).where(Topic.chapter_id == ch.id, Topic.deleted_at.is_(None)).limit(1))
    ).scalar_one_or_none()
    if not topic:
        topic = Topic(
            chapter_id=ch.id,
            name="Basis of Classification",
            code=f"boc-{uuid.uuid4().hex[:6]}",
            display_order=1,
        )
        db_session.add(topic)
        await db_session.flush()
    concept = (
        await db_session.execute(
            select(Concept).where(Concept.topic_id == topic.id, Concept.deleted_at.is_(None)).limit(1)
        )
    ).scalar_one_or_none()
    if not concept:
        concept = Concept(
            topic_id=topic.id,
            name="Levels of Organisation",
            code=f"loo-{uuid.uuid4().hex[:6]}",
            display_order=1,
        )
        db_session.add(concept)
        await db_session.flush()
    await db_session.commit()
    return str(concept.id)


async def _create_question(client, concept_id: str, **body_overrides) -> dict:
    resp = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": f"P33Z Q {uuid.uuid4().hex[:6]}",
            "slug": f"p33z-q-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": publishable_question_body(**body_overrides),
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


@asyncio_mark
async def test_zoology_in_review_queue_scope_and_authoritative_total(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_with_class(db_session)
    item = await _create_question(client, concept_id, stem=f"Campaign prep unique stem {uuid.uuid4().hex}")
    submitted = await client.post(
        f"/api/v1/cms/content-items/{item['id']}/submit",
        headers=csrf_headers(client),
    )
    assert submitted.status_code == 200, submitted.text

    page1 = await client.get(
        "/api/v1/cms/editorial-review-queue?subject_name=Zoology&status=IN_REVIEW&limit=5&offset=0"
    )
    assert page1.status_code == 200, page1.text
    body1 = page1.json()
    total = body1["meta"]["total"]
    assert isinstance(total, int) and total >= 1
    assert body1["meta"].get("subject_name") == "Zoology"
    assert body1["meta"].get("no_auto_publish") is True
    for row in body1["data"]:
        subj = ((row.get("academic") or {}).get("subject") or {}).get("name")
        if subj:
            assert subj == "Zoology"
        assert row.get("status") == "IN_REVIEW"

    page2 = await client.get(
        "/api/v1/cms/editorial-review-queue?subject_name=Zoology&status=IN_REVIEW&limit=20&offset=0"
    )
    assert page2.status_code == 200
    assert page2.json()["meta"]["total"] == total


@asyncio_mark
async def test_review_packet_exposes_class_level_and_remains_read_only(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_with_class(db_session)
    item = await _create_question(client, concept_id, stem=f"Class level packet stem {uuid.uuid4().hex}")
    submitted = await client.post(
        f"/api/v1/cms/content-items/{item['id']}/submit",
        headers=csrf_headers(client),
    )
    assert submitted.status_code == 200, submitted.text
    item_id = submitted.json()["data"]["id"]

    before = (
        await db_session.execute(
            text("SELECT status, version FROM cms.content_items WHERE id = CAST(:id AS uuid)"),
            {"id": item_id},
        )
    ).one()

    packet = await client.get(f"/api/v1/cms/content-items/{item_id}/review-packet")
    assert packet.status_code == 200, packet.text
    data = packet.json()["data"]
    assert data["status"] == "IN_REVIEW"
    academic = data.get("academic") or {}
    assert academic.get("class_level") == "11"
    assert (academic.get("chapter") or {}).get("class_level") == "11"
    assert data.get("question", {}).get("stem")
    assert "ncert" in data
    assert "provenance" in data["ncert"]["disclaimer"].lower() or "ncert" in data["ncert"]["disclaimer"].lower()
    assert data["publication_eligibility"]["eligible_now"] is False
    assert "checklist" in data
    assert isinstance(data.get("suspected_duplicates"), list)

    after = (
        await db_session.execute(
            text("SELECT status, version FROM cms.content_items WHERE id = CAST(:id AS uuid)"),
            {"id": item_id},
        )
    ).one()
    assert after.status == before.status == "IN_REVIEW"
    assert after.version == before.version


@asyncio_mark
async def test_student_denied_zoology_campaign_endpoints(client, db_session, register_user):
    await register_user(client)  # student
    q = await client.get("/api/v1/cms/editorial-review-queue?subject_name=Zoology&status=IN_REVIEW")
    assert q.status_code in (401, 403)
    p = await client.get(f"/api/v1/cms/content-items/{uuid.uuid4()}/review-packet")
    assert p.status_code in (401, 403, 404)


@asyncio_mark
async def test_draft_status_excluded_from_in_review_zoology_queue(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_with_class(db_session)
    draft = await _create_question(client, concept_id, stem=f"Draft exclude stem {uuid.uuid4().hex}")
    assert draft["status"] == "DRAFT"

    resp = await client.get(
        "/api/v1/cms/editorial-review-queue?subject_name=Zoology&status=IN_REVIEW&limit=100&offset=0"
    )
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.json()["data"]]
    assert draft["id"] not in ids
    for row in resp.json()["data"]:
        assert row["status"] == "IN_REVIEW"
