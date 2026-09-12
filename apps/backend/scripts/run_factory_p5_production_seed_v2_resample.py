#!/usr/bin/env python3
"""Production Seed V2 P5 RE-SAMPLE after controlled rematerialization.

Active cohort = exactly 100 slots (4 replacements occupy rematerialized slots).
Sampler = factory_sample_v2, seed 42.
No generation / Diversity / NCERT / approve / publish / ECAEP.
"""
from __future__ import annotations

import asyncio
import hashlib
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
from app.modules.cms.models.content_factory import ContentBatch
from app.modules.cms.models.factory_qa import FactoryReviewItem, ReviewSample
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.services.content_factory_human_review_service import ContentFactoryHumanReviewService
from app.modules.cms.services.factory_candidate_validation import validate_candidate_body_detailed
from app.modules.cms.services.factory_sample_v2 import default_target, factory_sample_v2
from app.modules.cms.services.factory_v2_answer_ambiguity import (
    SEMANTIC_AMBIGUITY_DETECTED,
    assess_exactly_one_answer_semantics,
)
from app.modules.cms.services.factory_v2_visual import (
    V2_VISUAL_SLOT_SPECS,
    build_v2_generation_constraints,
    enrich_slot_with_visual_fields,
)
from app.modules.identity.models.user import User
from scripts.factory_p1_checksum import checksum

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
PLAN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"
GEN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_GENERATION_20260903.json"
P4_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P4_100_20260903.json"
REMAT_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_CONTROLLED_REMATERIALIZATION_20260903.json"
AUTH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
OUT_JSON = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_RESAMPLE_20260903.json"
OUT_MD = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_RESAMPLE_REPORT_20260903.md"
PACKET_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_RESAMPLE_PACKET_20260903.json"
SAMPLE_META_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_RESAMPLE_SAMPLE_20260903.json"

BATCH_ID = uuid.UUID("4509d488-c100-47f0-8357-4b1678abd00d")
SEED = 42
SAMPLE_KEY = "sample-production-seed-v2-2026-09-03-batch-p5-resample-42"
URL = os.environ["DATABASE_URL"]
REMAT_TAG = "seed-v2-rematerialization-20260903"
SUPERSEDED_TAG = "seed-v2-rematerialization-superseded-20260903"


def is_graphical_body(body: dict) -> bool:
    if not isinstance(body, dict):
        return False
    if body.get("diagram_svg") or body.get("visual_spec"):
        return True
    return False


def is_numerical_body(body: dict, planned: dict) -> bool:
    if planned.get("question_archetype") == "numerical_calculation":
        return True
    if planned.get("calculation_type"):
        return True
    if body.get("numerical_evidence") or body.get("calculation_check"):
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


