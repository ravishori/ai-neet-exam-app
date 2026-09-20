"""CMS content-items list: optional pilot_run_id provenance filter (read-only)."""

from __future__ import annotations

import uuid

from helpers_publishable_question import publishable_question_body

import pytest
from sqlalchemy import select

from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.ingestion.models import IngestionJob, IngestionSection
from app.modules.knowledge.models import KnowledgeUnit

pytestmark = pytest.mark.asyncio(loop_scope="session")

AUTHORIZED_RUN = "phase-d-30-mcq-authorized-20260825"
HISTORICAL_RUN = "phase-d-30-mcq-v1"
AUTHORIZED_COUNT = 30
HISTORICAL_COUNT = 5


async def _any_concept_id(db_session) -> uuid.UUID:
    from app.modules.academic.models import Concept

    return (await db_session.execute(select(Concept.id).limit(1))).scalar_one()


async def _author_id(db_session) -> uuid.UUID:
    from app.modules.identity.models.user import User

    return (await db_session.execute(select(User.id).limit(1))).scalar_one()


async def _seed_pilot_draft_questions(
    db_session,
    *,
    pilot_run_id: str,
    count: int,
    concept_id: uuid.UUID,
    author_id: uuid.UUID,
    title_prefix: str,
) -> list[str]:
    """Create DRAFT QUESTIONS linked via KU lineage to a job with pilot_run_id."""
    job = IngestionJob(
        source_file_path=f"pilot-filter-test/{pilot_run_id}.pdf",
        file_checksum=uuid.uuid4().hex,
        status="COMPLETED",
        pilot_run_id=pilot_run_id,
        target_mcq_count=count,
    )
    db_session.add(job)
    await db_session.flush()

    section = IngestionSection(
        job_id=job.id,
        heading="Pilot filter test section",
        source_page=1,
        raw_text="NCERT grounded fixture text for pilot run filter tests.",
        matched_concept_id=concept_id,
    )
    db_session.add(section)
    await db_session.flush()

    unit = KnowledgeUnit(
        version=1,
        content_hash=uuid.uuid4().hex,
        structured_facts=["Fixture fact for pilot filter."],
        summary="Fixture KU summary.",
        source_section_id=section.id,
        concept_id=concept_id,
        extraction_confidence=0.95,
        validation_status="PASSED",
    )
    db_session.add(unit)
    await db_session.commit()

    service = ContentWorkflowService(db_session)
    ids: list[str] = []
    for i in range(count):
        item = await service.create_item(
            content_type="QUESTION",
            concept_id=concept_id,
            title=f"{title_prefix} {i + 1}",
            slug=f"{title_prefix.lower().replace(' ', '-')}-{uuid.uuid4().hex[:10]}",
            tags=["ai-generated", "ingested", "pilot-filter-test"],
            language="en",
            body={
                "stem": f"Fixture stem {i + 1} for {pilot_run_id}?",
                "options": [
                    {"label": "A", "text": "One"},
                    {"label": "B", "text": "Two"},
                    {"label": "C", "text": "Three"},
                    {"label": "D", "text": "Four"},
                ],
                "correct_option": "A",
                "explanation": "Fixture explanation grounded in section text.",
                "difficulty": "MEDIUM",
            },
            author_id=author_id,
            knowledge_unit_refs=[(unit.id, 1)],
        )
        ids.append(str(item.id))
    return ids


