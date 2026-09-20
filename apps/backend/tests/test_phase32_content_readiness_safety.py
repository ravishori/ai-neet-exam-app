"""Phase 3.2 — no-auto-publish + inventory/readiness safety gates."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.modules.cms.services.draft_disposition import (
    classify_draft_disposition,
    disposition_tag,
    readiness_label_for_question,
)
from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

asyncio_mark = pytest.mark.asyncio(loop_scope="session")


async def _concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _create_question(client, concept_id: str | None, **body_overrides) -> dict:
    payload = {
        "content_type": "QUESTION",
        "title": f"P32 Q {uuid.uuid4().hex[:6]}",
        "slug": f"p32-q-{uuid.uuid4().hex[:10]}",
        "language": "en",
        "body": publishable_question_body(**body_overrides),
    }
    if concept_id:
        payload["concept_id"] = concept_id
    resp = await client.post("/api/v1/cms/content-items", json=payload, headers=csrf_headers(client))
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def test_disposition_model_does_not_imply_publish():
    assert classify_draft_disposition(
        status="DRAFT",
        concept_id=None,
        structural_valid=True,
        has_provenance_lineage=True,
        suspected_duplicate=False,
        has_stem=True,
    ) == "UNMAPPED"
    assert classify_draft_disposition(
        status="DRAFT",
        concept_id=uuid.uuid4(),
        structural_valid=True,
        has_provenance_lineage=True,
        suspected_duplicate=False,
        has_stem=True,
    ) == "READY_FOR_ECAEP"
    assert disposition_tag("UNMAPPED") == "disposition:UNMAPPED"
    # APPROVED without NCERT is still not "published"
    assert readiness_label_for_question(
        status="APPROVED",
        concept_id=uuid.uuid4(),
        structural_valid=True,
        has_provenance_lineage=True,
        ncert_verified=False,
        suspected_duplicate=False,
    ) == "NEEDS NCERT VERIFICATION"


@asyncio_mark
async def test_approval_does_not_publish(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)
    submit = await client.post(f"/api/v1/cms/content-items/{item['id']}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200
    assert submit.json()["data"]["status"] == "IN_REVIEW"

    review = await client.post(
        f"/api/v1/cms/content-items/{item['id']}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    assert review.status_code == 200
    assert review.json()["data"]["status"] == "APPROVED"
    assert review.json()["data"]["status"] != "PUBLISHED"


@asyncio_mark
async def test_unauthorized_publish_rejected(client, db_session, register_user):
    await register_user(client)  # student
    resp = await client.post(
        f"/api/v1/cms/content-items/{uuid.uuid4()}/publish",
        headers=csrf_headers(client),
    )
    assert resp.status_code in (401, 403, 404)


@asyncio_mark
async def test_draft_and_unmapped_not_in_published_concept_listing(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    draft = await _create_question(client, concept_id)
    published_list = await client.get(f"/api/v1/cms/concepts/{concept_id}/published")
    assert published_list.status_code == 200
    ids = [i["id"] for i in published_list.json()["data"]]
    assert draft["id"] not in ids


@asyncio_mark
async def test_content_readiness_endpoint_shape(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get("/api/v1/cms/content-readiness")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["content_type"] == "QUESTION"
    assert data["quality_gates"]["never_mass_publish_drafts"] is True
    assert data["quality_gates"]["student_visible_status"] == "PUBLISHED"
    assert data["quality_gates"]["approval_is_not_publication"] is True
    assert data["campaign_notes"]["do_not_claim_content_ready"] is True
    assert data["ecaep_rules"]["no_auto_publish"] is True
    assert "status_counts" in data
    assert "by_subject_status" in data
    assert isinstance(data["published"], int)
    assert isinstance(data["unmapped_concept"], int)


@asyncio_mark
async def test_student_cannot_access_content_readiness(client, db_session, register_user):
    await register_user(client)
    resp = await client.get("/api/v1/cms/content-readiness")
    assert resp.status_code in (401, 403)


@asyncio_mark
async def test_ncert_certify_does_not_publish(client, db_session, register_user):
    """If certify endpoint is hit on non-approved / wrong state, must not become PUBLISHED."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)
    certify = await client.post(
        f"/api/v1/cms/content-items/{item['id']}/certify-ncert",
        json={"verification_method": "unit-test"},
        headers=csrf_headers(client),
    )
    if certify.status_code < 400:
        assert certify.json()["data"].get("status") != "PUBLISHED"
    refreshed = await client.get(f"/api/v1/cms/content-items/{item['id']}")
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["status"] == "DRAFT"
