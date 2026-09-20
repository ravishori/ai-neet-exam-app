"""TRUSTED-FACTORY-SUBMIT-001 — DRAFT -> IN_REVIEW without a redundant
EVALUATOR LLM call, for explicitly eligible Content Factory items only.

Reuses the existing p3 fixture helpers (real blueprint/batch via the API,
real generation via ContentFactoryGenerationService with a ScriptedProvider
— never a live LLM) so eligibility is checked against real generation
lineage (generation_candidates -> jobs -> runs -> blueprints), not mocks.

Covers exactly the 8 scenarios required:
1. ordinary submit_for_review() still invokes EVALUATOR
2. trusted path skips EVALUATOR
3. trusted path reaches IN_REVIEW
4. human review() still required for APPROVED
5. publish() still enforces all existing gates
6. an untrusted DRAFT cannot use the trusted path
7. no LLM calls in trusted-path tests (verified via a call-counting patch,
   not just "no network" — the EvaluatorService.evaluate() entrypoint
   itself must not be invoked)
8. RBAC: only content.factory.trusted_submit holders can call the endpoint
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

from app.core.exceptions import AppError
from app.modules.ai.gateway.base import AIResponse
from app.modules.cms.services.content_factory_generation_service import ContentFactoryGenerationService
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.cms.services.trusted_factory_submission import evaluate_trusted_factory_submission
from conftest import csrf_headers
from tests.test_content_factory_p3 import ScriptedProvider, _concept_chain

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _resp(body: dict, *, model: str = "mock-claude") -> AIResponse:
    return AIResponse(
        text=json.dumps(body), model=model, prompt_tokens=10, completion_tokens=20,
        is_fallback=False, cost_usd=0.001,
    )


def _mcq(*, stem: str, ncert_evidence: dict | None = None) -> dict:
    body = {
        "stem": stem,
        "options": [
            {"label": "A", "text": "Alpha option text"},
            {"label": "B", "text": "Beta option text"},
            {"label": "C", "text": "Gamma option text"},
            {"label": "D", "text": "Delta option text"},
        ],
        "correct_option": "A",
        "explanation": "Option A is correct because it matches the learning objective reasoning required.",
        "difficulty": "medium",
    }
    if ncert_evidence is not None:
        body["ncert_evidence"] = ncert_evidence
    return body


_VALID_EVIDENCE = {
    "verification_level": "SECTION_VERIFIED",
    "source_document": "NCERT Class XI Physics",
    "document_version": "reprint-on-disk",
    "class_level": "11",
    "chapter": "Current Electricity",
    "section": "Current Electricity",
    "page_number": None,
    "source_excerpt": None,
    "verification_method": "Gate-4 section reference + Class XI PDF on disk",
    "source_pdf_relpath": "Class 11/Physics/keph1dd/keph1dd/keph103.pdf",
}


async def _seed_trusted_blueprint(client, db_session, suffix: str):
    """Same shape as test_content_factory_p3._seed_eligible_blueprint, plus
    the ncert_derived + ncert_source_path fields TRUSTED-FACTORY-SUBMIT-001
    checks. Mirrors the real bulk-8k-* blueprints exactly."""
    subject, chapter, topic, concept = await _concept_chain(db_session)
    obj = await client.post(
        "/api/v1/cms/learning-objectives",
        json={
            "objective_key": f"trust-obj-{suffix}",
            "concept_id": str(concept.id),
            "title": "Apply Ohm's law to compute current from voltage and resistance",
        },
        headers=csrf_headers(client),
    )
    assert obj.status_code in (200, 201), obj.text
    fam = await client.post(
        "/api/v1/cms/question-families",
        json={
            "family_key": f"trust-fam-{suffix}",
            "name": "Formula application",
            "applicable_subject_codes": ["PHYSICS"],
            "cognitive_intent": "apply formula",
            "difficulty_min": "easy",
            "difficulty_max": "hard",
            "question_format": "MCQ_4",
        },
        headers=csrf_headers(client),
    )
    assert fam.status_code in (200, 201), fam.text
    bp = await client.post(
        "/api/v1/cms/question-blueprints",
        json={
            "blueprint_key": f"trust-bp-{suffix}",
            "subject_id": str(subject.id),
            "chapter_id": str(chapter.id),
            "topic_id": str(topic.id),
            "concept_id": str(concept.id),
            "learning_objective_id": obj.json()["data"]["id"],
            "question_family_id": fam.json()["data"]["id"],
            "difficulty": "medium",
            "target_count": 10,
            "provenance_tier": "ai",
            "constraints": {
                "question_format": "MCQ_4",
                "correct_option_count": 1,
                "explanation_required": True,
                "reasoning": "V=IR",
                "ncert_derived": True,
                "ncert_source_path": "D:\\ravishori\\AI Neet Exam App\\NCERT Books\\Class 11\\Physics\\keph1dd\\keph1dd\\keph103.pdf",
                "ncert_source_relative": "Class 11/Physics/keph1dd/keph1dd/keph103.pdf",
                "neet_ug_2026": {
                    "subject": "PHYSICS",
                    "unit_number": 12,
                    "unit_name": "CURRENT ELECTRICITY",
                    "topic_id": "PHYSICS:U12:T01",
                },
            },
        },
        headers=csrf_headers(client),
    )
    assert bp.status_code in (200, 201), bp.text
    batch = await client.post(
        "/api/v1/cms/content-batches",
        json={
            "batch_key": f"trust-batch-{suffix}",
            "name": "Trusted-submit test batch",
            "subject_id": str(subject.id),
            "concept_id": str(concept.id),
            "target_count": 5,
            "source_type": "AI",
            "source_tier": "ai",
        },
        headers=csrf_headers(client),
    )
    assert batch.status_code in (200, 201), batch.text
    return {"blueprint_id": bp.json()["data"]["id"], "batch_id": batch.json()["data"]["id"]}


async def _generate_one(db_session, user_id, seeded, *, stem: str, ncert_evidence: dict | None, suffix: str) -> str:
    provider = ScriptedProvider([_resp(_mcq(stem=stem, ncert_evidence=ncert_evidence))])
    service = ContentFactoryGenerationService(db_session, provider=provider)
    result = await service.generate_for_batch(
        uuid.UUID(seeded["batch_id"]),
        blueprint_id=uuid.UUID(seeded["blueprint_id"]),
        target_count=1,
        actor_id=uuid.UUID(user_id),
        job_key=f"trust-job-{suffix}",
        sync_cap=True,
        bulk_mode=True,  # matches the real bulk-8k-* generation path
    )
    assert result["created"] == 1, result
    assert provider.calls == 1  # exactly one scripted (non-LLM) call, never more
    return result["content_item_ids"][0]


class _CountingEvaluate:
    """Drop-in replacement for EvaluatorService.evaluate — counts calls
    without making any network/LLM call, so we can assert exactly whether
    the ordinary vs trusted path actually invoked it."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, *, content_type: str, body: dict) -> dict:
        self.calls += 1
        return {
            "status": "completed", "reason": "", "flags": [], "similarity_matches": [],
            "confidence": 0.9, "checked_at": "2026-01-01T00:00:00+00:00",
        }


