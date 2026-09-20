#!/usr/bin/env python3
"""FACTORY-P5 sample + review packet for Production Seed V2 exact 100 (P4 GREEN).

Uses factory_sample_v1 stratified draw restricted to the exact P3/P4 membership.
No LLM. No content body mutation. Decisions submitted in a separate controlled step
(or by the companion decisions path in the same session when DECISIONS are provided).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import sys
import uuid
from collections import Counter, defaultdict
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
from app.modules.cms.models.factory_qa import FactoryReviewItem, QAResult, ReviewSample
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.services.content_factory_human_review_service import ContentFactoryHumanReviewService
from app.modules.cms.services.content_factory_qa_service import ContentFactorySamplingService
from scripts.factory_p1_checksum import checksum

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
P3_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_GENERATION_20260903.json"
P4_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P4_100_20260903.json"
PLAN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"
AUTH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
POST = AUDITS / "TALOS_PRODUCTION_SEED_V1_POST_PUBLICATION_AUDIT_20260903.json"
PACKET_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_100_PACKET_20260903.json"
SAMPLE_META_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_100_SAMPLE_20260903.json"

BATCH_ID = uuid.UUID("4509d488-c100-47f0-8357-4b1678abd00d")
BATCH_KEY = "production-seed-v2-2026-09-03-batch"
SEED = 42
SAMPLE_KEY = "sample-production-seed-v2-2026-09-03-batch-p5-100-42"
EXPECTED_V1_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"


def load_membership() -> tuple[list[str], dict]:
    p3 = json.loads(P3_PATH.read_text(encoding="utf-8"))
    p4 = json.loads(P4_PATH.read_text(encoding="utf-8"))
    ids = list(p4["exact_candidate_ids"])
    p3_ids = [s["content_item_id"] for s in p3["slot_coverage"]["slots"] if s.get("status") == "GENERATED"]
    if set(ids) != set(p3_ids) or len(ids) != 100:
        raise SystemExit(f"P3/P4 membership mismatch: p4={len(ids)} p3={len(set(p3_ids))}")
    if p4.get("verdict") != "GREEN":
        raise SystemExit(f"P4 verdict not GREEN: {p4.get('verdict')}")
    if any(q.get("overall_p4_classification") != "GREEN" for q in p4["per_question"]):
        raise SystemExit("Not all P4 items classified GREEN")
    return ids, p4


def is_graphical_body(body: dict) -> bool:
    if not isinstance(body, dict):
        return False
    for key in ("diagram_svg", "diagram", "figure", "image_url", "visual", "graph"):
        if body.get(key):
            return True
    stem = str(body.get("stem") or "")
    if any(tok in stem.lower() for tok in ("shown in the figure", "in the diagram", "as shown", "graph below", "figure below")):
        return True
    return False


async def pop_fp(session: AsyncSession, tag: str) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status='PUBLISHED') AS published,
                       COUNT(*) FILTER (WHERE status='DRAFT') AS draft,
                       md5(coalesce(string_agg(
                         ci.id::text||'|'||ci.slug||'|'||ci.status||'|'||coalesce(ci.concept_id::text,'null')
                         ||'|'||md5(coalesce(cv.body::text,''))||'|'||coalesce(array_to_string(ci.tags,','),''),
                         E'\\n' ORDER BY ci.id::text), '')) AS content_fp
                FROM cms.content_items ci
                LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.content_type='QUESTION' AND ci.deleted_at IS NULL AND :tag = ANY(ci.tags)
                """
            ),
            {"tag": tag},
        )
    ).mappings().one()
    return dict(row)


