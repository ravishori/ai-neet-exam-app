"""FACTORY-P5: stratified GREEN sample + review packet for exact P3 Gemini 95 population.

Uses factory_sample_v1: n = min(N, max(n_min, ceil(k*sqrt(N)))) with settings defaults.
Population restricted to the 95 P3 content_item_ids (excludes 5 older batch CREATED items).
No LLM. No content mutation. Decisions submitted in a separate controlled step.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.modules.knowledge.models  # noqa: F401
from app.core.config import get_settings
from app.modules.cms.acquisition.physics_integrity_fingerprints import collect_integrity_snapshot
from app.modules.cms.models.content_factory import ContentBatch
from app.modules.cms.models.content_factory_planning import QuestionBlueprint
from app.modules.cms.models.factory_qa import QAResult, ReviewSample
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.services.content_factory_human_review_service import ContentFactoryHumanReviewService
from app.modules.cms.services.content_factory_qa_service import ContentFactorySamplingService
from scripts.factory_p1_checksum import checksum

BATCH_ID = uuid.UUID("22c5684b-cf86-4137-82bf-be237be1e2ee")
BATCH_KEY = "factory-p3-pilot-2026-09-01-batch"
SEED = 42
SAMPLE_KEY = "sample-factory-p3-pilot-2026-09-01-batch-p3-95-42"
STAMP = "20260902"
AUDITS = Path(r"D:\ravishori\AI Neet Exam App\docs\audits")
P3_RESULTS = Path(r"D:\ravishori\AI Neet Exam App\docs\product\CONTENT_FACTORY_P3_PILOT_RESULTS.json")
P4_RESULTS = Path(r"D:\ravishori\AI Neet Exam App\docs\audits\TALOS_FACTORY_P4_95_RESULTS_20260902.json")


def load_p3_ids() -> list[str]:
    data = json.loads(P3_RESULTS.read_text(encoding="utf-8"))
    ids: list[str] = []
    for r in data["results"]:
        ids.extend(r.get("content_item_ids") or [])
    p4 = json.loads(P4_RESULTS.read_text(encoding="utf-8"))
    p4_ids = {q["item_id"] for q in p4["per_question"]}
    if set(ids) != p4_ids or len(ids) != 95:
        raise SystemExit(f"P3/P4 population mismatch: p3={len(ids)} p4={len(p4_ids)}")
    if any(q["overall_p4_classification"] != "GREEN" for q in p4["per_question"]):
        raise SystemExit("Not all P4 items are GREEN")
    return ids


async def integrity_bundle(session: AsyncSession, url: str, item_ids: list[str]) -> dict:
    cs = await checksum(url)
    snap = await collect_integrity_snapshot(session)
    snap_out = {k: v for k, v in snap.items() if not str(k).endswith("_row_canons")}
    rows = (
        await session.execute(
            text(
                """
                SELECT ci.id::text AS id, ci.status, md5(cv.body::text) AS body_md5,
                       cv.workflow_state
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                ORDER BY ci.id
                """
            ),
            {"ids": item_ids},
        )
    ).mappings().all()
    body_fp = __import__("hashlib").md5(
        "|".join(f"{r['id']}:{r['body_md5']}:{r['status']}" for r in rows).encode()
    ).hexdigest()
    return {
        "checksum": {
            "counts": dict(cs["counts"]),
            "item_checksum": cs["item_checksum"],
            "body_checksum": cs["versions"]["body_checksum"],
            "versions": cs["versions"]["versions"],
            "review_count": cs["review_count"],
        },
        "integrity": snap_out,
        "p5_population": {
            "count": len(rows),
            "status_distribution": dict(Counter(r["status"] for r in rows)),
            "body_status_fingerprint": body_fp,
            "bodies": {
                r["id"]: {
                    "status": r["status"],
                    "body_md5": r["body_md5"],
                    "workflow_state": r["workflow_state"],
                }
                for r in rows
            },
        },
    }


async def main() -> None:
    item_ids = load_p3_ids()
    settings = get_settings()
    url = settings.database_url
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        pre = await integrity_bundle(session, url, item_ids)
        pre_path = AUDITS / f"TALOS_FACTORY_P5_95_PRE_BASELINE_{STAMP}.json"

        # Authoritative sample size against N=95 P3 GREEN population
        n_green = 95
        k = settings.factory_green_sample_k
        n_min = settings.factory_green_sample_min
        target = min(n_green, max(n_min, int(math.ceil(k * math.sqrt(n_green)))))

        # Load GREEN tuples only for P3 95
        rows = list(
            (
                await session.execute(
                    select(GenerationCandidate, QAResult, QuestionBlueprint)
                    .join(QAResult, QAResult.id == GenerationCandidate.latest_qa_result_id)
                    .outerjoin(QuestionBlueprint, QuestionBlueprint.id == GenerationCandidate.blueprint_id)
                    .where(
                        GenerationCandidate.batch_id == BATCH_ID,
                        GenerationCandidate.status == "CREATED",
                        GenerationCandidate.deleted_at.is_(None),
                        GenerationCandidate.content_item_id.in_([uuid.UUID(i) for i in item_ids]),
                        QAResult.is_latest.is_(True),
                        QAResult.classification == "GREEN",
                        QAResult.sampling_eligible.is_(True),
                    )
                )
            ).all()
        )
        if len(rows) != 95:
            raise SystemExit(f"Expected 95 GREEN sampling-eligible P3 candidates, got {len(rows)}")

        green = [(c, q, bp) for c, q, bp in rows]
        selected, strata = ContentFactorySamplingService._stratified_draw(
            green, target=target, seed=SEED
        )

        # Create ReviewSample (idempotent by sample_key)
        existing = (
            await session.execute(
                select(ReviewSample).where(
                    ReviewSample.sample_key == SAMPLE_KEY, ReviewSample.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        actor = (
            await session.execute(
                text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
            )
        ).scalar_one()

        if existing:
            sample = existing
            idempotent = True
        else:
            reasons = {str(cid): "GREEN_STRATIFIED_SAMPLE_P3_95" for cid in selected}
            sample = ReviewSample(
                sample_key=SAMPLE_KEY,
                batch_id=BATCH_ID,
                policy_version=settings.factory_sampling_policy_version,
                seed=SEED,
                green_sample_size=len(selected),
                selected_candidate_ids=selected,
                yellow_candidate_ids=[],
                red_candidate_ids=[],
                selection_reasons=reasons,
                strata_summary={
                    **strata,
                    "population_restriction": "p3_gemini_95_only",
                    "excluded_older_batch_created": 5,
                    "formula": f"min({n_green}, max({n_min}, ceil({k}*sqrt({n_green})))) = {target}",
                },
                note="P5 controlled sample for P3 Gemini 95 — excludes 5 older batch CREATED",
                created_by=actor,
                updated_by=actor,
                version=1,
            )
            session.add(sample)
            await session.flush()
            await ContentFactoryHumanReviewService(session).materialize_sample_items(
                sample, actor_id=actor
            )
            await session.commit()
            idempotent = False
            sample = (
                await session.execute(
                    select(ReviewSample).where(ReviewSample.sample_key == SAMPLE_KEY)
                )
            ).scalar_one()

        hr = ContentFactoryHumanReviewService(session)
        # Build packets without flipping all to IN_REVIEW via get_review_packet side effect —
        # use direct queries to avoid premature status change before decisions.
        fri_rows = list(
            (
                await session.execute(
                    select(GenerationCandidate).where(
                        GenerationCandidate.id.in_(selected),
                        GenerationCandidate.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
        )
        cand_by_id = {c.id: c for c in fri_rows}

        # Ensure FRI rows exist
        from app.modules.cms.models.factory_qa import FactoryReviewItem

        fris = list(
            (
                await session.execute(
                    select(FactoryReviewItem).where(
                        FactoryReviewItem.sample_id == sample.id,
                        FactoryReviewItem.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
        )
        if len(fris) != len(selected):
            await hr.materialize_sample_items(sample, actor_id=actor)
            await session.commit()
            fris = list(
                (
                    await session.execute(
                        select(FactoryReviewItem).where(
                            FactoryReviewItem.sample_id == sample.id,
                            FactoryReviewItem.deleted_at.is_(None),
                        )
                    )
                ).scalars().all()
            )

        packets = []
        for fri in sorted(fris, key=lambda x: str(x.content_item_id)):
            # Build packet manually to avoid SELECTED→IN_REVIEW until decision phase
            cand = cand_by_id.get(fri.candidate_id) or (
                await session.execute(
                    select(GenerationCandidate).where(GenerationCandidate.id == fri.candidate_id)
                )
            ).scalar_one()
            row = (
                await session.execute(
                    text(
                        """
                        SELECT ci.id::text AS item_id, ci.status, ci.tags,
                               md5(cv.body::text) AS body_md5,
                               cv.body, cv.workflow_state,
                               s.name AS subject, ch.name AS chapter, t.name AS topic, c.name AS concept
                        FROM cms.content_items ci
                        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                        JOIN academic.concepts c ON c.id = ci.concept_id
                        JOIN academic.topics t ON t.id = c.topic_id
                        JOIN academic.chapters ch ON ch.id = t.chapter_id
                        JOIN academic.subjects s ON s.id = ch.subject_id
                        WHERE ci.id = CAST(:id AS uuid)
                        """
                    ),
                    {"id": str(fri.content_item_id)},
                )
            ).mappings().one()
            body = row["body"] if isinstance(row["body"], dict) else json.loads(row["body"])
            qa = None
            if fri.qa_result_id:
                qa = (
                    await session.execute(select(QAResult).where(QAResult.id == fri.qa_result_id))
                ).scalar_one_or_none()
            packets.append(
                {
                    "factory_review_item_id": str(fri.id),
                    "candidate_id": str(fri.candidate_id),
                    "item_id": row["item_id"],
                    "selection_class": fri.selection_class,
                    "review_status": fri.review_status,
                    "subject": row["subject"],
                    "chapter": row["chapter"],
                    "topic": row["topic"],
                    "concept": row["concept"],
                    "difficulty": body.get("difficulty"),
                    "stem": body.get("stem"),
                    "options": body.get("options"),
                    "correct_option": body.get("correct_option"),
                    "explanation": body.get("explanation"),
                    "status": row["status"],
                    "workflow_state": row["workflow_state"],
                    "body_md5": row["body_md5"],
                    "tags": list(row["tags"] or []),
                    "provider": cand.provider,
                    "routing": cand.routing_policy,
                    "model": cand.model_used,
                    "is_fallback": cand.is_fallback,
                    "p4_classification": qa.classification if qa else None,
                    "p4_gate_results": qa.gate_results if qa else None,
                    "p4_note": "P4 = automated QA; P5 = human review",
                    "scientific_certification": False,
                    "ncert_verified": False,
                }
            )

        batch = (
            await session.execute(select(ContentBatch).where(ContentBatch.id == BATCH_ID))
        ).scalar_one()

        # Population vs sample distribution
        pop_subj = Counter()
        for r in (
            await session.execute(
                text(
                    """
                    SELECT s.name AS subject, count(*)::int AS n
                    FROM cms.content_items ci
                    JOIN academic.concepts c ON c.id = ci.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                    GROUP BY s.name
                    """
                ),
                {"ids": item_ids},
            )
        ).mappings():
            pop_subj[r["subject"]] = r["n"]
        sample_subj = Counter(p["subject"] for p in packets)

        pre_out = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "database": url.rsplit("/", 1)[-1].split("?")[0],
            "note": "Read-only baseline before P5 sample materialization writes (QA metadata already present from P4).",
            "batch": {"id": str(BATCH_ID), "batch_key": BATCH_KEY, "status": batch.status},
            "population_item_ids": item_ids,
            "excluded": {
                "older_batch_created_candidates": 5,
                "note": "Excluded from P5 population; not in CONTENT_FACTORY_P3_PILOT_RESULTS.json",
            },
            **pre,
            "qa_fields_sample": {
                "all_p4_green": True,
                "lineage_expected": "gemini / fixed:gemini / gemini-3.6-flash",
            },
        }
        # If this is first run, baseline was taken before sample writes — rewrite note if we already wrote sample
        if not idempotent:
            pre_out["note"] = (
                "Baseline captured in same transaction window prior to sample insert; "
                "content bodies/statuses unchanged by sampling."
            )
        pre_path.write_text(json.dumps(pre_out, indent=2, default=str), encoding="utf-8")

        sample_doc = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "authoritative_rule": "factory_sample_v1",
            "formula": f"n=min(N, max({n_min}, ceil({k}*sqrt(N))))",
            "population_size_N": n_green,
            "computed_sample_size": target,
            "actual_sample_size": len(selected),
            "seed": SEED,
            "selection_algorithm": "ContentFactorySamplingService._stratified_draw round-robin by subject|family|difficulty|blueprint",
            "sample_key": SAMPLE_KEY,
            "sample_id": str(sample.id),
            "idempotent_hit": idempotent,
            "strata": sample.strata_summary,
            "selected_candidate_ids": [str(x) for x in selected],
            "selected_item_ids": [p["item_id"] for p in packets],
            "population_distribution_by_subject": dict(pop_subj),
            "sample_distribution_by_subject": dict(sample_subj),
            "population_restriction": "P3 Gemini 95 only",
        }
        sample_path = AUDITS / f"TALOS_FACTORY_P5_95_SAMPLE_{STAMP}.json"
        sample_path.write_text(json.dumps(sample_doc, indent=2, default=str), encoding="utf-8")

        packet_doc = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "P4 = automated QA. P5 = human review. Packet is read-only content snapshot.",
            "sample_key": SAMPLE_KEY,
            "sample_id": str(sample.id),
            "seed": SEED,
            "items": packets,
        }
        packet_path = AUDITS / f"TALOS_FACTORY_P5_95_REVIEW_PACKET_{STAMP}.json"
        packet_path.write_text(json.dumps(packet_doc, indent=2, default=str), encoding="utf-8")

    await engine.dispose()
    print(
        json.dumps(
            {
                "sample_size": len(selected),
                "target": target,
                "seed": SEED,
                "sample_key": SAMPLE_KEY,
                "sample_id": str(sample.id),
                "idempotent": idempotent,
                "subjects": dict(sample_subj),
                "item_ids": [p["item_id"] for p in packets],
                "pre": str(pre_path),
                "sample": str(sample_path),
                "packet": str(packet_path),
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
