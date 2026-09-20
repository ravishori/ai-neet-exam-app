"""WAVE-P0-9: Batch A acquisition — DRAFT only, idempotent, no auto-publish."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.cms.acquisition.batch_a_acquisition_service import BatchAAcquisitionService
from app.modules.cms.acquisition.batch_a_catalog import BATCH_A_QUESTIONS, catalog_stats
from app.modules.cms.models import ContentItem
from app.modules.cms.schemas.content_bodies import assert_body_publishable
from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _mini_catalog():
    base = BATCH_A_QUESTIONS[0]
    return [
        {
            **base,
            "source_key": f"test-batch-a-{uuid.uuid4().hex[:8]}",
            "stem": f"Unique test stem for batch A {uuid.uuid4().hex}?",
            "title": "Batch A test question",
        }
    ]


def test_catalog_meets_anti_monoculture_shape():
    stats = catalog_stats()
    assert stats["total"] == 74
    assert stats["chapters"] >= 6
    assert len(stats["by_difficulty"]) >= 2
    # At least Physics, Chemistry, Botany, Zoology chapters represented via keys
    keys = set(stats["by_chapter_key"])
    assert "electrostatics" in keys and "optics" in keys
    assert "equilibrium" in keys and "organic-basics" in keys
    assert "cell" in keys
    assert "animal-kingdom" in keys and "biomolecules" in keys and "human-reproduction" in keys


def test_catalog_bodies_structurally_valid():
    for q in BATCH_A_QUESTIONS:
        body = {
            "stem": q["stem"],
            "options": q["options"],
            "correct_option": q["correct_option"],
            "explanation": q["explanation"],
            "difficulty": q["difficulty"],
        }
        assert_body_publishable("QUESTION", body)


async def test_student_cannot_run_batch_a(client, register_user):
    await register_user(client)
    resp = await client.post("/api/v1/cms/acquisition/batch-a", headers=csrf_headers(client))
    assert resp.status_code in (401, 403), resp.text


async def test_batch_a_creates_draft_only_and_is_idempotent(client, db_session, register_user):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    catalog = _mini_catalog()
    service = BatchAAcquisitionService(db_session)

    report1 = await service.run(author_id=author_id, questions=catalog)
    assert report1["created"] == 1
    assert report1["rejected"] == 0
    item_id = report1["created_items"][0]["id"]

    item = (
        await db_session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.id == uuid.UUID(item_id))
        )
    ).scalar_one()
    assert item.status == "DRAFT"
    assert item.concept_id is not None
    latest = next(v for v in item.versions if v.id == item.latest_version_id)
    assert latest.model_used == "human-authored-batch-a"
    assert latest.workflow_state == "DRAFT"

    report2 = await service.run(author_id=author_id, questions=catalog)
    assert report2["created"] == 0
    assert report2["skipped_duplicate"] == 1

    # Must not be student-visible as published
    published = await client.get(f"/api/v1/cms/concepts/{item.concept_id}/published")
    assert published.status_code == 200
    assert item_id not in [i["id"] for i in published.json()["data"]]


async def test_batch_a_rejects_invalid_body(client, db_session, register_user):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    bad = [
        {
            "source_key": f"bad-{uuid.uuid4().hex[:8]}",
            "chapter_key": "electrostatics",
            "concept_code": "coulomb-force",
            "title": "Bad",
            "stem": "Incomplete?",
            "options": [
                {"label": "A", "text": "only one"},
                {"label": "B", "text": "two"},
            ],
            "correct_option": "A",
            "explanation": "too few options",
            "difficulty": "easy",
        }
    ]
    # Hierarchy must exist first
    service = BatchAAcquisitionService(db_session)
    await service.ensure_hierarchy()
    report = await service.run(author_id=uuid.UUID(user["id"]), questions=bad)
    assert report["created"] == 0
    assert report["rejected"] == 1


async def test_batch_a_api_endpoint(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    # Smoke: endpoint authorized; may create remaining catalog items on shared test DB.
    resp = await client.post("/api/v1/cms/acquisition/batch-a", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["batch_id"] == "acquisition-batch-A-diversify-p0"
    assert data["rules"]["no_auto_publish"] is True
    assert "created" in data and "skipped_duplicate" in data
    for row in data.get("created_items", []):
        assert row["status"] == "DRAFT"