async def t6f2_fp(session: AsyncSession) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       md5(coalesce(string_agg(
                         ci.id::text||'|'||ci.slug||'|'||ci.status||'|'||md5(coalesce(cv.body::text,'')),
                         E'\\n' ORDER BY ci.id::text), '')) AS content_fp
                FROM cms.content_items ci
                LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.content_type='QUESTION' AND ci.deleted_at IS NULL
                  AND :tag = ANY(ci.tags) AND ci.status='PUBLISHED'
                """
            ),
            {"tag": "physics-t6f1-pilot-20260902"},
        )
    ).mappings().one()
    return dict(row)


async def fingerprint_items(session: AsyncSession, ids: list[str]) -> dict:
    rows = (
        await session.execute(
            text(
                """
                SELECT ci.id::text AS id, ci.status, md5(cv.body::text) AS body_md5
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                ORDER BY ci.id
                """
            ),
            {"ids": ids},
        )
    ).mappings().all()
    blob = "|".join(f"{r['id']}:{r['body_md5']}:{r['status']}" for r in rows)
    return {
        "n": len(rows),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "bodies_fp": hashlib.sha256(blob.encode()).hexdigest(),
        "bodies": {r["id"]: {"status": r["status"], "body_md5": r["body_md5"]} for r in rows},
    }


async def integrity_bundle(session: AsyncSession, url: str, item_ids: list[str], v1_ids: list[str]) -> dict:
    cs = await checksum(url)
    snap = await collect_integrity_snapshot(session)
    snap_out = {k: v for k, v in snap.items() if not str(k).endswith("_row_canons")}
    return {
        "checksum": {
            "counts": dict(cs["counts"]),
            "item_checksum": cs["item_checksum"],
            "body_checksum": cs["versions"]["body_checksum"],
            "versions": cs["versions"]["versions"],
            "review_count": cs["review_count"],
        },
        "integrity": snap_out,
        "v2": await fingerprint_items(session, item_ids),
        "v1": await fingerprint_items(session, v1_ids),
        "t6d": await pop_fp(session, "physics-t6d-pilot-20260902"),
        "t6f2": await t6f2_fp(session),
        "legacy": await pop_fp(session, "legacy-physics-5000-import-20260902"),
    }


async def main() -> int:
    item_ids, p4 = load_membership()
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    plan_by_slot = {s["slot_id"]: s for s in plan["slots"]}
    p3 = json.loads(P3_PATH.read_text(encoding="utf-8"))
    slot_by_item = {
        s["content_item_id"]: s for s in p3["slot_coverage"]["slots"] if s.get("content_item_id")
    }
    auth = json.loads(AUTH.read_text(encoding="utf-8"))
    v1_ids = auth["exact_uuid_allowlist"]
    settings = get_settings()
    url = settings.database_url
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        pre = await integrity_bundle(session, url, item_ids, v1_ids)
        batch = (
            await session.execute(select(ContentBatch).where(ContentBatch.id == BATCH_ID))
        ).scalar_one()
        if batch.batch_key != BATCH_KEY:
            raise SystemExit(f"Batch key mismatch: {batch.batch_key}")

        n_green = 100
        k = settings.factory_green_sample_k
        n_min = settings.factory_green_sample_min
        target = min(n_green, max(n_min, int(math.ceil(k * math.sqrt(n_green)))))

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
        if len(rows) != 100:
            raise SystemExit(f"Expected 100 GREEN sampling-eligible V2 candidates, got {len(rows)}")

        green = [(c, q, bp) for c, q, bp in rows]
        selected, strata = ContentFactorySamplingService._stratified_draw(
            green, target=target, seed=SEED
        )

        actor = (
            await session.execute(
                text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
            )
        ).scalar_one()

        existing = (
            await session.execute(
                select(ReviewSample).where(
                    ReviewSample.sample_key == SAMPLE_KEY, ReviewSample.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if existing:
            sample = existing
            idempotent = True
            selected = list(existing.selected_candidate_ids or [])
        else:
            reasons = {str(cid): "GREEN_STRATIFIED_SAMPLE_SEED_V2_100" for cid in selected}
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
                    "population_restriction": "production_seed_v2_exact_100",
                    "formula": f"min({n_green}, max({n_min}, ceil({k}*sqrt({n_green})))) = {target}",
                    "graphical_stratification": "NOT_SUPPORTED_BY_factory_sample_v1",
                },
                note="P5 controlled sample for Production Seed V2 exact 100 — DRAFT only",
                created_by=actor,
                updated_by=actor,
                version=1,
            )
            session.add(sample)
            await session.flush()
            await ContentFactoryHumanReviewService(session).materialize_sample_items(
                sample, actor_id=actor
            )
            if batch.status == "QA":
                batch.status = "SAMPLING"
            await session.commit()
            idempotent = False
            sample = (
                await session.execute(select(ReviewSample).where(ReviewSample.sample_key == SAMPLE_KEY))
            ).scalar_one()

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
            await ContentFactoryHumanReviewService(session).materialize_sample_items(
                sample, actor_id=actor
            )
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

        # Population graphical census (bodies)
        pop_bodies = (
            await session.execute(
                text(
                    """
                    SELECT ci.id::text AS id, cv.body, s.name AS subject,
                           cv.body->>'difficulty' AS difficulty
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                    JOIN academic.concepts c ON c.id = ci.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                    """
                ),
                {"ids": item_ids},
            )
        ).mappings().all()
        pop_graphical = sum(
            1
            for r in pop_bodies
            if is_graphical_body(r["body"] if isinstance(r["body"], dict) else json.loads(r["body"]))
        )
        plan_archetype_pop = Counter()
        for iid in item_ids:
            slot = slot_by_item.get(iid) or {}
            planned = plan_by_slot.get(slot.get("slot_id") or "", {})
            plan_archetype_pop[planned.get("question_archetype") or "unknown"] += 1

        packets = []
        sample_subj = Counter()
        sample_diff = Counter()
        sample_arch = Counter()
        sample_graphical = 0
        for fri in sorted(fris, key=lambda x: str(x.content_item_id)):
            row = (
                await session.execute(
                    text(
                        """
                        SELECT ci.id::text AS item_id, ci.status, ci.tags,
                               md5(cv.body::text) AS body_md5,
                               cv.body, cv.workflow_state,
                               s.name AS subject, ch.name AS chapter, t.name AS topic, c.name AS concept,
                               c.code AS concept_code,
                               gc.provider, gc.model_used, gc.routing_policy, gc.is_fallback,
                               qb.blueprint_key, qb.constraints, qb.difficulty AS bp_difficulty
                        FROM cms.content_items ci
                        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                        JOIN cms.generation_candidates gc ON gc.id = CAST(:cid AS uuid)
                        LEFT JOIN cms.question_blueprints qb ON qb.id = gc.blueprint_id
                        JOIN academic.concepts c ON c.id = ci.concept_id
                        JOIN academic.topics t ON t.id = c.topic_id
                        JOIN academic.chapters ch ON ch.id = t.chapter_id
                        JOIN academic.subjects s ON s.id = ch.subject_id
                        WHERE ci.id = CAST(:id AS uuid)
                        """
                    ),
                    {"id": str(fri.content_item_id), "cid": str(fri.candidate_id)},
                )
            ).mappings().one()
            body = row["body"] if isinstance(row["body"], dict) else json.loads(row["body"])
            graphical = is_graphical_body(body)
            if graphical:
                sample_graphical += 1
            slot = slot_by_item.get(row["item_id"]) or {}
            planned = plan_by_slot.get(slot.get("slot_id") or "", {})
            arch = planned.get("question_archetype") or (row["constraints"] or {}).get("question_archetype")
            sample_subj[row["subject"]] += 1
            sample_diff[body.get("difficulty") or row["bp_difficulty"] or "unknown"] += 1
            sample_arch[arch or "unknown"] += 1
            packets.append(
                {
                    "factory_review_item_id": str(fri.id),
                    "candidate_id": str(fri.candidate_id),
                    "item_id": row["item_id"],
                    "slot_id": slot.get("slot_id"),
                    "plan_blueprint_id": slot.get("plan_blueprint_id")
                    or (row["constraints"] or {}).get("plan_blueprint_id"),
                    "selection_class": fri.selection_class,
                    "review_status": fri.review_status,
                    "subject": row["subject"],
                    "chapter": row["chapter"],
                    "topic": row["topic"],
                    "concept": row["concept"],
                    "concept_code": row["concept_code"],
                    "difficulty": body.get("difficulty"),
                    "question_archetype": arch,
                    "independent_verification_required": planned.get("independent_verification_required"),
                    "graphical": graphical,
                    "has_diagram_svg": bool(body.get("diagram_svg")),
                    "stem": body.get("stem"),
                    "options": body.get("options"),
                    "correct_option": body.get("correct_option"),
                    "explanation": body.get("explanation"),
                    "status": row["status"],
                    "workflow_state": row["workflow_state"],
                    "body_md5": row["body_md5"],
                    "provider": row["provider"],
                    "routing": row["routing_policy"],
                    "model": row["model_used"],
                    "is_fallback": row["is_fallback"],
                    "blueprint_key": row["blueprint_key"],
                    "scientific_certification": False,
                    "ncert_verified": False,
                }
            )

        sample_doc = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "sample_key": SAMPLE_KEY,
            "sample_id": str(sample.id),
            "batch_id": str(BATCH_ID),
            "batch_key": BATCH_KEY,
            "idempotent": idempotent,
            "policy_version": settings.factory_sampling_policy_version,
            "selection_algorithm": "factory_sample_v1 stratified round-robin by subject|family|difficulty|blueprint",
            "seed": SEED,
            "formula": f"min({n_green}, max({n_min}, ceil({k}*sqrt({n_green})))) = {target}",
            "target_sample_size": target,
            "actual_sample_size": len(selected),
            "selected_candidate_ids": [str(x) for x in selected],
            "population_item_ids": item_ids,
            "population_n": 100,
            "strata_summary": sample.strata_summary,
            "subject_distribution_sample": dict(sample_subj),
            "difficulty_distribution_sample": dict(sample_diff),
            "archetype_distribution_sample": dict(sample_arch),
            "graphical_distribution": {
                "population_graphical": pop_graphical,
                "population_non_graphical": 100 - pop_graphical,
                "sample_graphical": sample_graphical,
                "sample_non_graphical": len(packets) - sample_graphical,
                "sampling_stratifies_graphical": False,
                "limitation": (
                    "factory_sample_v1 does not stratify by graphical/non-graphical. "
                    "Distribution is recorded observationally only."
                ),
            },
            "plan_archetype_population": dict(plan_archetype_pop),
            "integrity_before": {
                "v2_bodies_fp": pre["v2"]["bodies_fp"],
                "v2_status": pre["v2"]["status_counts"],
                "v1_bodies_fp": pre["v1"]["bodies_fp"],
                "t6d_fp": pre["t6d"]["content_fp"],
                "t6f2_fp": pre["t6f2"]["content_fp"],
                "legacy_fp": pre["legacy"]["content_fp"],
                "cms_counts": pre["checksum"]["counts"],
                "seed_v1_hash_ok": auth.get("allowlist_sha256") == EXPECTED_V1_SHA,
            },
        }
        SAMPLE_META_PATH.write_text(json.dumps(sample_doc, indent=2, default=str), encoding="utf-8")
        PACKET_PATH.write_text(
            json.dumps(
                {
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "sample_key": SAMPLE_KEY,
                    "packets": packets,
                    "disclaimer": "P5 review packet — not NCERT certified; not scientifically certified",
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "sample_size": len(packets),
                    "subjects": dict(sample_subj),
                    "difficulty": dict(sample_diff),
                    "archetypes": dict(sample_arch),
                    "graphical_sample": sample_graphical,
                    "graphical_population": pop_graphical,
                    "packet": str(PACKET_PATH),
                },
                indent=2,
            )
        )
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
