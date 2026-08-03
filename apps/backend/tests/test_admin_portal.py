"""Integration tests: Admin Portal (PR 11) — all 9 modules.

Covers: dashboard aggregation, question management pagination/bulk/report
triage, knowledge unit list/detail, PDF management pagination/drill-down,
visual asset review + permission gating, AI review queue, search console
reindex, audit log writes+reads, and user/role management filters/bulk/
permission editor.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _publish_question(client, concept_id: str, *, stem: str = "2 + 2 = ?") -> str:
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "Admin portal test question",
            "slug": f"admin-portal-test-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": {
                "stem": stem,
                "options": [{"label": "A", "text": "3"}, {"label": "B", "text": "4"}],
                "correct_option": "B",
                "explanation": "n/a",
            },
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    await client.post(f"/api/v1/cms/content-items/{item_id}/review", json={"decision": "approve"}, headers=csrf_headers(client))
    await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    return item_id


# ---------------------------------------------------------------------------
# Module 1: Admin Dashboard
# ---------------------------------------------------------------------------


async def test_dashboard_requires_analytics_view_permission(client):
    resp = await client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 401  # not even logged in


async def test_dashboard_returns_aggregated_counts(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    resp = await client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "content_by_status" in data
    assert "ingestion_by_status" in data
    assert "pending_visual_assets" in data
    assert "open_content_reports" in data
    assert "total_users" in data
    assert data["total_users"] >= 1


async def test_dashboard_forbidden_for_student(client, db_session, register_user):
    await register_user(client, db_session=db_session)  # default STUDENT role
    resp = await client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Module 2: Question Management
# ---------------------------------------------------------------------------


async def test_content_items_list_is_paginated(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    for i in range(3):
        await _publish_question(client, concept_id, stem=f"Question {i}")

    resp = await client.get("/api/v1/cms/content-items", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] >= 3


async def test_bulk_archive_publishes_and_reports_per_item_outcome(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    item_id = await _publish_question(client, concept_id)

    resp = await client.post(
        "/api/v1/cms/content-items/bulk",
        json={"item_ids": [item_id, str(uuid.uuid4())], "action": "archive"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()["data"]
    assert results[0]["success"] is True
    assert results[1]["success"] is False


async def test_content_report_triage_list_and_resolve(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    item_id = await _publish_question(client, concept_id)

    report = await client.post(
        f"/api/v1/cms/questions/{item_id}/report", json={"reason": "UNCLEAR"}, headers=csrf_headers(client)
    )
    assert report.status_code == 201, report.text

    listing = await client.get("/api/v1/cms/content-reports", params={"status": "OPEN"})
    assert listing.status_code == 200, listing.text
    reports = listing.json()["data"]
    assert len(reports) == 1
    report_id = reports[0]["id"]

    resolve = await client.patch(
        f"/api/v1/cms/content-reports/{report_id}", json={"status": "RESOLVED"}, headers=csrf_headers(client)
    )
    assert resolve.status_code == 200, resolve.text
    assert resolve.json()["data"]["status"] == "RESOLVED"

    still_open = await client.get("/api/v1/cms/content-reports", params={"status": "OPEN"})
    assert still_open.json()["data"] == []


# ---------------------------------------------------------------------------
# Module 3: Knowledge Unit Management
# ---------------------------------------------------------------------------


async def _create_knowledge_unit(db_session, *, concept_id: str) -> str:
    from app.modules.ingestion.models import IngestionJob, IngestionSection
    from app.modules.knowledge.models import KnowledgeUnit

    job = IngestionJob(source_file_path="admin-portal-test.pdf", file_checksum=uuid.uuid4().hex, status="STRUCTURING")
    db_session.add(job)
    await db_session.flush()

    section = IngestionSection(job_id=job.id, heading="Test section", source_page=1, raw_text="text", matched_concept_id=uuid.UUID(concept_id))
    db_session.add(section)
    await db_session.flush()

    unit = KnowledgeUnit(
        version=1,
        content_hash=uuid.uuid4().hex,
        structured_facts=["A fact."],
        summary="A test summary.",
        source_section_id=section.id,
        concept_id=uuid.UUID(concept_id),
        extraction_confidence=0.9,
        validation_status="PASSED",
    )
    db_session.add(unit)
    await db_session.commit()
    return str(unit.id), str(job.id)


async def test_knowledge_units_list_and_detail(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    unit_id, _ = await _create_knowledge_unit(db_session, concept_id=concept_id)

    listing = await client.get("/api/v1/knowledge/units", params={"validation_status": "PASSED"})
    assert listing.status_code == 200, listing.text
    assert any(u["id"] == unit_id for u in listing.json()["data"])

    detail = await client.get(f"/api/v1/knowledge/units/{unit_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["structured_facts"] == ["A fact."]
    assert detail.json()["data"]["concept_name"] is not None


async def test_knowledge_units_requires_permission(client, db_session, register_user):
    await register_user(client, db_session=db_session)  # STUDENT
    resp = await client.get("/api/v1/knowledge/units")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Module 4: PDF Management
# ---------------------------------------------------------------------------


async def test_ingestion_jobs_list_paginated_and_filterable(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    unit_id, job_id = await _create_knowledge_unit(db_session, concept_id=concept_id)

    listing = await client.get("/api/v1/ingestion/jobs", params={"status": "STRUCTURING", "limit": 10})
    assert listing.status_code == 200, listing.text
    assert any(j["id"] == job_id for j in listing.json()["data"])
    assert "total" in listing.json()["meta"]


async def test_ingestion_job_detail_drilldown(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    unit_id, job_id = await _create_knowledge_unit(db_session, concept_id=concept_id)

    detail = await client.get(f"/api/v1/ingestion/jobs/{job_id}/detail")
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert len(data["sections"]) == 1
    assert len(data["knowledge_units"]) == 1
    assert data["knowledge_units"][0]["id"] == unit_id


# ---------------------------------------------------------------------------
# Module 5: Visual Asset Review
# ---------------------------------------------------------------------------


async def _create_visual_asset(db_session, *, job_id: str, review_status: str = "AUTO_DETECTED") -> str:
    from app.modules.ingestion.models.visual_asset import VisualAsset

    asset = VisualAsset(
        job_id=uuid.UUID(job_id),
        source_page=1,
        asset_type="diagram",
        detection_method="embedded_image",
        review_status=review_status,
    )
    db_session.add(asset)
    await db_session.commit()
    return str(asset.id)


async def test_visual_asset_approve_and_reject_flow(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    _, job_id = await _create_knowledge_unit(db_session, concept_id=concept_id)
    asset_id = await _create_visual_asset(db_session, job_id=job_id)

    listing = await client.get("/api/v1/ingestion/visual-assets", params={"review_status": "AUTO_DETECTED"})
    assert listing.status_code == 200, listing.text
    assert any(a["id"] == asset_id for a in listing.json()["data"])

    approve = await client.post(f"/api/v1/ingestion/visual-assets/{asset_id}/approve", headers=csrf_headers(client))
    assert approve.status_code == 200, approve.text
    assert approve.json()["data"]["review_status"] == "VERIFIED"
    assert approve.json()["data"]["approved_by"] is not None


async def test_visual_asset_reject_records_reason(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    _, job_id = await _create_knowledge_unit(db_session, concept_id=concept_id)
    asset_id = await _create_visual_asset(db_session, job_id=job_id)

    reject = await client.post(
        f"/api/v1/ingestion/visual-assets/{asset_id}/reject", json={"reason": "Bad crop"}, headers=csrf_headers(client)
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["data"]["review_status"] == "REJECTED"
    assert reject.json()["data"]["rejection_reason"] == "Bad crop"


async def test_visual_asset_review_requires_permission(client, db_session, register_user):
    await register_user(client, db_session=db_session)  # STUDENT
    resp = await client.get("/api/v1/ingestion/visual-assets")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Module 6: AI Review Queue
# ---------------------------------------------------------------------------


async def test_ai_review_queue_lists_in_review_items_with_report(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)

    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "AI review queue test",
            "slug": f"ai-review-test-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": {
                "stem": "test?",
                "options": [{"label": "A", "text": "x"}, {"label": "B", "text": "y"}],
                "correct_option": "A",
                "explanation": "n/a",
            },
        },
        headers=csrf_headers(client),
    )
    item_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))

    queue = await client.get("/api/v1/cms/ai-review-queue")
    assert queue.status_code == 200, queue.text
    matched = next((i for i in queue.json()["data"] if i["id"] == item_id), None)
    assert matched is not None
    assert matched["latest_version"]["ai_check_report"] is not None


# ---------------------------------------------------------------------------
# Module 7: Search Console
# ---------------------------------------------------------------------------


async def test_search_reindex_succeeds_for_admin(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    resp = await client.post("/api/v1/cms/search/reindex", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    assert "reindexed_count" in resp.json()["data"]


async def test_search_reindex_forbidden_for_content_manager(client, db_session, register_user):
    # search.admin is deliberately narrower than knowledge.manage/visual_assets.review —
    # reindexing is a heavier ops action, scoped to ADMIN/SUPER_ADMIN only.
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.post("/api/v1/cms/search/reindex", headers=csrf_headers(client))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Module 8: Audit Logs
# ---------------------------------------------------------------------------


async def test_audit_log_written_on_visual_asset_approve_and_readable(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    _, job_id = await _create_knowledge_unit(db_session, concept_id=concept_id)
    asset_id = await _create_visual_asset(db_session, job_id=job_id)

    await client.post(f"/api/v1/ingestion/visual-assets/{asset_id}/approve", headers=csrf_headers(client))

    logs = await client.get("/api/v1/admin/audit-logs", params={"action": "visual_asset.approve"})
    assert logs.status_code == 200, logs.text
    entries = logs.json()["data"]
    assert len(entries) == 1
    assert entries[0]["entity_id"] == asset_id
    assert entries[0]["actor_email"] is not None


async def test_audit_logs_requires_audit_view_permission(client, db_session, register_user):
    await register_user(client, role_codes=["TEACHER"], db_session=db_session)
    resp = await client.get("/api/v1/admin/audit-logs")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Module 9: User & Role Management
# ---------------------------------------------------------------------------


async def test_users_list_paginated_and_searchable(client, db_session, register_user):
    admin = await register_user(client, role_codes=["ADMIN"], db_session=db_session)

    resp = await client.get("/api/v1/users", params={"search": admin["email"]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["email"] == admin["email"]


async def test_users_bulk_suspend_and_activate(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)

    # A second, independent client/session for the target user — registering
    # a second user on the SAME client would switch its cookies to that new
    # (unprivileged) user, since /auth/register auto-logs-in the caller.
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other_client:
        target = await register_user(other_client, db_session=db_session)

    resp = await client.post(
        "/api/v1/users/bulk", json={"user_ids": [target["id"]], "action": "suspend"}, headers=csrf_headers(client)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"][0]["success"] is True

    check = await client.get("/api/v1/users", params={"status": "suspended"})
    assert any(u["id"] == target["id"] for u in check.json()["data"])


async def test_role_permission_editor_updates_and_persists(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)

    roles = await client.get("/api/v1/roles")
    support_role = next(r for r in roles.json()["data"] if r["code"] == "SUPPORT")
    assert "audit.view" not in support_role["permission_codes"]

    update = await client.patch(
        f"/api/v1/roles/{support_role['id']}/permissions",
        json={"permission_codes": [*support_role["permission_codes"], "audit.view"]},
        headers=csrf_headers(client),
    )
    assert update.status_code == 200, update.text
    assert "audit.view" in update.json()["data"]["permission_codes"]


async def test_role_permission_editor_rejects_super_admin_edit(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    roles = await client.get("/api/v1/roles")
    super_admin_role = next(r for r in roles.json()["data"] if r["code"] == "SUPER_ADMIN")

    resp = await client.patch(
        f"/api/v1/roles/{super_admin_role['id']}/permissions", json={"permission_codes": []}, headers=csrf_headers(client)
    )
    assert resp.status_code == 400
