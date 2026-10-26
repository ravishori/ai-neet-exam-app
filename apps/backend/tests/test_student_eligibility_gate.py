"""Student eligibility gate: PUBLISHED alone must never be sufficient for a
question to reach practice/mock-test selection -- see
app.modules.cms.schemas.content_bodies.is_student_eligible and its single
call site, assessment_repository.published_question_ids_for_scope (shared
by generate_practice, generate_mock, and generate_full_mock).

Covers: ANSWER_PENDING excluded, ANSWER_CONFLICT excluded, structurally
invalid excluded, a normal valid question included, the legacy dict-shaped
options format (F-17, 12,396/19,589 production rows) still included after
normalization, consistency across both the practice and mock endpoints,
and that the reported available/delivered counts reflect the post-gate
pool, not the raw PUBLISHED count."""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _fresh_concept_id(db_session) -> str:
    """A concept with no pre-existing PUBLISHED questions, so each test's
    pool is exactly the rows it inserts -- mirrors
    test_practice_availability.py's _concept_without_published."""
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
    assert concept_id is not None, "need a concept with no published questions for a clean pool"
    return str(concept_id)


async def _publish_via_api(client, concept_id: str, *, stem: str, correct_option: str = "B") -> str:
    """A genuinely valid question, through the real create/submit/review/
    publish workflow -- the positive control every exclusion test is
    contrasted against."""
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": stem[:60],
            "slug": f"gate-{_uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": publishable_question_body(stem=stem, correct_option=correct_option),
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{item_id}/review", json={"decision": "approve"}, headers=csrf_headers(client)
    )
    pub = await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    assert pub.status_code == 200, pub.text
    return item_id