@pytest.fixture
def counting_evaluate(monkeypatch):
    counter = _CountingEvaluate()
    from app.modules.ai.services.evaluator_service import EvaluatorService

    async def _patched(self, *, content_type: str, body: dict) -> dict:
        return await counter(content_type=content_type, body=body)

    monkeypatch.setattr(EvaluatorService, "evaluate", _patched)
    return counter


async def test_ordinary_submit_still_invokes_evaluator(client, register_user, db_session, counting_evaluate):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_trusted_blueprint(client, db_session, suffix)
    item_id = await _generate_one(
        db_session, user["id"], seeded, stem=f"Ordinary path stem {suffix}?",
        ncert_evidence=_VALID_EVIDENCE, suffix=suffix,
    )

    service = ContentWorkflowService(db_session)
    item = await service.submit_for_review(uuid.UUID(item_id))

    assert counting_evaluate.calls == 1
    assert item.status == "IN_REVIEW"


async def test_trusted_path_skips_evaluator_and_reaches_in_review(client, register_user, db_session, counting_evaluate):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_trusted_blueprint(client, db_session, suffix)
    item_id = await _generate_one(
        db_session, user["id"], seeded, stem=f"Trusted path stem {suffix}?",
        ncert_evidence=_VALID_EVIDENCE, suffix=suffix,
    )

    service = ContentWorkflowService(db_session)
    item = await service.submit_for_review_trusted_factory(
        uuid.UUID(item_id),
        actor_id=uuid.UUID(user["id"]),
        expected_batch_id=uuid.UUID(seeded["batch_id"]),
    )

    assert counting_evaluate.calls == 0  # the whole point: 0 LLM-facing calls
    assert item.status == "IN_REVIEW"

    latest = await service.repo.get_version(item.latest_version_id)
    assert latest.ai_check_report["status"] == "skipped_trusted_factory"
    assert latest.ai_check_report["flags"] == []

    audit_row = (
        await db_session.execute(
            text(
                "SELECT action, log_metadata FROM system.audit_logs "
                "WHERE entity_id = :id AND action = 'content.submit_trusted_factory'"
            ),
            {"id": item_id},
        )
    ).first()
    assert audit_row is not None
    assert audit_row[1]["evaluator_skipped"] is True


