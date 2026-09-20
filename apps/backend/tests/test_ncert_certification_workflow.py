"""Canonical APPROVED-state NCERT certification workflow tests.

Uses trinetra_test_db SAVEPOINT isolation — does not touch live Biology batch.
"""

from __future__ import annotations

import copy
import uuid

import pytest
from sqlalchemy import select

from helpers_publishable_question import publishable_question_body
from app.core.exceptions import AppError
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import (
    ContentWorkflowError,
    ContentWorkflowService,
)
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
        "section": "1.1 What is Living?",
        "page_number": None,
        "source_excerpt": "The living world is rich in variety.",
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


async def _create_and_approve(
    service: ContentWorkflowService,
    *,
    author_id: uuid.UUID,
    title: str,
    slug: str,
    body: dict,
    concept_id: uuid.UUID | None,
    tags: list[str] | None = None,
) -> ContentItem:
    item = await service.create_item(
        content_type="QUESTION",
        concept_id=concept_id,
        title=title,
        slug=slug,
        tags=tags or [BIO_BATCH, f"batch:{BIO_BATCH}", "question_type:factual"],
        language="en",
        body=body,
        author_id=author_id,
    )
    await service.submit_for_review(item.id)
    return await service.review(
        item.id, reviewer_id=author_id, decision="approve", comment="test approve"
    )


def _identity(body: dict) -> dict:
    return {
        k: copy.deepcopy(body.get(k))
        for k in ("stem", "options", "correct_option", "explanation", "difficulty")
    }


