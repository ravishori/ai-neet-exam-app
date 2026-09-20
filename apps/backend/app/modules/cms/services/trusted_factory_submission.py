"""TRUSTED-FACTORY-SUBMIT-001 — narrow, explicit eligibility check for a
Content Factory-generated DRAFT question to enter IN_REVIEW without a
redundant EVALUATOR LLM call.

Context: the EVALUATOR's own output is advisory-only (never gates any
ECAEP transition — see submit_for_review()/ai_check_service.py), and its
only non-redundant dimension (open-ended factual/scientific judgment) is
exactly the one it never actually blocks on. Every other check it nominally
performs (NCERT alignment, scientific/numerical consistency, structural
soundness) already has a stronger, evidence-grounded deterministic
equivalent that runs at generation time and/or in the publish() gate set.

This module answers ONE narrow question: does this specific item already
deterministically satisfy everything publish() would require on content
grounds (i.e. everything except review_state_ok, which cannot be true yet
for a DRAFT item)? Trust is never inferred from status=DRAFT alone — every
criterion is checked explicitly against real generation/publication
records. Read-only: performs no writes, no LLM calls, no status changes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cms.models.content_factory import GenerationJob, GenerationRun
from app.modules.cms.models.content_factory_planning import QuestionBlueprint
from app.modules.cms.models.content_item import ContentItem
from app.modules.cms.models.content_version import ContentVersion
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

_UNVERIFIED_LEVELS = (None, "NOT_VERIFIED")


@dataclass
class TrustedFactoryEligibility:
    eligible: bool = False
    reasons: list[str] = field(default_factory=list)
    generation_job_id: uuid.UUID | None = None
    generation_run_id: uuid.UUID | None = None
    blueprint_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None


async def evaluate_trusted_factory_submission(
    session: AsyncSession,
    item_id: uuid.UUID,
    *,
    expected_batch_id: uuid.UUID | None = None,
) -> TrustedFactoryEligibility:
    """Every criterion is an explicit, narrow, server-side check against
    real records — never inferred from status=DRAFT alone.

    `expected_batch_id`, when supplied, must match the item's actual
    generation batch — this is how a caller's "explicit batch/item
    selection" is enforced rather than trusted blindly: even if a caller
    passes a batch_id, an item that doesn't actually belong to it is
    rejected, not silently reassigned.
    """
    out = TrustedFactoryEligibility()

    item = await session.get(ContentItem, item_id)
    if item is None:
        out.reasons.append("NOT_FOUND")
        return out
    if item.content_type != "QUESTION":
        out.reasons.append("NOT_QUESTION")
        return out
    if item.status != "DRAFT":
        out.reasons.append("NOT_DRAFT")
        return out
    if not item.concept_id:
        out.reasons.append("MISSING_CONCEPT_ID")
        return out

    if not item.latest_version_id:
        out.reasons.append("NO_VERSION")
        return out
    latest = await session.get(ContentVersion, item.latest_version_id)
    if latest is None:
        out.reasons.append("NO_VERSION")
        return out

    candidate = (
        await session.execute(
            select(GenerationCandidate).where(GenerationCandidate.content_item_id == item.id)
        )
    ).scalar_one_or_none()
    if candidate is None:
        out.reasons.append("NO_GENERATION_CANDIDATE")
        return out

    out.generation_job_id = candidate.job_id
    out.generation_run_id = candidate.run_id
    out.blueprint_id = candidate.blueprint_id
    out.batch_id = candidate.batch_id

    if expected_batch_id is not None and candidate.batch_id != expected_batch_id:
        out.reasons.append("BATCH_MISMATCH")
        return out

    job = await session.get(GenerationJob, candidate.job_id)
    if job is None or job.status != "SUCCEEDED":
        out.reasons.append("GENERATION_JOB_NOT_SUCCEEDED")
        return out

    run = await session.get(GenerationRun, candidate.run_id)
    if run is None or run.status != "SUCCEEDED":
        out.reasons.append("GENERATION_RUN_NOT_SUCCEEDED")
        return out

    blueprint = await session.get(QuestionBlueprint, candidate.blueprint_id)
    if blueprint is None:
        out.reasons.append("BLUEPRINT_NOT_FOUND")
        return out
    constraints = blueprint.constraints or {}
    if not bool(constraints.get("ncert_derived")):
        out.reasons.append("NOT_NCERT_DERIVED")
        return out
    if not constraints.get("ncert_source_path"):
        out.reasons.append("NO_NCERT_SOURCE_PATH")
        return out

    body = latest.body or {}
    ncert_evidence = body.get("ncert_evidence")
    if not ncert_evidence:
        out.reasons.append("NO_NCERT_EVIDENCE")
        return out
    if ncert_evidence.get("verification_level") in _UNVERIFIED_LEVELS:
        out.reasons.append("NCERT_EVIDENCE_NOT_VERIFIED")
        return out

    gate_report = await evaluate_question_publication_gates(
        session,
        item_id=item.id,
        status=item.status,
        content_type=item.content_type,
        concept_id=item.concept_id,
        body=body,
        tags=list(item.tags or []),
        model_used=latest.model_used,
        knowledge_unit_id=latest.knowledge_unit_id,
    )
    if not gate_report.content_ready:
        out.reasons.append("PUBLICATION_GATES_NOT_MET:" + ";".join(gate_report.reasons))
        return out

    out.eligible = True
    return out
