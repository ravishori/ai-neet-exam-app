"""Server-side QUESTION publication gates (T6-E-FIX).

A QUESTION cannot become PUBLISHED unless all mandatory gates pass.
Frontend disabling is insufficient — this is enforced in ContentWorkflowService.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.cms.schemas.content_bodies import QuestionBody, assert_body_publishable
from app.modules.cms.schemas.question_evidence import NcertEvidence, ProvenanceBlock
from app.modules.cms.services.factory_candidate_validation import stem_hash
from app.modules.cms.services.numerical_validation import classify_and_verify


@dataclass
class PublicationGateReport:
    structural_ok: bool = False
    scientific_ok: bool = False
    ncert_ok: bool = False
    taxonomy_ok: bool = False
    duplicate_ok: bool = False
    provenance_ok: bool = False
    review_state_ok: bool = False
    reasons: list[str] = field(default_factory=list)
    numerical_status: str = "NOT_NUMERICAL"
    ncert_level: str | None = None

    @property
    def passed(self) -> bool:
        return all(
            [
                self.structural_ok,
                self.scientific_ok,
                self.ncert_ok,
                self.taxonomy_ok,
                self.duplicate_ok,
                self.provenance_ok,
                self.review_state_ok,
            ]
        )

    @property
    def content_ready(self) -> bool:
        """Same as `passed` but excludes `review_state_ok` — used by callers
        (e.g. TRUSTED-FACTORY-SUBMIT-001) that need "would this pass publish()
        on content grounds" for a DRAFT/pre-review item, where review_state_ok
        is by definition always false. Never used to skip the actual
        publish()-time review_state_ok check itself."""
        return all(
            [
                self.structural_ok,
                self.scientific_ok,
                self.ncert_ok,
                self.taxonomy_ok,
                self.duplicate_ok,
                self.provenance_ok,
            ]
        )


def _section_from_ncert_ref(ref: str) -> str | None:
    # e.g. "NCERT XI Physics Ch 2 §2.4" → "2.4" or full ref as section anchor
    if "§" in ref:
        return ref.split("§", 1)[1].strip()
    if "Ch" in ref:
        return ref
    return ref or None


async def evaluate_question_publication_gates(
    session: AsyncSession,
    *,
    item_id: uuid.UUID | None,
    status: str,
    content_type: str,
    concept_id: uuid.UUID | None,
    body: dict[str, Any],
    tags: list[str] | None,
    model_used: str | None,
    knowledge_unit_id: uuid.UUID | None,
) -> PublicationGateReport:
    report = PublicationGateReport()
    tags = tags or []

    if content_type != "QUESTION":
        # Non-questions: structural + review only (existing assert_body_publishable path)
        report.structural_ok = True
        report.scientific_ok = True
        report.ncert_ok = True
        report.taxonomy_ok = True
        report.duplicate_ok = True
        report.provenance_ok = True
        report.review_state_ok = status == "APPROVED"
        if not report.review_state_ok:
            report.reasons.append("review:not_approved")
        return report

    report.review_state_ok = status == "APPROVED"
    if not report.review_state_ok:
        report.reasons.append("review:not_approved")

    # Structural
    try:
        assert_body_publishable("QUESTION", body)
        qb = QuestionBody.model_validate(body)
        report.structural_ok = True
    except Exception as exc:  # noqa: BLE001
        report.structural_ok = False
        report.reasons.append(f"structural:{exc}")
        qb = None

    # Taxonomy
    if not concept_id:
        report.taxonomy_ok = False
        report.reasons.append("taxonomy:missing_concept_id")
    else:
        row = (
            await session.execute(
                select(Concept.id, Concept.deleted_at, Subject.code)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .join(Subject, Subject.id == Chapter.subject_id)
                .where(Concept.id == concept_id)
            )
        ).one_or_none()
        if not row or row.deleted_at is not None:
            report.taxonomy_ok = False
            report.reasons.append("taxonomy:concept_missing_or_deleted")
        else:
            report.taxonomy_ok = True

    # Provenance
    prov = None
    if qb and qb.provenance:
        prov = qb.provenance
    if prov and prov.origin.strip() and prov.source.strip():
        report.provenance_ok = True
    elif model_used or knowledge_unit_id:
        report.provenance_ok = True
    elif any(t.startswith("ncert:") or t.startswith("source_pdf:") or t.startswith("validation:") for t in tags):
        report.provenance_ok = True
    else:
        report.provenance_ok = False
        report.reasons.append("provenance:missing")

    # NCERT evidence
    ncert = qb.ncert_evidence if qb else None
    if ncert is None:
        # Tag-only NCERT is insufficient for publish — require structured evidence
        report.ncert_ok = False
        report.reasons.append("ncert:missing_evidence")
    else:
        report.ncert_level = ncert.verification_level
        if ncert.verification_level == "NOT_VERIFIED":
            report.ncert_ok = False
            report.reasons.append("ncert:NOT_VERIFIED")
        elif ncert.verification_level == "PAGE_VERIFIED" and ncert.page_number is None:
            report.ncert_ok = False
            report.reasons.append("ncert:fabricated_page_claim")
        else:
            report.ncert_ok = True

    # Scientific / numerical
    calc = None
    if qb and qb.numerical_evidence and qb.numerical_evidence.calculation_check:
        calc = qb.numerical_evidence.calculation_check
    elif qb and qb.calculation_check:
        calc = qb.calculation_check
    status_n, detail = classify_and_verify(calc)
    report.numerical_status = status_n
    if status_n == "NOT_NUMERICAL":
        report.scientific_ok = True
    elif status_n == "NUMERICAL_COMPLETE":
        report.scientific_ok = True
    elif status_n == "NUMERICAL_INCOMPLETE":
        report.scientific_ok = False
        report.reasons.append(f"scientific:{detail}")
    else:
        report.scientific_ok = False
        report.reasons.append(f"scientific:{detail}")

    # Duplicate vs other published questions
    if qb:
        h = stem_hash(qb.stem)
        if item_id is None:
            stems = (
                await session.execute(
                    text(
                        """
                        SELECT ci.id, cv.body->>'stem' AS stem
                        FROM cms.content_items ci
                        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                        WHERE ci.content_type = 'QUESTION'
                          AND ci.status = 'PUBLISHED'
                          AND ci.deleted_at IS NULL
                          AND cv.body ? 'stem'
                        """
                    )
                )
            ).all()
        else:
            stems = (
                await session.execute(
                    text(
                        """
                        SELECT ci.id, cv.body->>'stem' AS stem
                        FROM cms.content_items ci
                        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                        WHERE ci.content_type = 'QUESTION'
                          AND ci.status = 'PUBLISHED'
                          AND ci.deleted_at IS NULL
                          AND cv.body ? 'stem'
                          AND ci.id <> CAST(:exclude_id AS uuid)
                        """
                    ),
                    {"exclude_id": str(item_id)},
                )
            ).all()
        dup = any(stem_hash(s) == h for _, s in stems if s)
        if dup:
            report.duplicate_ok = False
            report.reasons.append("duplicate:published_stem")
        else:
            report.duplicate_ok = True
    else:
        report.duplicate_ok = False
        report.reasons.append("duplicate:unvalidated_body")

    return report


async def assert_question_publishable(
    session: AsyncSession,
    *,
    item_id: uuid.UUID | None,
    status: str,
    content_type: str,
    concept_id: uuid.UUID | None,
    body: dict[str, Any],
    tags: list[str] | None,
    model_used: str | None,
    knowledge_unit_id: uuid.UUID | None,
) -> PublicationGateReport:
    report = await evaluate_question_publication_gates(
        session,
        item_id=item_id,
        status=status,
        content_type=content_type,
        concept_id=concept_id,
        body=body,
        tags=tags,
        model_used=model_used,
        knowledge_unit_id=knowledge_unit_id,
    )
    if content_type != "QUESTION":
        return report
    if not report.passed:
        raise AppError(
            "QUESTION failed mandatory publication gates: " + "; ".join(report.reasons),
            code="PUBLICATION_GATES_FAILED",
            status_code=422,
        )
    return report


_CLASS_LEVEL_ROMAN = {"11": "XI", "12": "XII"}


def build_section_ncert_evidence(
    *,
    ncert_reference: str,
    source_pdf_relpath: str,
    class_level: str = "11",
    subject: str = "Physics",
) -> dict[str, Any]:
    """SECTION_VERIFIED evidence — never invents page numbers.

    `class_level` and `subject` default to the values this helper's
    original two callers (physics_t6d_bank.py, cms/seed.py) always used —
    both are Physics-XI-only, so their behavior is unchanged. Callers with
    other subjects/classes (e.g. the bulk-generated corpus) must pass
    both explicitly, sourced only from data already on the blueprint
    (neet_ug_2026.subject, chapter.class_level) — never invented.
    """
    section = _section_from_ncert_ref(ncert_reference)
    chapter = ncert_reference
    roman_class = _CLASS_LEVEL_ROMAN.get(class_level, class_level)
    source_document = f"NCERT Class {roman_class} {subject}"
    ev = NcertEvidence(
        verification_level="SECTION_VERIFIED",
        source_document=source_document,
        document_version="reprint-on-disk",
        class_level=class_level,
        chapter=chapter,
        section=section,
        page_number=None,
        source_excerpt=None,
        verification_method=f"Gate-4 section reference + Class {roman_class} PDF on disk",
        source_pdf_relpath=source_pdf_relpath,
    )
    return ev.model_dump()


def build_test_provenance(*, batch_id: str = "unit-test") -> dict[str, Any]:
    return ProvenanceBlock(
        origin="human_authored_test",
        source="unit-test-fixture",
        batch_id=batch_id,
        validation_process="unit-test",
        verification_process="unit-test",
    ).model_dump()