async def test_certify_approved_not_verified_succeeds(client, db_session, register_user):
    author_id = await _author_id(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    service = ContentWorkflowService(db_session)
    body = _unverified_body()
    before_id = _identity(body)
    item = await _create_and_approve(
        service,
        author_id=author_id,
        title="certify ok",
        slug=f"cert-ok-{uuid.uuid4().hex[:8]}",
        body=body,
        concept_id=concept_id,
    )
    assert item.status == "APPROVED"

    result = await service.certify_ncert_evidence(
        item.id, actor_user_id=author_id, required_batch_id=BIO_BATCH, commit=True
    )
    assert result["changed"] is True
    assert result["previous_verification_level"] == "NOT_VERIFIED"
    assert result["new_verification_level"] == "SOURCE_TEXT_VERIFIED"
    assert result["status"] == "APPROVED"
    assert result["operation"] == "certify_ncert_evidence"

    refreshed = await service.repo.get_item(item.id)
    latest = await service.repo.get_version(refreshed.latest_version_id)
    assert latest.body["ncert_evidence"]["verification_level"] == "SOURCE_TEXT_VERIFIED"
    assert _identity(latest.body) == before_id
    assert refreshed.concept_id == concept_id
    assert refreshed.status == "APPROVED"
    assert latest.body["provenance"]["batch_id"] == BIO_BATCH
    assert latest.body["provenance"]["origin"] == "ai_generated"
    assert latest.body["provenance"]["source"] == "attached_ncert_pdf"

    gate = await evaluate_question_publication_gates(
        db_session,
        item_id=refreshed.id,
        status=refreshed.status,
        content_type="QUESTION",
        concept_id=refreshed.concept_id,
        body=latest.body,
        tags=list(refreshed.tags or []),
        model_used=latest.model_used,
        knowledge_unit_id=latest.knowledge_unit_id,
    )
    assert "ncert:NOT_VERIFIED" not in gate.reasons
    assert gate.ncert_ok is True
    assert refreshed.status != "PUBLISHED"


async def test_certify_rejects_draft_in_review_superseded_published(
    client, db_session, register_user
):
    author_id = await _author_id(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    service = ContentWorkflowService(db_session)

    draft = await service.create_item(
        content_type="QUESTION",
        concept_id=concept_id,
        title="draft",
        slug=f"cert-draft-{uuid.uuid4().hex[:8]}",
        tags=[BIO_BATCH],
        language="en",
        body=_unverified_body(),
        author_id=author_id,
    )
    with pytest.raises(ContentWorkflowError):
        await service.certify_ncert_evidence(draft.id, actor_user_id=author_id)

    in_review = await service.submit_for_review(draft.id)
    with pytest.raises(ContentWorkflowError):
        await service.certify_ncert_evidence(in_review.id, actor_user_id=author_id)

    approved = await service.review(
        in_review.id, reviewer_id=author_id, decision="approve", comment="ok"
    )

    superseded = await service.create_item(
        content_type="QUESTION",
        concept_id=concept_id,
        title="superseded",
        slug=f"cert-sup-{uuid.uuid4().hex[:8]}",
        tags=[BIO_BATCH],
        language="en",
        body=_unverified_body(),
        author_id=author_id,
    )
    superseded.status = "SUPERSEDED"
    await db_session.flush()
    with pytest.raises(ContentWorkflowError):
        await service.certify_ncert_evidence(superseded.id, actor_user_id=author_id)

    await service.certify_ncert_evidence(approved.id, actor_user_id=author_id)
    published = await service.publish(approved.id)
    assert published.status == "PUBLISHED"
    with pytest.raises(ContentWorkflowError):
        await service.certify_ncert_evidence(published.id, actor_user_id=author_id)


async def test_certify_rejects_wrong_batch_and_missing(client, db_session, register_user):
    author_id = await _author_id(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    service = ContentWorkflowService(db_session)
    item = await _create_and_approve(
        service,
        author_id=author_id,
        title="wrong batch",
        slug=f"cert-wb-{uuid.uuid4().hex[:8]}",
        body=_unverified_body(),
        concept_id=concept_id,
        tags=["OTHER-BATCH"],
    )
    with pytest.raises(AppError) as exc:
        await service.certify_ncert_evidence(
            item.id, actor_user_id=author_id, required_batch_id=BIO_BATCH
        )
    assert exc.value.code == "BATCH_MISMATCH"

    with pytest.raises(AppError) as exc2:
        await service.certify_ncert_evidence(uuid.uuid4(), actor_user_id=author_id)
    assert exc2.value.code == "NOT_FOUND"


async def test_certify_idempotent(client, db_session, register_user):
    author_id = await _author_id(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    service = ContentWorkflowService(db_session)
    item = await _create_and_approve(
        service,
        author_id=author_id,
        title="idem",
        slug=f"cert-idem-{uuid.uuid4().hex[:8]}",
        body=_unverified_body(),
        concept_id=concept_id,
    )
    r1 = await service.certify_ncert_evidence(item.id, actor_user_id=author_id)
    assert r1["changed"] is True
    latest1 = await service.repo.get_version(
        (await service.repo.get_item(item.id)).latest_version_id
    )
    body1 = copy.deepcopy(latest1.body)

    r2 = await service.certify_ncert_evidence(item.id, actor_user_id=author_id)
    assert r2["changed"] is False
    assert r2["already_certified"] is True
    latest2 = await service.repo.get_version(
        (await service.repo.get_item(item.id)).latest_version_id
    )
    assert latest2.body == body1


async def test_certify_atomic_batch_success_and_rollback(client, db_session, register_user):
    author_id = await _author_id(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    service = ContentWorkflowService(db_session)

    items = []
    for i in range(3):
        items.append(
            await _create_and_approve(
                service,
                author_id=author_id,
                title=f"batch {i}",
                slug=f"cert-batch-{i}-{uuid.uuid4().hex[:8]}",
                body=_unverified_body(),
                concept_id=concept_id,
            )
        )

    for it in items:
        await service.certify_ncert_evidence(it.id, actor_user_id=author_id, commit=False)
    await db_session.commit()
    for it in items:
        latest = await service.repo.get_version(
            (await service.repo.get_item(it.id)).latest_version_id
        )
        assert latest.body["ncert_evidence"]["verification_level"] == "SOURCE_TEXT_VERIFIED"

    a = await _create_and_approve(
        service,
        author_id=author_id,
        title="roll a",
        slug=f"cert-roll-a-{uuid.uuid4().hex[:8]}",
        body=_unverified_body(),
        concept_id=concept_id,
    )
    b = await _create_and_approve(
        service,
        author_id=author_id,
        title="roll b",
        slug=f"cert-roll-b-{uuid.uuid4().hex[:8]}",
        body=_unverified_body(),
        concept_id=concept_id,
    )
    draft = await service.create_item(
        content_type="QUESTION",
        concept_id=concept_id,
        title="roll fail",
        slug=f"cert-roll-fail-{uuid.uuid4().hex[:8]}",
        tags=[BIO_BATCH],
        language="en",
        body=_unverified_body(),
        author_id=author_id,
    )

    nested = await db_session.begin_nested()
    try:
        await service.certify_ncert_evidence(a.id, actor_user_id=author_id, commit=False)
        await service.certify_ncert_evidence(b.id, actor_user_id=author_id, commit=False)
        with pytest.raises(ContentWorkflowError):
            await service.certify_ncert_evidence(draft.id, actor_user_id=author_id, commit=False)
        await nested.rollback()
    except Exception:
        await nested.rollback()
        raise

    await db_session.refresh(a)
    await db_session.refresh(b)
    for it in (a, b):
        latest = await service.repo.get_version(
            (await service.repo.get_item(it.id)).latest_version_id
        )
        assert latest.body["ncert_evidence"]["verification_level"] == "NOT_VERIFIED"


async def test_certify_does_not_publish_or_expose_students(client, db_session, register_user):
    author_id = await _author_id(client, db_session, register_user)
    concept_id = await _concept_id(db_session)
    service = ContentWorkflowService(db_session)
    item = await _create_and_approve(
        service,
        author_id=author_id,
        title="no pub",
        slug=f"cert-nopub-{uuid.uuid4().hex[:8]}",
        body=_unverified_body(),
        concept_id=concept_id,
        tags=[BIO_BATCH, "class:11"],
    )
    await service.certify_ncert_evidence(item.id, actor_user_id=author_id)
    refreshed = await service.repo.get_item(item.id)
    assert refreshed.status == "APPROVED"

    pool = set(await AssessmentRepository(db_session).published_question_ids_for_scope("FULL", None))
    assert refreshed.id not in pool

    page, _tot = await CmsRepository(db_session).list_questions(
        class_level="11", limit=100, offset=0
    )
    assert all(i.id != refreshed.id for i in page)
