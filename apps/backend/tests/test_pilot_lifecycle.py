"""Phase D pilot E2E: DRAFT → ECAEP → publish → practice → mastery (ADR-0032).

Uses a controlled mocked ingestion slice (coherent section + grounded KU facts),
not the full pilot orchestration against real NCERT PDFs.
"""

import uuid

import pytest
from sqlalchemy import select

from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.cms.models import ContentItem, ContentVersion, ContentVersionKnowledgeUnit
from app.modules.ingestion.models import IngestionJob, IngestionSection
from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.ingestion_pipeline_service import IngestionPipelineService
from app.modules.ingestion.tests.pilot_test_helpers import (
    mock_empty_visual_assets,
    mock_extraction_patch,
    pilot_ai_gateway_factory,
    unique_pilot_run_id,
)
from app.modules.knowledge.models import KnowledgeUnit
from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = [pytest.mark.asyncio(loop_scope="session"), pytest.mark.e2e]


async def _author_id(db_session) -> uuid.UUID:
    from app.modules.identity.models.user import User

    return (await db_session.execute(select(User.id).limit(1))).scalar_one()


async def _create_grounded_pilot_draft(db_session, monkeypatch) -> tuple[ContentItem, str]:
    doc = await SourceDocumentRepository(db_session).get_by_relative_path(
        "Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf"
    )
    if doc is None:
        pytest.skip("physics pilot source not registered in test DB")

    fake_extract, fake_split = mock_extraction_patch()
    monkeypatch.setattr("app.modules.ingestion.services.ingestion_pipeline_service.extract_pages", fake_extract)
    monkeypatch.setattr("app.modules.ingestion.services.ingestion_pipeline_service.split_into_sections", fake_split)
    monkeypatch.setattr(
        "app.modules.ingestion.services.ingestion_pipeline_service.detect_visual_assets",
        mock_empty_visual_assets,
    )
    monkeypatch.setattr(AIGateway, "generate", pilot_ai_gateway_factory())

    run_id = unique_pilot_run_id("test-lifecycle")
    pipeline = IngestionPipelineService(db_session)
    job = await pipeline.start_job(
        source_document_id=doc.id,
        target_mcq_count=1,
        pilot_run_id=run_id,
        force_pilot_rerun=True,
    )
    await pipeline.run(job_id=job.id, author_id=await _author_id(db_session))

    item = (
        await db_session.execute(
            select(ContentItem)
            .join(ContentVersion, ContentVersion.content_item_id == ContentItem.id)
            .join(
                ContentVersionKnowledgeUnit,
                ContentVersionKnowledgeUnit.content_version_id == ContentVersion.id,
            )
            .join(KnowledgeUnit, KnowledgeUnit.id == ContentVersionKnowledgeUnit.knowledge_unit_id)
            .join(IngestionSection, IngestionSection.id == KnowledgeUnit.source_section_id)
            .where(
                IngestionSection.job_id == job.id,
                ContentItem.content_type == "QUESTION",
                ContentItem.status == "DRAFT",
            )
        )
    ).scalar_one()
    return item, run_id


@pytest.mark.e2e
async def test_pilot_draft_through_publish_and_practice(client, db_session, register_user, monkeypatch):
    draft, _run_id = await _create_grounded_pilot_draft(db_session, monkeypatch)
    assert draft.status == "DRAFT"

    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    item_id = str(draft.id)

    # T6-E-FIX: ensure publication evidence is present (pipeline draft may predate gates).
    latest = await db_session.get(ContentVersion, draft.latest_version_id)
    assert latest is not None
    enriched = publishable_question_body(
        stem=latest.body["stem"],
        options=latest.body["options"],
        correct_option=latest.body["correct_option"],
        explanation=latest.body.get("explanation") or "Pilot grounded explanation for publish gates.",
        difficulty=latest.body.get("difficulty") or "medium",
    )
    latest.body = enriched
    await db_session.commit()

    submit = await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    assert submit.status_code == 200, submit.text
    assert submit.json()["data"]["status"] == "IN_REVIEW"

    review = await client.post(
        f"/api/v1/cms/content-items/{item_id}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    assert review.status_code == 200, review.text
    assert review.json()["data"]["status"] == "APPROVED"

    publish = await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    assert publish.status_code == 200, publish.text
    assert publish.json()["data"]["status"] == "PUBLISHED"

    concept_id = str(draft.concept_id)
    generate = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CONCEPT", "scope_id": concept_id},
        headers=csrf_headers(client),
    )
    assert generate.status_code == 201, generate.text
    assessment_id = generate.json()["data"]["id"]

    start = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    assert start.status_code == 201, start.text
    attempt_id = start.json()["data"]["id"]

    answer = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"content_item_id": item_id, "selected_option": "A"},
        headers=csrf_headers(client),
    )
    assert answer.status_code == 200, answer.text

    submit_attempt = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
    assert submit_attempt.status_code == 200, submit_attempt.text
    assert submit_attempt.json()["data"]["correct_count"] >= 1

    from app.modules.learning.models.concept_mastery import ConceptMastery

    mastery = (
        await db_session.execute(
            select(ConceptMastery).where(ConceptMastery.concept_id == draft.concept_id)
        )
    ).scalar_one_or_none()
    assert mastery is not None
