"""Phase 3.3 — controlled ECAEP / publication safety / student isolation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.modules.cms.services.draft_disposition import intake_code_for_draft, ncert_state_from_evidence
from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

asyncio_mark = pytest.mark.asyncio(loop_scope="session")


async def _concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _create_question(client, concept_id: str, **body_overrides) -> dict:
    resp = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": f"P33 Q {uuid.uuid4().hex[:6]}",
            "slug": f"p33-q-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": publishable_question_body(**body_overrides),
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def test_intake_and_ncert_helpers_do_not_imply_publish():
    assert (
        intake_code_for_draft(
            status="DRAFT",
            concept_id=uuid.uuid4(),
            structural_valid=True,
            has_provenance_lineage=True,
            suspected_duplicate=False,
            has_stem=True,
        )
        == "READY_FOR_REVIEW"
    )
    assert (
        intake_code_for_draft(
            status="DRAFT",
            concept_id=None,
            structural_valid=True,
            has_provenance_lineage=True,
            suspected_duplicate=False,
            has_stem=True,
        )
        == "NEEDS_MAPPING"
    )
    ncert = ncert_state_from_evidence(tags=[], body={"provenance": {"origin": "import"}})
    assert ncert["is_verified"] is False
    assert "provenance" in ncert["disclaimer"].lower()


@asyncio_mark
async def test_draft_cannot_publish_invalid_transition(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)
    assert item["status"] == "DRAFT"
    pub = await client.post(f"/api/v1/cms/content-items/{item['id']}/publish", headers=csrf_headers(client))
    assert pub.status_code >= 400
    refreshed = await client.get(f"/api/v1/cms/content-items/{item['id']}")
    assert refreshed.json()["data"]["status"] == "DRAFT"


@asyncio_mark
async def test_in_review_cannot_publish_without_approval(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)
    submit = await client.post(f"/api/v1/cms/content-items/{item['id']}/submit", headers=csrf_headers(client))
    assert submit.json()["data"]["status"] == "IN_REVIEW"
    pub = await client.post(f"/api/v1/cms/content-items/{item['id']}/publish", headers=csrf_headers(client))
    assert pub.status_code >= 400
    assert (await client.get(f"/api/v1/cms/content-items/{item['id']}")).json()["data"]["status"] == "IN_REVIEW"


@asyncio_mark
async def test_approval_remains_distinct_from_publish(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)
    await client.post(f"/api/v1/cms/content-items/{item['id']}/submit", headers=csrf_headers(client))
    review = await client.post(
        f"/api/v1/cms/content-items/{item['id']}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    assert review.status_code == 200
    assert review.json()["data"]["status"] == "APPROVED"


@asyncio_mark
async def test_bulk_publish_rejects_draft(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)
    bulk = await client.post(
        "/api/v1/cms/content-items/bulk",
        json={"action": "publish", "item_ids": [item["id"]]},
        headers=csrf_headers(client),
    )
    assert bulk.status_code == 200, bulk.text
    outcomes = bulk.json()["data"]
    assert len(outcomes) == 1
    assert outcomes[0]["success"] is False
    assert (await client.get(f"/api/v1/cms/content-items/{item['id']}")).json()["data"]["status"] == "DRAFT"


@asyncio_mark
async def test_review_packet_exposes_ncert_and_publication_eligibility(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)
    await client.post(f"/api/v1/cms/content-items/{item['id']}/submit", headers=csrf_headers(client))
    packet = await client.get(f"/api/v1/cms/content-items/{item['id']}/review-packet")
    assert packet.status_code == 200, packet.text
    data = packet.json()["data"]
    assert "ncert" in data
    assert data["ncert"]["disclaimer"]
    assert data["publication_eligibility"]["approval_is_not_publication"] is True
    assert data["publication_eligibility"]["eligible_now"] is False
    assert "approve" in data["allowed_decisions"]
    assert "publish" not in data["allowed_decisions"]  # still IN_REVIEW


@asyncio_mark
async def test_content_intake_chemistry_readonly(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get("/api/v1/cms/content-intake?subject_name=Chemistry&status=DRAFT&limit=10")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["subject"] == "Chemistry"
    assert data["rules"]["no_auto_publish"] is True
    assert data["rules"]["unmapped_backlog_excluded"] is True
    assert "intake_counts" in data
    assert isinstance(data["items"], list)


@asyncio_mark
async def test_zoology_queue_subject_name_filter(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get(
        "/api/v1/cms/editorial-review-queue?status=IN_REVIEW&subject_name=Zoology&limit=20&offset=0"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["no_auto_publish"] is True
    assert body["meta"].get("subject_name") == "Zoology"
    for row in body["data"]:
        subj = (row.get("academic") or {}).get("subject") or {}
        if subj.get("name"):
            assert subj["name"] == "Zoology"
        assert "ncert" in row
        assert "blocking_reasons" in row


@asyncio_mark
async def test_student_questions_exclude_draft(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    draft = await _create_question(client, concept_id)
    # Switch to student session for browse
    await register_user(client)  # student
    listing = await client.get("/api/v1/cms/questions?limit=50")
    assert listing.status_code == 200
    ids = [i["id"] for i in listing.json()["data"]]
    assert draft["id"] not in ids


@asyncio_mark
async def test_unauthorized_bulk_publish_rejected(client, db_session, register_user):
    await register_user(client)  # student
    resp = await client.post(
        "/api/v1/cms/content-items/bulk",
        json={"action": "publish", "item_ids": [str(uuid.uuid4())]},
        headers=csrf_headers(client),
    )
    assert resp.status_code in (401, 403)
