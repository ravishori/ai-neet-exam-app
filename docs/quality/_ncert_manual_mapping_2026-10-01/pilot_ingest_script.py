"""Scratch pilot runner for 3 newly-mapped sources (manual-evidence mapping
expansion, 2026-10-01) — no AI. Local dev DB only."""

from __future__ import annotations

import asyncio
import json
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.modules.identity.models.user import User
from app.modules.ingestion.models.source_document import SourceDocument
from app.modules.ingestion.services.ingestion_pipeline_service import S1_SOURCE_INGESTION_RUN_ID, IngestionPipelineService

PILOT_PATHS = [
    "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-1.pdf",
    "Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-1.pdf",
    "Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-1.pdf",
]


async def main() -> None:
    async with AsyncSessionLocal() as session:
        existing_user = (await session.execute(select(User.id).limit(1))).scalar_one_or_none()
        author_id = existing_user or uuid.uuid4()
        docs = (
            await session.execute(select(SourceDocument).where(SourceDocument.relative_source_path.in_(PILOT_PATHS)))
        ).scalars().all()

        pipeline = IngestionPipelineService(session)
        results = []
        for doc in docs:
            job, created = await pipeline.start_source_ingestion_job(
                source_document_id=doc.id, ingestion_run_id=S1_SOURCE_INGESTION_RUN_ID, force_rerun=True
            )
            if created or job.status != "COMPLETED":
                await pipeline.run_source_ingestion(job_id=job.id, author_id=author_id)
                job = await pipeline.repo.get_job(job.id)
            results.append(
                {
                    "path": doc.relative_source_path,
                    "created": created,
                    "job_status": job.status,
                    "sections": job.sections_detected,
                    "ku_created": job.knowledge_units_created,
                    "ku_rejected": job.knowledge_units_rejected,
                    "error": job.error_message,
                }
            )
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
