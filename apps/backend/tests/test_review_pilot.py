"""HR-2.5 — Controlled Human Review Pilot instrumentation tests.

Covers timing capture, each pilot decision, required changes-requested
reason, all 9 issue codes, pilot-only scope, unauthorized access, report
calculations, 0 LLM calls, and 0 unintended content mutations. Never
approves/publishes via this instrumentation layer itself.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.core.exceptions import AppError
from app.modules.cms.services.review_pilot_service import (
    CHANGES_REQUESTED_REASONS,
    build_pilot_report,
    record_pilot_event,
)
from conftest import csrf_headers
from tests.test_content_factory_p3 import _concept_chain

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_in_review_item(db_session, user_id, *, suffix: str) -> str:
    from app.modules.cms.services.content_workflow_service import ContentWorkflowService

    _, _, _, concept = await _concept_chain(db_session)
    service = ContentWorkflowService(db_session)
    item = await service.create_item(
        content_type="QUESTION",
        concept_id=concept.id,
        title=f"Pilot item {suffix}",
        slug=f"pilot-item-{suffix}",
        tags=[],
        language="en",
        body={
            "stem": f"Pilot stem {suffix}?",
            "options": [
                {"label": "A", "text": "a"}, {"label": "B", "text": "b"},
                {"label": "C", "text": "c"}, {"label": "D", "text": "d"},
            ],
            "correct_option": "A",
            "explanation": "Because a is right for this reasoning chain.",
            "difficulty": "medium",
        },
        author_id=uuid.UUID(user_id),
    )

    async def _fake_ai_check(*args, **kwargs):
        return {
            "status": "completed", "reason": "", "flags": [], "similarity_matches": [],
            "confidence": 0.9, "checked_at": "2026-01-01T00:00:00+00:00",
        }

    import app.modules.cms.services.content_workflow_service as cws

    original = cws.run_ai_check
    cws.run_ai_check = _fake_ai_check
    try:
        submitted = await service.submit_for_review(item.id)
    finally:
        cws.run_ai_check = original
    return str(submitted.id)


async def test_timing_capture(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id = await _make_in_review_item(db_session, user["id"], suffix="timing")

    started = datetime.now(UTC)
    submitted = started + timedelta(seconds=42)
    row = await record_pilot_event(
        db_session,
        pilot_id="pilot-test",
        content_item_id=uuid.UUID(item_id),
        actor_user_id=uuid.UUID(user["id"]),
        decision="SKIPPED",
        review_started_at=started,
        decision_submitted_at=submitted,
        review_duration_seconds=42.0,
        subject="Physics", class_level="11", chapter="Kinematics", batch_id=None, risk_bucket="AMBER",
    )
    assert row.log_metadata["review_duration_seconds"] == 42.0
    assert row.log_metadata["review_started_at"] == started.isoformat()
    assert row.log_metadata["decision_submitted_at"] == submitted.isoformat()


@pytest.mark.parametrize("decision", ["APPROVED", "CHANGES_REQUESTED", "SKIPPED", "FLAGGED"])
async def test_each_decision_recorded(db_session, register_user, client, decision):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id = await _make_in_review_item(db_session, user["id"], suffix=f"dec-{decision}")

    reason = "OTHER" if decision in ("CHANGES_REQUESTED", "FLAGGED") else None
    row = await record_pilot_event(
        db_session,
        pilot_id="pilot-test",
        content_item_id=uuid.UUID(item_id),
        actor_user_id=uuid.UUID(user["id"]),
        decision=decision,
        review_started_at=datetime.now(UTC),
        decision_submitted_at=datetime.now(UTC),
        review_duration_seconds=10.0,
        subject="Chemistry", class_level="12", chapter="Some chapter", batch_id=None, risk_bucket="RED",
        reason=reason,
    )
    assert row.log_metadata["decision"] == decision


async def test_changes_requested_requires_reason(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id = await _make_in_review_item(db_session, user["id"], suffix="reason-required")

    with pytest.raises(AppError) as exc_info:
        await record_pilot_event(
            db_session,
            pilot_id="pilot-test",
            content_item_id=uuid.UUID(item_id),
            actor_user_id=uuid.UUID(user["id"]),
            decision="CHANGES_REQUESTED",
            review_started_at=datetime.now(UTC),
            decision_submitted_at=datetime.now(UTC),
            review_duration_seconds=5.0,
            subject="Botany", class_level="11", chapter=None, batch_id=None, risk_bucket="GREEN",
        )
    assert exc_info.value.code == "PILOT_REASON_REQUIRED"


@pytest.mark.parametrize("reason", list(CHANGES_REQUESTED_REASONS))
async def test_all_issue_codes_accepted(db_session, register_user, client, reason):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id = await _make_in_review_item(db_session, user["id"], suffix=f"code-{reason}")

    row = await record_pilot_event(
        db_session,
        pilot_id="pilot-test",
        content_item_id=uuid.UUID(item_id),
        actor_user_id=uuid.UUID(user["id"]),
        decision="CHANGES_REQUESTED",
        review_started_at=datetime.now(UTC),
        decision_submitted_at=datetime.now(UTC),
        review_duration_seconds=8.0,
        subject="Zoology", class_level="12", chapter=None, batch_id=None, risk_bucket="AMBER",
        reason=reason,
    )
    assert row.log_metadata["reason"] == reason


async def test_invalid_reason_rejected(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id = await _make_in_review_item(db_session, user["id"], suffix="bad-reason")
    with pytest.raises(AppError) as exc_info:
        await record_pilot_event(
            db_session,
            pilot_id="pilot-test",
            content_item_id=uuid.UUID(item_id),
            actor_user_id=uuid.UUID(user["id"]),
            decision="CHANGES_REQUESTED",
            review_started_at=datetime.now(UTC),
            decision_submitted_at=datetime.now(UTC),
            review_duration_seconds=8.0,
            subject=None, class_level=None, chapter=None, batch_id=None, risk_bucket=None,
            reason="NOT_A_REAL_CODE",
        )
    assert exc_info.value.code == "INVALID_PILOT_REASON"


async def test_pilot_only_scope_via_endpoint(db_session, register_user, client):
    """Recording a pilot event must never mutate content_items itself."""
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id = await _make_in_review_item(db_session, user["id"], suffix="scope")

    before = (
        await db_session.execute(text("SELECT status FROM cms.content_items WHERE id = :id"), {"id": item_id})
    ).scalar_one()
    assert before == "IN_REVIEW"

    resp = await client.post(
        "/api/v1/cms/review-pilot/events",
        json={
            "pilot_id": "pilot-test",
            "content_item_id": item_id,
            "decision": "SKIPPED",
            "review_started_at": datetime.now(UTC).isoformat(),
            "decision_submitted_at": datetime.now(UTC).isoformat(),
            "review_duration_seconds": 3.5,
            "subject": "Physics",
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201, resp.text

    after = (
        await db_session.execute(text("SELECT status FROM cms.content_items WHERE id = :id"), {"id": item_id})
    ).scalar_one()
    assert after == "IN_REVIEW"  # unchanged — pilot recording never mutates content


async def test_unauthorized_access(client, register_user):
    await register_user(client)  # STUDENT — no content.review
    resp = await client.post(
        "/api/v1/cms/review-pilot/events",
        json={
            "pilot_id": "pilot-test",
            "content_item_id": str(uuid.uuid4()),
            "decision": "SKIPPED",
            "review_started_at": datetime.now(UTC).isoformat(),
            "decision_submitted_at": datetime.now(UTC).isoformat(),
            "review_duration_seconds": 1.0,
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 403

    report_resp = await client.get("/api/v1/cms/review-pilot/report", params={"pilot_id": "pilot-test"})
    assert report_resp.status_code == 403


async def test_report_calculations(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    pilot_id = f"pilot-report-{uuid.uuid4().hex[:8]}"

    durations_and_risk = [
        ("APPROVED", "RED", 10.0, None),
        ("APPROVED", "RED", 20.0, None),
        ("CHANGES_REQUESTED", "AMBER", 30.0, "ANSWER"),
        ("SKIPPED", "AMBER", 40.0, None),
        ("FLAGGED", "GREEN", 50.0, "OTHER"),
    ]
    for i, (decision, risk, dur, reason) in enumerate(durations_and_risk):
        item_id = await _make_in_review_item(db_session, user["id"], suffix=f"report-{i}")
        await record_pilot_event(
            db_session,
            pilot_id=pilot_id,
            content_item_id=uuid.UUID(item_id),
            actor_user_id=uuid.UUID(user["id"]),
            decision=decision,
            review_started_at=datetime.now(UTC),
            decision_submitted_at=datetime.now(UTC),
            review_duration_seconds=dur,
            subject="Physics", class_level="11", chapter="Ch", batch_id="batch-1", risk_bucket=risk,
            reason=reason,
        )

    report = await build_pilot_report(db_session, pilot_id=pilot_id)
    assert report["total_reviewed"] == 5
    assert report["decision_distribution"] == {
        "APPROVED": 2, "CHANGES_REQUESTED": 1, "SKIPPED": 1, "FLAGGED": 1,
    }
    assert report["rates"]["approval_rate"] == 0.4
    assert report["duration_seconds"]["median"] == 30.0
    assert report["duration_seconds"]["n"] == 5
    assert report["duration_by_risk_bucket"]["RED"]["n"] == 2
    assert report["decision_by_risk_bucket"]["RED"] == {"APPROVED": 2}
    assert report["issue_frequency"] == {"ANSWER": 1, "OTHER": 1}
    assert report["subject_distribution"] == {"Physics": 5}
    assert report["batch_distribution"] == {"batch-1": 5}
    assert "small_sample_disclaimer" in report
    assert report["no_llm_used"] is True


async def test_report_endpoint_scoped_to_pilot_id(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_a = await _make_in_review_item(db_session, user["id"], suffix="scoped-a")
    item_b = await _make_in_review_item(db_session, user["id"], suffix="scoped-b")

    await record_pilot_event(
        db_session, pilot_id="pilot-alpha", content_item_id=uuid.UUID(item_a),
        actor_user_id=uuid.UUID(user["id"]), decision="APPROVED",
        review_started_at=datetime.now(UTC), decision_submitted_at=datetime.now(UTC),
        review_duration_seconds=5.0, subject=None, class_level=None, chapter=None, batch_id=None, risk_bucket=None,
    )
    await record_pilot_event(
        db_session, pilot_id="pilot-beta", content_item_id=uuid.UUID(item_b),
        actor_user_id=uuid.UUID(user["id"]), decision="SKIPPED",
        review_started_at=datetime.now(UTC), decision_submitted_at=datetime.now(UTC),
        review_duration_seconds=5.0, subject=None, class_level=None, chapter=None, batch_id=None, risk_bucket=None,
    )

    resp = await client.get("/api/v1/cms/review-pilot/report", params={"pilot_id": "pilot-alpha"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_reviewed"] == 1
    assert data["decision_distribution"] == {"APPROVED": 1}


async def test_no_llm_calls_from_pilot_instrumentation(db_session, register_user, client):
    """Structural check: record_pilot_event and build_pilot_report never
    import/call anything from app.modules.ai.*"""
    import app.modules.cms.services.review_pilot_service as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "app.modules.ai" not in source
    assert "AIGateway" not in source
    assert "EvaluatorService" not in source
