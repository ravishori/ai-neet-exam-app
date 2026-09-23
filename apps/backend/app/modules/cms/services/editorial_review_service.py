"""WAVE-P0-6 — human ECAEP editorial review helpers.

Does not approve or publish. Surfaces queue prioritization, structural
readiness, provenance as stored, suspected duplicates, and a checklist
template. AI check reports are assistance only — never scientific certification.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.modules.cms.models import ContentItem, ContentReview, ContentVersion
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.schemas.content_bodies import validate_body
from app.modules.cms.services.draft_disposition import (
    intake_code_for_draft,
    ncert_state_from_evidence,
    readiness_label_for_question,
)

# Human checklist — assist only; never auto-certifies publish readiness.
REVIEW_CHECKLIST: list[dict[str, str]] = [
    {
        "id": "sci_correct",
        "category": "Scientific correctness",
        "prompt": "Independently verify: is the answer scientifically correct? (Structural validity ≠ scientific validity.)",
    },
    {
        "id": "sci_syllabus",
        "category": "NCERT / NEET alignment",
        "prompt": "Verify relevance to the intended NCERT/NEET syllabus and chapter — do not assume from title alone.",
    },
    {
        "id": "sci_unique",
        "category": "Answer",
        "prompt": "Verify the marked correct option is the only defensible answer.",
    },
    {
        "id": "q_distractors",
        "category": "Distractors",
        "prompt": "Verify incorrect options are plausible, unambiguous, and free of accidental clues.",
    },
    {"id": "q_clear", "category": "Question quality", "prompt": "Is the wording clear and unambiguous?"},
    {"id": "q_difficulty", "category": "Question quality", "prompt": "Is the difficulty appropriate?"},
    {"id": "neet_style", "category": "NEET suitability", "prompt": "Is the examination style and conceptual depth appropriate?"},
    {"id": "map_subject", "category": "Academic mapping", "prompt": "Verify subject / chapter / topic / concept mapping is correct."},
    {
        "id": "expl_ok",
        "category": "Explanation",
        "prompt": "Verify the explanation is accurate, clear, rigorous, and consistent with the answer.",
    },
    {
        "id": "prov_ok",
        "category": "Provenance",
        "prompt": "Verify source information as stored — never invent NTA/official claims. Flag if source verification is required.",
    },
]

# Planning targets for the human campaign (WAVE-P0-7). Not auto-publish quotas.
CAMPAIGN_TARGET_PER_AREA = 25
# Biology = Botany + Zoology in the academic seed (NEET UG).
CAMPAIGN_AREAS: dict[str, tuple[str, ...]] = {
    "Physics": ("Physics",),
    "Chemistry": ("Chemistry",),
    "Biology": ("Botany", "Zoology"),
}

PRIORITIZATION_EXPLAINED = (
    "Order: (1) structurally valid body, (2) concept mapped, (3) known version lineage "
    "(model_used or knowledge_unit_id), (4) campaign subject area below target, "
    "(5) chapters with fewer PUBLISHED questions, (6) difficulty diversification hint, "
    "(7) older pending items first. "
    "Reasons are shown per item. Scores assist triage only — they do not certify scientific correctness "
    "and never auto-approve or auto-publish."
)


def campaign_area_for_subject(subject_name: str | None) -> str | None:
    if not subject_name:
        return None
    for area, subjects in CAMPAIGN_AREAS.items():
        if subject_name in subjects:
            return area
    return None


def _priority_reasons(
    *,
    structural_valid: bool,
    mapped: bool,
    has_lineage: bool,
    campaign_area: str | None,
    subject_published: int,
    subject_remaining: int,
    chapter_name: str | None,
    chapter_published: int,
    difficulty: str | None,
) -> list[str]:
    reasons: list[str] = []
    if structural_valid:
        reasons.append("Structurally valid body")
    else:
        reasons.append("Structural issues — fix before prioritizing for publish")
    if mapped:
        reasons.append("Academic concept mapping present")
    else:
        reasons.append("Missing academic mapping")
    if has_lineage:
        reasons.append("Known provenance lineage on version")
    else:
        reasons.append("Source verification required — provenance lineage missing")
    if campaign_area and subject_remaining > 0:
        reasons.append(
            f"{campaign_area} is below target ({subject_published}/{CAMPAIGN_TARGET_PER_AREA}; "
            f"{subject_remaining} remaining)"
        )
    elif campaign_area:
        reasons.append(f"{campaign_area} has already met the planning target ({subject_published}/{CAMPAIGN_TARGET_PER_AREA})")
    if chapter_name is not None:
        if chapter_published == 0:
            reasons.append(f"Chapter “{chapter_name}” currently has no published questions")
        elif chapter_published < 3:
            reasons.append(f"Chapter “{chapter_name}” has low published coverage ({chapter_published})")
        elif chapter_published >= 8:
            reasons.append(f"Chapter “{chapter_name}” is already concentrated ({chapter_published} published) — prefer diversification")
    if difficulty:
        reasons.append(f"Difficulty: {difficulty}")
    return reasons


def _priority_tuple(
    *,
    structural_valid: bool,
    mapped: bool,
    has_lineage: bool,
    subject_remaining: int,
    chapter_published: int,
    difficulty: str | None,
    created_at,
) -> tuple:
    diff_rank = {"easy": 0, "medium": 1, "hard": 2}.get((difficulty or "").lower(), 1)
    return (
        0 if structural_valid else 1,
        0 if mapped else 1,
        0 if has_lineage else 1,
        0 if subject_remaining > 0 else 1,  # below-target areas first
        -subject_remaining,  # more remaining → earlier (ascending sort)
        chapter_published,  # fewer published → earlier
        diff_rank,
        created_at.timestamp() if created_at else 0.0,
    )


def _structural_assessment(content_type: str, body: dict | None, concept_id: uuid.UUID | None) -> dict[str, Any]:
    issues: list[str] = []
    if not body:
        issues.append("Missing body")
        return {"valid": False, "issues": issues, "review_ready": False}

    try:
        validate_body(content_type, body)
    except ValidationError as exc:
        issues.extend(err.get("msg", str(err)) for err in exc.errors())
    except Exception as exc:  # noqa: BLE001 — surface unexpected schema failures as issues
        issues.append(str(exc))

    if content_type == "QUESTION" and not concept_id:
        issues.append("Missing academic concept mapping")

    valid = len(issues) == 0
    return {"valid": valid, "issues": issues, "review_ready": valid}


def _provenance_from_version(version: ContentVersion | None) -> dict[str, Any]:
    if not version:
        return {
            "model_used": None,
            "knowledge_unit_id": None,
            "knowledge_unit_version": None,
            "prompt_version": None,
            "confidence_score": None,
            "generation_cost_usd": None,
            "has_lineage": False,
            "status": "missing",
        }
    has_lineage = bool(version.model_used or version.knowledge_unit_id)
    return {
        "model_used": version.model_used,
        "knowledge_unit_id": str(version.knowledge_unit_id) if version.knowledge_unit_id else None,
        "knowledge_unit_version": version.knowledge_unit_version,
        "prompt_version": version.prompt_version,
        "confidence_score": version.confidence_score,
        "generation_cost_usd": version.generation_cost_usd,
        "has_lineage": has_lineage,
        "status": "known" if has_lineage else "missing",
    }


class EditorialReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CmsRepository(session)

    async def chapter_question_counts(self) -> dict[uuid.UUID, dict[str, Any]]:
        """Published/draft/in_review QUESTION counts keyed by chapter_id."""
        from app.modules.academic.models import Chapter, Concept, Subject, Topic

        rows = await self.session.execute(
            select(
                Chapter.id,
                Chapter.name,
                Subject.name.label("subject_name"),
                ContentItem.status,
                func.count(ContentItem.id),
            )
            .select_from(ContentItem)
            .join(Concept, Concept.id == ContentItem.concept_id)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.deleted_at.is_(None),
                ContentItem.status.in_(("DRAFT", "IN_REVIEW", "APPROVED", "PUBLISHED", "CHANGES_REQUESTED")),
            )
            .group_by(Chapter.id, Chapter.name, Subject.name, ContentItem.status)
        )
        out: dict[uuid.UUID, dict[str, Any]] = {}
        for chapter_id, chapter_name, subject_name, status, count in rows.all():
            bucket = out.setdefault(
                chapter_id,
                {
                    "chapter_id": str(chapter_id),
                    "chapter_name": chapter_name,
                    "subject_name": subject_name,
                    "draft": 0,
                    "in_review": 0,
                    "approved": 0,
                    "published": 0,
                    "changes_requested": 0,
                    "total_non_archived": 0,
                },
            )
            key = {
                "DRAFT": "draft",
                "IN_REVIEW": "in_review",
                "APPROVED": "approved",
                "PUBLISHED": "published",
                "CHANGES_REQUESTED": "changes_requested",
            }.get(status)
            if key:
                bucket[key] = int(count)
                bucket["total_non_archived"] += int(count)
        return out

    async def find_suspected_duplicates(self, item: ContentItem, stem: str | None, *, limit: int = 8) -> list[dict]:
        """Exact stem match among non-archived QUESTIONS — human decides; never auto-reject."""
        if not stem or not stem.strip():
            return []
        stem_norm = stem.strip()
        result = await self.session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.deleted_at.is_(None),
                ContentItem.status != "ARCHIVED",
                ContentItem.id != item.id,
            )
            .limit(200)
        )
        suspects: list[dict] = []
        for other in result.scalars().unique().all():
            by_id = {v.id: v for v in other.versions}
            latest = by_id.get(other.latest_version_id)
            other_stem = (latest.body or {}).get("stem") if latest else None
            if isinstance(other_stem, str) and other_stem.strip() == stem_norm:
                suspects.append(
                    {
                        "id": str(other.id),
                        "title": other.title,
                        "status": other.status,
                        "stem_preview": other_stem[:160],
                    }
                )
            if len(suspects) >= limit:
                break
        return suspects

    async def list_reviews_for_version(self, version_id: uuid.UUID | None) -> list[dict]:
        if not version_id:
            return []
        result = await self.session.execute(
            select(ContentReview).where(ContentReview.content_version_id == version_id).order_by(ContentReview.reviewed_at.desc())
        )
        return [
            {
                "id": str(r.id),
                "reviewer_id": str(r.reviewer_id) if r.reviewer_id else None,
                "decision": r.decision,
                "comment": r.comment,
                "reviewed_at": r.reviewed_at,
            }
            for r in result.scalars().all()
        ]

    async def list_queue(
        self,
        *,
        status: str | None = "IN_REVIEW",
        subject_id: uuid.UUID | None = None,
        subject_name: str | None = None,
        chapter_id: uuid.UUID | None = None,
        topic_id: uuid.UUID | None = None,
        difficulty: str | None = None,
        provenance: str | None = None,  # any | known | missing
        review_readiness: str | None = None,  # any | structurally_ready | needs_work
        batch_tag: str | None = None,
        pilot_only: bool = False,
        content_type: str = "QUESTION",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int, dict]:
        from app.modules.academic.models import Chapter, Concept, Subject, Topic
        from app.modules.cms.acquisition.batch_a_catalog import BATCH_ID, MODEL_USED

        if subject_name and not subject_id:
            subject_id = await self._resolve_subject_id(subject_name)

        pilot_ids: set[str] | None = None
        if pilot_only:
            from app.modules.cms.acquisition.batch_a_pilot import build_pilot_report

            pilot_report = await build_pilot_report(self.session)
            pilot_ids = {row["id"] for row in pilot_report["selected"]}

        query = (
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.content_type == content_type, ContentItem.deleted_at.is_(None))
        )
        if status:
            query = query.where(ContentItem.status == status)
        else:
            # "any" actionable editorial statuses — exclude published/archived noise
            query = query.where(
                ContentItem.status.in_(("DRAFT", "IN_REVIEW", "CHANGES_REQUESTED", "APPROVED"))
            )

        needs_join = any(v is not None for v in (subject_id, chapter_id, topic_id))
        if needs_join:
            query = (
                query.join(Concept, Concept.id == ContentItem.concept_id)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .join(Subject, Subject.id == Chapter.subject_id)
            )
            if subject_id:
                query = query.where(Subject.id == subject_id)
            if chapter_id:
                query = query.where(Chapter.id == chapter_id)
            if topic_id:
                query = query.where(Topic.id == topic_id)

        result = await self.session.execute(query.order_by(ContentItem.created_at.asc()).limit(500))
        items = list(result.scalars().unique().all())
        chapter_counts = await self.chapter_question_counts()
        area_published = await self._campaign_area_published_counts()
        concept_ids = [i.concept_id for i in items if i.concept_id]
        names = await self.repo.academic_names_for_concepts(concept_ids)

        scored: list[tuple[tuple, dict]] = []
        for item in items:
            if pilot_ids is not None and str(item.id) not in pilot_ids:
                continue
            tags = item.tags or []
            by_id = {v.id: v for v in item.versions}
            latest = by_id.get(item.latest_version_id)
            if batch_tag:
                model_used = latest.model_used if latest else None
                is_batch = batch_tag in tags or (
                    batch_tag == BATCH_ID and (model_used == MODEL_USED or (item.slug or "").startswith("batch-a-"))
                )
                if not is_batch:
                    continue

            body = latest.body if latest else {}
            structural = _structural_assessment(item.content_type, body, item.concept_id)
            provenance_info = _provenance_from_version(latest)
            ncert = ncert_state_from_evidence(tags=tags, body=body if isinstance(body, dict) else None)
            academic = names.get(item.concept_id) if item.concept_id else None
            chapter_meta = None
            chapter_published = 0
            chapter_name = None
            subject_name_resolved = None
            if academic and academic.get("chapter"):
                ch_id = uuid.UUID(academic["chapter"]["id"])
                chapter_meta = chapter_counts.get(ch_id)
                chapter_published = int(chapter_meta["published"]) if chapter_meta else 0
                chapter_name = academic["chapter"].get("name")
            if academic and academic.get("subject"):
                subject_name_resolved = academic["subject"].get("name")

            if difficulty and (body or {}).get("difficulty", "").lower() != difficulty.lower():
                continue
            if provenance == "known" and not provenance_info["has_lineage"]:
                continue
            if provenance == "missing" and provenance_info["has_lineage"]:
                continue
            if review_readiness == "structurally_ready" and not structural["review_ready"]:
                continue
            if review_readiness == "needs_work" and structural["review_ready"]:
                continue

            area = campaign_area_for_subject(subject_name_resolved)
            published_in_area = area_published.get(area, 0) if area else 0
            remaining = max(0, CAMPAIGN_TARGET_PER_AREA - published_in_area) if area else 0
            reasons = _priority_reasons(
                structural_valid=structural["valid"],
                mapped=bool(item.concept_id),
                has_lineage=provenance_info["has_lineage"],
                campaign_area=area,
                subject_published=published_in_area,
                subject_remaining=remaining,
                chapter_name=chapter_name,
                chapter_published=chapter_published,
                difficulty=(body or {}).get("difficulty"),
            )
            is_batch_a = BATCH_ID in tags or (latest and latest.model_used == MODEL_USED)
            if is_batch_a:
                reasons = [
                    "Human-authored Batch A — SME review required",
                    "Not official NTA/NCERT content",
                    *reasons,
                ]

            blocking = []
            if not structural["valid"]:
                blocking.extend(structural["issues"])
            if not item.concept_id:
                blocking.append("Missing academic concept mapping")
            if not ncert["is_verified"]:
                blocking.append("NCERT verification not established (provenance ≠ NCERT certification)")

            row = {
                "id": str(item.id),
                "title": item.title,
                "content_type": item.content_type,
                "status": item.status,
                "language": item.language,
                "difficulty": (body or {}).get("difficulty"),
                "academic": {
                    "subject": academic.get("subject") if academic else None,
                    "chapter": academic.get("chapter") if academic else None,
                    "topic": academic.get("topic") if academic else None,
                    "concept": academic.get("concept") if academic else None,
                    "class_level": academic.get("class_level") if academic else None,
                },
                "campaign_area": area,
                "batch_a": is_batch_a,
                "structural": structural,
                "provenance": {
                    "status": provenance_info["status"],
                    "has_lineage": provenance_info["has_lineage"],
                    "model_used": latest.model_used if latest else None,
                    "label": "Human-authored Batch A" if is_batch_a else None,
                },
                "ncert": {
                    "verification_level": ncert["verification_level"],
                    "is_verified": ncert["is_verified"],
                    "disclaimer": ncert["disclaimer"],
                },
                "blocking_reasons": blocking,
                "ai_check_flags": (latest.ai_check_report or {}).get("flags", []) if latest else [],
                "ai_check_status": (latest.ai_check_report or {}).get("status") if latest else None,
                "chapter_inventory": chapter_meta,
                "explanation_present": bool((body or {}).get("explanation")),
                "priority_reasons": reasons,
                "created_at": item.created_at,
            }
            key = _priority_tuple(
                structural_valid=structural["valid"],
                mapped=bool(item.concept_id),
                has_lineage=provenance_info["has_lineage"],
                subject_remaining=remaining,
                chapter_published=chapter_published,
                difficulty=(body or {}).get("difficulty"),
                created_at=item.created_at,
            )
            scored.append((key, row))

        scored.sort(key=lambda pair: pair[0])
        total = len(scored)
        page = [row for _, row in scored[offset : offset + limit]]
        recommended = page[0] if page and offset == 0 else None
        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "subject_id": str(subject_id) if subject_id else None,
            "subject_name": subject_name,
            "prioritization": PRIORITIZATION_EXPLAINED,
            "ai_disclaimer": "AI check flags are assistance only — not scientific certification or publish authority.",
            "recommended_next": (
                {
                    "id": recommended["id"],
                    "title": recommended["title"],
                    "priority_reasons": recommended["priority_reasons"],
                }
                if recommended
                else None
            ),
            "quality_vs_science": (
                "STRUCTURAL VALIDITY is automated field/shape checking only. "
                "SCIENTIFIC VALIDITY requires human SME judgement and is never auto-certified."
            ),
            "no_auto_approve": True,
            "no_auto_publish": True,
            "pilot_only": pilot_only,
            "batch_tag": batch_tag,
        }
        return page, total, meta

    async def _resolve_subject_id(self, subject_name: str) -> uuid.UUID | None:
        from app.modules.academic.models import Subject

        result = await self.session.execute(
            select(Subject.id).where(func.lower(Subject.name) == subject_name.strip().lower()).limit(1)
        )
        return result.scalar_one_or_none()

    async def _campaign_area_published_counts(self) -> dict[str, int]:
        """PUBLISHED QUESTION counts rolled up into Physics / Chemistry / Biology."""
        from app.modules.academic.models import Chapter, Concept, Subject, Topic

        rows = await self.session.execute(
            select(Subject.name, func.count(ContentItem.id))
            .select_from(ContentItem)
            .join(Concept, Concept.id == ContentItem.concept_id)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.status == "PUBLISHED",
                ContentItem.deleted_at.is_(None),
            )
            .group_by(Subject.name)
        )
        by_subject = {name: int(count) for name, count in rows.all()}
        return {
            area: sum(by_subject.get(s, 0) for s in subjects) for area, subjects in CAMPAIGN_AREAS.items()
        }

    async def campaign_dashboard(self) -> dict:
        """WAVE-P0-7 campaign control — planning targets only; never auto-publishes.

        Phase 3.3-R1: pipeline / subject / status inventory counts are COMPLETE
        DB aggregates. Structural quality percentages remain an explicit SAMPLE
        and must not be labelled as full-inventory totals.
        """
        from app.modules.academic.models import Chapter, Concept, Subject, Topic

        # COMPLETE status totals (QUESTIONs)
        by_status = await self.session.execute(
            select(ContentItem.status, func.count())
            .where(ContentItem.content_type == "QUESTION", ContentItem.deleted_at.is_(None))
            .group_by(ContentItem.status)
        )
        status_counts = {row[0]: int(row[1]) for row in by_status.all()}
        total_questions = max(1, sum(status_counts.values()))

        # COMPLETE per-subject status via SQL (no first-N truncation)
        subject_status_rows = await self.session.execute(
            select(Subject.name, ContentItem.status, func.count(ContentItem.id))
            .select_from(ContentItem)
            .join(Concept, Concept.id == ContentItem.concept_id)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(ContentItem.content_type == "QUESTION", ContentItem.deleted_at.is_(None))
            .group_by(Subject.name, ContentItem.status)
        )
        subject_status: dict[str, dict[str, int]] = {}
        for subject_name, status, count in subject_status_rows.all():
            bucket = subject_status.setdefault(
                subject_name,
                {"draft": 0, "in_review": 0, "approved": 0, "published": 0, "changes_requested": 0, "archived": 0},
            )
            key = {
                "DRAFT": "draft",
                "IN_REVIEW": "in_review",
                "APPROVED": "approved",
                "PUBLISHED": "published",
                "CHANGES_REQUESTED": "changes_requested",
                "ARCHIVED": "archived",
            }.get(status)
            if key:
                bucket[key] += int(count)

        unmapped_rows = await self.session.execute(
            select(ContentItem.status, func.count())
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.deleted_at.is_(None),
                ContentItem.concept_id.is_(None),
            )
            .group_by(ContentItem.status)
        )
        unmapped_bucket = {
            "draft": 0,
            "in_review": 0,
            "approved": 0,
            "published": 0,
            "changes_requested": 0,
            "archived": 0,
        }
        for status, count in unmapped_rows.all():
            key = {
                "DRAFT": "draft",
                "IN_REVIEW": "in_review",
                "APPROVED": "approved",
                "PUBLISHED": "published",
                "CHANGES_REQUESTED": "changes_requested",
                "ARCHIVED": "archived",
            }.get(status)
            if key:
                unmapped_bucket[key] += int(count)
        if sum(unmapped_bucket.values()) > 0:
            subject_status["UNMAPPED"] = unmapped_bucket

        missing_mapping = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(ContentItem)
                    .where(
                        ContentItem.content_type == "QUESTION",
                        ContentItem.deleted_at.is_(None),
                        ContentItem.concept_id.is_(None),
                    )
                )
            ).scalar()
            or 0
        )
        missing_provenance = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(ContentItem)
                    .join(ContentVersion, ContentVersion.id == ContentItem.latest_version_id)
                    .where(
                        ContentItem.content_type == "QUESTION",
                        ContentItem.deleted_at.is_(None),
                        ContentVersion.model_used.is_(None),
                        ContentVersion.knowledge_unit_id.is_(None),
                    )
                )
            ).scalar()
            or 0
        )

        # SAMPLE-only structural scan (explicitly not full inventory)
        quality_sample_limit = 500
        sample_result = await self.session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.content_type == "QUESTION", ContentItem.deleted_at.is_(None))
            .order_by(ContentItem.created_at.desc())
            .limit(quality_sample_limit)
        )
        sample_items = list(sample_result.scalars().unique().all())
        structurally_invalid = 0
        with_explanation = 0
        with_provenance = 0
        with_mapping = 0
        structurally_valid = 0
        for item in sample_items:
            by_id = {v.id: v for v in item.versions}
            latest = by_id.get(item.latest_version_id)
            body = latest.body if latest else {}
            structural = _structural_assessment(item.content_type, body, item.concept_id)
            provenance = _provenance_from_version(latest)
            if item.concept_id:
                with_mapping += 1
            if provenance["has_lineage"]:
                with_provenance += 1
            if structural["valid"]:
                structurally_valid += 1
            else:
                structurally_invalid += 1
            if (body or {}).get("explanation"):
                with_explanation += 1

        area_published = await self._campaign_area_published_counts()
        targets = []
        for area, subjects in CAMPAIGN_AREAS.items():
            published = area_published.get(area, 0)
            remaining = max(0, CAMPAIGN_TARGET_PER_AREA - published)
            pipeline = {"draft": 0, "in_review": 0, "approved": 0, "changes_requested": 0}
            for subj in subjects:
                for k in pipeline:
                    pipeline[k] += subject_status.get(subj, {}).get(k, 0)
            targets.append(
                {
                    "area": area,
                    "subjects_included": list(subjects),
                    "published": published,
                    "target": CAMPAIGN_TARGET_PER_AREA,
                    "remaining": remaining,
                    "progress_ratio": round(min(1.0, published / CAMPAIGN_TARGET_PER_AREA), 4),
                    "pipeline": pipeline,
                    "pipeline_complete": True,
                    "met_planning_target": remaining == 0,
                }
            )

        chapter_counts = await self.chapter_question_counts()
        all_chapters = await self.session.execute(
            select(Chapter.id, Chapter.name, Subject.name.label("subject_name"))
            .join(Subject, Subject.id == Chapter.subject_id)
            .order_by(Subject.display_order, Chapter.display_order)
        )
        chapter_rows = []
        for chapter_id, chapter_name, subject_name in all_chapters.all():
            meta = chapter_counts.get(chapter_id) or {
                "draft": 0,
                "in_review": 0,
                "approved": 0,
                "published": 0,
                "changes_requested": 0,
            }
            review_queue = int(meta["in_review"]) + int(meta.get("approved", 0))
            draft_pool = int(meta["draft"]) + int(meta.get("changes_requested", 0))
            published = int(meta["published"])
            concentration = (
                "high"
                if (draft_pool + int(meta["in_review"])) >= 5
                else ("low_published" if published == 0 else "normal")
            )
            chapter_rows.append(
                {
                    "chapter_id": str(chapter_id),
                    "chapter_name": chapter_name,
                    "subject_name": subject_name,
                    "campaign_area": campaign_area_for_subject(subject_name),
                    "published": published,
                    "review_queue": review_queue,
                    "draft": int(meta["draft"]),
                    "in_review": int(meta["in_review"]),
                    "approved": int(meta.get("approved", 0)),
                    "changes_requested": int(meta.get("changes_requested", 0)),
                    "concentration": concentration,
                }
            )

        sample_n = max(1, len(sample_items))
        return {
            "targets": targets,
            "status_counts": {
                "draft": int(status_counts.get("DRAFT", 0)),
                "in_review": int(status_counts.get("IN_REVIEW", 0)),
                "approved": int(status_counts.get("APPROVED", 0)),
                "published": int(status_counts.get("PUBLISHED", 0)),
                "changes_requested": int(status_counts.get("CHANGES_REQUESTED", 0)),
                "archived": int(status_counts.get("ARCHIVED", 0)),
                # Complete inventory aggregates (not first-N scan)
                "missing_provenance": missing_provenance,
                "missing_mapping": missing_mapping,
                # Structural invalid remains sample-derived — see quality_metrics.sample_*
                "structurally_invalid": structurally_invalid,
            },
            "count_semantics": {
                "status_counts": "COMPLETE — all non-deleted QUESTION rows",
                "by_academic_subject": "COMPLETE — SQL GROUP BY subject × status",
                "targets.pipeline": "COMPLETE — rolled up from full subject aggregates",
                "targets.published": "COMPLETE — PUBLISHED QUESTION counts by campaign area",
                "chapter_coverage": "COMPLETE — all chapters with status aggregates",
                "quality_metrics_percentages": (
                    f"SAMPLE — structural body checks on up to {quality_sample_limit} recent questions; "
                    "not a full-inventory total"
                ),
                "structurally_invalid": "SAMPLE — from quality sample only",
            },
            "by_academic_subject": [
                {"subject": name, **counts} for name, counts in sorted(subject_status.items())
            ],
            "chapter_coverage": chapter_rows,
            "quality_metrics": {
                "total_questions_scanned": len(sample_items),
                "sample_limit": quality_sample_limit,
                "sample_only": True,
                "inventory_total_questions": sum(status_counts.values()),
                "pct_with_provenance": round(100 * with_provenance / sample_n, 1),
                "pct_with_academic_mapping": round(100 * with_mapping / sample_n, 1),
                "pct_with_explanation": round(100 * with_explanation / sample_n, 1),
                "pct_structurally_valid": round(100 * structurally_valid / sample_n, 1),
                "pct_reviewed_or_beyond": round(
                    100
                    * (
                        status_counts.get("IN_REVIEW", 0)
                        + status_counts.get("APPROVED", 0)
                        + status_counts.get("PUBLISHED", 0)
                        + status_counts.get("CHANGES_REQUESTED", 0)
                        + status_counts.get("ARCHIVED", 0)
                    )
                    / total_questions,
                    1,
                ),
                "pct_approved_or_published": round(
                    100 * (status_counts.get("APPROVED", 0) + status_counts.get("PUBLISHED", 0)) / total_questions, 1
                ),
                "pct_published": round(100 * status_counts.get("PUBLISHED", 0) / total_questions, 1),
                "disclaimer": (
                    "STRUCTURAL VALIDITY percentages are SAMPLE-ONLY (recent questions). "
                    "Pipeline / subject / status inventory counts are COMPLETE DB aggregates. "
                    "SCIENTIFIC VALIDITY is never inferred — human SME review is mandatory. "
                    "Do not publish to inflate progress bars."
                ),
            },
            "prioritization": PRIORITIZATION_EXPLAINED,
            "rules": {
                "human_review_mandatory": True,
                "no_auto_approve": True,
                "no_auto_publish": True,
                "no_mass_publish_drafts": True,
                "planning_target_only": True,
                "biology_includes": ["Botany", "Zoology"],
                "inventory_counts_complete": True,
            },
        }

    async def review_packet(self, item_id: uuid.UUID) -> dict:
        item = await self.repo.get_item(item_id)
        if not item:
            raise NotFoundError("Content item not found")

        by_id = {v.id: v for v in item.versions}
        latest = by_id.get(item.latest_version_id)
        body = latest.body if latest else {}
        structural = _structural_assessment(item.content_type, body, item.concept_id)
        provenance = _provenance_from_version(latest)
        names = await self.repo.academic_names_for_concepts([item.concept_id] if item.concept_id else [])
        academic = names.get(item.concept_id) if item.concept_id else None
        chapter_counts = await self.chapter_question_counts()
        chapter_inventory = None
        if academic and academic.get("chapter"):
            chapter_inventory = chapter_counts.get(uuid.UUID(academic["chapter"]["id"]))

        question = None
        if item.content_type == "QUESTION" and body:
            question = {
                "stem": body.get("stem"),
                "options": body.get("options", []),
                "correct_option": body.get("correct_option"),
                "explanation": body.get("explanation"),
                "difficulty": body.get("difficulty"),
                "bloom_level": body.get("bloom_level"),
                "pyq_year": body.get("pyq_year"),
            }

        duplicates = await self.find_suspected_duplicates(item, (body or {}).get("stem") if isinstance(body, dict) else None)
        reviews = await self.list_reviews_for_version(latest.id if latest else None)

        from app.modules.cms.acquisition.batch_a_catalog import BATCH_ID, MODEL_USED

        tags = item.tags or []
        is_batch_a = BATCH_ID in tags or (latest and latest.model_used == MODEL_USED) or (item.slug or "").startswith(
            "batch-a-"
        )
        checklist = list(REVIEW_CHECKLIST)
        if is_batch_a:
            checklist = checklist + [
                {
                    "id": "batch_a_origin",
                    "category": "Provenance",
                    "prompt": "Confirm display: Human-authored Batch A — SME review required. Not official NTA/NCERT content.",
                },
                {
                    "id": "source_verify",
                    "category": "Provenance",
                    "prompt": "If no authoritative source was checked: mark Source verification required — do not invent citations.",
                },
            ]

        return {
            "item_id": str(item.id),
            "title": item.title,
            "content_type": item.content_type,
            "status": item.status,
            "language": item.language,
            "tags": tags,
            "concept_id": str(item.concept_id) if item.concept_id else None,
            "academic": academic,
            "question": question,
            "body": body,
            "batch_a": {
                "is_batch_a": is_batch_a,
                "display_label": "Human-authored Batch A" if is_batch_a else None,
                "sme_review_required": True if is_batch_a else None,
                "not_official_nta_ncert": True if is_batch_a else None,
            },
            "provenance": {
                **provenance,
                "source_verification_required": not provenance["has_lineage"] or is_batch_a,
                "display_label": "Human-authored Batch A" if is_batch_a else None,
                "display_note": (
                    (
                        "Human-authored Batch A — SME review required. Not official NTA/NCERT. "
                        + (
                            "Source verification required"
                            if not provenance["has_lineage"]
                            else "Provenance fields shown as stored — verify accuracy; do not invent NTA/official labels"
                        )
                    )
                    if is_batch_a
                    else (
                        "Source verification required"
                        if not provenance["has_lineage"]
                        else "Provenance fields shown as stored — verify accuracy; do not invent NTA/official labels"
                    )
                ),
            },
            "structural": {
                **structural,
                "note": "Structural validity ≠ scientific validity. Human SME verification is mandatory.",
            },
            "ncert": ncert_state_from_evidence(tags=tags, body=body if isinstance(body, dict) else None),
            "publication_eligibility": {
                "eligible_now": False,
                "requires_status": "APPROVED",
                "current_status": item.status,
                "approval_is_not_publication": True,
                "ncert_certify_does_not_publish": True,
                "blocking_reasons": (
                    (structural["issues"] if not structural["valid"] else [])
                    + ([] if item.concept_id else ["Missing academic concept mapping"])
                    + (
                        []
                        if item.status == "APPROVED"
                        else [f"Cannot publish from status {item.status} — explicit APPROVED + publish required"]
                    )
                ),
                "note": "Publish requires content.publish permission, APPROVED status, and publication gates. Never auto.",
            },
            "suspected_duplicates": duplicates,
            "reviews": reviews,
            "ai_assistance": {
                "report": latest.ai_check_report if latest else None,
                "disclaimer": "AI assistance only — does not certify scientific correctness or authorize publish.",
            },
            "factory_qa": await self._factory_qa_packet(item.id),
            "checklist": checklist,
            "review_notes_guidance": {
                "encourage_notes": True,
                "examples": [
                    "Correct — approve.",
                    "Answer needs correction.",
                    "Explanation needs revision.",
                    "Chapter mapping incorrect.",
                    "Difficulty should be Medium.",
                    "Verify against NCERT.",
                    "Question ambiguous.",
                    "Distractor C too obvious.",
                    "Provenance requires verification.",
                ],
                "student_visibility": "Reviewer notes are editorial-only unless the product explicitly exposes them.",
            },
            "chapter_inventory": chapter_inventory,
            "campaign_notes": {
                "target": "≥25 reviewed and published questions per Physics / Chemistry / Biology (Botany+Zoology) while improving chapter diversity",
                "do_not_mass_publish": True,
                "human_review_mandatory": True,
                "planning_target_only": True,
                "quality_over_campaign_target": True,
                "checklist_does_not_approve": True,
            },
            "allowed_decisions": {
                "IN_REVIEW": ["approve", "request_changes"],
                "APPROVED": ["publish"],
                "DRAFT": ["submit"],
                "CHANGES_REQUESTED": ["edit then resubmit"],
            }.get(item.status, []),
        }

    async def _factory_qa_packet(self, content_item_id: uuid.UUID) -> dict:
        """Minimal FACTORY-P4/P5 evidence for editorial packet — never certifies science."""
        from sqlalchemy import select

        from app.modules.cms.models.factory_qa import FactoryReviewItem
        from app.modules.cms.services.content_factory_qa_service import ContentFactoryQAService

        qa = await ContentFactoryQAService(self.session).get_latest_for_item(content_item_id)
        fri = (
            await self.session.execute(
                select(FactoryReviewItem)
                .where(
                    FactoryReviewItem.content_item_id == content_item_id,
                    FactoryReviewItem.deleted_at.is_(None),
                )
                .order_by(FactoryReviewItem.updated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        factory_review = None
        if fri:
            factory_review = {
                "factory_review_item_id": str(fri.id),
                "selection_class": fri.selection_class,
                "review_status": fri.review_status,
                "decision": fri.decision,
                "ecaep_submit_eligible": fri.ecaep_submit_eligible,
                "failure_reasons": fri.failure_reasons,
                "disclaimer": fri.disclaimer,
            }
        if not qa:
            return {
                "present": False,
                "disclaimer": "No factory QAResult — AUTOMATED_QA ≠ scientific validation",
                "factory_review": factory_review,
            }
        return {
            "present": True,
            "classification": qa.classification,
            "qa_version": qa.qa_version,
            "failed_checks": qa.failed_checks,
            "warnings": qa.warnings,
            "duplicate_class": qa.duplicate_class,
            "gate_results": qa.gate_results,
            "blueprint_id": str(qa.blueprint_id) if qa.blueprint_id else None,
            "blueprint_version": qa.blueprint_version,
            "generation_run_id": str(qa.generation_run_id) if qa.generation_run_id else None,
            "sampling_eligible": qa.sampling_eligible,
            "quarantine": qa.quarantine,
            "scientific_certification": False,
            "disclaimer": qa.disclaimer,
            "factory_review": factory_review,
        }

    async def coverage_imbalance(self) -> dict:
        chapters = list((await self.chapter_question_counts()).values())
        chapters.sort(key=lambda c: (-c["draft"], -c["in_review"], c["published"], c["chapter_name"]))
        concentrated = [c for c in chapters if c["draft"] + c["in_review"] >= 5]
        thin_published = [c for c in chapters if c["published"] == 0 and (c["draft"] + c["in_review"]) > 0]
        return {
            "by_chapter": chapters,
            "high_draft_concentration": concentrated[:12],
            "mapped_but_unpublished_chapters": thin_published[:20],
            "guidance": (
                "Prefer diversifying chapters when selecting the next batch to submit/review. "
                "Do not publish drafts solely to balance counts."
            ),
        }

    async def subject_intake(
        self,
        *,
        subject_name: str,
        status: str | None = "DRAFT",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Phase 3.3 controlled Chemistry/Zoology intake — read-only classification.

        Never mutates, never publishes, never loads the unmapped 5k backlog.
        """
        from collections import Counter

        from app.modules.academic.models import Chapter, Concept, Subject, Topic

        allowed = {"Chemistry", "Zoology", "Physics", "Botany"}
        if subject_name not in allowed:
            raise NotFoundError(f"Unknown subject for intake: {subject_name}")

        subject_id = await self._resolve_subject_id(subject_name)
        if not subject_id:
            raise NotFoundError(f"Subject not found: {subject_name}")

        status_filter = None if status in (None, "", "any", "ALL") else status
        query = (
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .join(Concept, Concept.id == ContentItem.concept_id)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.deleted_at.is_(None),
                Subject.id == subject_id,
            )
        )
        if status_filter:
            query = query.where(ContentItem.status == status_filter)

        # Cap scan for operational queues — never pull unmapped global backlog.
        result = await self.session.execute(query.order_by(ContentItem.created_at.asc()).limit(400))
        items = list(result.scalars().unique().all())
        names = await self.repo.academic_names_for_concepts([i.concept_id for i in items if i.concept_id])

        stem_map: dict[str, list[str]] = {}
        for item in items:
            by_id = {v.id: v for v in item.versions}
            latest = by_id.get(item.latest_version_id)
            body = latest.body if latest else {}
            stem = (body.get("stem") or "").strip().lower() if isinstance(body, dict) else ""
            if stem:
                stem_map.setdefault(stem, []).append(str(item.id))
        dup_stems = {s for s, ids in stem_map.items() if len(ids) > 1}

        intake_counts: Counter[str] = Counter()
        rows: list[dict] = []
        for item in items:
            by_id = {v.id: v for v in item.versions}
            latest = by_id.get(item.latest_version_id)
            body = latest.body if latest else {}
            structural = _structural_assessment(item.content_type, body, item.concept_id)
            provenance = _provenance_from_version(latest)
            ncert = ncert_state_from_evidence(tags=item.tags, body=body if isinstance(body, dict) else None)
            stem = (body.get("stem") or "").strip().lower() if isinstance(body, dict) else ""
            academic = names.get(item.concept_id) if item.concept_id else None
            code = intake_code_for_draft(
                status=item.status,
                concept_id=item.concept_id,
                structural_valid=structural["valid"],
                has_provenance_lineage=provenance["has_lineage"],
                suspected_duplicate=stem in dup_stems,
                has_stem=bool(stem),
            )
            readiness = readiness_label_for_question(
                status=item.status,
                concept_id=item.concept_id,
                structural_valid=structural["valid"],
                has_provenance_lineage=provenance["has_lineage"],
                ncert_verified=ncert["is_verified"],
                suspected_duplicate=stem in dup_stems,
            )
            intake_counts[code] += 1
            rows.append(
                {
                    "id": str(item.id),
                    "title": item.title,
                    "status": item.status,
                    "intake_code": code,
                    "readiness_label": readiness,
                    "difficulty": (body or {}).get("difficulty") if isinstance(body, dict) else None,
                    "academic": academic,
                    "structural": structural,
                    "provenance": {"has_lineage": provenance["has_lineage"], "status": provenance["status"]},
                    "ncert": {
                        "verification_level": ncert["verification_level"],
                        "is_verified": ncert["is_verified"],
                    },
                    "suspected_duplicate": stem in dup_stems,
                    "blocking_reasons": structural["issues"]
                    + ([] if provenance["has_lineage"] else ["Missing provenance lineage"])
                    + ([] if ncert["is_verified"] else ["NCERT verification not established"]),
                }
            )

        total = len(rows)
        page = rows[offset : offset + limit]
        return {
            "subject": subject_name,
            "status_filter": status_filter or "any",
            "total": total,
            "limit": limit,
            "offset": offset,
            "intake_counts": dict(intake_counts),
            "items": page,
            "rules": {
                "read_only": True,
                "no_auto_submit": True,
                "no_auto_approve": True,
                "no_auto_publish": True,
                "unmapped_backlog_excluded": True,
                "classification_is_heuristic": True,
                "does_not_certify_science_or_ncert": True,
            },
        }

    async def content_readiness(self) -> dict:
        """Phase 3.2 operational readiness — read-only; never publishes or mutates content.

        Answers: what can safely move toward publication, what is blocked, and why.
        Student-facing practice continues to require status=PUBLISHED only.
        """
        from app.modules.academic.models import Chapter, Concept, Subject, Topic

        by_status_rows = await self.session.execute(
            select(ContentItem.status, func.count())
            .where(ContentItem.content_type == "QUESTION", ContentItem.deleted_at.is_(None))
            .group_by(ContentItem.status)
        )
        status_counts = {str(row[0]): int(row[1]) for row in by_status_rows.all()}

        unmapped = await self.session.execute(
            select(func.count())
            .select_from(ContentItem)
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.deleted_at.is_(None),
                ContentItem.concept_id.is_(None),
            )
        )
        unmapped_concept = int(unmapped.scalar() or 0)

        subject_status_rows = await self.session.execute(
            select(Subject.name, ContentItem.status, func.count(ContentItem.id))
            .select_from(ContentItem)
            .join(Concept, Concept.id == ContentItem.concept_id)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(ContentItem.content_type == "QUESTION", ContentItem.deleted_at.is_(None))
            .group_by(Subject.name, ContentItem.status)
        )
        by_subject_status = [
            {"subject": name, "status": status, "count": int(count)}
            for name, status, count in subject_status_rows.all()
        ]
        # Surface unmapped drafts as an explicit subject bucket for operators.
        if unmapped_concept:
            unmapped_by_status = await self.session.execute(
                select(ContentItem.status, func.count())
                .where(
                    ContentItem.content_type == "QUESTION",
                    ContentItem.deleted_at.is_(None),
                    ContentItem.concept_id.is_(None),
                )
                .group_by(ContentItem.status)
            )
            for status, count in unmapped_by_status.all():
                by_subject_status.append(
                    {"subject": "UNMAPPED", "status": str(status), "count": int(count)}
                )

        coverage = await self.coverage_imbalance()

        return {
            "content_type": "QUESTION",
            "status_counts": status_counts,
            "published": int(status_counts.get("PUBLISHED", 0)),
            "draft": int(status_counts.get("DRAFT", 0)),
            "in_review": int(status_counts.get("IN_REVIEW", 0)),
            "approved_awaiting_publish": int(status_counts.get("APPROVED", 0)),
            "unmapped_concept": unmapped_concept,
            "by_subject_status": sorted(
                by_subject_status, key=lambda r: (r["subject"], r["status"])
            ),
            "chapter_imbalance": {
                "high_draft_concentration": [
                    {
                        "chapter_name": c["chapter_name"],
                        "subject_name": c["subject_name"],
                        "draft": c["draft"],
                        "published": c["published"],
                    }
                    for c in coverage["high_draft_concentration"]
                ],
                "mapped_but_unpublished_chapters": [
                    {
                        "chapter_name": c["chapter_name"],
                        "subject_name": c["subject_name"],
                        "draft": c["draft"],
                        "published": c["published"],
                    }
                    for c in coverage["mapped_but_unpublished_chapters"]
                ],
                "guidance": coverage["guidance"],
            },
            "quality_gates": {
                "publish_requires": [
                    "status=APPROVED",
                    "content.publish permission",
                    "explicit publish action (single or bulk)",
                    "QUESTION publication gates (structure, mapping, evidence policy)",
                ],
                "never_mass_publish_drafts": True,
                "student_visible_status": "PUBLISHED",
                "approval_is_not_publication": True,
                "ncert_certify_does_not_publish": True,
            },
            "campaign_notes": {
                "first_target_suggestion": (
                    "Prioritize Chemistry and Zoology IN_REVIEW / APPROVED items with "
                    "concept mapping — never publish to hit a numerical quota."
                ),
                "full_neet_mock_not_ready_below": 180,
                "do_not_claim_content_ready": True,
                "inventory_is_db_derived": True,
                "ncert_note": (
                    "Provenance/source fields are not NCERT certification. "
                    "Only explicit ncert evidence / certify-ncert workflow counts. "
                    "Re-run scripts/content_readiness_inventory.py for live NCERT tag counts."
                ),
            },
            "ecaep_rules": {
                "no_auto_publish": True,
                "no_auto_approve": True,
                "human_review_mandatory": True,
            },
        }
