"""RS-001-A2-B — durable publication-gate behavioural evidence.

Covers the ContentWorkflowService flow constraints that live outside
the QUESTION body publish gates: the pre-review academic-mapping check
(Case D), the full happy-path publish workflow including the
review-state gate that blocks a pre-approval publish (Case E), and
non-QUESTION content types that must not have QUESTION-specific
publish gates applied (Case F).

Tests MUST exercise the real committed publish path — no mocks, no
manual status writes.
"""

from __future__ import annotations

import uuid

import pytest

from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _concept_id(db_session) -> str:
    from sqlalchemy import select

    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _author(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)


async def test_cannot_publish_question_without_concept_mapping(client, db_session, register_user):
    """Case D — a QUESTION without a concept_id is blocked at
    submit_for_review with MISSING_ACADEMIC_MAPPING and never reaches a
    state where publish would be attempted."""
    await _author(client, db_session, register_user)
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "title": "Unmapped question",
            "slug": f"unmapped-q-{uuid.uuid4().hex[:8]}",
            "language": "en",
            "body": publishable_question_body(stem=f"Unmapped {uuid.uuid4().hex[:8]}"),
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]

    submit = await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 422
    assert submit.json()["errors"][0]["code"] == "MISSING_ACADEMIC_MAPPING"


async def test_question_workflow_publish_requires_approval_and_gates(client, db_session, register_user):
    """Case E — a QUESTION cannot publish before it is APPROVED
    (review_state gate); once the DRAFT → IN_REVIEW → APPROVED →
    PUBLISHED path completes, the row is visible in the student-facing
    published listing."""
    await _author(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "Mapped gated question",
            "slug": f"mapped-q-{uuid.uuid4().hex[:8]}",
            "language": "en",
            "body": publishable_question_body(stem=f"E2E gated {uuid.uuid4().hex[:8]}"),
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]

    # review_state gate — publish before approval is refused
    bad_publish = await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    assert bad_publish.status_code >= 400

    submit = await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text
    review = await client.post(
        f"/api/v1/cms/content-items/{item_id}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    assert review.status_code == 200, review.text
    publish = await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    assert publish.status_code == 200, publish.text
    assert publish.json()["data"]["status"] == "PUBLISHED"

    student_list = await client.get("/api/v1/cms/questions")
    assert student_list.status_code == 200
    ids = [q["id"] for q in student_list.json()["data"]]
    assert item_id in ids


async def test_non_question_publish_bypasses_question_gates(client, db_session, register_user):
    """Case F — a CONCEPT_NOTE has no NCERT / duplicate / provenance
    obligations, so it must publish through the same workflow without
    the QUESTION-specific gates blocking it. Proves the content_type
    short-circuit in evaluate_question_publication_gates and its
    corresponding branch in ContentWorkflowService.publish."""
    await _author(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "CONCEPT_NOTE",
            "concept_id": concept_id,
            "title": f"A2B non-question note {uuid.uuid4().hex[:8]}",
            "slug": f"a2b-cn-{uuid.uuid4().hex[:8]}",
            "language": "en",
            "body": {"summary": "Concept note that must publish without QUESTION gates.", "sections": []},
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]

    submit = await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text
    review = await client.post(
        f"/api/v1/cms/content-items/{item_id}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    assert review.status_code == 200, review.text
    publish = await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    assert publish.status_code == 200, publish.text
    assert publish.json()["data"]["status"] == "PUBLISHED"
