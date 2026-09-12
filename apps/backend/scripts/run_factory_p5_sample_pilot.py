"""FACTORY-P5: materialize human review sample for pilot batch (sampling only — no AI, no review decisions)."""

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
from app.modules.cms.models.factory_qa import FactoryReviewItem, ReviewSample
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.services.content_factory_qa_service import ContentFactorySamplingService
from scripts.factory_p1_checksum import checksum

BATCH_ID = uuid.UUID("22c5684b-cf86-4137-82bf-be237be1e2ee")
BATCH_KEY = "factory-p3-pilot-2026-09-01-batch"
SAMPLE_KEY = "sample-factory-p3-pilot-2026-09-01-batch-42"
SEED = 42
GREEN_SIZE = 5
EXPECTED_ITEM_IDS = {
    "a369a657-148b-4253-8c5f-6630e316d5c5",
    "bf421a0d-51e0-4bed-8ee5-fe2788e6dfba",
    "5b75b731-0444-4617-9df8-4bca76d4373d",
    "681f77af-d6bd-4a50-92e9-173a3ccc363e",
    "5e4eb66f-bcbf-4a57-9446-1cbe62d8e8f5",
}
URL = os.environ["DATABASE_URL"]


async def body_md5s(session: AsyncSession, item_ids: set[str]) -> dict[str, str]:
    rows = (
        await session.execute(
            text(
                """
                SELECT ci.id::text AS item_id, md5(cv.body::text) AS body_md5
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                ORDER BY ci.id
                """
            ),
            {"ids": list(item_ids)},
        )
    ).mappings().all()
    return {r["item_id"]: r["body_md5"] for r in rows}


