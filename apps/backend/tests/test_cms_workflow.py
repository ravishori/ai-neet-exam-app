"""Integration tests: ECAEP content workflow state machine (ADR-0009 / ADR-0020)."""

import pytest
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _content_author(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)


async def _create_draft(client, concept_id: str) -> dict:
    resp = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "CONCEPT_NOTE",
            "concept_id": concept_id,
            "title": "Workflow test note",
            "slug": f"workflow-test-note-{concept_id[:8]}",
            "language": "en",
            "body": {"summary": "A test concept note.", "sections": []},
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_full_workflow_draft_to_published(client, db_session, register_user):
    await _content_author(client, db_session, register_user)
    concept_id = await _any_concept_id(db_session)
    item = await _create_draft(client, concept_id)
    assert item["status"] == "DRAFT"

    submit = await client.post(f"/api/v1/cms/content-items/{item['id']}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text
    assert submit.json()["data"]["status"] == "IN_REVIEW"

    review = await client.post(
        f"/api/v1/cms/content-items/{item['id']}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    assert review.status_code == 200, review.text
    assert review.json()["data"]["status"] == "APPROVED"

    publish = await client.post(f"/api/v1/cms/content-items/{item['id']}/publish", headers=csrf_headers(client))
    assert publish.status_code == 200, publish.text
    assert publish.json()["data"]["status"] == "PUBLISHED"

    archive = await client.post(f"/api/v1/cms/content-items/{item['id']}/archive", headers=csrf_headers(client))
    assert archive.status_code == 200, archive.text
    assert archive.json()["data"]["status"] == "ARCHIVED"


async def test_cannot_publish_a_draft_directly(client, db_session, register_user):
    await _content_author(client, db_session, register_user)
    concept_id = await _any_concept_id(db_session)
    item = await _create_draft(client, concept_id)

    resp = await client.post(f"/api/v1/cms/content-items/{item['id']}/publish", headers=csrf_headers(client))
    assert resp.status_code >= 400


async def test_cannot_submit_an_already_published_item(client, db_session, register_user):
    await _content_author(client, db_session, register_user)
    concept_id = await _any_concept_id(db_session)
    item = await _create_draft(client, concept_id)

    await client.post(f"/api/v1/cms/content-items/{item['id']}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{item['id']}/review", json={"decision": "approve"}, headers=csrf_headers(client)
    )
    await client.post(f"/api/v1/cms/content-items/{item['id']}/publish", headers=csrf_headers(client))

    resp = await client.post(f"/api/v1/cms/content-items/{item['id']}/submit", headers=csrf_headers(client))
    assert resp.status_code >= 400


async def test_changes_requested_sends_it_back_to_draft_editable_state(client, db_session, register_user):
    await _content_author(client, db_session, register_user)
    concept_id = await _any_concept_id(db_session)
    item = await _create_draft(client, concept_id)

    await client.post(f"/api/v1/cms/content-items/{item['id']}/submit", headers=csrf_headers(client))
    review = await client.post(
        f"/api/v1/cms/content-items/{item['id']}/review",
        json={"decision": "request_changes", "comment": "Needs more detail"},
        headers=csrf_headers(client),
    )
    assert review.status_code == 200, review.text
    assert review.json()["data"]["status"] == "CHANGES_REQUESTED"

    update = await client.patch(
        f"/api/v1/cms/content-items/{item['id']}",
        json={"body": {"summary": "Updated with more detail.", "sections": []}},
        headers=csrf_headers(client),
    )
    assert update.status_code == 200, update.text


async def test_published_content_not_visible_before_publish(client, db_session, register_user):
    await _content_author(client, db_session, register_user)
    concept_id = await _any_concept_id(db_session)
    item = await _create_draft(client, concept_id)

    resp = await client.get(f"/api/v1/cms/concepts/{concept_id}/published")
    assert resp.status_code == 200
    assert item["id"] not in [i["id"] for i in resp.json()["data"]]
