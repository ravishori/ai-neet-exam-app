#!/usr/bin/env python3
"""Production Seed V2 P3 generation — DRAFT only, fixed Gemini, frozen 100-slot plan.

Does NOT approve, publish, run P4/P5, or mutate Seed V1 / T6-D / T6-F2 / legacy.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["FACTORY_PROVIDER_MODE"] = "fixed"
os.environ["FACTORY_PROVIDER"] = "gemini"
os.environ["FACTORY_PROVIDER_FALLBACK_CHAIN"] = ""
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
from app.core.config import get_settings
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.ai.gateway.base import PROVIDER_BLOCKED
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.schemas.content_factory import ContentBatchCreateRequest
from app.modules.cms.schemas.content_factory_planning import (
    LearningObjectiveCreateRequest,
    QuestionBlueprintCreateRequest,
    QuestionFamilyCreateRequest,
)
from app.modules.cms.services.factory_v2_visual import build_v2_generation_constraints
from app.modules.cms.services.content_factory_generation_service import ContentFactoryGenerationService
from app.modules.cms.services.content_factory_planning_service import ContentFactoryPlanningService
from app.modules.cms.services.content_factory_service import ContentFactoryService
from app.modules.cms.services.factory_seed_diversity import _FORBIDDEN_TEMPLATE_PATTERNS
from app.modules.identity.models.user import User
from scripts.factory_p1_checksum import checksum
from scripts.run_factory_p3_pilot import _provider_preflight

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
PLAN_PATH = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"
OUT_PATH = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V2_GENERATION_20260903.json"
AUTH = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
POST = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V1_POST_PUBLICATION_AUDIT_20260903.json"
P3_RESULTS = ROOT / "docs" / "product" / "CONTENT_FACTORY_P3_PILOT_RESULTS.json"

SEED_TAG = "production-seed-v2-2026-09-03"
BATCH_KEY = "production-seed-v2-2026-09-03-batch"
URL = os.environ["DATABASE_URL"]
GLOBAL_MAX_ATTEMPTS = 200
GLOBAL_MAX_COST_USD = 30.0
EXPECTED_V1_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"
FORBIDDEN = [name for name, _ in _FORBIDDEN_TEMPLATE_PATTERNS]


def plan_sha256() -> str:
    return hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()


def load_p3_95_ids() -> list[str]:
    if not P3_RESULTS.is_file():
        return []
    data = json.loads(P3_RESULTS.read_text(encoding="utf-8"))
    ids: list[str] = []
    for r in data.get("results") or []:
        ids.extend(r.get("content_item_ids") or [])
    return ids


async def fingerprint_items(session: AsyncSession, ids: list[str]) -> dict:
    if not ids:
        return {"n": 0, "bodies_fp": None, "status_counts": {}}
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
    }


async def pop_fp(session: AsyncSession, tag: str) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status='PUBLISHED') AS published,
                       COUNT(*) FILTER (WHERE status='DRAFT') AS draft,
                       COUNT(*) FILTER (WHERE status='APPROVED') AS approved,
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
                  AND :tag = ANY(ci.tags) AND ci.status = 'PUBLISHED'
                """
            ),
            {"tag": "physics-t6f1-pilot-20260902"},
        )
    ).mappings().one()
    return {"tag": "physics-t6f1-pilot-20260902", **dict(row)}


async def v1_status(session: AsyncSession, ids: list[str]) -> dict:
    rows = (
        await session.execute(
            text(
                "SELECT status, count(*) FROM cms.content_items WHERE id = ANY(CAST(:ids AS uuid[])) GROUP BY status"
            ),
            {"ids": ids},
        )
    ).all()
    return dict(rows)


