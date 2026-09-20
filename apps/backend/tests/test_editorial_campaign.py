"""WAVE-P0-7: editorial campaign control — targets, coverage, explainable priority."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.modules.cms.services.editorial_review_service import (
    CAMPAIGN_AREAS,
    CAMPAIGN_TARGET_PER_AREA,
    campaign_area_for_subject,
)
from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _four_options(**overrides):
    return publishable_question_body(**overrides)



async def _concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def test_campaign_area_mapping():
    assert campaign_area_for_subject("Physics") == "Physics"
    assert campaign_area_for_subject("Chemistry") == "Chemistry"
    assert campaign_area_for_subject("Botany") == "Biology"
    assert campaign_area_for_subject("Zoology") == "Biology"
    assert campaign_area_for_subject(None) is None
    assert CAMPAIGN_TARGET_PER_AREA == 25
    assert CAMPAIGN_AREAS["Biology"] == ("Botany", "Zoology")


async def test_editorial_campaign_requires_review_permission(client, db_session, register_user):
    await register_user(client)  # student
    resp = await client.get("/api/v1/cms/editorial-campaign")
    assert resp.status_code in (401, 403), resp.text


async def test_editorial_campaign_dashboard_shape(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get("/api/v1/cms/editorial-campaign")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    areas = {t["area"] for t in data["targets"]}
    assert areas == {"Physics", "Chemistry", "Biology"}
    for t in data["targets"]:
        assert t["target"] == 25
        assert t["published"] >= 0
        assert t["remaining"] == max(0, 25 - t["published"])
        assert 0 <= t["progress_ratio"] <= 1
        assert "pipeline" in t

    sc = data["status_counts"]
    for key in (
        "draft",
        "in_review",
        "approved",
        "published",
        "changes_requested",
        "missing_provenance",
        "missing_mapping",
        "structurally_invalid",
    ):
        assert key in sc
        assert sc[key] >= 0

    assert "chapter_coverage" in data
    assert isinstance(data["chapter_coverage"], list)
    assert "scientific" in data["quality_metrics"]["disclaimer"].lower()
    assert data["rules"]["no_auto_publish"] is True
    assert data["rules"]["human_review_mandatory"] is True
    assert data["rules"]["planning_target_only"] is True


async def test_queue_exposes_priority_reasons(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": f"Priority reason Q {uuid.uuid4().hex[:6]}",
            "slug": f"prio-q-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": _four_options(),
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]
    submit = await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text

    queue = await client.get("/api/v1/cms/editorial-review-queue?status=IN_REVIEW")
    assert queue.status_code == 200, queue.text
    body = queue.json()
    assert "prioritization" in body["meta"]
    assert body["meta"].get("recommended_next") is not None
    match = next((r for r in body["data"] if r["id"] == item_id), None)
    assert match is not None
    assert match["priority_reasons"]
    assert any("tructur" in r or "mapping" in r.lower() or "target" in r.lower() or "Chapter" in r for r in match["priority_reasons"])


async def test_teacher_cannot_publish_still(client, db_session, register_user):
    await register_user(client, role_codes=["TEACHER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": f"Teacher publish deny {uuid.uuid4().hex[:6]}",
            "slug": f"teach-deny-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": _four_options(),
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201
    item_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    # Teacher cannot reach approve; campaign endpoint also denied
    campaign = await client.get("/api/v1/cms/editorial-campaign")
    assert campaign.status_code in (401, 403)
    publish = await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    assert publish.status_code in (401, 403) or publish.status_code >= 400


async def test_student_published_boundary_unchanged(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": f"Unpublished boundary {uuid.uuid4().hex[:6]}",
            "slug": f"bound-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": _four_options(),
        },
        headers=csrf_headers(client),
    )
    item_id = create.json()["data"]["id"]
    published = await client.get(f"/api/v1/cms/concepts/{concept_id}/published")
    assert published.status_code == 200
    assert item_id not in [i["id"] for i in published.json()["data"]]
