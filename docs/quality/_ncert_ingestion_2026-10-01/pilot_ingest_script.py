"""Scratch pilot runner for the 2 pilot-ready NCERT sources — NOT a permanent
script, used once for docs/quality/ncert-knowledge-units-ingestion-2026-10-01.md.
No AI calls. Local dev DB only."""

from __future__ import annotations

import asyncio
import json
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.modules.identity.models.user import User
from app.modules.ingestion.models.source_document import SourceDocument
from app.modules.ingestion.services.ingestion_pipeline_service import S1_SOURCE_INGESTION_RUN_ID, IngestionPipelineService


async def main() -> None:
    async with AsyncSessionLocal() as session:
        existing_user = (await session.execute(select(User.id).limit(1))).scalar_one_or_none()
        # author_id is unused by the deterministic structuring path (it's
        # immediately discarded — see deterministic_structuring_service.py's
        # `del author_id` — "deterministic path, no AI audit actor required")
        # and no local user rows exist in this dev DB, so a random UUID is
        # safe here; it is never persisted as a real FK by this code path.
        author_id = existing_user or uuid.uuid4()
        docs = (
            await session.execute(
                select(SourceDocument).where(
                    SourceDocument.relative_source_path.in_(
                        [
                            "Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf",
                            "Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf",
                        ]
                    )
                )
            )
        ).scalars().all()

        pipeline = IngestionPipelineService(session)
        results = []
        for doc in docs:
            job, created = await pipeline.start_source_ingestion_job(
                source_document_id=doc.id, ingestion_run_id=S1_SOURCE_INGESTION_RUN_ID
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