async def protected_bundle(session: AsyncSession) -> dict:
    post = json.loads(POST.read_text(encoding="utf-8"))
    auth = json.loads(AUTH.read_text(encoding="utf-8"))
    ids = auth["exact_uuid_allowlist"]
    t6d = await pop_fp(session, "physics-t6d-pilot-20260902")
    t6f2 = await t6f2_fp(session)
    legacy = await pop_fp(session, "legacy-physics-5000-import-20260902")
    v1_items = await fingerprint_items(session, ids)
    exp = post["protected_population_integrity"]["after"]
    st = await v1_status(session, ids)
    return {
        "seed_v1_allowlist_sha256": auth.get("allowlist_sha256"),
        "seed_v1_items": v1_items,
        "seed_v1_status": st,
        "t6d": t6d,
        "t6f2": t6f2,
        "legacy": legacy,
        "unchanged_vs_post_publication": {
            "t6d": exp["t6d"]["content_fp"] == t6d["content_fp"] and int(exp["t6d"]["total"]) == int(t6d["total"]),
            "t6f2": exp["t6f2"]["content_fp"] == t6f2["content_fp"] and int(exp["t6f2"]["total"]) == int(t6f2["total"]),
            "legacy": exp["legacy"]["content_fp"] == legacy["content_fp"] and int(exp["legacy"]["total"]) == int(legacy["total"]),
            "seed_v1_hash": auth.get("allowlist_sha256") == EXPECTED_V1_SHA,
            "seed_v1_published_30": st.get("PUBLISHED") == 30,
        },
    }


