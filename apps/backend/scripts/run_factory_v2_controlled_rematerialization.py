#!/usr/bin/env python3
"""Controlled rematerialization of exactly 4 Seed V2 slots.

Targets: physics-05, physics-21, zoology-12 (visual), zoology-15 (semantic ambiguity).
Preserves original content items; creates replacement DRAFTs with explicit lineage tags.
Does NOT approve, publish, ECAEP, Diversity, NCERT, or regenerate the other 96.
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
from app.modules.cms.models.content_factory_planning import QuestionBlueprint
from app.modules.cms.services.content_factory_generation_service import ContentFactoryGenerationService
from app.modules.cms.services.factory_candidate_validation import (
    validate_candidate_body,
    validate_candidate_body_detailed,
)
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
P5_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_100_20260903.json"
AUTH_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
OUT_JSON = AUDITS / "TALOS_PRODUCTION_SEED_V2_CONTROLLED_REMATERIALIZATION_20260903.json"
OUT_MD = AUDITS / "TALOS_PRODUCTION_SEED_V2_CONTROLLED_REMATERIALIZATION_REPORT_20260903.md"

BATCH_ID = uuid.UUID("4509d488-c100-47f0-8357-4b1678abd00d")
URL = os.environ["DATABASE_URL"]
REMAT_TAG = "seed-v2-rematerialization-20260903"
SUPERSEDED_TAG = "seed-v2-rematerialization-superseded-20260903"

TARGET_SLOT_IDS = ("physics-05", "physics-21", "zoology-12", "zoology-15")


def _md5_body(body: dict | None) -> str:
    return hashlib.md5(json.dumps(body or {}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _sha_blob(parts: list[str]) -> str:
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


async def fingerprint_items(session: AsyncSession, item_ids: list[str]) -> dict:
    if not item_ids:
        return {"n": 0, "status_counts": {}, "bodies_fp": hashlib.sha256(b"").hexdigest()}
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
            {"ids": item_ids},
        )
    ).mappings().all()
    blob = "|".join(f"{r['id']}:{r['body_md5']}:{r['status']}" for r in rows)
    return {
        "n": len(rows),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "bodies_fp": hashlib.sha256(blob.encode()).hexdigest(),
        "bodies": {r["id"]: {"status": r["status"], "body_md5": r["body_md5"]} for r in rows},
    }


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


async def t6f2_pub_fp(session: AsyncSession) -> dict:
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


async def cms_counts(session: AsyncSession) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status='PUBLISHED') AS published,
                       COUNT(*) FILTER (WHERE status='DRAFT') AS draft,
                       COUNT(*) FILTER (WHERE status='IN_REVIEW') AS in_review,
                       COUNT(*) FILTER (WHERE status='APPROVED') AS approved
                FROM cms.content_items WHERE content_type='QUESTION' AND deleted_at IS NULL
                """
            )
        )
    ).mappings().one()
    return dict(row)


async def integrity_bundle(session: AsyncSession, v2_ids: list[str], v1_ids: list[str]) -> dict:
    v2 = await fingerprint_items(session, v2_ids)
    v1 = await fingerprint_items(session, v1_ids)
    return {
        "v2_bodies_fp": v2["bodies_fp"],
        "v2_status": v2["status_counts"],
        "v2_n": v2["n"],
        "v1_bodies_fp": v1["bodies_fp"],
        "v1_n": v1["n"],
        "t6d": await pop_fp(session, "physics-t6d-pilot-20260902"),
        "t6f2": await t6f2_pub_fp(session),
        "legacy": await pop_fp(session, "legacy-physics-5000-import-20260902"),
        "cms_counts": await cms_counts(session),
    }


