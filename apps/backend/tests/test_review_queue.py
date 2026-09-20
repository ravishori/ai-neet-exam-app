"""HR-1 — Review Queue Foundation tests.

Covers: unauthorized/authorized access, IN_REVIEW-only filtering,
pagination, every supported filter, deterministic ordering, deterministic
risk classification, session defaults/creation/resume, claim success,
duplicate-claim prevention, expired-claim reclaim, non-IN_REVIEW rejection,
RBAC, and audit entries. Never approves or publishes anything.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.core.exceptions import AppError
from app.modules.cms.models.review_queue import DEFAULT_SESSION_SIZE
from app.modules.cms.services.review_queue_service import ReviewQueueService
from app.modules.cms.services.review_risk import classify_review_risk
from conftest import csrf_headers
from tests.test_content_factory_p3 import _concept_chain
from tests.test_trusted_factory_submission import (
    _VALID_EVIDENCE,
    _generate_one,
    _seed_trusted_blueprint,
    counting_evaluate,  # noqa: F401 — pytest fixture reused across modules
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_in_review_item(client, db_session, user, *, suffix: str | None = None) -> tuple[str, str]:
    """Real Content Factory lineage -> IN_REVIEW via the trusted path (no
    LLM call needed). Returns (item_id, batch_id)."""
    from app.modules.cms.services.content_workflow_service import ContentWorkflowService

    suffix = suffix or uuid.uuid4().hex[:8]
    seeded = await _seed_trusted_blueprint(client, db_session, suffix)
    item_id = await _generate_one(
        db_session, user["id"], seeded, stem=f"HR1 stem {suffix}?",
        ncert_evidence=_VALID_EVIDENCE, suffix=suffix,
    )
    service = ContentWorkflowService(db_session)
    await service.submit_for_review_trusted_factory(
        uuid.UUID(item_id), actor_id=uuid.UUID(user["id"]), expected_batch_id=uuid.UUID(seeded["batch_id"]),
    )
    return item_id, seeded["batch_id"]


# --------------------------------------------------------------------- A


async def test_review_queue_requires_permission(client, register_user):
    await register_user(client)  # STUDENT — no content.review
    resp = await client.get("/api/v1/cms/review-queue")
    assert resp.status_code == 403


async def test_review_queue_authorized_access(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    await _make_in_review_item(client, db_session, user)
    resp = await client.get("/api/v1/cms/review-queue")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


async def test_review_queue_only_returns_in_review(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    from app.modules.cms.services.content_workflow_service import ContentWorkflowService

    suffix = uuid.uuid4().hex[:8]
    _, _, _, concept = await _concept_chain(db_session)
    service = ContentWorkflowService(db_session)
    draft = await service.create_item(
        content_type="QUESTION", concept_id=concept.id, title="Draft not in review",
        slug=f"hr1-draft-{suffix}", tags=[], language="en",
        body={
            "stem": f"Draft stem {suffix}?",
            "options": [
                {"label": "A", "text": "a"}, {"label": "B", "text": "b"},
                {"label": "C", "text": "c"}, {"label": "D", "text": "d"},
            ],
            "correct_option": "A",
            "explanation": "Because a is right for this reasoning chain.",
            "difficulty": "medium",
        },
        author_id=uuid.UUID(user["id"]),
    )
    item_id, _batch = await _make_in_review_item(client, db_session, user, suffix=suffix + "b")

    resp = await client.get("/api/v1/cms/review-queue", params={"limit": 200})
    ids = {row["id"] for row in resp.json()["data"]}
    assert item_id in ids
    assert str(draft.id) not in ids


async def test_review_queue_pagination(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    ids = []
    for i in range(3):
        item_id, _ = await _make_in_review_item(client, db_session, user, suffix=f"pg{i}-{uuid.uuid4().hex[:6]}")
        ids.append(item_id)

    resp1 = await client.get("/api/v1/cms/review-queue", params={"limit": 1, "offset": 0})
    resp2 = await client.get("/api/v1/cms/review-queue", params={"limit": 1, "offset": 1})
    assert resp1.status_code == resp2.status_code == 200
    page1 = resp1.json()["data"]
    page2 = resp2.json()["data"]
    assert len(page1) == 1
    assert len(page2) == 1
    assert page1[0]["id"] != page2[0]["id"]


async def test_review_queue_batch_id_filter(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_a, batch_a = await _make_in_review_item(client, db_session, user, suffix="batcha" + uuid.uuid4().hex[:6])
    item_b, batch_b = await _make_in_review_item(client, db_session, user, suffix="batchb" + uuid.uuid4().hex[:6])
    assert batch_a != batch_b

    resp = await client.get("/api/v1/cms/review-queue", params={"batch_id": batch_a, "limit": 200})
    ids = {row["id"] for row in resp.json()["data"]}
    assert item_a in ids
    assert item_b not in ids


async def test_review_queue_subject_class_chapter_topic_filters(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id, _ = await _make_in_review_item(client, db_session, user, suffix="acad" + uuid.uuid4().hex[:6])
    subject, chapter, topic, _concept = await _concept_chain(db_session)

    for params in (
        {"subject_id": str(subject.id)},
        {"chapter_id": str(chapter.id)},
        {"topic_id": str(topic.id)},
    ):
        resp = await client.get("/api/v1/cms/review-queue", params={**params, "limit": 200})
        assert resp.status_code == 200
        ids = {row["id"] for row in resp.json()["data"]}
        assert item_id in ids, params

    if chapter.class_level:
        resp = await client.get(
            "/api/v1/cms/review-queue", params={"class_level": chapter.class_level, "limit": 200}
        )
        ids = {row["id"] for row in resp.json()["data"]}
        assert item_id in ids


async def test_review_queue_risk_bucket_filter_and_trusted_flag(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id, _ = await _make_in_review_item(client, db_session, user, suffix="risk" + uuid.uuid4().hex[:6])

    resp = await client.get("/api/v1/cms/review-queue", params={"limit": 200})
    row = next(r for r in resp.json()["data"] if r["id"] == item_id)
    assert row["risk_bucket"] in ("RED", "AMBER", "GREEN")
    assert row["is_trusted_factory"] is True  # went through submit_for_review_trusted_factory

    resp2 = await client.get(
        "/api/v1/cms/review-queue", params={"risk_bucket": row["risk_bucket"], "limit": 200}
    )
    ids = {r["id"] for r in resp2.json()["data"]}
    assert item_id in ids

    other_bucket = next(b for b in ("RED", "AMBER", "GREEN") if b != row["risk_bucket"])
    resp3 = await client.get("/api/v1/cms/review-queue", params={"risk_bucket": other_bucket, "limit": 200})
    ids3 = {r["id"] for r in resp3.json()["data"]}
    assert item_id not in ids3


async def test_review_queue_invalid_risk_bucket_rejected(client, register_user, db_session):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get("/api/v1/cms/review-queue", params={"risk_bucket": "PURPLE"})
    assert resp.status_code == 400


async def test_review_queue_deterministic_ordering(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    for i in range(3):
        await _make_in_review_item(client, db_session, user, suffix=f"ord{i}-{uuid.uuid4().hex[:6]}")

    resp1 = await client.get("/api/v1/cms/review-queue", params={"limit": 50})
    resp2 = await client.get("/api/v1/cms/review-queue", params={"limit": 50})
    ids1 = [r["id"] for r in resp1.json()["data"]]
    ids2 = [r["id"] for r in resp2.json()["data"]]
    assert ids1 == ids2  # identical calls -> identical order


# --------------------------------------------------------------------- B


def test_classify_review_risk_red_on_failed_gate():
    result = classify_review_risk(
        content_ready=False, gate_reasons=["structural:bad"], ai_check_flags=[],
        ncert_verification_level=None, has_provenance_lineage=False,
    )
    assert result.bucket == "RED"


def test_classify_review_risk_red_on_ai_flags():
    result = classify_review_risk(
        content_ready=True, gate_reasons=[], ai_check_flags=["possible_duplicate"],
        ncert_verification_level="SECTION_VERIFIED", has_provenance_lineage=True,
    )
    assert result.bucket == "RED"


def test_classify_review_risk_green():
    result = classify_review_risk(
        content_ready=True, gate_reasons=[], ai_check_flags=[],
        ncert_verification_level="SECTION_VERIFIED", has_provenance_lineage=True,
    )
    assert result.bucket == "GREEN"


def test_classify_review_risk_amber_default():
    result = classify_review_risk(
        content_ready=True, gate_reasons=[], ai_check_flags=[],
        ncert_verification_level=None, has_provenance_lineage=False,
    )
    assert result.bucket == "AMBER"


# --------------------------------------------------------------------- C


async def test_default_session_size(db_session, register_user, client, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    await _make_in_review_item(client, db_session, user, suffix="sess-def" + uuid.uuid4().hex[:6])
    service = ReviewQueueService(db_session)
    session_row = await service.create_session(reviewer_id=uuid.UUID(user["id"]))
    assert session_row.session_size == DEFAULT_SESSION_SIZE == 25


async def test_explicit_session_size(db_session, register_user, client, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    for i in range(3):
        await _make_in_review_item(client, db_session, user, suffix=f"sess-exp{i}-{uuid.uuid4().hex[:6]}")
    service = ReviewQueueService(db_session)
    session_row = await service.create_session(reviewer_id=uuid.UUID(user["id"]), session_size=2)
    assert session_row.session_size == 2
    assert len(session_row.item_ids) <= 2


async def test_create_review_session_endpoint(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    await _make_in_review_item(client, db_session, user, suffix="sess-ep" + uuid.uuid4().hex[:6])
    resp = await client.post(
        "/api/v1/cms/review-sessions", json={"session_size": 5}, headers=csrf_headers(client)
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["reviewer_id"] == user["id"]
    assert data["status"] == "ACTIVE"
    assert data["position"] == 0

    audit_row = (
        await db_session.execute(
            text(
                "SELECT action FROM system.audit_logs WHERE entity_id = :id AND action = 'review_session.create'"
            ),
            {"id": data["id"]},
        )
    ).first()
    assert audit_row is not None


async def test_review_session_resume_and_progress(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    await _make_in_review_item(client, db_session, user, suffix="resume" + uuid.uuid4().hex[:6])
    resp = await client.post(
        "/api/v1/cms/review-sessions", json={"session_size": 25}, headers=csrf_headers(client)
    )
    session_id = resp.json()["data"]["id"]

    resume = await client.get(f"/api/v1/cms/review-sessions/{session_id}")
    assert resume.status_code == 200
    assert resume.json()["data"]["position"] == 0

    advanced = await client.post(
        f"/api/v1/cms/review-sessions/{session_id}/advance", headers=csrf_headers(client)
    )
    assert advanced.status_code == 200
    assert advanced.json()["data"]["position"] == 1


async def test_review_session_requires_permission(client, register_user):
    await register_user(client)  # STUDENT
    resp = await client.post("/api/v1/cms/review-sessions", json={}, headers=csrf_headers(client))
    assert resp.status_code == 403


# --------------------------------------------------------------------- D


async def test_successful_claim(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id, _ = await _make_in_review_item(client, db_session, user, suffix="claim-ok" + uuid.uuid4().hex[:6])

    resp = await client.post(f"/api/v1/cms/content-items/{item_id}/claim", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["content_item_id"] == item_id
    assert data["reviewer_id"] == user["id"]
    assert data["status"] == "ACTIVE"

    audit_row = (
        await db_session.execute(
            text("SELECT action FROM system.audit_logs WHERE entity_id = :id AND action = 'review_claim.claim'"),
            {"id": item_id},
        )
    ).first()
    assert audit_row is not None


async def test_duplicate_concurrent_claim_prevented(client, register_user, db_session, counting_evaluate):  # noqa: F811
    owner = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id, _ = await _make_in_review_item(client, db_session, owner, suffix="claim-dup" + uuid.uuid4().hex[:6])

    service = ReviewQueueService(db_session)
    await service.claim_item(uuid.UUID(item_id), reviewer_id=uuid.UUID(owner["id"]))

    other = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    with pytest.raises(AppError) as exc_info:
        await service.claim_item(uuid.UUID(item_id), reviewer_id=uuid.UUID(other["id"]))
    assert exc_info.value.code == "ALREADY_CLAIMED"


async def test_expired_claim_can_be_reclaimed(client, register_user, db_session, counting_evaluate):  # noqa: F811
    owner = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id, _ = await _make_in_review_item(client, db_session, owner, suffix="claim-exp" + uuid.uuid4().hex[:6])

    service = ReviewQueueService(db_session)
    claim = await service.claim_item(uuid.UUID(item_id), reviewer_id=uuid.UUID(owner["id"]))
    # Force the lease into the past, simulating expiry.
    claim.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    other = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    new_claim = await service.claim_item(uuid.UUID(item_id), reviewer_id=uuid.UUID(other["id"]))
    assert new_claim.reviewer_id == uuid.UUID(other["id"])
    assert new_claim.status == "ACTIVE"


async def test_non_in_review_question_cannot_be_claimed(client, register_user, db_session):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    from app.modules.cms.services.content_workflow_service import ContentWorkflowService

    _, _, _, concept = await _concept_chain(db_session)
    service_wf = ContentWorkflowService(db_session)
    suffix = uuid.uuid4().hex[:8]
    draft = await service_wf.create_item(
        content_type="QUESTION", concept_id=concept.id, title="Draft cannot claim",
        slug=f"hr1-noclaim-{suffix}", tags=[], language="en",
        body={
            "stem": f"Noclaim stem {suffix}?",
            "options": [
                {"label": "A", "text": "a"}, {"label": "B", "text": "b"},
                {"label": "C", "text": "c"}, {"label": "D", "text": "d"},
            ],
            "correct_option": "A",
            "explanation": "Because a is right for this reasoning chain.",
            "difficulty": "medium",
        },
        author_id=uuid.UUID(user["id"]),
    )
    service = ReviewQueueService(db_session)
    with pytest.raises(AppError) as exc_info:
        await service.claim_item(draft.id, reviewer_id=uuid.UUID(user["id"]))
    assert exc_info.value.code == "NOT_CLAIMABLE"


async def test_claim_and_release_endpoint_flow(client, register_user, db_session, counting_evaluate):  # noqa: F811
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id, _ = await _make_in_review_item(client, db_session, user, suffix="claim-rel" + uuid.uuid4().hex[:6])

    claimed = await client.post(f"/api/v1/cms/content-items/{item_id}/claim", headers=csrf_headers(client))
    assert claimed.status_code == 200

    released = await client.post(
        f"/api/v1/cms/content-items/{item_id}/release-claim", headers=csrf_headers(client)
    )
    assert released.status_code == 200
    assert released.json()["data"]["status"] == "RELEASED"

    audit_row = (
        await db_session.execute(
            text("SELECT action FROM system.audit_logs WHERE entity_id = :id AND action = 'review_claim.release'"),
            {"id": item_id},
        )
    ).first()
    assert audit_row is not None

    # Re-claimable after release.
    service = ReviewQueueService(db_session)
    reclaim = await service.claim_item(uuid.UUID(item_id), reviewer_id=uuid.UUID(user["id"]))
    assert reclaim.status == "ACTIVE"


async def test_claim_requires_permission(client, register_user, db_session, counting_evaluate):  # noqa: F811
    owner = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id, _ = await _make_in_review_item(client, db_session, owner, suffix="claim-rbac" + uuid.uuid4().hex[:6])

    await register_user(client)  # STUDENT — no content.review
    resp = await client.post(f"/api/v1/cms/content-items/{item_id}/claim", headers=csrf_headers(client))
    assert resp.status_code == 403


async def test_release_claim_you_do_not_hold_is_forbidden(client, register_user, db_session, counting_evaluate):  # noqa: F811
    owner = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id, _ = await _make_in_review_item(client, db_session, owner, suffix="claim-forbid" + uuid.uuid4().hex[:6])

    service = ReviewQueueService(db_session)
    await service.claim_item(uuid.UUID(item_id), reviewer_id=uuid.UUID(owner["id"]))

    other = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    with pytest.raises(AppError) as exc_info:
        await service.release_claim(uuid.UUID(item_id), reviewer_id=uuid.UUID(other["id"]))
    assert exc_info.value.code == "FORBIDDEN"