async def _insert_published_raw(db_session, concept_id: str, *, title: str, body: dict) -> str:
    """Raw INSERT bypassing the create/publish API's QuestionBody
    validation -- the only way to construct a PUBLISHED row the validated
    path would refuse to produce (same mechanism test_assessment_and_
    mastery.py's _publish_pending_answer_question/_publish_dict_options_
    question already use)."""
    from app.modules.cms.models import ContentItem, ContentVersion

    item_id = _uuid.uuid4()
    version_id = _uuid.uuid4()
    db_session.add(
        ContentItem(
            id=item_id, content_type="QUESTION", concept_id=_uuid.UUID(concept_id), title=title,
            slug=f"gate-raw-{str(item_id)[:8]}", tags=[], language="en", status="PUBLISHED",
            current_version_id=None, latest_version_id=None, version=1,
        )
    )
    await db_session.flush()
    db_session.add(
        ContentVersion(
            id=version_id, content_item_id=item_id, version_no=1, body=body,
            workflow_state="PUBLISHED", authored_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    item = await db_session.get(ContentItem, item_id)
    item.current_version_id = version_id
    item.latest_version_id = version_id
    await db_session.commit()
    return str(item_id)


def _ids_from(response_json: dict) -> set[str]:
    return {q["content_item_id"] for q in response_json["data"]["questions"]}


async def _generate_and_list_ids(client, *, endpoint: str, scope_id: str) -> tuple[set[str], dict]:
    generate = await client.post(
        endpoint, json={"scope_type": "CONCEPT", "scope_id": scope_id}, headers=csrf_headers(client)
    )
    assert generate.status_code == 201, generate.text
    body = generate.json()
    assessment_id = body["data"]["id"]

    start = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    assert start.status_code == 201, start.text
    attempt_id = start.json()["data"]["id"]

    attempt = await client.get(f"/api/v1/attempts/{attempt_id}")
    assert attempt.status_code == 200, attempt.text
    return _ids_from(attempt.json()), body["meta"] or {}


async def test_answer_pending_question_excluded_from_practice(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _fresh_concept_id(db_session)
    valid_id = await _publish_via_api(client, concept_id, stem="Valid control question?")
    pending_id = await _insert_published_raw(
        db_session,
        concept_id,
        title="Pending answer",
        body={
            "stem": "A PYQ with no verified answer yet?",
            "options": [
                {"label": "A", "text": "3"}, {"label": "B", "text": "4"},
                {"label": "C", "text": "5"}, {"label": "D", "text": "22"},
            ],
            "correct_option": None,
            "answer_status": "ANSWER_PENDING",
            "explanation": None,
        },
    )

    ids, meta = await _generate_and_list_ids(client, endpoint="/api/v1/assessments/practice", scope_id=concept_id)
    assert valid_id in ids
    assert pending_id not in ids


async def test_answer_conflict_question_excluded_from_practice(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _fresh_concept_id(db_session)
    valid_id = await _publish_via_api(client, concept_id, stem="Valid control question two?")
    conflict_id = await _insert_published_raw(
        db_session,
        concept_id,
        title="Conflicted answer",
        body={
            "stem": "A PYQ where two reviewers asserted different answers?",
            "options": [
                {"label": "A", "text": "One"}, {"label": "B", "text": "Two"},
                {"label": "C", "text": "Three"}, {"label": "D", "text": "Four"},
            ],
            "correct_option": "A",
            "answer_status": "ANSWER_CONFLICT",
            "explanation": "Disputed.",
        },
    )

    ids, meta = await _generate_and_list_ids(client, endpoint="/api/v1/assessments/practice", scope_id=concept_id)
    assert valid_id in ids
    assert conflict_id not in ids


async def test_structurally_invalid_question_excluded_from_practice(client, db_session, register_user):
    """Three options instead of four -- a shape the validated create API
    cannot produce, but a raw PYQ write might (same bypass mechanism)."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _fresh_concept_id(db_session)
    valid_id = await _publish_via_api(client, concept_id, stem="Valid control question three?")
    malformed_id = await _insert_published_raw(
        db_session,
        concept_id,
        title="Only three options",
        body={
            "stem": "A question missing one option?",
            "options": [
                {"label": "A", "text": "One"}, {"label": "B", "text": "Two"}, {"label": "C", "text": "Three"},
            ],
            "correct_option": "A",
            "explanation": "N/A",
        },
    )

    ids, meta = await _generate_and_list_ids(client, endpoint="/api/v1/assessments/practice", scope_id=concept_id)
    assert valid_id in ids
    assert malformed_id not in ids


async def test_legacy_dict_shaped_options_question_still_included(client, db_session, register_user):
    """F-17: dict-keyed options (12,396/19,589 production rows) is a
    presentation-format quirk already normalized by every renderer, not a
    content defect -- the gate must not reject it."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _fresh_concept_id(db_session)
    legacy_id = await _insert_published_raw(
        db_session,
        concept_id,
        title="Legacy dict options",
        body={
            "stem": "Legacy-format question: 2 + 2 = ?",
            "options": {"A": "3", "B": "4", "C": "5", "D": "22"},
            "correct_option": "B",
            "explanation": "Basic arithmetic.",
        },
    )

    ids, meta = await _generate_and_list_ids(client, endpoint="/api/v1/assessments/practice", scope_id=concept_id)
    assert legacy_id in ids


async def test_gate_is_consistent_between_practice_and_mock_endpoints(client, db_session, register_user):
    """Same exclusion rule, exercised via /assessments/mock -- both funnel
    through the same published_question_ids_for_scope, but this proves it
    end-to-end for the second endpoint explicitly rather than assuming it
    from a shared code path."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _fresh_concept_id(db_session)
    valid_id = await _publish_via_api(client, concept_id, stem="Valid control question four?")
    pending_id = await _insert_published_raw(
        db_session,
        concept_id,
        title="Pending answer (mock)",
        body={
            "stem": "Another PYQ with no verified answer yet?",
            "options": [
                {"label": "A", "text": "3"}, {"label": "B", "text": "4"},
                {"label": "C", "text": "5"}, {"label": "D", "text": "22"},
            ],
            "correct_option": None,
            "answer_status": "ANSWER_PENDING",
            "explanation": None,
        },
    )

    ids, meta = await _generate_and_list_ids(client, endpoint="/api/v1/assessments/mock", scope_id=concept_id)
    assert valid_id in ids
    assert pending_id not in ids
    # Honest-inventory meta must reflect the POST-gate pool (1 eligible),
    # not the raw PUBLISHED count (2) -- generate_mock requests "every
    # available question in scope" (question_count=None), so
    # available_count/delivered_count must both already be 1, not 2.
    assert meta.get("available_count") == 1
    assert meta.get("delivered_count") == 1


async def test_excluded_question_remains_visible_to_admin(client, db_session, register_user):
    """The gate narrows student-facing SELECTION only -- it must never
    delete, hide, or otherwise affect the excluded row for an authorized
    admin/content-manager, who can still see and fix it."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _fresh_concept_id(db_session)
    pending_id = await _insert_published_raw(
        db_session,
        concept_id,
        title="Pending answer (admin-visible)",
        body={
            "stem": "Admin must still be able to see and fix this one?",
            "options": [
                {"label": "A", "text": "3"}, {"label": "B", "text": "4"},
                {"label": "C", "text": "5"}, {"label": "D", "text": "22"},
            ],
            "correct_option": None,
            "answer_status": "ANSWER_PENDING",
            "explanation": None,
        },
    )

    admin_view = await client.get(f"/api/v1/cms/content-items/{pending_id}")
    assert admin_view.status_code == 200, admin_view.text
    assert admin_view.json()["data"]["status"] == "PUBLISHED"