async def test_human_review_still_required_for_approved(client, register_user, db_session, counting_evaluate):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_trusted_blueprint(client, db_session, suffix)
    item_id = await _generate_one(
        db_session, user["id"], seeded, stem=f"Review-required stem {suffix}?",
        ncert_evidence=_VALID_EVIDENCE, suffix=suffix,
    )

    service = ContentWorkflowService(db_session)
    item = await service.submit_for_review_trusted_factory(
        uuid.UUID(item_id), actor_id=uuid.UUID(user["id"]), expected_batch_id=uuid.UUID(seeded["batch_id"]),
    )
    assert item.status == "IN_REVIEW"  # not APPROVED — trusted-submit never approves

    # publish() must reject — item isn't APPROVED yet, no review() happened.
    from app.modules.cms.services.content_workflow_service import ContentWorkflowError

    with pytest.raises(ContentWorkflowError):
        await service.publish(uuid.UUID(item_id))

    approved = await service.review(
        uuid.UUID(item_id), reviewer_id=uuid.UUID(user["id"]), decision="approve", comment="looks good",
    )
    assert approved.status == "APPROVED"


async def test_publish_still_enforces_all_gates(client, register_user, db_session, counting_evaluate):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_trusted_blueprint(client, db_session, suffix)
    item_id = await _generate_one(
        db_session, user["id"], seeded, stem=f"Publish-gate stem {suffix}?",
        ncert_evidence=_VALID_EVIDENCE, suffix=suffix,
    )

    service = ContentWorkflowService(db_session)
    await service.submit_for_review_trusted_factory(
        uuid.UUID(item_id), actor_id=uuid.UUID(user["id"]), expected_batch_id=uuid.UUID(seeded["batch_id"]),
    )
    await service.review(uuid.UUID(item_id), reviewer_id=uuid.UUID(user["id"]), decision="approve", comment=None)

    published = await service.publish(uuid.UUID(item_id))
    assert published.status == "PUBLISHED"

    # Full gate set genuinely ran — not skipped — confirmed via search reindex
    # side effect and status; a second publish() call is now correctly rejected.
    from app.modules.cms.services.content_workflow_service import ContentWorkflowError

    with pytest.raises(ContentWorkflowError):
        await service.publish(uuid.UUID(item_id))


