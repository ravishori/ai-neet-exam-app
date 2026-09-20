"""ECAEP review → approval gate verification (Biology-representative cases).

Runs against trinetra_test_db with SAVEPOINT isolation (conftest): all
workflow commits roll back when the test ends. Does NOT touch the live
Biology batch on trinetra_db.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import ContentWorkflowError, ContentWorkflowService
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

pytestmark = pytest.mark.asyncio(loop_scope="session")

BIO_BATCH = "20260911-BIO11-CH01-B001"


async def _concept_id(db_session) -> uuid.UUID:
    from app.modules.academic.models import Concept

    return (await db_session.execute(select(Concept.id).limit(1))).scalar_one()


async def _author_id(client, db_session, register_user) -> uuid.UUID:
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    return uuid.UUID(user["id"])


def _unverified_body(**kwargs) -> dict:
    body = publishable_question_body(**kwargs)
    body["ncert_evidence"] = {
        "verification_level": "NOT_VERIFIED",
        "source_document": "ncert-books-class-11-biology-chapter-1.pdf",
        "class_level": "11",
        "chapter": "The Living World",
        "section": "1.1",
        "page_number": None,
        "source_excerpt": "What is living? How do we define life?",
        "verification_method": "gemini_jsonl_acquisition_unverified",
        "source_pdf_relpath": "StudyMaterial/ncert-books-class-11-biology-chapter-1.pdf",
    }
    body["provenance"] = {
        "origin": "ai_generated",
        "source": "attached_ncert_pdf",
        "batch_id": BIO_BATCH,
        "validation_process": "UNVERIFIED_ACQUISITION",
        "class_level": "11",
        "chapter": "The Living World",
    }
    return body


async def _create_question(
    service: ContentWorkflowService,
    *,
    author_id: uuid.UUID,
    title: str,
    slug: str,
    body: dict,
    concept_id: uuid.UUID | None,
    tags: list[str] | None = None,
) -> ContentItem:
    return await service.create_item(
        content_type="QUESTION",
        concept_id=concept_id,
        title=title,
        slug=slug,
        tags=tags or [BIO_BATCH, f"batch:{BIO_BATCH}", "question_type:factual", "ncert_level:NOT_VERIFIED"],
        language="en",
        body=body,
        author_id=author_id,
    )


async def test_ecaep_happy_path_and_queue_visibility(client, db_session, register_user):
    """Normal repaired-like QUESTION: DRAFT → submit → IN_REVIEW (queue) → approve.

    Stops before publish (eligibility checked via gates). Fixture rolls back.
    """
    author_id = await _author_id(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    service = ContentWorkflowService(db_session)
    repo = CmsRepository(db_session)

    item = await _create_question(
        service,
        author_id=author_id,
        title=f"ECAEP normal {BIO_BATCH}",
        slug=f"ecaep-normal-{uuid.uuid4().hex[:8]}",
        body=publishable_question_body(stem=f"Normal repaired Biology stem {uuid.uuid4().hex}?"),
        concept_id=concept_id,
        tags=[BIO_BATCH, "question_type:conceptual", "ncert_level:SECTION_VERIFIED"],
    )
    assert item.status == "DRAFT"

    # DRAFT cannot publish
    with pytest.raises(ContentWorkflowError, match="Cannot publish"):
        await service.publish(item.id)

    submitted = await service.submit_for_review(item.id)
    assert submitted.status == "IN_REVIEW"

    # Student path still PUBLISHED-only
    student_items, _ = await repo.list_questions(limit=100, offset=0)
    assert all(i.status == "PUBLISHED" for i in student_items)
    assert submitted.id not in {i.id for i in student_items}

    # Practice pool excludes IN_REVIEW
    pool = await AssessmentRepository(db_session).published_question_ids_for_scope("FULL", None)
    assert submitted.id not in pool

    # AI review queue (canonical CMS path)
    queue_page, queue_total = await repo.list_items_paginated(status="IN_REVIEW", limit=100, offset=0)
    assert any(i.id == submitted.id for i in queue_page) or queue_total >= 1
    assert any(i.id == submitted.id for i in queue_page)

    http_queue = await client.get("/api/v1/cms/ai-review-queue?status=IN_REVIEW&limit=100")
    assert http_queue.status_code == 200, http_queue.text
    assert any(row["id"] == str(submitted.id) for row in http_queue.json()["data"])

    approved = await service.review(item.id, reviewer_id=author_id, decision="approve", comment="ok")
    assert approved.status == "APPROVED"

    # Still not student-visible until publish
    student_items2, _ = await repo.list_questions(limit=100, offset=0)
    assert approved.id not in {i.id for i in student_items2}

    gate = await evaluate_question_publication_gates(
        db_session,
        item_id=approved.id,
        status=approved.status,
        content_type="QUESTION",
        concept_id=approved.concept_id,
        body=(await repo.get_version(approved.latest_version_id)).body,
        tags=list(approved.tags or []),
        model_used=None,
        knowledge_unit_id=None,
    )
    assert gate.review_state_ok is True
    # publishable_question_body uses SECTION_VERIFIED — eligible if other gates pass
    assert gate.ncert_ok is True
    assert gate.taxonomy_ok is True


async def test_ecaep_distractor_style_and_rstar_lineage(client, db_session, register_user):
    """Distractor-style + R* replacement: active DRAFT submits; SUPERSEDED cannot."""
    author_id = await _author_id(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    service = ContentWorkflowService(db_session)

    old = await _create_question(
        service,
        author_id=author_id,
        title=f"ECAEP old Mayr {BIO_BATCH}",
        slug=f"ecaep-old-{uuid.uuid4().hex[:8]}",
        body=_unverified_body(stem=f"Old trivia {uuid.uuid4().hex}?"),
        concept_id=concept_id,
    )
    replacement = await _create_question(
        service,
        author_id=author_id,
        title=f"ECAEP R* replacement {BIO_BATCH}",
        slug=f"ecaep-rstar-{uuid.uuid4().hex[:8]}",
        body=publishable_question_body(
            stem=f"Replacement species concept {uuid.uuid4().hex}?",
            options=[
                {"label": "A", "text": "Biological species concept"},
                {"label": "B", "text": "Only morphology"},
                {"label": "C", "text": "Only fossils"},
                {"label": "D", "text": "Only geography"},
            ],
            correct_option="A",
            explanation="Biological species concept is the intended replacement focus.",
        ),
        concept_id=concept_id,
        tags=[BIO_BATCH, "question_type:comparison", f"external_id:GEMINI-{BIO_BATCH}-R000095"],
    )
    old2, rep2 = await service.supersede_draft(old.id, replacement_item_id=replacement.id, author_id=author_id)
    assert old2.status == "SUPERSEDED"
    assert rep2.status == "DRAFT"
    assert rep2.replaces_id == old.id
    rev = await service.get_replacement_for(old.id)
    assert rev is not None and rev.id == replacement.id

    with pytest.raises(ContentWorkflowError, match="Cannot submit"):
        await service.submit_for_review(old.id)

    with pytest.raises(ContentWorkflowError, match="Cannot publish"):
        await service.publish(old.id)

    distractor = await _create_question(
        service,
        author_id=author_id,
        title=f"ECAEP distractor Q35-like {BIO_BATCH}",
        slug=f"ecaep-q35-{uuid.uuid4().hex[:8]}",
        body=publishable_question_body(
            stem=f"Distractor repair stem {uuid.uuid4().hex}?",
            options=[
                {"label": "A", "text": "Weak distractor A"},
                {"label": "B", "text": "Weak distractor B"},
                {"label": "C", "text": "Correct repaired option"},
                {"label": "D", "text": "Weak distractor D"},
            ],
            correct_option="C",
            explanation="C is correct after distractor repair.",
        ),
        concept_id=concept_id,
    )

    for active in (replacement, distractor):
        submitted = await service.submit_for_review(active.id)
        assert submitted.status == "IN_REVIEW"
        # Lineage intact after submit
        if active.id == replacement.id:
            refreshed = await CmsRepository(db_session).get_item(replacement.id)
            assert refreshed.replaces_id == old.id


async def test_missing_concept_and_ncert_unverified_block_gates(client, db_session, register_user):
    """concept_id missing blocks submit; NOT_VERIFIED blocks publish after approve."""
    author_id = await _author_id(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    service = ContentWorkflowService(db_session)
    repo = CmsRepository(db_session)

    unmapped = await _create_question(
        service,
        author_id=author_id,
        title=f"ECAEP unmapped {BIO_BATCH}",
        slug=f"ecaep-unmapped-{uuid.uuid4().hex[:8]}",
        body=_unverified_body(stem=f"Unmapped {uuid.uuid4().hex}?"),
        concept_id=None,
    )
    from app.core.exceptions import AppError

    with pytest.raises(AppError) as exc:
        await service.submit_for_review(unmapped.id)
    assert exc.value.code == "MISSING_ACADEMIC_MAPPING"
    still = await repo.get_item(unmapped.id)
    assert still.status == "DRAFT"

    unverified = await _create_question(
        service,
        author_id=author_id,
        title=f"ECAEP unverified {BIO_BATCH}",
        slug=f"ecaep-unverified-{uuid.uuid4().hex[:8]}",
        body=_unverified_body(stem=f"Unverified NCERT {uuid.uuid4().hex}?"),
        concept_id=concept_id,
    )
    await service.submit_for_review(unverified.id)
    await service.review(unverified.id, reviewer_id=author_id, decision="approve", comment="approve for gate test")
    approved = await repo.get_item(unverified.id)
    assert approved.status == "APPROVED"

    gate = await evaluate_question_publication_gates(
        db_session,
        item_id=approved.id,
        status=approved.status,
        content_type="QUESTION",
        concept_id=approved.concept_id,
        body=(await repo.get_version(approved.latest_version_id)).body,
        tags=list(approved.tags or []),
        model_used=None,
        knowledge_unit_id=None,
    )
    assert gate.review_state_ok is True
    assert gate.ncert_ok is False
    assert "ncert:NOT_VERIFIED" in gate.reasons

    with pytest.raises(AppError) as pub_exc:
        await service.publish(unverified.id)
    assert pub_exc.value.code == "PUBLICATION_GATES_FAILED"
    assert "ncert:NOT_VERIFIED" in pub_exc.value.message
    after = await repo.get_item(unverified.id)
    assert after.status == "APPROVED"

    # review:not_approved — DRAFT/IN_REVIEW cannot publish
    draft2 = await _create_question(
        service,
        author_id=author_id,
        title=f"ECAEP draft publish block {BIO_BATCH}",
        slug=f"ecaep-draft-pub-{uuid.uuid4().hex[:8]}",
        body=publishable_question_body(stem=f"Draft publish {uuid.uuid4().hex}?"),
        concept_id=concept_id,
    )
    with pytest.raises(ContentWorkflowError, match="Cannot publish"):
        await service.publish(draft2.id)
    await service.submit_for_review(draft2.id)
    with pytest.raises(ContentWorkflowError, match="Cannot publish"):
        await service.publish(draft2.id)
