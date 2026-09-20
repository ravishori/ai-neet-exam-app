#!/usr/bin/env python3
"""Production Seed V2 — Controlled NUMERICAL remediation for exactly 4 FAIL slots.

Targets: physics-10, physics-11, physics-20, physics-34
Preserves originals; creates DRAFT replacements with lineage tags.
Independent deterministic numerical verification required before acceptance.
Does NOT approve/publish/ECAEP/NCERT re-run/regenerate the other 96.
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
from app.modules.cms.services.factory_candidate_validation import validate_candidate_body_detailed
from app.modules.cms.services.factory_seed_diversity import classify_against_prior, jaccard, tokset
from app.modules.cms.services.factory_v2_answer_ambiguity import assess_exactly_one_answer_semantics
from app.modules.cms.services.factory_v2_numerical_verify import (
    ORIGINAL_FAILURE_EXPECTATIONS,
    verify_slot_body,
)
from app.modules.cms.services.factory_v2_visual import enrich_slot_with_visual_fields, build_v2_generation_constraints
from app.modules.identity.models.user import User

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
PLAN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"
GEN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_GENERATION_20260903.json"
P4_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P4_100_20260903.json"
VISUAL_REMAT_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_CONTROLLED_REMATERIALIZATION_20260903.json"
NCERT_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_NCERT_CERTIFICATION_20260903.json"
AUTH_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
OUT_JSON = AUDITS / "TALOS_PRODUCTION_SEED_V2_NUMERICAL_REMEDIATION_20260904.json"
OUT_MD = AUDITS / "TALOS_PRODUCTION_SEED_V2_NUMERICAL_REMEDIATION_REPORT_20260904.md"

BATCH_ID = uuid.UUID("4509d488-c100-47f0-8357-4b1678abd00d")
URL = os.environ["DATABASE_URL"]
REMAT_TAG = "seed-v2-numerical-remediation-20260904"
SUPERSEDED_TAG = "seed-v2-numerical-remediation-superseded-20260904"
ATTEMPT_FAIL_TAG = "seed-v2-numerical-remediation-attempt-failed-20260904"
VISUAL_SUPERSEDED = "seed-v2-rematerialization-superseded-20260903"

TARGET_SLOT_IDS = ("physics-10", "physics-11", "physics-20", "physics-34")
MAX_ATTEMPTS_PER_SLOT = 3

FAILURE_HINTS = {
    "physics-10": (
        "Prior defective question had wrong KE-loss pairing for a perfectly inelastic collision. "
        "Create a NEW inelastic collision numerical with different masses/speeds. "
        "Compute common velocity, impulse on the initially stationary block, and KE loss; "
        "ensure EXACTLY one option states both correct impulse and correct KE loss."
    ),
    "physics-11": (
        "Prior defective question mis-stated final KE after ∫F dx. "
        "Create a NEW work–energy numerical with a different F(x) and interval. "
        "Kf must equal Ki+W and appear in exactly one option."
    ),
    "physics-20": (
        "Prior defective question used wrong ΔL=FL/(AY) value. "
        "Create a NEW Young's modulus elongation numerical with different F,L,A,Y. "
        "ΔL must appear in exactly one option with consistent scientific notation."
    ),
    "physics-34": (
        "Prior defective question's options omitted the true image shift (7.5 cm class error). "
        "Create a NEW thin-lens numerical (different f and distances). "
        "Independently compute u,v before/after object move; the exact shift magnitude AND "
        "direction (towards/away) MUST appear in exactly one option."
    ),
}


def _md5_body(body: dict | None) -> str:
    return hashlib.md5(json.dumps(body or {}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


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
        "stem": body.get("stem") or "",
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
    enriched = enrich_slot_with_visual_fields(slot)
    cons = build_v2_generation_constraints(enriched, base=base)
    hint = FAILURE_HINTS[slot["slot_id"]]
    cons["question_archetype"] = "numerical_calculation"
    cons["independent_verification_required"] = True
    cons["enforce_prior_stem_diversity"] = True
    cons["numerical_safety"] = True
    cons["reasoning"] = (
        f"NUMERICAL SAFETY REMEDIATION for slot {slot['slot_id']}. "
        f"Concept: {slot.get('concept')}. Topic: {slot.get('topic')}. "
        f"{hint} "
        "Use a FRESH physical scenario (do not paraphrase the defective original). "
        "Solve the problem yourself before writing options. "
        "Exactly four options A–D; exactly one numerically correct; no duplicate values; "
        "consistent units; explanation must use stem values and arrive at the correct option."
    )
    cons["seed_slot_id"] = slot["slot_id"]
    bp.constraints = cons
    bp.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(bp)
    return dict(bp.constraints or {})


def diversity_vs_priors(stem: str, options: list[dict], prior_stems: list[str]) -> dict:
    label, code = classify_against_prior(
        stem=stem,
        option_texts=[str(o.get("text") or "") for o in options],
        prior_stems=prior_stems,
        reject_forbidden_templates=True,
    )
    max_j = 0.0
    for p in prior_stems:
        max_j = max(max_j, jaccard(tokset(stem), tokset(p)))
    return {"classification": label, "code": code, "max_stem_jaccard": round(max_j, 4)}


def active_ids_map(gen_slots: list[dict], visual_repl: dict[str, str], num_repl: dict[str, str]) -> dict[str, str]:
    out = {}
    for s in gen_slots:
        sid = s["slot_id"]
        out[sid] = num_repl.get(sid) or visual_repl.get(sid) or s["content_item_id"]
    return out


async def main() -> int:
    settings = get_settings()
    if (settings.factory_provider or "").strip().lower() != "gemini":
        raise SystemExit("FACTORY_PROVIDER must be gemini")
    if (settings.factory_provider_mode or "").strip().lower() != "fixed":
        raise SystemExit("FACTORY_PROVIDER_MODE must be fixed")
    if (settings.factory_provider_fallback_chain or "").strip():
        raise SystemExit("Fallback chain must be empty")
    if (settings.gemini_model or "").strip() != "gemini-3.6-flash":
        print(f"WARN: gemini_model={settings.gemini_model} (expected gemini-3.6-flash)", flush=True)

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    gen = json.loads(GEN_PATH.read_text(encoding="utf-8"))
    p4 = json.loads(P4_PATH.read_text(encoding="utf-8"))
    visual_remat = json.loads(VISUAL_REMAT_PATH.read_text(encoding="utf-8"))
    ncert = json.loads(NCERT_PATH.read_text(encoding="utf-8"))
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))

    if ncert.get("verdict") != "RED":
        raise SystemExit("Expected NCERT certification RED authorizing numerical remediation")

    slots_by_id = {s["slot_id"]: s for s in plan["slots"]}
    gen_by_id = {s["slot_id"]: s for s in gen["slot_coverage"]["slots"]}
    visual_repl = {r["slot_id"]: r["replacement_content_item_id"] for r in visual_remat["results"]}
    v1_ids = list(auth["exact_uuid_allowlist"])

    # Current active before this remediation (visual remats applied)
    pre_active_map = active_ids_map(gen["slot_coverage"]["slots"], visual_repl, {})
    pre_active_ids = list(pre_active_map.values())
    if len(pre_active_ids) != 100:
        raise SystemExit(f"pre-active != 100: {len(pre_active_ids)}")

    targets = []
    for sid in TARGET_SLOT_IDS:
        slot = enrich_slot_with_visual_fields(dict(slots_by_id[sid]))
        g = gen_by_id[sid]
        # Current active original for these slots is still the gen id (not visual-rematted)
        orig_id = pre_active_map[sid]
        if orig_id != g["content_item_id"]:
            raise SystemExit(f"{sid} unexpected active id {orig_id}")
        targets.append(
            {
                "slot_id": sid,
                "slot": slot,
                "original_content_item_id": orig_id,
                "factory_blueprint_id": g["factory_blueprint_id"],
                "plan_blueprint_id": g["plan_blueprint_id"],
                "subject": g["subject"],
                "ncert_source_path": slot.get("ncert_source_path"),
            }
        )

    nontarget_ids = [pre_active_map[s["slot_id"]] for s in gen["slot_coverage"]["slots"] if s["slot_id"] not in TARGET_SLOT_IDS]
    if len(nontarget_ids) != 96:
        raise SystemExit(f"nontarget != 96: {len(nontarget_ids)}")

    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    results: list[dict] = []
    provider_totals = {
        "provider": "gemini",
        "provider_mode": "fixed",
        "routing": "fixed:gemini",
        "model_expected": "gemini-3.6-flash",
        "fallback_chain": "",
        "fallback_count": 0,
        "attempts": 0,
        "created": 0,
        "rejected_validation": 0,
        "duplicate": 0,
        "diversity_rejected": 0,
        "failed_provider": 0,
        "failed_parse": 0,
        "cost_usd": 0.0,
        "models": Counter(),
    }
    num_repl: dict[str, str] = {}
    failed_attempt_ids: list[str] = []

    async with Session() as session:
        before_active = await fingerprint_items(session, pre_active_ids)
        before_nontarget = await fingerprint_items(session, nontarget_ids)
        before_v1 = await fingerprint_items(session, v1_ids)
        before_t6d = await pop_fp(session, "physics-t6d-pilot-20260902")
        before_t6f2 = await t6f2_fp(session)
        before_legacy = await pop_fp(session, "legacy-physics-5000-import-20260902")
        # prior visual-superseded historical
        hist_visual = [r["original_content_item_id"] for r in visual_remat["results"]]
        before_hist_visual = await fingerprint_items(session, hist_visual)

        actor = (await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))).scalar_one()
        actor_id = actor.id
        gen_svc = ContentFactoryGenerationService(session)

        # Prior stems = remaining 96 active
        prior_stems = []
        for iid in nontarget_ids:
            it = await load_item(session, iid)
            prior_stems.append(it["stem"])

        for t in targets:
            slot_id = t["slot_id"]
            slot = t["slot"]
            orig_id = t["original_content_item_id"]
            bp_id = t["factory_blueprint_id"]
            print(f"\n=== NUMERICAL REMEDIATE {slot_id} (original={orig_id}) ===", flush=True)

            orig = await load_item(session, orig_id)
            orig_verify = verify_slot_body(slot_id, orig["body"])
            if orig_verify.get("status") != "FAIL":
                raise SystemExit(f"{slot_id} original not FAIL under independent verifier: {orig_verify}")

            cons = await update_blueprint_constraints(session, bp_id, slot)
            # Include defective stem in diversity priors for this slot
            slot_priors = list(prior_stems) + [orig["stem"]]

            entry: dict = {
                "slot_id": slot_id,
                "subject": t["subject"],
                "chapter": slot.get("chapter"),
                "topic": slot.get("topic"),
                "concept": slot.get("concept"),
                "difficulty": slot.get("difficulty"),
                "question_archetype": slot.get("question_archetype"),
                "ncert_source_path_preserved": t.get("ncert_source_path"),
                "plan_blueprint_id": t["plan_blueprint_id"],
                "factory_blueprint_id": bp_id,
                "original_content_item_id": orig_id,
                "original_body_md5": orig["body_md5"],
                "original_status": orig["status"],
                "original_failure": {
                    "ncert_cert_expectation": ORIGINAL_FAILURE_EXPECTATIONS[slot_id],
                    "independent_verification": orig_verify,
                    "stored_answer": orig["body"].get("correct_option"),
                    "stem_fingerprint": hashlib.sha256(orig["stem"].encode()).hexdigest()[:16],
                },
                "reason": "NUMERICAL_ANSWER_MISMATCH_NCERT_CERT_RED",
                "attempts": [],
                "replacement_content_item_id": None,
                "success": False,
            }

            accepted = None
            for attempt_i in range(1, MAX_ATTEMPTS_PER_SLOT + 1):
                job_key = f"numrem-v2-20260904-{slot_id}-a{attempt_i}-{uuid.uuid4().hex[:8]}"
                print(f"  attempt {attempt_i}/{MAX_ATTEMPTS_PER_SLOT} job={job_key}", flush=True)
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
                    provider_totals["models"][m] += int(n)

                attempt_rec = {
                    "attempt": attempt_i,
                    "job_key": job_key,
                    "stop_reason": result.get("stop_reason"),
                    "attempted": attempted,
                    "created": result.get("created"),
                    "content_item_ids": created_ids,
                    "cost_usd": cost,
                    "routing_policy": result.get("routing_policy"),
                    "models": result.get("models"),
                    "providers": result.get("providers"),
                    "rejected_validation": result.get("rejected_validation"),
                    "duplicate": result.get("duplicate"),
                    "diversity_rejected": result.get("diversity_rejected"),
                }

                if not created_ids:
                    attempt_rec["outcome"] = "NO_CANDIDATE_CREATED"
                    entry["attempts"].append(attempt_rec)
                    print(f"  no candidate created stop={result.get('stop_reason')}", flush=True)
                    continue

                new_id = created_ids[0]
                repl = await load_item(session, new_id)
                detailed = validate_candidate_body_detailed(
                    repl["body"], expected_difficulty=slot["difficulty"], constraints=cons
                )
                sem = assess_exactly_one_answer_semantics(repl["body"])
                num = verify_slot_body(slot_id, repl["body"])
                div = diversity_vs_priors(repl["stem"], repl["body"].get("options") or [], slot_priors)
                # Also check vs other accepted replacements this run
                for other in results:
                    if other.get("replacement_content_item_id") and other.get("replacement_stem"):
                        d2 = diversity_vs_priors(
                            repl["stem"],
                            repl["body"].get("options") or [],
                            [other["replacement_stem"]],
                        )
                        if d2["classification"] in (
                            "EXACT_DUPLICATE",
                            "NORMALIZED_DUPLICATE",
                            "NEAR_DUPLICATE",
                            "SAME_TEMPLATE_REPETITION",
                        ):
                            div = {**d2, "vs": other["slot_id"]}

                dup_same = repl["body_md5"] == orig["body_md5"]
                num_ok = num.get("status") == "PASS"
                struct_ok = bool(detailed.get("ok"))
                sem_ok = (not sem.hard_fail) and sem.status != "SEMANTIC_AMBIGUITY_DETECTED"
                div_ok = div["classification"] in ("UNIQUE", "LEGITIMATE_CONCEPTUAL_OVERLAP", "UNCERTAIN")
                draft_ok = repl["status"] == "DRAFT"
                opt_ok = bool((num.get("option_validation") or {}).get("ok", True)) and num.get(
                    "single_correct_in_options", True
                )

                attempt_rec.update(
                    {
                        "candidate_id": new_id,
                        "body_md5": repl["body_md5"],
                        "status": repl["status"],
                        "validation": {
                            "ok": detailed.get("ok"),
                            "errors": detailed.get("errors"),
                            "warnings": detailed.get("warnings"),
                            "structural_status": detailed.get("structural_status"),
                            "semantic_status": detailed.get("semantic_status"),
                        },
                        "semantic_assessment": {"status": sem.status, "signals": sem.flags, "hard_fail": sem.hard_fail},
                        "numerical_verification": num,
                        "diversity": div,
                        "duplicate_same_body_as_original": dup_same,
                        "gates": {
                            "structural": struct_ok,
                            "semantic": sem_ok,
                            "numerical": num_ok,
                            "options": opt_ok,
                            "diversity": div_ok,
                            "draft": draft_ok,
                            "not_same_body": not dup_same,
                        },
                    }
                )

                success = all([struct_ok, sem_ok, num_ok, opt_ok, div_ok, draft_ok, not dup_same])
                if success:
                    attempt_rec["outcome"] = "ACCEPTED"
                    entry["attempts"].append(attempt_rec)
                    accepted = {
                        "id": new_id,
                        "body": repl["body"],
                        "stem": repl["stem"],
                        "body_md5": repl["body_md5"],
                        "status": repl["status"],
                        "num": num,
                        "sem": sem,
                        "div": div,
                        "detailed": detailed,
                        "attempt": attempt_i,
                    }
                    print(f"  ACCEPTED {new_id} num=PASS stored={num.get('stored_answer')}", flush=True)
                    break

                # Failed attempt — preserve as audit DRAFT but not active
                await append_tags(
                    session,
                    new_id,
                    [ATTEMPT_FAIL_TAG, f"slot:{slot_id}", f"attempt:{attempt_i}", "seed-v2"],
                )
                await session.commit()
                failed_attempt_ids.append(new_id)
                attempt_rec["outcome"] = f"REJECTED:{num.get('status')}"
                if not num_ok:
                    attempt_rec["reject_reason"] = f"numerical_{num.get('status')}"
                elif not struct_ok:
                    attempt_rec["reject_reason"] = "structural"
                elif not sem_ok:
                    attempt_rec["reject_reason"] = "semantic"
                elif not div_ok:
                    attempt_rec["reject_reason"] = f"diversity:{div['classification']}"
                else:
                    attempt_rec["reject_reason"] = "other"
                entry["attempts"].append(attempt_rec)
                print(
                    f"  rejected {new_id} num={num.get('status')} struct={struct_ok} "
                    f"sem={sem.status} div={div['classification']}",
                    flush=True,
                )

            if accepted:
                new_id = accepted["id"]
                await append_tags(
                    session,
                    orig_id,
                    [
                        SUPERSEDED_TAG,
                        f"replaced-by:{new_id}",
                        f"slot:{slot_id}",
                        "seed-v2-historical-preserved",
                        "seed-v2-numerical-failure-original",
                    ],
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
                        "seed-v2-numerical-remediated-active",
                    ],
                )
                await session.commit()
                num_repl[slot_id] = new_id
                # Add accepted stem to priors for subsequent slots
                prior_stems.append(accepted["stem"])
                entry.update(
                    {
                        "replacement_content_item_id": new_id,
                        "replacement_body_md5": accepted["body_md5"],
                        "replacement_status": accepted["status"],
                        "replacement_stem": accepted["stem"],
                        "replacement_stored_answer": accepted["body"].get("correct_option"),
                        "replacement_numerical_verification": accepted["num"],
                        "replacement_semantic": {
                            "status": accepted["sem"].status,
                            "signals": accepted["sem"].flags,
                        },
                        "replacement_diversity": accepted["div"],
                        "replacement_validation": {
                            "ok": accepted["detailed"].get("ok"),
                            "errors": accepted["detailed"].get("errors"),
                        },
                        "lineage": {
                            "original_preserved": True,
                            "original_id": orig_id,
                            "replacement_id": new_id,
                            "original_body_md5_unchanged_expected": orig["body_md5"],
                            "superseded_tag": SUPERSEDED_TAG,
                            "remediation_tag": REMAT_TAG,
                        },
                        "success": True,
                        "accepted_on_attempt": accepted["attempt"],
                    }
                )
            else:
                entry["failure"] = "NO_ACCEPTABLE_REPLACEMENT_AFTER_RETRIES"
                entry["success"] = False
            results.append(entry)

        # Post integrity
        post_active_map = active_ids_map(gen["slot_coverage"]["slots"], visual_repl, num_repl)
        post_active_ids = list(post_active_map.values())
        after_active = await fingerprint_items(session, post_active_ids)
        after_nontarget = await fingerprint_items(session, nontarget_ids)
        after_v1 = await fingerprint_items(session, v1_ids)
        after_t6d = await pop_fp(session, "physics-t6d-pilot-20260902")
        after_t6f2 = await t6f2_fp(session)
        after_legacy = await pop_fp(session, "legacy-physics-5000-import-20260902")
        after_hist_visual = await fingerprint_items(session, hist_visual)

        originals_preserved = []
        for t in targets:
            cur = await load_item(session, t["original_content_item_id"])
            entry = next(r for r in results if r["slot_id"] == t["slot_id"])
            originals_preserved.append(
                {
                    "slot_id": t["slot_id"],
                    "id": cur["id"],
                    "body_md5_unchanged": cur["body_md5"] == entry["original_body_md5"],
                    "status": cur["status"],
                    "has_superseded_tag": SUPERSEDED_TAG in (cur["tags"] or []),
                    "still_draft": cur["status"] == "DRAFT",
                }
            )

        successes = sum(1 for r in results if r.get("success"))
        all_num_pass = all(
            (r.get("replacement_numerical_verification") or {}).get("status") == "PASS" for r in results if r.get("success")
        )
        protected_ok = (
            after_v1["bodies_fp"] == before_v1["bodies_fp"]
            and after_t6d["content_fp"] == before_t6d["content_fp"]
            and after_t6f2["content_fp"] == before_t6f2["content_fp"]
            and after_legacy["content_fp"] == before_legacy["content_fp"]
            and after_hist_visual["bodies_fp"] == before_hist_visual["bodies_fp"]
            and after_nontarget["bodies_fp"] == before_nontarget["bodies_fp"]
        )
        active_n_ok = len(post_active_ids) == 100 and len(set(post_active_ids)) == 100
        # superseded originals not in active
        superseded_leak = any(t["original_content_item_id"] in post_active_ids for t in targets if num_repl.get(t["slot_id"]))
        drafts_ok = all(
            (r.get("replacement_status") == "DRAFT") for r in results if r.get("replacement_content_item_id") and r.get("success")
        )

        verdict = "GREEN"
        limitations = [
            "NCERT certification NOT re-run in this gate — next gate required",
            "Independent verification covers the four concept-family solvers; novel unparsed templates would be REQUIRES_REVIEW",
            "Failed generation attempts (if any) preserved as DRAFT with attempt-failed tags — not active",
        ]
        if successes < 4 or not all_num_pass:
            verdict = "AMBER" if successes >= 1 and not any(
                (r.get("replacement_numerical_verification") or {}).get("status") == "FAIL" and r.get("success")
                for r in results
            ) else "RED"
            # If any accepted with FAIL num — RED; if missing acceptances — AMBER/RED
            if successes < 4:
                verdict = "RED" if successes == 0 else "AMBER"
            limitations.append(f"successes={successes}/4")
        # Any successful replacement that somehow isn't PASS → RED
        for r in results:
            if r.get("success") and (r.get("replacement_numerical_verification") or {}).get("status") != "PASS":
                verdict = "RED"
                limitations.append(f"{r['slot_id']}_accepted_without_num_pass")
        if not protected_ok or not active_n_ok or superseded_leak:
            verdict = "RED"
            limitations.append("integrity_or_active_population_violation")
        if not all(o["body_md5_unchanged"] and o["still_draft"] for o in originals_preserved):
            verdict = "RED"
            limitations.append("original_mutation_or_status_change")
        if not drafts_ok:
            verdict = "RED"
            limitations.append("replacement_not_draft")
        if provider_totals["fallback_count"] != 0:
            verdict = "RED"
            limitations.append("fallback_used")

        artifact = {
            "audit": "Production Seed V2 Numerical Remediation — Exact 4 Failures",
            "date": "2026-09-04",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "verdict": verdict,
            "targets": list(TARGET_SLOT_IDS),
            "batch_uuid": str(BATCH_ID),
            "provider": {
                **provider_totals,
                "models": dict(provider_totals["models"]),
            },
            "active_population": {
                "before_n": 100,
                "after_n": len(post_active_ids),
                "after_ids_by_slot": post_active_map,
                "numerical_replacements": num_repl,
                "visual_replacements_unchanged": visual_repl,
                "failed_attempt_ids": failed_attempt_ids,
            },
            "results": results,
            "originals_preserved": originals_preserved,
            "integrity_before": {
                "active_fp": before_active["bodies_fp"],
                "nontarget96_fp": before_nontarget["bodies_fp"],
                "v1_fp": before_v1["bodies_fp"],
                "t6d_fp": before_t6d["content_fp"],
                "t6f2_fp": before_t6f2["content_fp"],
                "legacy_fp": before_legacy["content_fp"],
                "visual_hist_fp": before_hist_visual["bodies_fp"],
            },
            "integrity_after": {
                "active_fp": after_active["bodies_fp"],
                "nontarget96_fp": after_nontarget["bodies_fp"],
                "v1_fp": after_v1["bodies_fp"],
                "t6d_fp": after_t6d["content_fp"],
                "t6f2_fp": after_t6f2["content_fp"],
                "legacy_fp": after_legacy["content_fp"],
                "visual_hist_fp": after_hist_visual["bodies_fp"],
            },
            "integrity_checks": {
                "nontarget_96_unchanged": after_nontarget["bodies_fp"] == before_nontarget["bodies_fp"],
                "protected_unchanged": protected_ok,
                "active_count_100": active_n_ok,
                "superseded_not_in_active": not superseded_leak,
                "approvals": 0,
                "publications": 0,
                "ecaep": 0,
                "ncert_rerun": False,
            },
            "counts": {"approvals": 0, "publications": 0, "ecaep": 0, "ncert_certification": 0},
            "tests": {"note": "Filled by agent after pytest", "thresholds_weakened": False},
            "limitations": limitations,
            "next_gate_recommendation": (
                "NCERT Certification Re-run — Exact Active 100"
                if verdict == "GREEN"
                else "Resolve unsuccessful numerical replacements before NCERT re-run"
            ),
            "phase_stop": "NUMERICAL_REMEDIATION_COMPLETE",
            "script": "apps/backend/scripts/run_factory_v2_numerical_remediation.py",
        }

        OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

        md = [
            "# Production Seed V2 — Numerical Remediation (Exact 4 Failures)",
            "",
            f"**Verdict: {verdict}**  ",
            f"**Captured:** {artifact['captured_at']}  ",
            "Provider: Gemini / gemini-3.6-flash / fixed:gemini / fallback=0",
            "",
            "## Targets",
            ", ".join(TARGET_SLOT_IDS),
            "",
            "## Results",
        ]
        for r in results:
            md.append(
                f"### {r['slot_id']} — {'SUCCESS' if r.get('success') else 'FAILED'}\n"
                f"- original: `{r['original_content_item_id']}`\n"
                f"- replacement: `{r.get('replacement_content_item_id')}`\n"
                f"- attempts: {len(r.get('attempts') or [])}\n"
                f"- independent num: {(r.get('replacement_numerical_verification') or {}).get('status')}\n"
                f"- stored answer: {r.get('replacement_stored_answer')}\n"
                f"- expected option: {(r.get('replacement_numerical_verification') or {}).get('expected_option')}\n"
            )
        md += [
            "",
            f"## Cost / attempts",
            f"attempts={provider_totals['attempts']} created={provider_totals['created']} "
            f"cost_usd={provider_totals['cost_usd']:.6f} failed_attempts_tagged={len(failed_attempt_ids)}",
            "",
            "## Integrity",
            f"nontarget96 unchanged: {artifact['integrity_checks']['nontarget_96_unchanged']}  ",
            f"protected unchanged: {artifact['integrity_checks']['protected_unchanged']}  ",
            f"active n=100: {artifact['integrity_checks']['active_count_100']}",
            "",
            "## Next gate",
            artifact["next_gate_recommendation"],
            "",
            "**STOP** — Do not NCERT re-run / approve / publish / generate more / 1k-scale from this gate alone.",
            "",
        ]
        OUT_MD.write_text("\n".join(md), encoding="utf-8")

        print(
            json.dumps(
                {
                    "verdict": verdict,
                    "successes": successes,
                    "num_repl": num_repl,
                    "cost_usd": provider_totals["cost_usd"],
                    "failed_attempts": len(failed_attempt_ids),
                    "protected_ok": protected_ok,
                },
                indent=2,
            ),
            flush=True,
        )

    await engine.dispose()
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