async def test_pilot_run_id_omitted_unchanged_behavior(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    before = await client.get("/api/v1/cms/content-items", params={"limit": 5, "offset": 0})
    assert before.status_code == 200, before.text
    assert "total" in before.json()["meta"]
    assert len(before.json()["data"]) <= 5


async def test_authorized_pilot_returns_exactly_30(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    author_id = await _author_id(db_session)
    seeded = await _seed_pilot_draft_questions(
        db_session,
        pilot_run_id=AUTHORIZED_RUN,
        count=AUTHORIZED_COUNT,
        concept_id=concept_id,
        author_id=author_id,
        title_prefix="Authorized Pilot Q",
    )
    assert len(seeded) == AUTHORIZED_COUNT

    resp = await client.get(
        "/api/v1/cms/content-items",
        params={"pilot_run_id": AUTHORIZED_RUN, "limit": 100, "offset": 0},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["total"] == AUTHORIZED_COUNT
    assert len(body["data"]) == AUTHORIZED_COUNT
    returned = {row["id"] for row in body["data"]}
    assert returned == set(seeded)


async def test_historical_pilot_returns_historical_only(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    author_id = await _author_id(db_session)
    historical = await _seed_pilot_draft_questions(
        db_session,
        pilot_run_id=HISTORICAL_RUN,
        count=HISTORICAL_COUNT,
        concept_id=concept_id,
        author_id=author_id,
        title_prefix="Historical Pilot Q",
    )

    resp = await client.get(
        "/api/v1/cms/content-items",
        params={"pilot_run_id": HISTORICAL_RUN, "limit": 100, "offset": 0},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["total"] == HISTORICAL_COUNT
    assert {row["id"] for row in body["data"]} == set(historical)


async def test_authorized_and_historical_never_mix(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    author_id = await _author_id(db_session)
    auth_run = f"mix-auth-{uuid.uuid4().hex[:8]}"
    hist_run = f"mix-hist-{uuid.uuid4().hex[:8]}"
    auth_ids = await _seed_pilot_draft_questions(
        db_session,
        pilot_run_id=auth_run,
        count=3,
        concept_id=concept_id,
        author_id=author_id,
        title_prefix="Mix Auth Q",
    )
    hist_ids = await _seed_pilot_draft_questions(
        db_session,
        pilot_run_id=hist_run,
        count=4,
        concept_id=concept_id,
        author_id=author_id,
        title_prefix="Mix Hist Q",
    )

    auth_resp = await client.get("/api/v1/cms/content-items", params={"pilot_run_id": auth_run, "limit": 50})
    hist_resp = await client.get("/api/v1/cms/content-items", params={"pilot_run_id": hist_run, "limit": 50})
    auth_set = {row["id"] for row in auth_resp.json()["data"]}
    hist_set = {row["id"] for row in hist_resp.json()["data"]}
    assert auth_set == set(auth_ids)
    assert hist_set == set(hist_ids)
    assert auth_set.isdisjoint(hist_set)


async def test_nonexistent_pilot_run_returns_zero(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get(
        "/api/v1/cms/content-items",
        params={"pilot_run_id": "does-not-exist-pilot-run-xyz", "limit": 20},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["meta"]["total"] == 0
    assert resp.json()["data"] == []


async def test_draft_question_authorized_pilot_exactly_30(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    author_id = await _author_id(db_session)
    seeded = await _seed_pilot_draft_questions(
        db_session,
        pilot_run_id=AUTHORIZED_RUN,
        count=AUTHORIZED_COUNT,
        concept_id=concept_id,
        author_id=author_id,
        title_prefix="Combo Filter Q",
    )

    resp = await client.get(
        "/api/v1/cms/content-items",
        params={
            "pilot_run_id": AUTHORIZED_RUN,
            "status": "DRAFT",
            "content_type": "QUESTION",
            "limit": 100,
            "offset": 0,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["total"] == AUTHORIZED_COUNT
    assert len(body["data"]) == AUTHORIZED_COUNT
    assert all(row["status"] == "DRAFT" for row in body["data"])
    assert all(row["content_type"] == "QUESTION" for row in body["data"])
    assert {row["id"] for row in body["data"]} == set(seeded)


async def test_status_and_content_type_still_work_with_pilot_filter(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    author_id = await _author_id(db_session)
    run_id = f"status-type-{uuid.uuid4().hex[:8]}"
    await _seed_pilot_draft_questions(
        db_session,
        pilot_run_id=run_id,
        count=2,
        concept_id=concept_id,
        author_id=author_id,
        title_prefix="Status Type Q",
    )

    draft_q = await client.get(
        "/api/v1/cms/content-items",
        params={"pilot_run_id": run_id, "status": "DRAFT", "content_type": "QUESTION"},
    )
    assert draft_q.json()["meta"]["total"] == 2

    published = await client.get(
        "/api/v1/cms/content-items",
        params={"pilot_run_id": run_id, "status": "PUBLISHED", "content_type": "QUESTION"},
    )
    assert published.json()["meta"]["total"] == 0

    notes = await client.get(
        "/api/v1/cms/content-items",
        params={"pilot_run_id": run_id, "content_type": "CONCEPT_NOTE"},
    )
    assert notes.json()["meta"]["total"] == 0


async def test_pilot_filter_pagination_counts(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _any_concept_id(db_session)
    author_id = await _author_id(db_session)
    run_id = f"page-{uuid.uuid4().hex[:8]}"
    seeded = await _seed_pilot_draft_questions(
        db_session,
        pilot_run_id=run_id,
        count=5,
        concept_id=concept_id,
        author_id=author_id,
        title_prefix="Page Q",
    )

    page1 = await client.get(
        "/api/v1/cms/content-items",
        params={"pilot_run_id": run_id, "limit": 2, "offset": 0},
    )
    page2 = await client.get(
        "/api/v1/cms/content-items",
        params={"pilot_run_id": run_id, "limit": 2, "offset": 2},
    )
    page3 = await client.get(
        "/api/v1/cms/content-items",
        params={"pilot_run_id": run_id, "limit": 2, "offset": 4},
    )
    assert page1.json()["meta"]["total"] == 5
    assert page2.json()["meta"]["total"] == 5
    assert page3.json()["meta"]["total"] == 5
    assert len(page1.json()["data"]) == 2
    assert len(page2.json()["data"]) == 2
    assert len(page3.json()["data"]) == 1
    all_ids = (
        {r["id"] for r in page1.json()["data"]}
        | {r["id"] for r in page2.json()["data"]}
        | {r["id"] for r in page3.json()["data"]}
    )
    assert all_ids == set(seeded)


async def test_pilot_filter_requires_content_create_permission(client, db_session, register_user):
    await register_user(client, db_session=db_session)  # STUDENT
    resp = await client.get(
        "/api/v1/cms/content-items",
        params={"pilot_run_id": AUTHORIZED_RUN},
    )
    assert resp.status_code == 403