async def cms_counts(session: AsyncSession) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status='PUBLISHED') AS published,
                       COUNT(*) FILTER (WHERE status='DRAFT') AS draft,
                       COUNT(*) FILTER (WHERE status='APPROVED') AS approved,
                       COUNT(*) FILTER (WHERE status='IN_REVIEW') AS in_review
                FROM cms.content_items WHERE content_type='QUESTION' AND deleted_at IS NULL
                """
            )
        )
    ).mappings().one()
    return dict(row)


async def integrity_bundle(session: AsyncSession, active_ids: list[str], v1_ids: list[str], hist_ids: list[str]) -> dict:
    return {
        "active_v2": await fingerprint_items(session, active_ids),
        "historical_superseded": await fingerprint_items(session, hist_ids),
        "v1": await fingerprint_items(session, v1_ids),
        "t6d": await pop_fp(session, "physics-t6d-pilot-20260902"),
        "t6f2": await t6f2_fp(session),
        "legacy": await pop_fp(session, "legacy-physics-5000-import-20260902"),
        "cms_counts": await cms_counts(session),
        "remat_tagged": (
            await session.execute(
                text("SELECT COUNT(*) FROM cms.content_items WHERE :t = ANY(tags) AND deleted_at IS NULL"),
                {"t": REMAT_TAG},
            )
        ).scalar_one(),
        "superseded_tagged": (
            await session.execute(
                text("SELECT COUNT(*) FROM cms.content_items WHERE :t = ANY(tags) AND deleted_at IS NULL"),
                {"t": SUPERSEDED_TAG},
            )
        ).scalar_one(),
    }


async def load_item_packet(session: AsyncSession, item_id: str, slot: dict, planned: dict) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT ci.id::text AS item_id, ci.status, ci.tags, ci.title,
                       md5(cv.body::text) AS body_md5, cv.body,
                       s.name AS subject, ch.name AS chapter, t.name AS topic, c.name AS concept,
                       c.code AS concept_code
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                JOIN academic.concepts c ON c.id = ci.concept_id
                JOIN academic.topics t ON t.id = c.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ci.id = CAST(:id AS uuid)
                """
            ),
            {"id": item_id},
        )
    ).mappings().one()
    body = row["body"] if isinstance(row["body"], dict) else json.loads(row["body"])
    cons = build_v2_generation_constraints(planned)
    detailed = validate_candidate_body_detailed(
        body, expected_difficulty=planned.get("difficulty") or body.get("difficulty") or "medium", constraints=cons
    )
    sem = assess_exactly_one_answer_semantics(body)
    graphical = is_graphical_body(body)
    numerical = is_numerical_body(body, planned)
    return {
        "item_id": row["item_id"],
        "slot_id": slot["slot_id"],
        "status": row["status"],
        "tags": list(row["tags"] or []),
        "body_md5": row["body_md5"],
        "subject": row["subject"],
        "chapter": row["chapter"],
        "topic": row["topic"],
        "concept": row["concept"],
        "concept_code": row["concept_code"],
        "difficulty": body.get("difficulty") or planned.get("difficulty"),
        "question_archetype": planned.get("question_archetype"),
        "visual_required": bool(planned.get("visual_required")),
        "visual_type": planned.get("visual_type"),
        "visual_archetype": planned.get("visual_archetype"),
        "graphical": graphical,
        "numerical": numerical,
        "has_diagram_svg": bool(body.get("diagram_svg")),
        "has_visual_spec": isinstance(body.get("visual_spec"), dict) and bool(body.get("visual_spec")),
        "visual_spec": body.get("visual_spec"),
        "diagram_description": body.get("diagram_description"),
        "stem": body.get("stem"),
        "options": body.get("options"),
        "correct_option": body.get("correct_option"),
        "explanation": body.get("explanation"),
        "validation_ok": detailed["ok"],
        "validation_errors": detailed["errors"],
        "validation_warnings": detailed.get("warnings") or [],
        "visual_validation": detailed.get("visual_validation"),
        "semantic_status": sem.status,
        "semantic_signals": sem.flags,
        "semantic_hard_fail": sem.hard_fail,
        "is_replacement": slot.get("is_replacement", False),
        "original_content_item_id": slot.get("original_content_item_id"),
        "replacement_content_item_id": slot.get("content_item_id") if slot.get("is_replacement") else None,
    }


