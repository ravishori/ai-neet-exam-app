"""WAVE-P0-10: Batch A SME pilot — read-only selection; no status mutation."""

from __future__ import annotations

import uuid

from helpers_publishable_question import publishable_question_body

import pytest

from app.modules.cms.acquisition.batch_a_acquisition_service import BatchAAcquisitionService
from app.modules.cms.acquisition.batch_a_catalog import BATCH_A_QUESTIONS, MODEL_USED
from app.modules.cms.acquisition.batch_a_pilot import PILOT_TARGETS, build_pilot_report, select_pilot
from app.modules.cms.models import ContentItem
from sqlalchemy import select

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _catalog_slice(n: int = 8) -> list[dict]:
    """Small unique catalog for isolation (not full 74)."""
    out = []
    for q in BATCH_A_QUESTIONS[:n]:
        out.append(
            {
                **q,
                "source_key": f"pilot-test-{uuid.uuid4().hex[:10]}",
                "stem": f"Pilot test stem {uuid.uuid4().hex}?",
                "title": f"Pilot test {q['chapter_key']}",
            }
        )
    return out


def test_select_pilot_diversifies_when_enough_per_subject():
    """Unit: selection respects targets and does not invent statuses."""
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    items = []
    subjects = [("Physics", "Electrostatics"), ("Chemistry", "Equilibrium"), ("Botany", "Cell"), ("Zoology", "Animal Kingdom")]
    for subj, chap in subjects:
        for i in range(12):
            items.append(
                {
                    "id": str(uuid.uuid4()),
                    "slug": f"batch-a-x-{subj}-{i}",
                    "title": f"{subj} Q{i}",
                    "status": "DRAFT",
                    "subject": subj,
                    "chapter": f"{chap} {i % 2}",
                    "topic": f"Topic {i % 3}",
                    "concept": f"Concept {i}",
                    "concept_id": str(uuid.uuid4()),
                    "difficulty": ["easy", "medium", "hard"][i % 3],
                    "structural": {"valid": True, "review_ready": True, "issues": []},
                    "provenance": {"has_lineage": True, "status": "known"},
                    "model_used": MODEL_USED,
                    "created_at": now,
                }
            )
    report = select_pilot(items)
    assert report["selected_count"] == 40
    assert report["distributions"]["subject"] == PILOT_TARGETS
    assert report["rules"]["no_auto_approve"] is True
    assert report["rules"]["checklist_does_not_approve"] is True
    # Remaining outside pilot
    assert report["remaining_batch_a_untouched"] == len(items) - 40


async def test_student_cannot_view_batch_a_pilot(client, register_user):
    await register_user(client)
    resp = await client.get("/api/v1/cms/editorial-batch-a-pilot")
    assert resp.status_code in (401, 403), resp.text


async def test_pilot_endpoint_read_only_for_reviewer(client, db_session, register_user):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    catalog = _catalog_slice(4)
    await BatchAAcquisitionService(db_session).run(author_id=author_id, questions=catalog)
    await db_session.commit()

    before = (
        await db_session.execute(
            select(ContentItem.status).where(ContentItem.slug.in_([f"batch-a-{q['source_key']}" for q in catalog]))
        )
    ).scalars().all()
    assert all(s == "DRAFT" for s in before)

    resp = await client.get("/api/v1/cms/editorial-batch-a-pilot")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["pilot_id"] == "batch-a-sme-pilot-40"
    assert "selected" in data
    assert data["rules"]["no_bulk_publish"] is True

    after = (
        await db_session.execute(
            select(ContentItem.status).where(ContentItem.slug.in_([f"batch-a-{q['source_key']}" for q in catalog]))
        )
    ).scalars().all()
    assert after == before


async def test_queue_pilot_only_filter(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get(
        "/api/v1/cms/editorial-review-queue",
        params={"status": "DRAFT", "pilot_only": "true", "limit": 50},
    )
    assert resp.status_code == 200, resp.text
    meta = resp.json()["meta"]
    assert meta.get("pilot_only") is True


async def test_build_pilot_report_does_not_mutate(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    catalog = _catalog_slice(3)
    report_create = await BatchAAcquisitionService(db_session).run(author_id=author_id, questions=catalog)
    await db_session.commit()
    ids = [uuid.UUID(r["id"]) for r in report_create["created_items"]]

    statuses_before = {
        str(i.id): i.status
        for i in (
            await db_session.execute(select(ContentItem).where(ContentItem.id.in_(ids)))
        ).scalars()
    }

    await build_pilot_report(db_session)

    statuses_after = {
        str(i.id): i.status
        for i in (
            await db_session.execute(select(ContentItem).where(ContentItem.id.in_(ids)))
        ).scalars()
    }
    assert statuses_after == statuses_before