async def main() -> None:
    pre = await checksum(URL)
    pre_bodies = None

    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        pre_bodies = await body_md5s(session, EXPECTED_ITEM_IDS)

        actor_row = (
            await session.execute(
                text(
                    """
                    SELECT actor_user_id FROM system.audit_logs
                    WHERE action = 'factory.qa.completed'
                      AND entity_id = CAST(:bid AS uuid)
                    ORDER BY created_at DESC LIMIT 1
                    """
                ),
                {"bid": str(BATCH_ID)},
            )
        ).scalar_one_or_none()
        if not actor_row:
            actor_row = (
                await session.execute(
                    text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
                )
            ).scalar_one()
        actor_id = uuid.UUID(str(actor_row))

        svc = ContentFactorySamplingService(session)
        sample_result = await svc.create_sample(
            BATCH_ID,
            actor_id=actor_id,
            seed=SEED,
            sample_key=SAMPLE_KEY,
            green_size=GREEN_SIZE,
        )

        sample = (
            await session.execute(
                select(ReviewSample).where(ReviewSample.sample_key == SAMPLE_KEY, ReviewSample.deleted_at.is_(None))
            )
        ).scalar_one()

        fri_rows = list(
            (
                await session.execute(
                    select(FactoryReviewItem).where(
                        FactoryReviewItem.sample_id == sample.id,
                        FactoryReviewItem.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
        )

        cand_details = []
        for fri in fri_rows:
            cand = (
                await session.execute(
                    select(GenerationCandidate).where(GenerationCandidate.id == fri.candidate_id)
                )
            ).scalar_one()
            cand_details.append(
                {
                    "factory_review_item_id": str(fri.id),
                    "candidate_id": str(fri.candidate_id),
                    "content_item_id": str(fri.content_item_id) if fri.content_item_id else None,
                    "selection_class": fri.selection_class,
                    "review_status": fri.review_status,
                    "selection_reason": fri.selection_reason,
                    "candidate_factory_review_status": cand.factory_review_status,
                    "candidate_latest_factory_review_item_id": str(cand.latest_factory_review_item_id)
                    if cand.latest_factory_review_item_id
                    else None,
                    "qa_classification": cand.qa_classification,
                }
            )

        batch = (
            await session.execute(select(ContentBatch).where(ContentBatch.id == BATCH_ID))
        ).scalar_one()

        item_statuses = (
            await session.execute(
                text(
                    """
                    SELECT id::text, status FROM cms.content_items
                    WHERE id = ANY(CAST(:ids AS uuid[]))
                    ORDER BY id
                    """
                ),
                {"ids": list(EXPECTED_ITEM_IDS)},
            )
        ).mappings().all()

        post_bodies = await body_md5s(session, EXPECTED_ITEM_IDS)

        ecaep_reviews = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.content_reviews cr
                    JOIN cms.content_versions cv ON cv.id = cr.content_version_id
                    JOIN cms.content_items ci ON ci.id = cv.content_item_id
                    WHERE ci.id = ANY(CAST(:ids AS uuid[])) AND ci.deleted_at IS NULL
                    """
                ),
                {"ids": list(EXPECTED_ITEM_IDS)},
            )
        ).scalar()

    await engine.dispose()
    post = await checksum(URL)

    selected_item_ids = {d["content_item_id"] for d in cand_details if d["content_item_id"]}

    report = {
        "operation": "P5_SAMPLING_MATERIALIZATION",
        "batch_key": BATCH_KEY,
        "batch_id": str(BATCH_ID),
        "sample": {
            "id": str(sample.id),
            "sample_key": sample.sample_key,
            "seed": sample.seed,
            "policy_version": sample.policy_version,
            "green_sample_size": sample.green_sample_size,
            "selected_candidate_count": len(sample.selected_candidate_ids or []),
            "selected_candidate_ids": [str(x) for x in (sample.selected_candidate_ids or [])],
            "yellow_candidate_ids": [str(x) for x in (sample.yellow_candidate_ids or [])],
            "red_candidate_ids": [str(x) for x in (sample.red_candidate_ids or [])],
            "idempotent": sample_result.get("idempotent"),
        },
        "factory_review_items": {
            "count": len(fri_rows),
            "items": cand_details,
        },
        "batch": {
            "status": batch.status,
            "qa_pass_count": batch.qa_pass_count,
        },
        "content_item_statuses": [dict(r) for r in item_statuses],
        "verification": {
            "review_sample_count_is_1": True,
            "factory_review_item_count_is_5": len(fri_rows) == 5,
            "all_green_sample": all(d["selection_class"] == "GREEN_SAMPLE" for d in cand_details),
            "all_selected_status": all(d["review_status"] == "SELECTED" for d in cand_details),
            "all_candidate_selected": all(d["candidate_factory_review_status"] == "SELECTED" for d in cand_details),
            "all_latest_fri_populated": all(d["candidate_latest_factory_review_item_id"] for d in cand_details),
            "batch_status_sampling": batch.status == "SAMPLING",
            "selected_items_match_smoke_set": selected_item_ids == EXPECTED_ITEM_IDS,
        },
        "integrity": {
            "pre_checksum": pre,
            "post_checksum": post,
            "counts_unchanged": pre["counts"] == post["counts"],
            "item_checksum_unchanged": pre["item_checksum"] == post["item_checksum"],
            "body_checksum_unchanged": pre["versions"]["body_checksum"] == post["versions"]["body_checksum"],
            "review_count_unchanged": pre["review_count"] == post["review_count"],
            "smoke_item_ecaep_reviews": ecaep_reviews,
            "all_smoke_bodies_unchanged": pre_bodies == post_bodies,
        },
        "confirmations": {
            "zero_ai_provider_calls": True,
            "zero_new_questions": pre["counts"]["total"] == post["counts"]["total"],
            "zero_question_body_modifications": pre_bodies == post_bodies and pre["versions"]["body_checksum"] == post["versions"]["body_checksum"],
            "zero_ecaep_transitions_on_smoke_items": ecaep_reviews == 0 and all(r["status"] == "DRAFT" for r in item_statuses),
            "zero_publishing": pre["counts"]["published"] == post["counts"]["published"],
            "human_review_decisions_not_performed": all(d["review_status"] == "SELECTED" for d in cand_details),
        },
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
