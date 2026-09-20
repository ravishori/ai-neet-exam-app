"""One-shot P4 re-QA for factory-p3-pilot-2026-09-01-batch (force_new). QA-only — no AI."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.modules.knowledge.models  # noqa: F401
from app.modules.cms.models.content_factory import ContentBatch
from app.modules.cms.models.content_item import ContentItem
from app.modules.cms.models.factory_qa import QAResult
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.repositories.content_factory_repository import ContentFactoryRepository
from app.modules.cms.services.content_factory_qa_service import ContentFactoryQAService
from scripts.factory_p1_checksum import checksum

BATCH_KEY = "factory-p3-pilot-2026-09-01-batch"
EXPECTED_ITEM_IDS = [
    "a369a657-148b-4253-8c5f-6630e316d5c5",
    "bf421a0d-51e0-4bed-8ee5-fe2788e6dfba",
    "5b75b731-0444-4617-9df8-4bca76d4373d",
    "681f77af-d6bd-4a50-92e9-173a3ccc363e",
    "5e4eb66f-bcbf-4a57-9446-1cbe62d8e8f5",
]
URL = os.environ["DATABASE_URL"]


async def body_checksums(session: AsyncSession, item_ids: list[str]) -> dict[str, str]:
    rows = (
        await session.execute(
            text(
                """
                SELECT ci.id::text AS item_id,
                       md5(cv.body::text) AS body_md5
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                ORDER BY ci.id
                """
            ),
            {"ids": item_ids},
        )
    ).mappings().all()
    return {r["item_id"]: r["body_md5"] for r in rows}


async def main() -> None:
    pre = await checksum(URL)
    pre_bodies = None

    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        repo = ContentFactoryRepository(session)
        batch = await repo.get_batch_by_key(BATCH_KEY)
        if not batch:
            raise SystemExit(f"Batch not found: {BATCH_KEY}")

        pre_bodies = await body_checksums(session, EXPECTED_ITEM_IDS)

        actor_row = (
            await session.execute(
                text(
                    """
                    SELECT actor_user_id
                    FROM system.audit_logs
                    WHERE action = 'factory.qa.started'
                      AND log_metadata->>'batch_id' = :bid
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"bid": str(batch.id)},
            )
        ).scalar_one_or_none()
        if not actor_row:
            actor_row = (
                await session.execute(
                    text(
                        """
                        SELECT id FROM identity.users
                        WHERE deleted_at IS NULL
                        ORDER BY created_at
                        LIMIT 1
                        """
                    )
                )
            ).scalar_one()
        actor_id = uuid.UUID(str(actor_row))

        qa_svc = ContentFactoryQAService(session)
        result = await qa_svc.run_batch_qa(
            batch.id,
            actor_id=actor_id,
            force_new=True,
            job_key=f"p4-reclassify-pilot-{uuid.uuid4().hex[:8]}",
        )

        post_bodies = await body_checksums(session, EXPECTED_ITEM_IDS)

        item_details = []
        for item_id in EXPECTED_ITEM_IDS:
            iid = uuid.UUID(item_id)
            cand = (
                await session.execute(
                    select(GenerationCandidate).where(
                        GenerationCandidate.content_item_id == iid,
                        GenerationCandidate.batch_id == batch.id,
                        GenerationCandidate.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            item = (
                await session.execute(select(ContentItem).where(ContentItem.id == iid))
            ).scalar_one_or_none()
            qa = (
                await session.execute(
                    select(QAResult).where(
                        QAResult.content_item_id == iid,
                        QAResult.is_latest.is_(True),
                        QAResult.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            tags = list(item.tags or []) if item else []
            lineage_tags = [t for t in tags if t.startswith(("provider:", "routing:"))]
            gate_summary = {}
            if qa and qa.gate_results:
                for code in (
                    "A_STRUCTURE",
                    "B_BLUEPRINT",
                    "C_HIERARCHY",
                    "D_PROVENANCE",
                    "E_ANSWER",
                    "F_DUPLICATE",
                    "G_SAFETY",
                ):
                    g = qa.gate_results.get(code, {})
                    gate_summary[code] = {
                        "passed": g.get("passed"),
                        "failures": g.get("failures") or [],
                        "warnings": g.get("warnings") or [],
                    }
            item_details.append(
                {
                    "content_item_id": item_id,
                    "candidate_id": str(cand.id) if cand else None,
                    "content_item_status": item.status if item else None,
                    "tags_lineage": lineage_tags,
                    "qa_result_id": str(qa.id) if qa else None,
                    "qa_evaluation_no": qa.evaluation_no if qa else None,
                    "classification": qa.classification if qa else None,
                    "quarantine": qa.quarantine if qa else None,
                    "candidate_qa_classification": cand.qa_classification if cand else None,
                    "candidate_qa_quarantined": cand.qa_quarantined if cand else None,
                    "duplicate_class": qa.duplicate_class if qa else None,
                    "failed_checks": list(qa.failed_checks or []) if qa else [],
                    "gates": gate_summary,
                    "body_md5_unchanged": pre_bodies.get(item_id) == post_bodies.get(item_id),
                }
            )

        batch_reloaded = (
            await session.execute(select(ContentBatch).where(ContentBatch.id == batch.id))
        ).scalar_one()

    await engine.dispose()
    post = await checksum(URL)

    report = {
        "batch_key": BATCH_KEY,
        "batch_id": str(batch.id),
        "qa_run_summary": result,
        "items": item_details,
        "integrity": {
            "pre_checksum": pre,
            "post_checksum": post,
            "counts_unchanged": pre["counts"] == post["counts"],
            "item_checksum_unchanged": pre["item_checksum"] == post["item_checksum"],
            "body_checksum_unchanged": pre["versions"]["body_checksum"] == post["versions"]["body_checksum"],
            "review_count_unchanged": pre["review_count"] == post["review_count"],
            "all_smoke_bodies_unchanged": all(i["body_md5_unchanged"] for i in item_details),
            "batch_qa_pass_count": batch_reloaded.qa_pass_count,
            "batch_status": batch_reloaded.status,
        },
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
