"""FACTORY-P5: submit exactly five ACCEPT decisions via ContentFactoryHumanReviewService."""

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

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.modules.knowledge.models  # noqa: F401
from app.modules.cms.models.content_factory import ContentBatch
from app.modules.cms.models.factory_qa import FactoryReviewItem, ReviewSample
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.services.content_factory_human_review_service import ContentFactoryHumanReviewService
from scripts.factory_p1_checksum import checksum

BATCH_ID = uuid.UUID("22c5684b-cf86-4137-82bf-be237be1e2ee")
SAMPLE_ID = uuid.UUID("ffc9948e-a60e-4ca7-9bb2-5044b64e7eb0")
URL = os.environ["DATABASE_URL"]

DECISIONS = [
    ("d7c50929-73c4-4987-a374-32584e84d17b", "a369a657-148b-4253-8c5f-6630e316d5c5"),
    ("680cbb8c-80c7-427a-8567-95b1272941f1", "bf421a0d-51e0-4bed-8ee5-fe2788e6dfba"),
    ("d081bc88-92f9-4a88-957a-a5a8ac2933e6", "5b75b731-0444-4617-9df8-4bca76d4373d"),
    ("7315643d-71b1-4d6f-894c-1dbcc923f994", "681f77af-d6bd-4a50-92e9-173a3ccc363e"),
    ("15b20501-d7e3-4cfe-beb5-854d935be32c", "5e4eb66f-bcbf-4a57-9446-1cbe62d8e8f5"),
]
ITEM_IDS = {x[1] for x in DECISIONS}
EXPECTED_ITEM_CHECKSUM = "0030955c195ffd2a27463ea48d5c57a8"
EXPECTED_BODY_CHECKSUM = "54c3caaa25b17c25258364cb561f6153"


async def body_md5s(session, item_ids: set[str]) -> dict[str, str]:
    rows = (
        await session.execute(
            text(
                """
                SELECT ci.id::text, md5(cv.body::text) AS body_md5, ci.status, cv.workflow_state
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                ORDER BY ci.id
                """
            ),
            {"ids": list(item_ids)},
        )
    ).mappings().all()
    return {r["id"]: dict(r) for r in rows}


