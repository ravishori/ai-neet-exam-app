"""Phase 3.3-R1 — campaign counts must be complete aggregates, not first-2000 scans."""

from __future__ import annotations

import inspect
import uuid

import pytest
from sqlalchemy import func, select

from app.modules.cms.models import ContentItem
from app.modules.cms.services import editorial_review_service as ers
from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _concept_for_subject(db_session, subject_name: str) -> str | None:
    from app.modules.academic.models import Chapter, Concept, Subject, Topic

    result = await db_session.execute(
        select(Concept.id)
        .join(Topic, Topic.id == Concept.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .join(Subject, Subject.id == Chapter.subject_id)
        .where(Subject.name == subject_name)
        .limit(1)
    )
    cid = result.scalar_one_or_none()
    return str(cid) if cid else None


async def test_campaign_dashboard_source_has_no_2000_scan_cap():
    source = inspect.getsource(ers.EditorialReviewService.campaign_dashboard)
    assert ".limit(2000)" not in source
    assert "quality_sample_limit" in source
    assert "count_semantics" in source
    assert "COMPLETE" in source


async def test_campaign_dashboard_complete_count_semantics(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get("/api/v1/cms/editorial-campaign")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["rules"]["inventory_counts_complete"] is True
    assert data["rules"]["no_auto_publish"] is True
    assert "count_semantics" in data
    assert "COMPLETE" in data["count_semantics"]["status_counts"]
    assert "COMPLETE" in data["count_semantics"]["by_academic_subject"]
    assert "COMPLETE" in data["count_semantics"]["targets.pipeline"]
    assert "SAMPLE" in data["count_semantics"]["quality_metrics_percentages"]

    qm = data["quality_metrics"]
    assert qm.get("sample_only") is True
    assert qm.get("sample_limit") == 500
    assert qm["total_questions_scanned"] <= qm["sample_limit"]
    assert "SAMPLE" in qm["disclaimer"].upper() or "sample" in qm["disclaimer"].lower()

    # Complete inventory totals must match direct SQL (not min(pop, 2000))
    total_sql = int(
        (
            await db_session.execute(
                select(func.count())
                .select_from(ContentItem)
                .where(ContentItem.content_type == "QUESTION", ContentItem.deleted_at.is_(None))
            )
        ).scalar()
        or 0
    )
    status_sum = sum(
        int(data["status_counts"][k])
        for k in ("draft", "in_review", "approved", "published", "changes_requested", "archived")
    )
    assert status_sum == total_sql
    assert qm.get("inventory_total_questions") == total_sql

    for t in data["targets"]:
        assert t.get("pipeline_complete") is True

    # Biology pipeline = Botany + Zoology complete rollup
    by_subj = {row["subject"]: row for row in data["by_academic_subject"]}
    bio = next(t for t in data["targets"] if t["area"] == "Biology")
    expected_ir = int(by_subj.get("Botany", {}).get("in_review", 0)) + int(
        by_subj.get("Zoology", {}).get("in_review", 0)
    )
    assert bio["pipeline"]["in_review"] == expected_ir


async def test_campaign_subject_counts_include_new_in_review_items(
    client, db_session, register_user
):
    """Creating IN_REVIEW items must increase complete subject aggregates (not truncated)."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_for_subject(db_session, "Zoology")
    if not concept_id:
        pytest.skip("Zoology concept not seeded in test DB")

    before = (await client.get("/api/v1/cms/editorial-campaign")).json()["data"]
    before_zoo = next(
        (r for r in before["by_academic_subject"] if r["subject"] == "Zoology"),
        {"in_review": 0},
    )
    before_ir = int(before_zoo["in_review"])

    create_n = 3
    for i in range(create_n):
        create = await client.post(
            "/api/v1/cms/content-items",
            json={
                "content_type": "QUESTION",
                "concept_id": concept_id,
                "title": f"R1 campaign count Zoo {uuid.uuid4().hex[:8]}",
                "slug": f"r1-camp-zoo-{uuid.uuid4().hex[:10]}",
                "language": "en",
                "body": publishable_question_body(),
            },
            headers=csrf_headers(client),
        )
        assert create.status_code == 201, create.text
        item_id = create.json()["data"]["id"]
        submit = await client.post(
            f"/api/v1/cms/content-items/{item_id}/submit",
            headers=csrf_headers(client),
        )
        assert submit.status_code == 200, submit.text

    after = (await client.get("/api/v1/cms/editorial-campaign")).json()["data"]
    after_zoo = next(r for r in after["by_academic_subject"] if r["subject"] == "Zoology")
    assert int(after_zoo["in_review"]) == before_ir + create_n

    bio = next(t for t in after["targets"] if t["area"] == "Biology")
    botany_ir = int(
        next((r for r in after["by_academic_subject"] if r["subject"] == "Botany"), {"in_review": 0})[
            "in_review"
        ]
    )
    assert bio["pipeline"]["in_review"] == botany_ir + int(after_zoo["in_review"])


async def test_queue_combined_subject_status_filter(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get(
        "/api/v1/cms/editorial-review-queue?subject_name=Zoology&status=IN_REVIEW&limit=20&offset=0"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"].get("subject_name") == "Zoology" or body["meta"].get("total", 0) >= 0
    for row in body["data"]:
        subj = (row.get("academic") or {}).get("subject") or {}
        assert subj.get("name") == "Zoology"
        assert row["status"] == "IN_REVIEW"


async def test_student_denied_editorial_campaign(client, register_user):
    await register_user(client)
    resp = await client.get("/api/v1/cms/editorial-campaign")
    assert resp.status_code in (401, 403)
