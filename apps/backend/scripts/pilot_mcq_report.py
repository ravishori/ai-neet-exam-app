"""Summarize Phase D pilot run state from the database."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import any_, func, select

from app.core.database import AsyncSessionLocal
from app.modules.academic.models import Chapter
from app.modules.cms.models import ContentItem, ContentVersion, ContentVersionKnowledgeUnit
from app.modules.ingestion.models import IngestionJob, IngestionSection
from app.modules.ingestion.services.pilot_mcq_orchestration_service import PHASE_D_PILOT_RUN_ID
from app.modules.knowledge.models import KnowledgeUnit


async def main() -> int:
    async with AsyncSessionLocal() as session:
        jobs = (
            await session.execute(
                select(IngestionJob, Chapter)
                .join(Chapter, Chapter.id == IngestionJob.chapter_id)
                .where(IngestionJob.pilot_run_id == PHASE_D_PILOT_RUN_ID)
            )
        ).all()

        by_chapter: dict[str, dict] = {}
        for job, chapter in jobs:
            by_chapter[chapter.code] = {
                "job_id": str(job.id),
                "status": job.status,
                "questions_generated": job.questions_generated,
                "target": job.target_mcq_count,
                "sections": job.sections_detected,
            }

        ingested_tag = "ingested" == any_(ContentItem.tags)

        draft_count = (
            await session.execute(
                select(func.count(ContentItem.id)).where(
                    ContentItem.content_type == "QUESTION",
                    ContentItem.status == "DRAFT",
                    ingested_tag,
                )
            )
        ).scalar_one()

        status_counts = (
            await session.execute(
                select(ContentItem.status, func.count(ContentItem.id))
                .where(ContentItem.content_type == "QUESTION", ingested_tag)
                .group_by(ContentItem.status)
            )
        ).all()

        lineage_ok = 0
        ai_generated_tag = "ai-generated" == any_(ContentItem.tags)
        pilot_questions = (
            await session.execute(
                select(ContentItem, ContentVersion)
                .join(ContentVersion, ContentVersion.content_item_id == ContentItem.id)
                .where(
                    ContentItem.content_type == "QUESTION",
                    ingested_tag,
                    ai_generated_tag,
                )
            )
        ).all()

        for item, version in pilot_questions:
            refs = (
                await session.execute(
                    select(KnowledgeUnit, IngestionSection, IngestionJob)
                    .join(
                        ContentVersionKnowledgeUnit,
                        ContentVersionKnowledgeUnit.knowledge_unit_id == KnowledgeUnit.id,
                    )
                    .join(IngestionSection, IngestionSection.id == KnowledgeUnit.source_section_id)
                    .join(IngestionJob, IngestionJob.id == IngestionSection.job_id)
                    .where(
                        ContentVersionKnowledgeUnit.content_version_id == version.id,
                        IngestionJob.pilot_run_id == PHASE_D_PILOT_RUN_ID,
                    )
                )
            ).first()
            if refs and refs[2].source_document_id:
                lineage_ok += 1

        report = {
            "pilot_run_id": PHASE_D_PILOT_RUN_ID,
            "jobs_by_chapter": by_chapter,
            "ingested_question_status": {s: c for s, c in status_counts},
            "draft_ingested_questions": draft_count,
            "pilot_questions_with_full_lineage": lineage_ok,
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