async def ensure_concept_for_slot(session: AsyncSession, slot: dict, actor_id: uuid.UUID) -> uuid.UUID:
    if slot.get("concept_id"):
        cid = uuid.UUID(slot["concept_id"])
        exists = await session.get(Concept, cid)
        if not exists or exists.deleted_at is not None:
            raise SystemExit(f"Planned concept_id missing: {slot['slot_id']} {cid}")
        return cid
    chapter_id = uuid.UUID(slot["chapter_id"])
    chapter = await session.get(Chapter, chapter_id)
    if not chapter or chapter.deleted_at is not None:
        raise SystemExit(f"Planned chapter_id missing: {slot['slot_id']}")
    topic_code = f"sv2t-{slot['slot_id']}"[:80]
    concept_code = f"sv2c-{slot['slot_id']}"[:80]
    topic = (
        await session.execute(select(Topic).where(Topic.code == topic_code, Topic.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if not topic:
        topic = Topic(
            chapter_id=chapter_id,
            code=topic_code,
            name=(slot.get("topic") or f"Seed V2 {slot['slot_id']}")[:200],
            display_order=90,
            created_by=actor_id,
            updated_by=actor_id,
        )
        session.add(topic)
        await session.flush()
    concept = (
        await session.execute(select(Concept).where(Concept.code == concept_code, Concept.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if not concept:
        concept = Concept(
            topic_id=topic.id,
            code=concept_code,
            name=(slot.get("concept") or topic.name)[:200],
            summary=slot.get("planning_rationale"),
            ncert_reference=(slot.get("ncert_source_document") or "")[:300],
            difficulty=slot["difficulty"],
            display_order=90,
            created_by=actor_id,
            updated_by=actor_id,
        )
        session.add(concept)
        await session.flush()
    return concept.id


async def ensure_blueprints(session: AsyncSession, slots: list[dict], actor_id: uuid.UUID) -> tuple[list[dict], list[dict]]:
    planning = ContentFactoryPlanningService(session)
    out: list[dict] = []
    blueprint_failures: list[dict] = []
    for slot in slots:
        try:
            concept_id = await ensure_concept_for_slot(session, slot, actor_id)
        except SystemExit as exc:
            blueprint_failures.append(
                {
                    "slot_id": slot["slot_id"],
                    "plan_blueprint_id": slot["blueprint_id"],
                    "status": "NOT_GENERATED",
                    "reason": str(exc),
                }
            )
            continue
        concept = await session.get(Concept, concept_id)
        topic = await session.get(Topic, concept.topic_id)
        chapter = await session.get(Chapter, topic.chapter_id)
        subj = await session.get(Subject, chapter.subject_id)
        try:
            fam, _ = await planning.create_family(
                QuestionFamilyCreateRequest(
                    family_key=f"{SEED_TAG}-fam-{slot['slot_id']}"[:80],
                    name=f"Seed V2 {slot['subject']} {slot['intent']}"[:200],
                    applicable_subject_codes=[slot["subject_code"]],
                    cognitive_intent=slot["intent"],
                    difficulty_min="easy",
                    difficulty_max="hard",
                    question_format="MCQ_4",
                ),
                actor_id=actor_id,
            )
            obj, _ = await planning.create_objective(
                LearningObjectiveCreateRequest(
                    objective_key=f"{SEED_TAG}-obj-{slot['slot_id']}"[:120],
                    concept_id=concept_id,
                    title=f"Seed V2 {slot['slot_id']}: {slot['intent']}"[:300],
                    description=(
                        f"{slot.get('planning_rationale') or ''}\n"
                        f"Archetype: {slot['question_archetype']}. "
                        f"NCERT file: {slot.get('ncert_source_document')}. "
                        f"Do not invent page numbers, quotations, or figures. "
                        f"{slot.get('template_avoidance') or ''}"
                    )[:4000],
                    learning_level="apply",
                ),
                actor_id=actor_id,
            )
                    bp_key = slot["blueprint_key"]
                    bp, created = await planning.create_blueprint(
                        QuestionBlueprintCreateRequest(
                            blueprint_key=bp_key,
                            subject_id=subj.id,
                            chapter_id=chapter.id,
                            topic_id=topic.id,
                            concept_id=concept_id,
                            learning_objective_id=obj.id,
                            question_family_id=fam.id,
                            difficulty=slot["difficulty"],
                            target_count=1,
                            provenance_tier="ai",
                            constraints=build_v2_generation_constraints(
                                slot,
                                base={
                                    "question_format": "MCQ_4",
                                    "correct_option_count": 1,
                                    "explanation_required": True,
                                    "reasoning": slot["intent"],
                                    "cognitive_operation": slot.get("archetype_rationale") or slot["intent"],
                                    "question_archetype": slot["question_archetype"],
                                    "avoid_paraphrase_duplicates": True,
                                    "forbidden_templates": FORBIDDEN,
                                    "seed_slot_id": slot["slot_id"],
                                    "enforce_prior_stem_diversity": True,
                                    "plan_blueprint_id": slot["blueprint_id"],
                                    "ncert_source_document": slot.get("ncert_source_document"),
                                    "ncert_source_path": slot.get("ncert_source_path"),
                                },
                            ),
                            new_version=False,
                        ),
                        actor_id=actor_id,
                    )
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            blueprint_failures.append(
                {
                    "slot_id": slot["slot_id"],
                    "plan_blueprint_id": slot["blueprint_id"],
                    "status": "NOT_GENERATED",
                    "reason": f"planning_error:{exc}",
                }
            )
            continue
        if not bp.generation_eligible:
            blueprint_failures.append(
                {
                    "slot_id": slot["slot_id"],
                    "plan_blueprint_id": slot["blueprint_id"],
                    "status": "NOT_GENERATED",
                    "reason": f"Blueprint ineligible: {bp_key}",
                }
            )
            continue
        rec = {
            **slot,
            "factory_blueprint_id": str(bp.id),
            "factory_blueprint_created": created,
            "resolved_concept_id": str(concept_id),
        }
        out.append(rec)
        print(f"blueprint {'created' if created else 'reused'}: {bp_key}", flush=True)
        await session.commit()
    return out, blueprint_failures


async def tag_item(session: AsyncSession, item_id: str, slot_id: str) -> None:
    await session.execute(
        text(
            """
            UPDATE cms.content_items
            SET tags = (
                  SELECT ARRAY(SELECT DISTINCT x FROM unnest(COALESCE(tags, ARRAY[]::text[]) || CAST(:extra AS text[])) AS x)
                )
            WHERE id = CAST(:id AS uuid)
            """
        ),
        {"id": item_id, "extra": [SEED_TAG, f"slot:{slot_id}", "seed-v2"]},
    )


async def main() -> int:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    slots = plan["slots"]
    if len(slots) != 100:
        raise SystemExit(f"Plan must contain 100 slots, got {len(slots)}")
    sha = plan_sha256()
    settings = get_settings()
    preflight = _provider_preflight(settings)
    print("PROVIDER_PREFLIGHT", json.dumps({k: v for k, v in preflight.items() if k != "error"}, indent=2), flush=True)
    if not preflight["ok"]:
        OUT_PATH.write_text(
            json.dumps(
                {
                    "audit": "Production Seed V2 P3 Generation",
                    "date": "2026-09-03",
                    "status": "PROVIDER_BLOCKED",
                    "error": preflight.get("error"),
                    "plan_sha256": sha,
                    "verdict": "RED",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(json.dumps({"live_status": "PROVIDER_BLOCKED", "error": preflight["error"]}, indent=2))
        return 1

    if (settings.factory_provider or "").strip().lower() != "gemini":
        raise SystemExit("FACTORY_PROVIDER must be gemini")
    if float(settings.factory_max_pilot_attempt_multiplier) != 2.0:
        raise SystemExit("Do not change attempt multiplier")
    if float(settings.factory_max_pilot_cost_usd) != 30.0:
        raise SystemExit("Do not change cost ceiling setting")

    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    p3_ids = load_p3_95_ids()
    v1_ids = json.loads(AUTH.read_text(encoding="utf-8"))["exact_uuid_allowlist"]

    async with Session() as session:
        cs_before = await checksum(URL)
        prot_before = await protected_bundle(session)
        p3_before = await fingerprint_items(session, p3_ids)
        v1_before = await fingerprint_items(session, v1_ids)

        actor = (await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))).scalar_one_or_none()
        if not actor:
            raise SystemExit("No actor user")
        actor_id = actor.id

        planned, blueprint_failures = await ensure_blueprints(session, slots, actor_id)
        slot_results: list[dict] = list(blueprint_failures)
        if blueprint_failures:
            print(f"BLUEPRINT_FAILURES {len(blueprint_failures)}", flush=True)
        factory = ContentFactoryService(session)
        physics_sid = uuid.UUID(next(s["subject_id"] for s in slots if s["subject"] == "Physics"))
        batch, batch_created = await factory.create_batch(
            ContentBatchCreateRequest(
                batch_key=BATCH_KEY,
                name="Production Seed V2 — 100 DRAFT MCQs",
                description="P3 only from frozen 100-slot plan; DRAFT; not for auto-publish",
                subject_id=physics_sid,
                source_type="AI",
                source_tier="ai",
                target_count=100,
            ),
            actor_id=actor_id,
        )
        print(f"batch {'created' if batch_created else 'reused'}: {batch.id}", flush=True)

        existing = (
            await session.execute(
                text(
                    """
                    SELECT gc.blueprint_id::text, gc.content_item_id::text
                    FROM cms.generation_candidates gc
                    WHERE gc.batch_id = :bid AND gc.status = 'CREATED'
                      AND gc.deleted_at IS NULL AND gc.content_item_id IS NOT NULL
                    """
                ),
                {"bid": str(batch.id)},
            )
        ).all()
        bp_done = {r[0]: r[1] for r in existing}

        gen = ContentFactoryGenerationService(session)
        totals = Counter()
        total_cost = 0.0
        total_attempted = 0
        created_ids: list[str] = []
        stop_reason = None

        for slot in planned:
            factory_bp = slot["factory_blueprint_id"]
            if factory_bp in bp_done:
                item_id = bp_done[factory_bp]
                await tag_item(session, item_id, slot["slot_id"])
                created_ids.append(item_id)
                slot_results.append(
                    {
                        "slot_id": slot["slot_id"],
                        "plan_blueprint_id": slot["blueprint_id"],
                        "factory_blueprint_id": factory_bp,
                        "status": "GENERATED",
                        "reused": True,
                        "content_item_id": item_id,
                    }
                )
                print(f"skip existing {slot['slot_id']} -> {item_id}", flush=True)
                continue
            if total_attempted >= GLOBAL_MAX_ATTEMPTS:
                stop_reason = "GLOBAL_ATTEMPT_CAP"
                slot_results.append(
                    {
                        "slot_id": slot["slot_id"],
                        "plan_blueprint_id": slot["blueprint_id"],
                        "factory_blueprint_id": factory_bp,
                        "status": "NOT_GENERATED",
                        "reason": stop_reason,
                    }
                )
                continue
            if total_cost >= GLOBAL_MAX_COST_USD:
                stop_reason = "GLOBAL_BUDGET_CAP"
                slot_results.append(
                    {
                        "slot_id": slot["slot_id"],
                        "plan_blueprint_id": slot["blueprint_id"],
                        "factory_blueprint_id": factory_bp,
                        "status": "NOT_GENERATED",
                        "reason": stop_reason,
                    }
                )
                continue

            print(f"Generating {slot['slot_id']} ...", flush=True)
            remaining_attempts = GLOBAL_MAX_ATTEMPTS - total_attempted
            if remaining_attempts < 2:
                stop_reason = "GLOBAL_ATTEMPT_CAP"
                slot_results.append(
                    {
                        "slot_id": slot["slot_id"],
                        "plan_blueprint_id": slot["blueprint_id"],
                        "factory_blueprint_id": factory_bp,
                        "status": "NOT_GENERATED",
                        "reason": stop_reason,
                    }
                )
                continue
            result = await gen.generate_for_batch(
                batch.id,
                blueprint_id=uuid.UUID(factory_bp),
                target_count=1,
                actor_id=actor_id,
                job_key=f"{SEED_TAG}-job-{slot['slot_id']}-{uuid.uuid4().hex[:6]}",
                sync_cap=False,
            )
            attempted = int(result.get("attempted") or 0)
            cost = float(result.get("cost_usd") or 0)
            total_attempted += attempted
            total_cost += cost
            totals["rejected_validation"] += int(result.get("rejected_validation") or 0)
            totals["duplicate"] += int(result.get("duplicate") or 0)
            totals["diversity_rejected"] += int(result.get("diversity_rejected") or 0)
            totals["failed_parse"] += int(result.get("failed_parse") or 0)
            totals["failed_provider"] += int(result.get("failed_provider") or 0)
            ids = result.get("content_item_ids") or []
            if result.get("stop_reason") == PROVIDER_BLOCKED:
                slot_results.append(
                    {
                        "slot_id": slot["slot_id"],
                        "status": "NOT_GENERATED",
                        "reason": PROVIDER_BLOCKED,
                        "result": {k: result.get(k) for k in ("stop_reason", "attempted", "cost_usd")},
                    }
                )
                stop_reason = PROVIDER_BLOCKED
                print("PROVIDER_BLOCKED — stopping remaining slots", flush=True)
                for rest in planned[planned.index(slot) + 1 :]:
                    if rest["factory_blueprint_id"] not in bp_done:
                        slot_results.append(
                            {
                                "slot_id": rest["slot_id"],
                                "status": "NOT_GENERATED",
                                "reason": PROVIDER_BLOCKED,
                            }
                        )
                break
            if ids:
                for iid in ids:
                    await tag_item(session, iid, slot["slot_id"])
                    created_ids.append(iid)
                await session.commit()
                slot_results.append(
                    {
                        "slot_id": slot["slot_id"],
                        "subject": slot["subject"],
                        "plan_blueprint_id": slot["blueprint_id"],
                        "factory_blueprint_id": factory_bp,
                        "status": "GENERATED",
                        "content_item_id": ids[0],
                        "attempted": attempted,
                        "cost_usd": cost,
                        "provider_stop_reason": result.get("stop_reason"),
                    }
                )
                print(f"  -> created {ids[0]} attempts={attempted} cost={cost:.4f}", flush=True)
            else:
                slot_results.append(
                    {
                        "slot_id": slot["slot_id"],
                        "subject": slot["subject"],
                        "plan_blueprint_id": slot["blueprint_id"],
                        "factory_blueprint_id": factory_bp,
                        "status": "NOT_GENERATED",
                        "reason": result.get("stop_reason") or "NO_CREATED_ITEM",
                        "attempted": attempted,
                        "cost_usd": cost,
                        "rejected_validation": result.get("rejected_validation"),
                        "duplicate": result.get("duplicate"),
                        "failed_parse": result.get("failed_parse"),
                        "failed_provider": result.get("failed_provider"),
                        "diversity_rejected": result.get("diversity_rejected"),
                    }
                )
                print(f"  -> FAIL {result.get('stop_reason')} attempts={attempted}", flush=True)

        if stop_reason != PROVIDER_BLOCKED:
            retry_slots = [
                s
                for s in planned
                if not any(
                    r.get("slot_id") == s["slot_id"] and r.get("status") == "GENERATED" for r in slot_results
                )
            ]
            for slot in retry_slots:
                if any(r.get("slot_id") == slot["slot_id"] and r.get("status") == "GENERATED" for r in slot_results):
                    continue
                factory_bp = slot["factory_blueprint_id"]
                remaining = GLOBAL_MAX_ATTEMPTS - total_attempted
                if remaining < 2 or total_cost >= GLOBAL_MAX_COST_USD:
                    break
                print(f"Retry {slot['slot_id']} remaining_attempts={remaining} ...", flush=True)
                result = await gen.generate_for_batch(
                    batch.id,
                    blueprint_id=uuid.UUID(factory_bp),
                    target_count=1,
                    actor_id=actor_id,
                    job_key=f"{SEED_TAG}-retry-{slot['slot_id']}-{uuid.uuid4().hex[:6]}",
                    sync_cap=False,
                )
                attempted = int(result.get("attempted") or 0)
                cost = float(result.get("cost_usd") or 0)
                total_attempted += attempted
                total_cost += cost
                totals["rejected_validation"] += int(result.get("rejected_validation") or 0)
                totals["duplicate"] += int(result.get("duplicate") or 0)
                totals["diversity_rejected"] += int(result.get("diversity_rejected") or 0)
                totals["failed_parse"] += int(result.get("failed_parse") or 0)
                totals["failed_provider"] += int(result.get("failed_provider") or 0)
                ids = result.get("content_item_ids") or []
                if result.get("stop_reason") == PROVIDER_BLOCKED:
                    stop_reason = PROVIDER_BLOCKED
                    break
                if ids:
                    for iid in ids:
                        await tag_item(session, iid, slot["slot_id"])
                        created_ids.append(iid)
                    await session.commit()
                    slot_results = [r for r in slot_results if r.get("slot_id") != slot["slot_id"]]
                    slot_results.append(
                        {
                            "slot_id": slot["slot_id"],
                            "subject": slot["subject"],
                            "plan_blueprint_id": slot["blueprint_id"],
                            "factory_blueprint_id": factory_bp,
                            "status": "GENERATED",
                            "content_item_id": ids[0],
                            "attempted": attempted,
                            "cost_usd": cost,
                            "retry": True,
                        }
                    )
                    print(f"  -> retry created {ids[0]}", flush=True)

        # Lineage query for created items
        unique_ids = list(dict.fromkeys(created_ids))
        lineage = []
        fallback_count = 0
        if unique_ids:
            rows = (
                await session.execute(
                    text(
                        """
                        SELECT ci.id::text, ci.status,
                               s.name AS subject, gc.provider, gc.model_used, gc.routing_policy,
                               gc.is_fallback, gc.blueprint_id::text, qb.blueprint_key,
                               qb.constraints
                        FROM cms.content_items ci
                        JOIN cms.generation_candidates gc
                          ON gc.content_item_id = ci.id AND gc.status='CREATED' AND gc.deleted_at IS NULL
                        LEFT JOIN cms.question_blueprints qb ON qb.id = gc.blueprint_id
                        JOIN academic.concepts c ON c.id = ci.concept_id
                        JOIN academic.topics t ON t.id = c.topic_id
                        JOIN academic.chapters ch ON ch.id = t.chapter_id
                        JOIN academic.subjects s ON s.id = ch.subject_id
                        WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                        """
                    ),
                    {"ids": unique_ids},
                )
            ).mappings().all()
            for r in rows:
                if r["is_fallback"]:
                    fallback_count += 1
                cons = r["constraints"] if isinstance(r["constraints"], dict) else {}
                lineage.append(
                    {
                        "content_item_id": r["id"],
                        "status": r["status"],
                        "subject": r["subject"],
                        "provider": r["provider"],
                        "model": r["model_used"],
                        "routing": r["routing_policy"],
                        "is_fallback": bool(r["is_fallback"]),
                        "factory_blueprint_id": r["blueprint_id"],
                        "blueprint_key": r["blueprint_key"],
                        "slot_id": cons.get("seed_slot_id"),
                        "plan_blueprint_id": cons.get("plan_blueprint_id"),
                    }
                )

        prot_after = await protected_bundle(session)
        p3_after = await fingerprint_items(session, p3_ids)
        v1_after = await fingerprint_items(session, v1_ids)
        cs_after = await checksum(URL)

        gen_map = {r["slot_id"]: r for r in slot_results}
        generated_n = sum(1 for r in slot_results if r.get("status") == "GENERATED")
        by_subj = Counter()
        for r in slot_results:
            if r.get("status") == "GENERATED":
                by_subj[r.get("subject") or "unknown"] += 1
        # fill subject from plan if missing
        slot_by_id = {s["slot_id"]: s for s in planned}
        by_subj = Counter()
        for r in slot_results:
            if r.get("status") == "GENERATED":
                by_subj[slot_by_id[r["slot_id"]]["subject"]] += 1

        statuses = [r.get("status") for r in lineage]
        non_draft = [r for r in lineage if r["status"] != "DRAFT"]
        factory_bps = [s["factory_blueprint_id"] for s in planned]
        used_bps = {r["factory_blueprint_id"] for r in slot_results if r.get("status") == "GENERATED"}

        unchanged = prot_after["unchanged_vs_post_publication"]
        v1_body_unchanged = v1_before == v1_after
        p3_unchanged = p3_before == p3_after
        t6d_ok = prot_before["t6d"]["content_fp"] == prot_after["t6d"]["content_fp"]
        t6f2_ok = prot_before["t6f2"]["content_fp"] == prot_after["t6f2"]["content_fp"]
        legacy_ok = prot_before["legacy"]["content_fp"] == prot_after["legacy"]["content_fp"]

        yield_pct = round(100.0 * generated_n / max(total_attempted, 1), 2)
        failures = []
        if fallback_count:
            failures.append(f"fallback_count={fallback_count}")
        if non_draft:
            failures.append(f"non_draft={len(non_draft)}")
        if not (unchanged["seed_v1_published_30"] and v1_body_unchanged):
            failures.append("V1_CHANGED")
        if not t6d_ok:
            failures.append("T6D_CHANGED")
        if not t6f2_ok:
            failures.append("T6F2_CHANGED")
        if not legacy_ok:
            failures.append("LEGACY_CHANGED")
        if any((r.get("provider") or "").lower() not in {"gemini", None} for r in lineage if r.get("provider")):
            if any((r.get("provider") or "").lower() != "gemini" for r in lineage):
                failures.append("UNEXPECTED_PROVIDER")
        if total_attempted > GLOBAL_MAX_ATTEMPTS:
            failures.append("ATTEMPT_CAP_EXCEEDED")
        if total_cost > GLOBAL_MAX_COST_USD + 0.01:
            failures.append("COST_CAP_EXCEEDED")

        if failures:
            verdict = "RED"
        elif generated_n == 100 and fallback_count == 0:
            verdict = "GREEN"
        elif generated_n >= 80:
            verdict = "AMBER"
        else:
            verdict = "RED"

        doc = {
            "audit": "Production Seed V2 P3 Generation",
            "date": "2026-09-03",
            "status": "P3_ONLY",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "plan_artifact": str(PLAN_PATH.relative_to(ROOT)).replace("\\", "/"),
            "plan_sha256": sha,
            "batch_key": BATCH_KEY,
            "batch_uuid": str(batch.id),
            "batch_created": batch_created,
            "target": 100,
            "attempts": total_attempted,
            "max_attempts_policy": GLOBAL_MAX_ATTEMPTS,
            "created": generated_n,
            "rejected_validation": int(totals["rejected_validation"]),
            "duplicate_rejected": int(totals["duplicate"]),
            "diversity_rejected": int(totals["diversity_rejected"]),
            "parse_rejected": int(totals["failed_parse"]),
            "failed_provider": int(totals["failed_provider"]),
            "other_rejected": int(totals["diversity_rejected"]),
            "failed": sum(1 for r in slot_results if r.get("status") == "NOT_GENERATED"),
            "cost_usd": round(total_cost, 6),
            "cost_cap_usd": GLOBAL_MAX_COST_USD,
            "yield_created_per_attempt_pct": yield_pct,
            "provider": "gemini",
            "provider_mode": "fixed",
            "routing": preflight.get("routing"),
            "fallback_chain": "",
            "fallback_count": fallback_count,
            "model_observed": sorted({r.get("model") for r in lineage if r.get("model")}),
            "subject_counts_generated": {
                "Physics": by_subj.get("Physics", 0),
                "Chemistry": by_subj.get("Chemistry", 0),
                "Botany": by_subj.get("Botany", 0),
                "Zoology": by_subj.get("Zoology", 0),
            },
            "slot_coverage": {
                "generated": generated_n,
                "not_generated": 100 - generated_n,
                "slots": slot_results,
            },
            "blueprint_coverage": {
                "planned_factory_blueprints": len(set(factory_bps)),
                "generated_unique_factory_blueprints": len(used_bps),
                "one_blueprint_per_generated_item": len(used_bps) == generated_n,
            },
            "lineage_sample": lineage[:15],
            "lineage_count": len(lineage),
            "all_created_status_counts": dict(Counter(statuses)),
            "approvals": 0,
            "publications": 0,
            "ecaep_transitions": 0,
            "stop_reason": stop_reason,
            "protected_before": {
                "t6d_fp": prot_before["t6d"]["content_fp"],
                "t6f2_fp": prot_before["t6f2"]["content_fp"],
                "legacy_fp": prot_before["legacy"]["content_fp"],
                "v1_bodies_fp": v1_before.get("bodies_fp"),
            },
            "protected_after": {
                "t6d_fp": prot_after["t6d"]["content_fp"],
                "t6f2_fp": prot_after["t6f2"]["content_fp"],
                "legacy_fp": prot_after["legacy"]["content_fp"],
                "v1_bodies_fp": v1_after.get("bodies_fp"),
                "unchanged_vs_post_publication": unchanged,
            },
            "protected_population_integrity": {
                "V1": "UNCHANGED" if v1_body_unchanged and unchanged["seed_v1_published_30"] else "CHANGED",
                "T6-D": "UNCHANGED" if t6d_ok else "CHANGED",
                "T6-F2": "UNCHANGED" if t6f2_ok else "CHANGED",
                "legacy": "UNCHANGED" if legacy_ok else "CHANGED",
                "p3_95": "UNCHANGED" if p3_unchanged else "CHANGED",
            },
            "cms_checksum_before": cs_before,
            "cms_checksum_after": cs_after,
            "limitations": [
                "CHAPTER-mapped slots required creating academic topic/concept rows (codes sv2t-/sv2c-) under existing chapter_id so the factory could pin concept_id. Planned slot identity was not changed.",
                "Numerical independent calculation verification is not automated in P3; numerical slots remain flagged on the plan for later QA.",
                "P4/P5/diversity forensic/NCERT certification/approval/publication were not run.",
            ],
            "failures": failures,
            "verdict": verdict,
            "phase_stop": "P3_COMPLETE — do not proceed to P4 without separate authorization",
        }
        OUT_PATH.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"verdict": verdict, "created": generated_n, "attempts": total_attempted, "cost": total_cost, "failures": failures}, indent=2), flush=True)
    await engine.dispose()
    return 0 if verdict != "RED" or generated_n > 0 else 1


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