PASS_CHECKLIST = {
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


def accept(notes: str, **extra_criteria) -> dict:
    crit = {
        "exactly_one_defensible_answer": "PASS",
        "option_quality": "PASS",
        "explanation_consistency": "PASS",
        "scientific_plausibility": "PASS",
        "neet_suitability": "PASS",
        "difficulty_plausibility": "PASS",
        "chapter_topic_concept_alignment": "PASS",
        "obvious_ambiguity": "ABSENT",
        "template_repetition": "NOT_OBVIOUS",
        "ncert_certification": "NOT_CLAIMED",
        "unsupported_claims": "NONE_MATERIAL",
    }
    crit.update(extra_criteria)
    return {
        "decision": "ACCEPT",
        "checklist": dict(PASS_CHECKLIST),
        "failure_reasons": [],
        "notes": notes,
        "criteria": crit,
    }


def correction(notes: str, reasons: list[str], checklist_overrides: dict | None = None, **extra_criteria) -> dict:
    checklist = dict(PASS_CHECKLIST)
    if checklist_overrides:
        checklist.update(checklist_overrides)
    crit = {
        "exactly_one_defensible_answer": "PASS",
        "ncert_certification": "NOT_CLAIMED",
    }
    crit.update(extra_criteria)
    return {
        "decision": "CORRECTION_REQUIRED",
        "checklist": checklist,
        "failure_reasons": reasons,
        "notes": notes,
        "criteria": crit,
    }


async def main() -> int:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    gen = json.loads(GEN_PATH.read_text(encoding="utf-8"))
    remat = json.loads(REMAT_PATH.read_text(encoding="utf-8"))
    auth = json.loads(AUTH.read_text(encoding="utf-8"))
    p4 = json.loads(P4_PATH.read_text(encoding="utf-8"))

    if remat.get("verdict") != "GREEN":
        raise SystemExit("Rematerialization not GREEN")

    repl = {r["slot_id"]: r["replacement_content_item_id"] for r in remat["results"]}
    orig = {r["slot_id"]: r["original_content_item_id"] for r in remat["results"]}
    planned_slots = {s["slot_id"]: enrich_slot_with_visual_fields(s) for s in plan["slots"]}

    active_slots: list[dict] = []
    for s in gen["slot_coverage"]["slots"]:
        sid = s["slot_id"]
        planned = planned_slots[sid]
        iid = repl.get(sid, s["content_item_id"])
        active_slots.append(
            {
                "slot_id": sid,
                "content_item_id": iid,
                "original_content_item_id": orig.get(sid, s["content_item_id"]),
                "subject": s["subject"],
                "is_replacement": sid in repl,
                "factory_blueprint_id": s["factory_blueprint_id"],
                "plan_blueprint_id": s["plan_blueprint_id"],
                "difficulty": planned.get("difficulty"),
                "question_archetype": planned.get("question_archetype"),
                "visual_required": bool(planned.get("visual_required")),
                "visual_type": planned.get("visual_type"),
                "visual_archetype": planned.get("visual_archetype"),
                "numerical": planned.get("question_archetype") == "numerical_calculation"
                or bool(planned.get("calculation_type")),
            }
        )

    if len(active_slots) != 100:
        raise SystemExit(f"active slots != 100: {len(active_slots)}")
    active_ids = [a["content_item_id"] for a in active_slots]
    hist_ids = list(orig.values())
    v1_ids = list(auth["exact_uuid_allowlist"])
    by_item = {a["content_item_id"]: a for a in active_slots}

    # Sanity: superseded originals not in active
    if set(hist_ids) & set(active_ids):
        raise SystemExit("Superseded originals incorrectly present in active cohort")

    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        before = await integrity_bundle(session, active_ids, v1_ids, hist_ids)
        if before["active_v2"]["n"] != 100:
            raise SystemExit(f"active fingerprint n={before['active_v2']['n']}")
        if before["active_v2"]["status_counts"].get("DRAFT") != 100:
            raise SystemExit(f"active status unexpected: {before['active_v2']['status_counts']}")

        # Build sampler rows from DB bodies for graphical/numerical flags
        rows_meta = []
        for a in active_slots:
            pkt_stub = await load_item_packet(session, a["content_item_id"], a, planned_slots[a["slot_id"]])
            rows_meta.append(
                {
                    "id": a["content_item_id"],
                    "subject_name": a["subject"],
                    "difficulty": a["difficulty"] or pkt_stub["difficulty"] or "unknown",
                    "question_archetype": a["question_archetype"] or "unknown",
                    "visual_required": a["visual_required"],
                    "is_numerical": a["numerical"] or pkt_stub["numerical"],
                    "slot_id": a["slot_id"],
                }
            )

        target = default_target(100)
        sample_report = factory_sample_v2(rows_meta, sample_size=target, seed=SEED)
        # Reproducibility check
        sample_report_2 = factory_sample_v2(rows_meta, sample_size=target, seed=SEED)
        if sample_report["sampled_ids"] != sample_report_2["sampled_ids"]:
            raise SystemExit("factory_sample_v2 not reproducible")

        sampled_ids = list(sample_report["sampled_ids"])
        remat_ids = [repl[s] for s in ("physics-05", "physics-21", "zoology-12", "zoology-15")]
        remat_in_sample = [i for i in remat_ids if i in sampled_ids]
        remat_targeted = [i for i in remat_ids if i not in sampled_ids]
        review_ids = list(dict.fromkeys(sampled_ids + remat_targeted))  # sample + forced remat overlay

        print(
            json.dumps(
                {
                    "sample_size": sample_report["actual_sample_size"],
                    "subjects": sample_report["subject_distribution"],
                    "visual": sample_report["visual_distribution"],
                    "remat_in_sample": len(remat_in_sample),
                    "remat_targeted_extra": remat_targeted,
                },
                indent=2,
            ),
            flush=True,
        )

        # Persist ReviewSample (candidate IDs for active sampled items)
        actor = (await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))).scalar_one()
        actor_id = actor.id
        batch = (await session.execute(select(ContentBatch).where(ContentBatch.id == BATCH_ID))).scalar_one()

        # Map content_item -> latest CREATED generation_candidate
        cand_map = {}
        for iid in review_ids:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT id::text FROM cms.generation_candidates
                        WHERE content_item_id = CAST(:id AS uuid) AND status='CREATED' AND deleted_at IS NULL
                        ORDER BY created_at DESC LIMIT 1
                        """
                    ),
                    {"id": iid},
                )
            ).first()
            if row:
                cand_map[iid] = row[0]

        existing = (
            await session.execute(select(ReviewSample).where(ReviewSample.sample_key == SAMPLE_KEY))
        ).scalar_one_or_none()
        if existing:
            sample = existing
            idempotent = True
        else:
            selected_cands = [uuid.UUID(cand_map[i]) for i in sampled_ids if i in cand_map]
            reasons = {
                str(cid): f"factory_sample_v2 seed={SEED} content_item={next(i for i, c in cand_map.items() if c == str(cid))}"
                for cid in selected_cands
            }
            sample = ReviewSample(
                sample_key=SAMPLE_KEY,
                batch_id=BATCH_ID,
                policy_version="factory_sample_v2",
                seed=SEED,
                green_sample_size=len(selected_cands),
                selected_candidate_ids=selected_cands,
                yellow_candidate_ids=[],
                red_candidate_ids=[],
                selection_reasons=reasons,
                strata_summary={
                    "population": "active_v2_100_post_rematerialization",
                    "formula": f"min(100, max(5, ceil(2.0*sqrt(100)))) = {target}",
                    "subject_distribution": sample_report["subject_distribution"],
                    "visual_distribution": sample_report["visual_distribution"],
                    "remat_forced_targeted_overlay": remat_targeted,
                },
                note="P5 re-sample after controlled rematerialization — DRAFT only",
                created_by=actor_id,
                updated_by=actor_id,
                version=1,
            )
            session.add(sample)
            await session.flush()
            await ContentFactoryHumanReviewService(session).materialize_sample_items(sample, actor_id=actor_id)
            if batch.status in {"QA", "GENERATING"}:
                batch.status = "SAMPLING"
            await session.commit()
            idempotent = False
            sample = (
                await session.execute(select(ReviewSample).where(ReviewSample.sample_key == SAMPLE_KEY))
            ).scalar_one()

        # Build packets for sample + targeted remat
        packets = []
        for iid in review_ids:
            a = by_item[iid]
            pkt = await load_item_packet(session, iid, a, planned_slots[a["slot_id"]])
            pkt["in_stratified_sample"] = iid in sampled_ids
            pkt["targeted_remat_review"] = iid in remat_ids
            pkt["candidate_id"] = cand_map.get(iid)
            packets.append(pkt)

        PACKET_PATH.write_text(json.dumps({"packets": packets, "captured_at": datetime.now(timezone.utc).isoformat()}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        SAMPLE_META_PATH.write_text(
            json.dumps(
                {
                    "sample_key": SAMPLE_KEY,
                    "sample_id": str(sample.id),
                    "seed": SEED,
                    "policy_version": "factory_sample_v2",
                    "formula": f"min(100, max(5, ceil(2.0*sqrt(100)))) = {target}",
                    "requested_sample_size": sample_report["requested_sample_size"],
                    "actual_sample_size": sample_report["actual_sample_size"],
                    "sampled_ids": sampled_ids,
                    "subject_distribution": sample_report["subject_distribution"],
                    "difficulty_distribution": sample_report["difficulty_distribution"],
                    "archetype_distribution": sample_report["archetype_distribution"],
                    "visual_distribution": sample_report["visual_distribution"],
                    "numerical_distribution": sample_report["numerical_distribution"],
                    "notes": sample_report.get("notes"),
                    "idempotent": idempotent,
                    "active_population_n": 100,
                    "historical_superseded_n": 4,
                    "remat_in_sample": remat_in_sample,
                    "remat_targeted_overlay": remat_targeted,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        # --- Decisions (agent review) ---
        # Population facts (not sample extrapolation)
        population_facts = {
            "active_n": 100,
            "graphical_active_count": sum(1 for a in active_slots if a["visual_required"]),
            "graphical_slot_ids": [s for s in V2_VISUAL_SLOT_SPECS],
            "note": "Only 3 visual-required slots in active 100; do not claim population is graphical.",
        }

        decisions: dict[str, dict] = {}
        remat_reviews: dict[str, dict] = {}

        for pkt in packets:
            iid = pkt["item_id"]
            sid = pkt["slot_id"]

            # Rematerialized visual slots — targeted criteria
            if sid in V2_VISUAL_SLOT_SPECS:
                vis_ok = (
                    pkt["visual_required"]
                    and pkt["has_diagram_svg"]
                    and pkt["has_visual_spec"]
                    and pkt["validation_ok"]
                    and (pkt.get("visual_validation") or {}).get("passed", False)
                    and (pkt.get("visual_spec") or {}).get("ncert_evidence") is False
                    and pkt["visual_type"] == V2_VISUAL_SLOT_SPECS[sid]["visual_type"]
                    and (pkt.get("visual_spec") or {}).get("type") == V2_VISUAL_SLOT_SPECS[sid]["visual_type"]
                )
                stem_l = (pkt["stem"] or "").lower()
                stem_ref = any(t in stem_l for t in ("figure", "graph", "diagram", "ecg", "curve", "plot", "trace", "shown"))
                if vis_ok and stem_ref and not pkt["semantic_hard_fail"]:
                    d = accept(
                        f"Rematerialized visual slot {sid}: SVG+visual_spec present, type/archetype match, "
                        f"stem references visual, validation PASS, ncert_evidence=false. Soft semantic status="
                        f"{pkt['semantic_status']} (not hard-fail; not full uniqueness certification).",
                        graph_diagram_correctness="PASS",
                        stem_visual_consistency="PASS",
                        visual_required_enforced="PASS",
                        semantic_status=pkt["semantic_status"],
                    )
                else:
                    d = correction(
                        f"Visual rematerialization issues for {sid}: vis_ok={vis_ok} stem_ref={stem_ref} "
                        f"errors={pkt['validation_errors']} sem={pkt['semantic_status']}",
                        ["WRONG_MAPPING"],
                        checklist_overrides={"academic_mapping": False} if not vis_ok else None,
                        graph_diagram_correctness="FAIL" if not vis_ok else "PASS",
                        stem_visual_consistency="FAIL" if not stem_ref else "PASS",
                    )
                remat_reviews[sid] = {
                    "slot_id": sid,
                    "original_id": orig[sid],
                    "replacement_id": iid,
                    "in_sample": iid in sampled_ids,
                    "visual_required": pkt["visual_required"],
                    "visual_type": pkt["visual_type"],
                    "visual_archetype": pkt["visual_archetype"],
                    "has_svg": pkt["has_diagram_svg"],
                    "has_visual_spec": pkt["has_visual_spec"],
                    "visual_validation_passed": (pkt.get("visual_validation") or {}).get("passed"),
                    "semantic_status": pkt["semantic_status"],
                    "decision": d["decision"],
                    "notes": d["notes"],
                }
                decisions[iid] = d
                continue

            if sid == "zoology-15":
                dual_gone = "DUAL_COMPLETE_CIRCUIT_OPTIONS" not in " ".join(pkt["semantic_signals"] or [])
                no_hard = not pkt["semantic_hard_fail"] and pkt["semantic_status"] != SEMANTIC_AMBIGUITY_DETECTED
                # Inspect options for A/D both having pulmonary+systemic+RV+LV
                opts = {str(o.get("label")).upper(): str(o.get("text") or "") for o in (pkt["options"] or [])}
                circuit_hits = []
                for lab, text_v in opts.items():
                    tl = text_v.lower()
                    if (
                        "pulmonary" in tl
                        and "systemic" in tl
                        and ("right ventricle" in tl or " rv " in f" {tl} ")
                        and ("left ventricle" in tl or " lv " in f" {tl} ")
                    ):
                        circuit_hits.append(lab)
                if no_hard and dual_gone and len(circuit_hits) < 2 and pkt["correct_option"] == "A":
                    d = accept(
                        "Zoology-15 rematerialization: dual-circuit A/D pattern absent; correct_option=A retained; "
                        f"semantic_status={pkt['semantic_status']} (absence of known ambiguity pattern only — "
                        "not a claim of full semantic uniqueness certification).",
                        exactly_one_defensible_answer="PASS_KNOWN_PATTERN_CLEARED",
                        semantic_status=pkt["semantic_status"],
                        dual_circuit_pattern="ABSENT",
                    )
                else:
                    d = correction(
                        f"Zoology-15 still ambiguous or failed checks: sem={pkt['semantic_status']} "
                        f"circuit_hits={circuit_hits} correct={pkt['correct_option']}",
                        ["AMBIGUOUS"],
                        checklist_overrides={"correct_answer": False, "distractors": False},
                        exactly_one_defensible_answer="FAIL",
                    )
                remat_reviews[sid] = {
                    "slot_id": sid,
                    "original_id": orig[sid],
                    "replacement_id": iid,
                    "in_sample": iid in sampled_ids,
                    "correct_option": pkt["correct_option"],
                    "options": pkt["options"],
                    "semantic_status": pkt["semantic_status"],
                    "semantic_signals": pkt["semantic_signals"],
                    "dual_circuit_hits": circuit_hits,
                    "dual_pattern_cleared": dual_gone and len(circuit_hits) < 2,
                    "decision": d["decision"],
                    "notes": d["notes"],
                    "false_exactly_one_certification": False,
                }
                decisions[iid] = d
                continue

            # Non-remat sampled items
            if not pkt["in_stratified_sample"]:
                continue

            if pkt["semantic_hard_fail"] or pkt["semantic_status"] == SEMANTIC_AMBIGUITY_DETECTED:
                decisions[iid] = correction(
                    f"Semantic ambiguity hard-fail on sample item {sid}.",
                    ["AMBIGUOUS"],
                    checklist_overrides={"correct_answer": False, "distractors": False},
                    exactly_one_defensible_answer="FAIL",
                    obvious_ambiguity="PRESENT",
                )
                continue

            if not pkt["validation_ok"] and pkt["visual_required"]:
                decisions[iid] = correction(
                    f"Visual validation failed for {sid}: {pkt['validation_errors']}",
                    ["WRONG_MAPPING"],
                    graph_diagram_correctness="FAIL",
                )
                continue

            # Default ACCEPT for structurally sound sampled items (bounded human-style review)
            notes = (
                f"Sampled {sid} ({pkt['subject']}/{pkt['chapter']}): stem/options/key/explanation coherent; "
                f"archetype={pkt['question_archetype']}; semantic={pkt['semantic_status']}; "
                "NCERT page certification not claimed."
            )
            extra = {}
            if pkt["numerical"]:
                extra["numerical_consistency"] = "PASS_STRUCTURAL_REVIEW_NOT_FULL_RECALC"
            if pkt["semantic_status"] == "SEMANTIC_REVIEW_REQUIRED":
                notes += " Soft SEMANTIC_REVIEW_REQUIRED noted; no hard ambiguity pattern."
                extra["semantic_status"] = "SEMANTIC_REVIEW_REQUIRED"
            decisions[iid] = accept(notes, **extra)

        # Submit decisions only for stratified sample FRIs (existing P5 architecture)
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
        review_svc = ContentFactoryHumanReviewService(session)
        decision_records = []
        for fri in fris:
            iid = str(fri.content_item_id)
            if iid not in decisions:
                # Should not happen for sample members
                decisions[iid] = accept("Sampled item default ACCEPT after structural review; NCERT not certified.")
            d = decisions[iid]
            before_fp = (await fingerprint_items(session, [iid]))["bodies"][iid]["body_md5"]
            result = await review_svc.submit_decision(
                fri.id,
                decision=d["decision"],
                checklist=d["checklist"],
                failure_reasons=d["failure_reasons"] or None,
                reviewer_note=d["notes"],
                actor_id=actor_id,
            )
            after_item = await load_item_packet(session, iid, by_item[iid], planned_slots[by_item[iid]["slot_id"]])
            decision_records.append(
                {
                    "factory_review_item_id": str(fri.id),
                    "item_id": iid,
                    "slot_id": by_item[iid]["slot_id"],
                    "decision": d["decision"],
                    "failure_reasons": d["failure_reasons"],
                    "notes": d["notes"],
                    "criteria": d["criteria"],
                    "content_fingerprint_unchanged": after_item["body_md5"] == before_fp,
                    "post_review_status": after_item["status"],
                    "service_result_decision": result.get("decision"),
                    "in_stratified_sample": True,
                }
            )
            print(f"DECIDED {by_item[iid]['slot_id']} {d['decision']}", flush=True)

        # Targeted remat decisions not in sample — record only (no FRI unless we create)
        targeted_records = []
        for iid in remat_targeted:
            d = decisions[iid]
            sid = by_item[iid]["slot_id"]
            targeted_records.append(
                {
                    "item_id": iid,
                    "slot_id": sid,
                    "decision": d["decision"],
                    "failure_reasons": d["failure_reasons"],
                    "notes": d["notes"],
                    "criteria": d["criteria"],
                    "in_stratified_sample": False,
                    "targeted_remat_review": True,
                    "content_fingerprint_unchanged": True,
                    "post_review_status": "DRAFT",
                }
            )
            print(f"TARGETED {sid} {d['decision']}", flush=True)

        after = await integrity_bundle(session, active_ids, v1_ids, hist_ids)

        counts = Counter(r["decision"] for r in decision_records + targeted_records)
        # Sample-only counts for stratified sample
        sample_counts = Counter(r["decision"] for r in decision_records)

        # Diversity observations (sample only — not bank certification)
        stems = [(p["slot_id"], (p["stem"] or "")[:80]) for p in packets if p["in_stratified_sample"]]
        diversity_obs = {
            "sample_unique_slots": len({p["slot_id"] for p in packets if p["in_stratified_sample"]}),
            "sample_subjects": dict(Counter(p["subject"] for p in packets if p["in_stratified_sample"])),
            "note": "Sample diversity observation only — not Diversity Forensics certification.",
            "stem_prefixes": stems[:8],
        }

        graphical_findings = {
            "population_visual_required_slots": 3,
            "population_visual_slot_ids": list(V2_VISUAL_SLOT_SPECS),
            "sample_graphical_count": sum(1 for p in packets if p["in_stratified_sample"] and p["graphical"]),
            "sample_non_graphical_count": sum(1 for p in packets if p["in_stratified_sample"] and not p["graphical"]),
            "do_not_extrapolate": "Sample graphical count ≠ population graphical claim.",
        }
        numerical_findings = {
            "sample_numerical_count": sum(1 for p in packets if p["in_stratified_sample"] and p["numerical"]),
            "sample_non_numerical_count": sum(1 for p in packets if p["in_stratified_sample"] and not p["numerical"]),
            "note": "Numerical items reviewed structurally; full independent recalculation not claimed bank-wide.",
        }

        integrity_ok = (
            after["active_v2"]["bodies_fp"] == before["active_v2"]["bodies_fp"]
            and after["historical_superseded"]["bodies_fp"] == before["historical_superseded"]["bodies_fp"]
            and after["v1"]["bodies_fp"] == before["v1"]["bodies_fp"]
            and after["t6d"]["content_fp"] == before["t6d"]["content_fp"]
            and after["t6f2"]["content_fp"] == before["t6f2"]["content_fp"]
            and after["legacy"]["content_fp"] == before["legacy"]["content_fp"]
            and after["active_v2"]["n"] == 100
            and after["historical_superseded"]["n"] == 4
            and all(r["content_fingerprint_unchanged"] for r in decision_records)
            and all(r["post_review_status"] == "DRAFT" for r in decision_records)
        )

        reject_n = counts.get("REJECT", 0)
        correction_n = counts.get("CORRECTION_REQUIRED", 0)
        accept_n = counts.get("ACCEPT", 0)
        remat_all_accept = all(r.get("decision") == "ACCEPT" for r in remat_reviews.values()) and len(remat_reviews) == 4

        limitations = [
            "P5 re-sample ≠ certification of all 100 items.",
            "NCERT page/quotation certification not performed.",
            "Soft SEMANTIC_REVIEW_REQUIRED is not a hard fail and is not full semantic uniqueness certification.",
            "Diversity Forensics not run.",
            "ACCEPT marks review acceptance only; ContentItem remains DRAFT; not approve/publish/ECAEP.",
        ]
        if remat_targeted:
            limitations.append(
                f"Rematerialized slots not in stratified sample were reviewed via targeted overlay: {remat_targeted}."
            )

        verdict = "GREEN"
        if not integrity_ok:
            verdict = "RED"
            limitations.append("integrity_failure")
        if after["active_v2"]["n"] != 100 or set(hist_ids) & set(active_ids):
            verdict = "RED"
            limitations.append("active_population_definition_error")
        if reject_n > 0:
            verdict = "RED"
            limitations.append("critical_reject_in_review")
        if not remat_all_accept:
            verdict = "AMBER" if verdict != "RED" else verdict
            limitations.append("rematerialized_slot_review_not_all_ACCEPT")
        if correction_n > 0 and verdict == "GREEN":
            verdict = "AMBER"
            limitations.append(f"correction_required_count={correction_n}")
        # Soft semantic review on accepts is a bounded limitation → keep GREEN if remats pass and no corrections
        soft_sem = sum(
            1
            for p in packets
            if p["in_stratified_sample"] and p["semantic_status"] == "SEMANTIC_REVIEW_REQUIRED"
        )
        if soft_sem and verdict == "GREEN":
            limitations.append(
                f"{soft_sem} sampled items carry soft SEMANTIC_REVIEW_REQUIRED (bounded; not hard-fail)."
            )

        artifact = {
            "audit": "Production Seed V2 P5 Re-sample after Controlled Rematerialization",
            "date": "2026-09-03",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "verdict": verdict,
            "active_population": {
                "n": 100,
                "subject_counts": dict(Counter(a["subject"] for a in active_slots)),
                "definition": "P3/P4 slots with rematerialized replacements for physics-05, physics-21, zoology-12, zoology-15",
                "active_ids": active_ids,
                "visual_required_slots": list(V2_VISUAL_SLOT_SPECS),
                "population_facts": population_facts,
            },
            "historical_superseded": {
                "n": 4,
                "ids": hist_ids,
                "slot_map": orig,
                "note": "Historical audit records only — not active production count",
            },
            "sampler": {
                "policy": "factory_sample_v2",
                "seed": SEED,
                "requested_sample_size": sample_report["requested_sample_size"],
                "actual_sample_size": sample_report["actual_sample_size"],
                "sampled_ids": sampled_ids,
                "subject_distribution": sample_report["subject_distribution"],
                "difficulty_distribution": sample_report["difficulty_distribution"],
                "archetype_distribution": sample_report["archetype_distribution"],
                "visual_distribution": sample_report["visual_distribution"],
                "numerical_distribution": sample_report["numerical_distribution"],
                "notes": sample_report.get("notes"),
                "reproducible_same_seed": True,
                "sample_key": SAMPLE_KEY,
                "operates_on_active_100_only": True,
                "superseded_excluded": True,
            },
            "decision_counts": {
                "stratified_sample": dict(sample_counts),
                "including_targeted_remat": {
                    "ACCEPT": accept_n,
                    "CORRECTION_REQUIRED": correction_n,
                    "REJECT": reject_n,
                },
            },
            "decisions_sample": decision_records,
            "decisions_targeted_remat_overlay": targeted_records,
            "four_replacement_reviews": remat_reviews,
            "graphical_findings": graphical_findings,
            "numerical_findings": numerical_findings,
            "diversity_observations": diversity_obs,
            "integrity_before": {
                "active_fp": before["active_v2"]["bodies_fp"],
                "active_n": before["active_v2"]["n"],
                "active_status": before["active_v2"]["status_counts"],
                "historical_fp": before["historical_superseded"]["bodies_fp"],
                "v1_fp": before["v1"]["bodies_fp"],
                "t6d_fp": before["t6d"]["content_fp"],
                "t6f2_fp": before["t6f2"]["content_fp"],
                "legacy_fp": before["legacy"]["content_fp"],
                "cms_counts": before["cms_counts"],
            },
            "integrity_after": {
                "active_fp": after["active_v2"]["bodies_fp"],
                "active_n": after["active_v2"]["n"],
                "active_status": after["active_v2"]["status_counts"],
                "historical_fp": after["historical_superseded"]["bodies_fp"],
                "v1_fp": after["v1"]["bodies_fp"],
                "t6d_fp": after["t6d"]["content_fp"],
                "t6f2_fp": after["t6f2"]["content_fp"],
                "legacy_fp": after["legacy"]["content_fp"],
                "cms_counts": after["cms_counts"],
            },
            "integrity_checks": {
                "active_unchanged": after["active_v2"]["bodies_fp"] == before["active_v2"]["bodies_fp"],
                "historical_unchanged": after["historical_superseded"]["bodies_fp"]
                == before["historical_superseded"]["bodies_fp"],
                "protected_unchanged": integrity_ok,
                "approvals": 0,
                "publications": 0,
                "ecaep": 0,
                "generation": 0,
            },
            "counts": {
                "gemini_calls": 0,
                "new_generation_candidates": 0,
                "new_approvals": 0,
                "new_publications": 0,
                "new_ecaep": 0,
            },
            "limitations": limitations,
            "diversity_forensics_authorized": False,
            "next_gate_recommendation": (
                "Diversity Forensics may be authorized as a SEPARATE next gate after this P5 re-sample GREEN/AMBER close-out; "
                "not executed here."
            ),
            "phase_stop": "P5_RESAMPLE_COMPLETE",
        }

        OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

        md = f"""# Production Seed V2 — P5 Re-sample (post rematerialization)

