"""WAVE-P0-9 — diversified Batch A acquisition (DRAFT only).

Reuses ContentWorkflowService.create_item. Never approves or publishes.
Idempotent by slug = batch-a-{source_key}.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.cms.acquisition.batch_a_catalog import BATCH_A_QUESTIONS, BATCH_ID, MODEL_USED, PROMPT_VERSION
from app.modules.cms.acquisition.batch_a_hierarchy import BATCH_A_HIERARCHY, CHAPTER_CODE_BY_KEY
from app.modules.cms.models import ContentItem
from app.modules.cms.schemas.content_bodies import assert_body_publishable
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.system.services.audit_service import AuditService

logger = get_logger("cms.acquisition")


class BatchAAcquisitionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.workflow = ContentWorkflowService(session)

    async def ensure_hierarchy(self) -> dict[str, Any]:
        """Create missing topics/concepts under existing Batch A chapters (idempotent)."""
        created_topics = 0
        created_concepts = 0
        missing_chapters: list[str] = []

        for chapter_code, topics in BATCH_A_HIERARCHY.items():
            result = await self.session.execute(select(Chapter).where(Chapter.code == chapter_code))
            chapter = result.scalar_one_or_none()
            if not chapter:
                missing_chapters.append(chapter_code)
                continue

            for topic_order, (topic_code, topic_name, concepts) in enumerate(topics):
                t_result = await self.session.execute(
                    select(Topic).where(Topic.chapter_id == chapter.id, Topic.code == topic_code)
                )
                topic = t_result.scalar_one_or_none()
                if not topic:
                    topic = Topic(
                        chapter_id=chapter.id,
                        code=topic_code,
                        name=topic_name,
                        display_order=topic_order,
                    )
                    self.session.add(topic)
                    await self.session.flush()
                    created_topics += 1

                for concept_order, (concept_code, concept_name, summary) in enumerate(concepts):
                    c_result = await self.session.execute(
                        select(Concept).where(Concept.topic_id == topic.id, Concept.code == concept_code)
                    )
                    concept = c_result.scalar_one_or_none()
                    if not concept:
                        self.session.add(
                            Concept(
                                topic_id=topic.id,
                                code=concept_code,
                                name=concept_name,
                                summary=summary,
                                display_order=concept_order,
                            )
                        )
                        created_concepts += 1

        await self.session.commit()
        return {
            "created_topics": created_topics,
            "created_concepts": created_concepts,
            "missing_chapters": missing_chapters,
        }

    async def _concept_id_for(self, chapter_key: str, concept_code: str) -> uuid.UUID | None:
        chapter_code = CHAPTER_CODE_BY_KEY[chapter_key]
        result = await self.session.execute(
            select(Concept.id)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .where(Chapter.code == chapter_code, Concept.code == concept_code)
        )
        return result.scalar_one_or_none()

    async def _build_stem_index(self) -> dict[str, list[str]]:
        result = await self.session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.deleted_at.is_(None),
                ContentItem.status != "ARCHIVED",
            )
            .limit(5000)
        )
        index: dict[str, list[str]] = {}
        for item in result.scalars().unique().all():
            by_id = {v.id: v for v in item.versions}
            latest = by_id.get(item.latest_version_id)
            stem = (latest.body or {}).get("stem") if latest else None
            if isinstance(stem, str) and stem.strip():
                index.setdefault(stem.strip(), []).append(str(item.id))
        return index

    async def _existing_by_slug(self, slug: str) -> ContentItem | None:
        result = await self.session.execute(select(ContentItem).where(ContentItem.slug == slug))
        return result.scalar_one_or_none()

    async def run(
        self,
        *,
        author_id: uuid.UUID,
        questions: list[dict[str, Any]] | None = None,
        actor_user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        hierarchy = await self.ensure_hierarchy()
        if hierarchy["missing_chapters"]:
            raise AppError(
                f"Hierarchy gap — missing chapters: {hierarchy['missing_chapters']}",
                code="HIERARCHY_GAP",
                status_code=422,
            )

        catalog = questions if questions is not None else BATCH_A_QUESTIONS
        created: list[dict] = []
        skipped_duplicate: list[dict] = []
        rejected: list[dict] = []
        suspected_stem_dups: list[dict] = []

        # One-pass stem index for duplicate checks (avoid N×full-table scans).
        stem_index = await self._build_stem_index()

        for entry in catalog:
            source_key = entry["source_key"]
            slug = f"batch-a-{source_key}"
            existing = await self._existing_by_slug(slug)
            if existing:
                skipped_duplicate.append(
                    {
                        "source_key": source_key,
                        "id": str(existing.id),
                        "status": existing.status,
                        "reason": "idempotent_slug",
                    }
                )
                continue

            body = {
                "stem": entry["stem"],
                "options": entry["options"],
                "correct_option": entry["correct_option"],
                "explanation": entry["explanation"],
                "difficulty": entry["difficulty"],
            }
            try:
                assert_body_publishable("QUESTION", body)
            except AppError as exc:
                rejected.append({"source_key": source_key, "reason": exc.message, "code": exc.code})
                continue

            concept_id = await self._concept_id_for(entry["chapter_key"], entry["concept_code"])
            if not concept_id:
                rejected.append(
                    {
                        "source_key": source_key,
                        "reason": f"Missing concept {entry['concept_code']} under {entry['chapter_key']}",
                        "code": "HIERARCHY_GAP",
                    }
                )
                continue

            stem_n = entry["stem"].strip()
            stem_owners = stem_index.get(stem_n, [])
            if stem_owners:
                suspected_stem_dups.append({"source_key": source_key, "existing_ids": stem_owners})
                rejected.append(
                    {
                        "source_key": source_key,
                        "reason": "Exact stem duplicate of existing question(s)",
                        "code": "DUPLICATE_STEM",
                        "existing_ids": stem_owners,
                    }
                )
                continue

            tags = [
                BATCH_ID,
                f"source_key:{source_key}",
                "origin:human-authored",
                "alignment:ncert-curriculum-aligned",
                "not-official-nta",
                "sme-review-required",
            ]
            try:
                item = await self.workflow.create_item(
                    content_type="QUESTION",
                    concept_id=concept_id,
                    title=entry["title"][:300],
                    slug=slug[:320],
                    tags=tags,
                    language="en",
                    body=body,
                    author_id=author_id,
                    model_used=MODEL_USED,
                    prompt_version=PROMPT_VERSION,
                )
            except AppError as exc:
                rejected.append({"source_key": source_key, "reason": exc.message, "code": exc.code})
                continue

            if item.status != "DRAFT":
                rejected.append(
                    {
                        "source_key": source_key,
                        "reason": f"Unexpected status {item.status}",
                        "code": "UNEXPECTED_STATUS",
                    }
                )
                continue

            stem_index.setdefault(stem_n, []).append(str(item.id))
            created.append(
                {
                    "source_key": source_key,
                    "id": str(item.id),
                    "status": item.status,
                    "chapter_key": entry["chapter_key"],
                    "difficulty": entry["difficulty"],
                    "concept_code": entry["concept_code"],
                }
            )

        # Enrich distribution from created + academic names
        chapter_dist: dict[str, int] = {}
        subject_dist: dict[str, int] = {}
        difficulty_dist: dict[str, int] = {}
        for row in created:
            chapter_dist[row["chapter_key"]] = chapter_dist.get(row["chapter_key"], 0) + 1
            difficulty_dist[row["difficulty"]] = difficulty_dist.get(row["difficulty"], 0) + 1

        if created:
            ids = [uuid.UUID(r["id"]) for r in created]
            name_rows = await self.session.execute(
                select(ContentItem.id, Subject.name, Chapter.name, Topic.name)
                .join(Concept, Concept.id == ContentItem.concept_id)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .join(Subject, Subject.id == Chapter.subject_id)
                .where(ContentItem.id.in_(ids))
            )
            topic_dist: dict[str, int] = {}
            for _id, subject, chapter, topic in name_rows.all():
                subject_dist[subject] = subject_dist.get(subject, 0) + 1
                topic_dist[f"{chapter} / {topic}"] = topic_dist.get(f"{chapter} / {topic}", 0) + 1
        else:
            topic_dist = {}

        report = {
            "batch_id": BATCH_ID,
            "hierarchy": hierarchy,
            "planned": len(catalog),
            "created": len(created),
            "skipped_duplicate": len(skipped_duplicate),
            "rejected": len(rejected),
            "created_items": created,
            "skipped_items": skipped_duplicate,
            "rejected_items": rejected,
            "suspected_stem_duplicates": suspected_stem_dups,
            "distributions": {
                "subject": subject_dist,
                "chapter_key": chapter_dist,
                "topic": topic_dist,
                "difficulty": difficulty_dist,
            },
            "provenance": {
                "model_used": MODEL_USED,
                "prompt_version": PROMPT_VERSION,
                "all_created_have_model_used": True,
                "official_nta_claim": False,
                "note": "Human-authored NCERT-curriculum-aligned drafts — SME review required; not official NTA/NEET papers.",
            },
            "status_guarantee": "All newly created items are DRAFT",
            "rules": {
                "no_auto_approve": True,
                "no_auto_publish": True,
                "idempotent_by_slug": True,
            },
        }

        await AuditService(self.session).log(
            actor_user_id=actor_user_id or author_id,
            action="content.acquisition_batch",
            entity_type="acquisition_batch",
            entity_id=None,
            metadata={
                "batch_id": BATCH_ID,
                "created": report["created"],
                "skipped_duplicate": report["skipped_duplicate"],
                "rejected": report["rejected"],
                "created_ids": [c["id"] for c in created[:100]],
            },
        )
        logger.info(
            "batch_a_complete",
            created=report["created"],
            skipped=report["skipped_duplicate"],
            rejected=report["rejected"],
        )
        return report