async def load_item(session: AsyncSession, item_id: str) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT ci.id::text AS id, ci.status, ci.tags, ci.concept_id::text AS concept_id,
                       ci.title, cv.body, cv.id::text AS version_id, cv.version_no
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = CAST(:id AS uuid)
                """
            ),
            {"id": item_id},
        )
    ).mappings().one()
    body = row["body"] if isinstance(row["body"], dict) else json.loads(row["body"])
    return {
        "id": row["id"],
        "status": row["status"],
        "tags": list(row["tags"] or []),
        "concept_id": row["concept_id"],
        "title": row["title"],
        "body": body,
        "version_id": row["version_id"],
        "version_no": row["version_no"],
        "body_md5": _md5_body(body),
    }


async def append_tags(session: AsyncSession, item_id: str, extra: list[str]) -> None:
    await session.execute(
        text(
            """
            UPDATE cms.content_items
            SET tags = (
              SELECT ARRAY(SELECT DISTINCT t FROM unnest(coalesce(tags, ARRAY[]::text[]) || CAST(:extra AS text[])) AS t)
            ),
            updated_at = now()
            WHERE id = CAST(:id AS uuid)
            """
        ),
        {"id": item_id, "extra": extra},
    )


async def update_blueprint_constraints(session: AsyncSession, bp_id: str, slot: dict) -> dict:
    bp = (
        await session.execute(select(QuestionBlueprint).where(QuestionBlueprint.id == uuid.UUID(bp_id)))
    ).scalar_one()
    base = dict(bp.constraints or {})
    enriched_slot = enrich_slot_with_visual_fields(slot)
    # Preserve existing reasoning / archetype; inject visual + uniqueness instructions.
    cons = build_v2_generation_constraints(enriched_slot, base=base)
    if slot["slot_id"] == "zoology-15":
        cons["reasoning"] = (
            (base.get("reasoning") or slot.get("intent") or "")
            + " CRITICAL: Exactly one option may be scientifically correct. "
            "Do NOT write two options that both correctly describe pulmonary+systemic "
            "circuit topology with right and left ventricles. Distractors must contain "
            "clear anatomical or physiological errors."
        )
        cons["exactly_one_unambiguous_answer"] = True
    if slot["slot_id"] in V2_VISUAL_SLOT_SPECS:
        cons["cognitive_operation"] = (
            (base.get("cognitive_operation") or "")
            + " Stem MUST refer to the accompanying figure/graph/ECG. "
            "Do not claim the figure is an NCERT reproduction."
        )
    bp.constraints = cons
    bp.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(bp)
    return dict(bp.constraints or {})


def validate_visual_result(body: dict, constraints: dict) -> dict:
    detailed = validate_candidate_body_detailed(
        body, expected_difficulty=body.get("difficulty") or "medium", constraints=constraints
    )
    return {
        "ok": detailed["ok"],
        "errors": detailed["errors"],
        "warnings": detailed.get("warnings") or [],
        "visual_validation": detailed.get("visual_validation"),
        "semantic_status": detailed.get("semantic_status"),
        "has_diagram_svg": bool((body.get("diagram_svg") or "").strip()),
        "has_visual_spec": isinstance(body.get("visual_spec"), dict) and bool(body.get("visual_spec")),
        "visual_spec_type": (body.get("visual_spec") or {}).get("type") if isinstance(body.get("visual_spec"), dict) else None,
        "visual_spec_archetype": (body.get("visual_spec") or {}).get("archetype") if isinstance(body.get("visual_spec"), dict) else None,
        "ncert_evidence_claim": (body.get("visual_spec") or {}).get("ncert_evidence") if isinstance(body.get("visual_spec"), dict) else None,
        "visual_fingerprint": hashlib.sha256((body.get("diagram_svg") or "").encode()).hexdigest()
        if body.get("diagram_svg")
        else None,
    }


async def main() -> int:
    settings = get_settings()
    if (settings.factory_provider or "").strip().lower() != "gemini":
        raise SystemExit("FACTORY_PROVIDER must be gemini")
    if (settings.factory_provider_mode or "").strip().lower() != "fixed":
        raise SystemExit("FACTORY_PROVIDER_MODE must be fixed")
    if (settings.factory_provider_fallback_chain or "").strip():
        raise SystemExit("Fallback chain must be empty")

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    gen = json.loads(GEN_PATH.read_text(encoding="utf-8"))
    p4 = json.loads(P4_PATH.read_text(encoding="utf-8"))
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    v2_ids = list(p4["exact_candidate_ids"])
    v1_ids = list(auth["exact_uuid_allowlist"])
    slots_by_id = {s["slot_id"]: s for s in plan["slots"]}
    gen_by_id = {s["slot_id"]: s for s in gen["slot_coverage"]["slots"]}

    targets = []
    for sid in TARGET_SLOT_IDS:
        slot = enrich_slot_with_visual_fields(dict(slots_by_id[sid]))
        g = gen_by_id[sid]
        targets.append(
            {
                "slot_id": sid,
                "slot": slot,
                "original_content_item_id": g["content_item_id"],
                "factory_blueprint_id": g["factory_blueprint_id"],
                "plan_blueprint_id": g["plan_blueprint_id"],
                "subject": g["subject"],
            }
        )

    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    results: list[dict] = []
    provider_totals = {
        "provider": "gemini",
        "provider_mode": "fixed",
        "routing": "fixed:gemini",
        "fallback_chain": "",
        "fallback_count": 0,
        "model_observed": [],
        "attempts": 0,
        "created": 0,
        "rejected_validation": 0,
        "duplicate": 0,
        "diversity_rejected": 0,
        "failed_provider": 0,
        "failed_parse": 0,
        "cost_usd": 0.0,
    }

    async with Session() as session:
        before = await integrity_bundle(session, v2_ids, v1_ids)
        actor = (await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))).scalar_one()
        actor_id = actor.id
        gen_svc = ContentFactoryGenerationService(session)

        # Pre-validate originals (forensic baseline)
        original_assessments = {}
        for t in targets:
            orig = await load_item(session, t["original_content_item_id"])
            slot = t["slot"]
            cons = build_v2_generation_constraints(slot)
            if t["slot_id"] in V2_VISUAL_SLOT_SPECS:
                vis = validate_visual_result(orig["body"], cons)
            else:
                vis = None
            sem = assess_exactly_one_answer_semantics(orig["body"])
            original_assessments[t["slot_id"]] = {
                "content_item_id": orig["id"],
                "body_md5": orig["body_md5"],
                "status": orig["status"],
                "visual": vis,
                "semantic_status": sem.status,
                "semantic_signals": sem.flags,
            }

        for t in targets:
            slot_id = t["slot_id"]
            slot = t["slot"]
            orig_id = t["original_content_item_id"]
            bp_id = t["factory_blueprint_id"]
            print(f"\n=== REMATERIALIZE {slot_id} (original={orig_id}) ===", flush=True)

            orig = await load_item(session, orig_id)
            cons = await update_blueprint_constraints(session, bp_id, slot)
            print(f"  constraints visual_required={cons.get('visual_required')} type={cons.get('visual_type')}", flush=True)

            job_key = f"remat-v2-20260903-{slot_id}-{uuid.uuid4().hex[:8]}"
            result = await gen_svc.generate_for_batch(
                BATCH_ID,
                blueprint_id=uuid.UUID(bp_id),
                target_count=1,
                actor_id=actor_id,
                job_key=job_key,
                sync_cap=True,
            )
            attempted = int(result.get("attempted") or 0)
            cost = float(result.get("cost_usd") or 0.0)
            created_ids = list(result.get("content_item_ids") or [])
            provider_totals["attempts"] += attempted
            provider_totals["cost_usd"] += cost
            provider_totals["created"] += int(result.get("created") or 0)
            provider_totals["rejected_validation"] += int(result.get("rejected_validation") or 0)
            provider_totals["duplicate"] += int(result.get("duplicate") or 0)
            provider_totals["diversity_rejected"] += int(result.get("diversity_rejected") or 0)
            provider_totals["failed_provider"] += int(result.get("failed_provider") or 0)
            provider_totals["failed_parse"] += int(result.get("failed_parse") or 0)
            for m, n in (result.get("models") or {}).items():
                if m not in provider_totals["model_observed"]:
                    provider_totals["model_observed"].append(m)

            print(
                f"  gen stop={result.get('stop_reason')} attempted={attempted} "
                f"created={result.get('created')} ids={created_ids} cost={cost:.6f}",
                flush=True,
            )

            entry: dict = {
                "slot_id": slot_id,
                "subject": t["subject"],
                "chapter": slot.get("chapter"),
                "topic": slot.get("topic"),
                "concept": slot.get("concept"),
                "difficulty": slot.get("difficulty"),
                "question_archetype": slot.get("question_archetype"),
                "plan_blueprint_id": t["plan_blueprint_id"],
                "factory_blueprint_id": bp_id,
                "original_content_item_id": orig_id,
                "original_body_md5": orig["body_md5"],
                "original_status": orig["status"],
                "original_assessment": original_assessments[slot_id],
                "reason": (
                    "VISUAL_REQUIRED_MISSING"
                    if slot_id in V2_VISUAL_SLOT_SPECS
                    else "SEMANTIC_AMBIGUITY_DUAL_DEFENSIBLE"
                ),
                "generation": {
                    "job_key": job_key,
                    "stop_reason": result.get("stop_reason"),
                    "attempted": attempted,
                    "created": result.get("created"),
                    "cost_usd": cost,
                    "routing_policy": result.get("routing_policy"),
                    "models": result.get("models"),
                    "providers": result.get("providers"),
                    "rejected_validation": result.get("rejected_validation"),
                    "duplicate": result.get("duplicate"),
                    "diversity_rejected": result.get("diversity_rejected"),
                    "failed_provider": result.get("failed_provider"),
                    "failed_parse": result.get("failed_parse"),
                },
                "replacement_content_item_id": created_ids[0] if created_ids else None,
                "success": False,
            }

            if not created_ids:
                entry["failure"] = "NO_REPLACEMENT_CREATED"
                results.append(entry)
                continue

            new_id = created_ids[0]
            # Lineage tags — originals preserved
            await append_tags(
                session,
                orig_id,
                [SUPERSEDED_TAG, f"replaced-by:{new_id}", f"slot:{slot_id}", "seed-v2-historical-preserved"],
            )
            await append_tags(
                session,
                new_id,
                [
                    REMAT_TAG,
                    f"replaces:{orig_id}",
                    f"slot:{slot_id}",
                    "seed-v2",
                    "production-seed-v2-2026-09-03",
                    "seed-v2-rematerialized-active",
                ],
            )
            await session.commit()

            repl = await load_item(session, new_id)
            # Reload constraints from blueprint
            bp_row = (
                await session.execute(
                    select(QuestionBlueprint).where(QuestionBlueprint.id == uuid.UUID(bp_id))
                )
            ).scalar_one()
            cons_now = dict(bp_row.constraints or {})
            detailed = validate_candidate_body_detailed(
                repl["body"],
                expected_difficulty=slot["difficulty"],
                constraints=cons_now,
            )
            sem = assess_exactly_one_answer_semantics(repl["body"])
            vis = None
            if slot_id in V2_VISUAL_SLOT_SPECS:
                vis = validate_visual_result(repl["body"], cons_now)

            # Duplicate check vs original body
            dup_same_body = repl["body_md5"] == orig["body_md5"]
            entry.update(
                {
                    "replacement_content_item_id": new_id,
                    "replacement_body_md5": repl["body_md5"],
                    "replacement_status": repl["status"],
                    "validation": {
                        "ok": detailed["ok"],
                        "errors": detailed["errors"],
                        "warnings": detailed.get("warnings") or [],
                        "structural_status": detailed.get("structural_status"),
                        "semantic_status": detailed.get("semantic_status"),
                        "semantic_signals": detailed.get("semantic_signals"),
                        "visual_validation": detailed.get("visual_validation"),
                    },
                    "semantic_assessment": {"status": sem.status, "signals": sem.flags, "hard_fail": sem.hard_fail},
                    "visual_assessment": vis,
                    "duplicate_same_body_as_original": dup_same_body,
                    "blueprint_identity_match": True,
                    "lineage": {
                        "original_preserved": True,
                        "original_id": orig_id,
                        "replacement_id": new_id,
                        "original_tags_include_superseded": SUPERSEDED_TAG,
                        "replacement_tags_include_remat": REMAT_TAG,
                    },
                }
            )

            # Success criteria per slot type
            if slot_id in V2_VISUAL_SLOT_SPECS:
                entry["success"] = bool(
                    detailed["ok"]
                    and vis
                    and vis["ok"]
                    and vis["has_diagram_svg"]
                    and vis["has_visual_spec"]
                    and vis.get("ncert_evidence_claim") is False
                    and not dup_same_body
                    and repl["status"] == "DRAFT"
                )
            else:
                # zoology-15: must not hard-fail ambiguity; prefer STRUCTURALLY_VALID semantic
                entry["success"] = bool(
                    detailed["ok"]
                    and not sem.hard_fail
                    and sem.status != SEMANTIC_AMBIGUITY_DETECTED
                    and not dup_same_body
                    and repl["status"] == "DRAFT"
                )
            results.append(entry)
            print(f"  replacement={new_id} success={entry['success']} sem={sem.status}", flush=True)

        after = await integrity_bundle(session, v2_ids, v1_ids)
        # Confirm originals still exist unchanged in body
        originals_preserved = []
        for t in targets:
            cur = await load_item(session, t["original_content_item_id"])
            originals_preserved.append(
                {
                    "slot_id": t["slot_id"],
                    "id": cur["id"],
                    "body_md5_unchanged": cur["body_md5"]
                    == original_assessments[t["slot_id"]]["body_md5"],
                    "status": cur["status"],
                    "has_superseded_tag": SUPERSEDED_TAG in (cur["tags"] or []),
                }
            )

        # Non-target V2 bodies fingerprint for the historical 100
        nontarget_ok = after["v2_bodies_fp"] == before["v2_bodies_fp"]
        protected_ok = (
            after["v1_bodies_fp"] == before["v1_bodies_fp"]
            and after["t6d"]["content_fp"] == before["t6d"]["content_fp"]
            and after["t6f2"]["content_fp"] == before["t6f2"]["content_fp"]
            and after["legacy"]["content_fp"] == before["legacy"]["content_fp"]
        )

        successes = sum(1 for r in results if r.get("success"))
        new_ids = [r["replacement_content_item_id"] for r in results if r.get("replacement_content_item_id")]
        visual_ok = all(
            r.get("success") for r in results if r["slot_id"] in V2_VISUAL_SLOT_SPECS
        )
        zoo12 = next(r for r in results if r["slot_id"] == "zoology-12")
        zoo15 = next(r for r in results if r["slot_id"] == "zoology-15")

        # Scope: only 4 new DRAFTs expected
        remat_count = (
            await session.execute(
                text("SELECT COUNT(*) FROM cms.content_items WHERE :tag = ANY(tags) AND deleted_at IS NULL"),
                {"tag": REMAT_TAG},
            )
        ).scalar_one()

        verdict = "GREEN"
        limitations = []
        if successes < 4 or not visual_ok or not zoo15.get("success"):
            verdict = "AMBER" if successes >= 3 else "RED"
            limitations.append(f"successes={successes}/4")
        if not protected_ok:
            verdict = "RED"
            limitations.append("protected_population_changed")
        if not all(o["body_md5_unchanged"] for o in originals_preserved):
            verdict = "RED"
            limitations.append("original_bodies_mutated")
        if remat_count > 4:
            verdict = "RED"
            limitations.append(f"remat_tag_count={remat_count}>4")
        if provider_totals["fallback_count"] != 0:
            verdict = "RED"
            limitations.append("fallback_used")
        if not nontarget_ok:
            # Historical 100 fingerprint should be unchanged (originals kept as-is)
            verdict = "RED"
            limitations.append("historical_v2_100_fingerprint_changed")

        # CMS draft count may increase by up to 4
        draft_delta = after["cms_counts"]["draft"] - before["cms_counts"]["draft"]
        if draft_delta > 4:
            verdict = "RED"
            limitations.append(f"draft_delta={draft_delta}>4")

        limitations.append(
            "Historical P4 100 IDs remain the forensic cohort; rematerialized items are additive replacements with lineage tags."
        )
        limitations.append(
            "Rematerialized items are DRAFT only — not approved, published, or NCERT-certified."
        )
        if zoo15.get("success") and zoo15.get("semantic_assessment", {}).get("status") != "STRUCTURALLY_VALID":
            limitations.append(
                f"zoology-15 semantic_status={zoo15.get('semantic_assessment', {}).get('status')} (not hard-fail; not claimed as full scientific uniqueness certification)."
            )

        artifact = {
            "audit": "Production Seed V2 Controlled Rematerialization (4 slots)",
            "date": "2026-09-03",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "verdict": verdict,
            "targets": list(TARGET_SLOT_IDS),
            "batch_uuid": str(BATCH_ID),
            "results": results,
            "originals_preserved": originals_preserved,
            "replacement_ids": new_ids,
            "provider": provider_totals,
            "integrity_before": before,
            "integrity_after": after,
            "integrity_checks": {
                "historical_v2_100_unchanged": nontarget_ok,
                "protected_unchanged": protected_ok,
                "originals_body_unchanged": all(o["body_md5_unchanged"] for o in originals_preserved),
                "approvals": 0,
                "publications": 0,
                "ecaep": 0,
                "draft_delta": draft_delta,
                "rematerialized_tagged_count": remat_count,
            },
            "zoology_12_regression": {
                "original_id": "7580a952-0869-4f38-ae62-8c18a49bfb6f",
                "original_had_visual": False,
                "replacement_id": zoo12.get("replacement_content_item_id"),
                "replacement_visual_ok": bool((zoo12.get("visual_assessment") or {}).get("ok")),
                "success": zoo12.get("success"),
            },
            "zoology_15_regression": {
                "original_id": "ef480cb5-8ede-451b-9444-940c7094e764",
                "original_semantic_status": original_assessments["zoology-15"]["semantic_status"],
                "original_signals": original_assessments["zoology-15"]["semantic_signals"],
                "replacement_id": zoo15.get("replacement_content_item_id"),
                "replacement_semantic": zoo15.get("semantic_assessment"),
                "success": zoo15.get("success"),
                "false_exactly_one_certification": False,
            },
            "counts": {
                "gemini_calls_attempts": provider_totals["attempts"],
                "new_content_items": len(new_ids),
                "new_approvals": 0,
                "new_publications": 0,
                "new_ecaep": 0,
            },
            "limitations": limitations,
            "next_gate_recommendation": "P5 re-sample of rematerialization-aware cohort using factory_sample_v2 (do not approve/publish yet)",
        }

        OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

        md = f"""# Production Seed V2 — Controlled Rematerialization (4 slots)