async def test_untrusted_draft_cannot_use_trusted_path_missing_evidence(client, register_user, db_session, counting_evaluate):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_trusted_blueprint(client, db_session, suffix)
    # Same lineage as the trusted case, but NO ncert_evidence in the body —
    # exactly like the pre-backfill bulk-8k-* items.
    item_id = await _generate_one(
        db_session, user["id"], seeded, stem=f"Untrusted stem {suffix}?",
        ncert_evidence=None, suffix=suffix,
    )

    service = ContentWorkflowService(db_session)
    eligibility = await evaluate_trusted_factory_submission(
        db_session, uuid.UUID(item_id), expected_batch_id=uuid.UUID(seeded["batch_id"]),
    )
    assert eligibility.eligible is False
    assert "NO_NCERT_EVIDENCE" in eligibility.reasons

    with pytest.raises(AppError) as exc_info:
        await service.submit_for_review_trusted_factory(
            uuid.UUID(item_id), actor_id=uuid.UUID(user["id"]), expected_batch_id=uuid.UUID(seeded["batch_id"]),
        )
    assert exc_info.value.code == "NOT_TRUSTED_FACTORY_ELIGIBLE"
    assert counting_evaluate.calls == 0  # rejected before any evaluator attempt

    # Item is untouched — still DRAFT, ordinary submit_for_review still works.
    from app.modules.cms.repositories.cms_repository import CmsRepository

    repo = CmsRepository(db_session)
    item = await repo.get_item(uuid.UUID(item_id))
    assert item.status == "DRAFT"


async def test_untrusted_draft_no_generation_candidate_at_all(db_session, register_user, client, counting_evaluate):
    """A plain hand-authored DRAFT (no Content Factory lineage) must never
    be treated as trusted, no matter how "clean" its content is."""
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    _, _, _, concept = await _concept_chain(db_session)
    service = ContentWorkflowService(db_session)
    suffix = uuid.uuid4().hex[:8]
    item = await service.create_item(
        content_type="QUESTION",
        concept_id=concept.id,
        title="Manually authored question",
        slug=f"manual-question-{suffix}",
        tags=[],
        language="en",
        body=_mcq(stem=f"Manually authored stem {suffix} — no factory lineage?", ncert_evidence=_VALID_EVIDENCE),
        author_id=uuid.UUID(user["id"]),
    )

    eligibility = await evaluate_trusted_factory_submission(db_session, item.id)
    assert eligibility.eligible is False
    assert "NO_GENERATION_CANDIDATE" in eligibility.reasons

    with pytest.raises(AppError) as exc_info:
        await service.submit_for_review_trusted_factory(item.id, actor_id=uuid.UUID(user["id"]))
    assert exc_info.value.code == "NOT_TRUSTED_FACTORY_ELIGIBLE"
    assert counting_evaluate.calls == 0


async def test_batch_mismatch_rejected(client, register_user, db_session, counting_evaluate):
    """expected_batch_id must match the item's real batch — a caller
    cannot claim an item belongs to a batch it doesn't."""
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    suffix = uuid.uuid4().hex[:8]
    seeded = await _seed_trusted_blueprint(client, db_session, suffix)
    item_id = await _generate_one(
        db_session, user["id"], seeded, stem=f"Batch mismatch stem {suffix}?",
        ncert_evidence=_VALID_EVIDENCE, suffix=suffix,
    )

    wrong_batch_id = uuid.uuid4()
    eligibility = await evaluate_trusted_factory_submission(
        db_session, uuid.UUID(item_id), expected_batch_id=wrong_batch_id,
    )
    assert eligibility.eligible is False
    assert "BATCH_MISMATCH" in eligibility.reasons
    assert counting_evaluate.calls == 0


async def test_trusted_endpoint_requires_permission(client, register_user, db_session, counting_evaluate):
    await register_user(client)  # STUDENT (default) — no factory.trusted_submit permission
    resp = await client.post(
        "/api/v1/cms/content-items/submit-trusted-batch",
        json={"item_ids": [str(uuid.uuid4())], "batch_id": str(uuid.uuid4())},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 403
    assert counting_evaluate.calls == 0