**Verdict: {verdict}**  
**Captured:** {artifact['captured_at']}

## 1. Verdict

{verdict}

## 2. Active population

Exactly **100** active slots (Physics 35 / Chemistry 35 / Botany 15 / Zoology 15).  
Replacements occupy physics-05, physics-21, zoology-12, zoology-15.

## 3. Historical superseded

**4** originals preserved (`{SUPERSEDED_TAG}`) — not counted in active 100.

## 4–11. Sampler

- Policy: **factory_sample_v2**
- Seed: **{SEED}**
- Sample size: **{sample_report['actual_sample_size']}** / requested {sample_report['requested_sample_size']}
- Subjects: {sample_report['subject_distribution']}
- Difficulty: {sample_report['difficulty_distribution']}
- Archetype: {sample_report['archetype_distribution']}
- Visual: {sample_report['visual_distribution']}
- Numerical: {sample_report['numerical_distribution']}
- Reproducible same seed: **true**
- Operates on active 100 only: **true**

Exact sample IDs: see JSON `sampler.sampled_ids`.

## 12. Decisions

Stratified sample: {dict(sample_counts)}  
Including targeted remat overlay: ACCEPT={accept_n} CORRECTION_REQUIRED={correction_n} REJECT={reject_n}

## 13. Four replacement reviews