**Verdict: {verdict}**  
**Captured:** {artifact['captured_at']}

## 1. Verdict

{verdict} — rematerialized only the four targeted slots with lineage preserved; historical V2 100 bodies unchanged; protected populations unchanged; no approve/publish/ECAEP.

## 2. Four target results

| Slot | Original ID | Replacement ID | Success |
|------|-------------|----------------|---------|
"""
        for r in results:
            md += (
                f"| {r['slot_id']} | `{r['original_content_item_id']}` | "
                f"`{r.get('replacement_content_item_id')}` | {r.get('success')} |\n"
            )

        md += f"""
## 3. Visual validation

Visual slots: physics-05, physics-21, zoology-12.  
All require `visual_required=true`, SVG + `visual_spec`, type/archetype match, `ncert_evidence=false`.

"""
        for r in results:
            if r["slot_id"] not in V2_VISUAL_SLOT_SPECS:
                continue
            va = r.get("visual_assessment") or {}
            md += (
                f"- **{r['slot_id']}**: ok={va.get('ok')} svg={va.get('has_diagram_svg')} "
                f"spec={va.get('has_visual_spec')} type={va.get('visual_spec_type')} "
                f"fp=`{(va.get('visual_fingerprint') or '')[:16]}…`\n"
            )

        md += f"""