async def fri_snapshot(session, fri_id: str) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT fri.id::text AS factory_review_item_id,
                       fri.content_item_id::text,
                       fri.candidate_id::text,
                       fri.decision,
                       fri.review_status,
                       fri.reviewer_id::text,
                       fri.reviewed_at,
                       fri.reviewer_note,
                       fri.ecaep_submit_eligible,
                       gc.factory_review_status,
                       gc.latest_factory_review_item_id::text
                FROM cms.factory_review_items fri
                JOIN cms.generation_candidates gc ON gc.id = fri.candidate_id
                WHERE fri.id = CAST(:id AS uuid)
                """
            ),
            {"id": fri_id},
        )
    ).mappings().one()
    return dict(row)


async def main() -> None:
    pre = await checksum(URL)
    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    submission_results = []

    async with Session() as session:
        pre_bodies = await body_md5s(session, ITEM_IDS)

        actor_row = (
            await session.execute(
                text(
                    """
                    SELECT actor_user_id FROM system.audit_logs
                    WHERE action = 'factory.sampling.created'
                      AND log_metadata->>'batch_id' = :bid
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

        hr = ContentFactoryHumanReviewService(session)
        checklist = {
            "scientific_correctness": True,
            "correct_answer": True,
            "distractors": True,
            "neet_suitability": True,
            "explanation": True,
            "academic_mapping": True,
            "difficulty": True,
            "language": True,
            "provenance": True,
        }

        for fri_id, expected_item_id in DECISIONS:
            result = await hr.submit_decision(
                uuid.UUID(fri_id),
                decision="ACCEPT",
                actor_id=actor_id,
                checklist=checklist,
            )
            snap = await fri_snapshot(session, fri_id)
            assert snap["content_item_id"] == expected_item_id
            submission_results.append({"service_result": result, "snapshot": snap})

        post_bodies = await body_md5s(session, ITEM_IDS)

        fri_all = (
            await session.execute(
                text(
                    """
                    SELECT fri.id::text, fri.decision, fri.review_status, fri.ecaep_submit_eligible,
                           gc.factory_review_status
                    FROM cms.factory_review_items fri
                    JOIN cms.generation_candidates gc ON gc.id = fri.candidate_id
                    WHERE fri.sample_id = CAST(:sid AS uuid) AND fri.deleted_at IS NULL
                    ORDER BY fri.id
                    """
                ),
                {"sid": str(SAMPLE_ID)},
            )
        ).mappings().all()

        sample = (
            await session.execute(select(ReviewSample).where(ReviewSample.id == SAMPLE_ID))
        ).scalar_one()
        batch = (
            await session.execute(select(ContentBatch).where(ContentBatch.id == BATCH_ID))
        ).scalar_one()

        audits = (
            await session.execute(
                text(
                    """
                    SELECT id::text, action, entity_id::text, actor_user_id::text, created_at,
                           log_metadata
                    FROM system.audit_logs
                    WHERE action = 'factory.review.accepted'
                      AND entity_id = ANY(CAST(:ids AS uuid[]))
                    ORDER BY created_at
                    """
                ),
                {"ids": [x[0] for x in DECISIONS]},
            )
        ).mappings().all()

        smoke_reviews = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.content_reviews cr
                    JOIN cms.content_versions cv ON cv.id = cr.content_version_id
                    WHERE cv.content_item_id = ANY(CAST(:ids AS uuid[]))
                    """
                ),
                {"ids": list(ITEM_IDS)},
            )
        ).scalar()

        qa_history_counts = (
            await session.execute(
                text(
                    """
                    SELECT evaluation_no, classification, COUNT(*)
                    FROM cms.qa_results qr
                    JOIN cms.generation_candidates gc ON gc.id = qr.candidate_id
                    WHERE gc.content_item_id = ANY(CAST(:ids AS uuid[]))
                    GROUP BY evaluation_no, classification
                    ORDER BY evaluation_no, classification
                    """
                ),
                {"ids": list(ITEM_IDS)},
            )
        ).all()

    await engine.dispose()
    post = await checksum(URL)

    bodies_unchanged = all(
        pre_bodies[i]["body_md5"] == post_bodies[i]["body_md5"] for i in ITEM_IDS
    )

    report = {
        "p5_decision_submission_status": "SUCCESS",
        "decisions_submitted": len(submission_results),
        "submissions": submission_results,
        "sample_final_state": {
            "id": str(sample.id),
            "sample_key": sample.sample_key,
            "green_sample_size": sample.green_sample_size,
            "selected_count": len(sample.selected_candidate_ids or []),
        },
        "batch_final_state": {"id": str(batch.id), "status": batch.status, "qa_pass_count": batch.qa_pass_count},
        "all_review_items": [dict(r) for r in fri_all],
        "audit_records": [dict(a) for a in audits],
        "content_integrity": {
            "pre_item_checksum": pre["item_checksum"],
            "post_item_checksum": post["item_checksum"],
            "expected_item_checksum": EXPECTED_ITEM_CHECKSUM,
            "pre_body_checksum": pre["versions"]["body_checksum"],
            "post_body_checksum": post["versions"]["body_checksum"],
            "expected_body_checksum": EXPECTED_BODY_CHECKSUM,
            "pre_bodies": pre_bodies,
            "post_bodies": post_bodies,
            "bodies_unchanged": bodies_unchanged,
        },
        "ecaep_safety": {
            "all_draft": all(post_bodies[i]["status"] == "DRAFT" for i in ITEM_IDS),
            "all_workflow_draft": all(post_bodies[i]["workflow_state"] == "DRAFT" for i in ITEM_IDS),
            "smoke_item_content_reviews": smoke_reviews,
            "published_pre": pre["counts"]["published"],
            "published_post": post["counts"]["published"],
            "in_review_pre": pre["counts"]["in_review"],
            "in_review_post": post["counts"]["in_review"],
        },
        "qa_history_preserved": [{"evaluation_no": e, "classification": c, "count": n} for e, c, n in qa_history_counts],
        "confirmations": {
            "zero_ai_calls": True,
            "no_publication": pre["counts"]["published"] == post["counts"]["published"] == 11,
            "no_ecaep_transition": smoke_reviews == 0,
            "exactly_five_decisions": len(submission_results) == 5,
            "all_accept": all(s["snapshot"]["decision"] == "ACCEPT" for s in submission_results),
            "all_accepted_status": all(s["snapshot"]["review_status"] == "ACCEPTED" for s in submission_results),
            "all_ecaep_submit_eligible": all(s["snapshot"]["ecaep_submit_eligible"] is True for s in submission_results),
        },
        "verdict": "GREEN"
        if (
            len(submission_results) == 5
            and bodies_unchanged
            and pre["item_checksum"] == post["item_checksum"] == EXPECTED_ITEM_CHECKSUM
            and pre["versions"]["body_checksum"] == post["versions"]["body_checksum"] == EXPECTED_BODY_CHECKSUM
            and post["counts"]["published"] == 11
            and post["counts"]["in_review"] == 11
            and smoke_reviews == 0
            and all(post_bodies[i]["status"] == "DRAFT" for i in ITEM_IDS)
        )
        else "RED",
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