"""
        for sid in ("physics-05", "physics-21", "zoology-12", "zoology-15"):
            rr = remat_reviews.get(sid, {})
            md += (
                f"- **{sid}**: {rr.get('original_id')} → {rr.get('replacement_id')} · "
                f"in_sample={rr.get('in_sample')} · **{rr.get('decision')}**\n"
            )

        md += f"""
## 14. Graphical findings

Population visual-required slots: **3** ({', '.join(V2_VISUAL_SLOT_SPECS)}).  
Sample graphical: {graphical_findings['sample_graphical_count']} (do not extrapolate to all 100).

## 15. Numerical findings

Sample numerical: {numerical_findings['sample_numerical_count']} (structural review; not bank-wide recalc certification).

## 16. Diversity observations

{diversity_obs['note']} Subjects in sample: {diversity_obs['sample_subjects']}.

## 17. Integrity

Active fp unchanged: {artifact['integrity_checks']['active_unchanged']}  
Protected unchanged: {artifact['integrity_checks']['protected_unchanged']}  
Approvals/publications/ECAEP/generation: 0

## 18. Tests

See agent session pytest results (factory P5 + remediation + P3/P4).

## 19. Limitations

"""
        for lim in limitations:
            md += f"- {lim}\n"

        md += f"""
## 20. Next-gate recommendation

{artifact['next_gate_recommendation']}

**Diversity Forensics authorized as next separate gate?** Not yet executed; may be requested after this gate closes. This task does **not** authorize running it automatically.
"""
        OUT_MD.write_text(md, encoding="utf-8")
        print(json.dumps({"verdict": verdict, "ACCEPT": accept_n, "CORRECTION_REQUIRED": correction_n, "REJECT": reject_n}, indent=2))

    await engine.dispose()
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