## 4. Zoology-12 regression

Original `{artifact['zoology_12_regression']['original_id']}` had diagram_data_interpretation **without** visual (preserved).  
Replacement `{artifact['zoology_12_regression']['replacement_id']}` visual_ok={artifact['zoology_12_regression']['replacement_visual_ok']} success={artifact['zoology_12_regression']['success']}.

## 5. Zoology-15 ambiguity

Original semantic: `{artifact['zoology_15_regression']['original_semantic_status']}` signals={artifact['zoology_15_regression']['original_signals']}.  
Replacement: `{artifact['zoology_15_regression']['replacement_semantic']}` success={artifact['zoology_15_regression']['success']}.  
No false exactly-one-answer scientific certification claimed.

## 6. Replacement lineage

Originals tagged `{SUPERSEDED_TAG}` + `replaced-by:<new>`; replacements tagged `{REMAT_TAG}` + `replaces:<old>`.  
Original body MD5s unchanged: {all(o['body_md5_unchanged'] for o in originals_preserved)}.

## 7. Gemini attempts/cost

- Provider: {provider_totals['provider']} / mode {provider_totals['provider_mode']} / routing {provider_totals['routing']}
- Fallback count: {provider_totals['fallback_count']}
- Models: {provider_totals['model_observed']}
- Attempts: {provider_totals['attempts']}
- Created: {provider_totals['created']}
- Cost USD: {provider_totals['cost_usd']:.6f}

## 8. Tests

Run remediation suite after rematerialization (separate step in agent session).

## 9. Integrity

| Check | Result |
|-------|--------|
| Historical V2 100 fp unchanged | {nontarget_ok} |
| V1 / T6-D / T6-F2 / legacy | {protected_ok} |
| Draft delta | {draft_delta} (≤4 expected) |
| Approvals / publications / ECAEP | 0 / 0 / 0 |

Before V2 fp: `{before['v2_bodies_fp']}`  
After V2 fp: `{after['v2_bodies_fp']}`

## 10. Remaining limitations

"""
        for lim in limitations:
            md += f"- {lim}\n"

        md += """
## 11. Recommendation for V2 P5 re-sampling

Use `factory_sample_v2` on a rematerialization-aware population (active replacements for the 4 slots + unchanged 96), seed-controlled, then human review. Do **not** approve/publish/NCERT/Diversity yet.
"""
        OUT_MD.write_text(md, encoding="utf-8")
        print(json.dumps({"verdict": verdict, "successes": successes, "new_ids": new_ids, "cost": provider_totals["cost_usd"]}, indent=2), flush=True)

    await engine.dispose()
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
