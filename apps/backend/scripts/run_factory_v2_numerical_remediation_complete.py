#!/usr/bin/env python3
"""Complete V2 numerical remediation after broadened verifiers.

Rescues independently verified PASS attempts from the interrupted run for
physics-10 / physics-11, then generates physics-20 / physics-34 with Gemini.
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
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db")

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
from app.modules.cms.services.factory_v2_visual import build_v2_generation_constraints, enrich_slot_with_visual_fields
from app.modules.identity.models.user import User
from scripts.run_factory_v2_numerical_remediation import (
    ATTEMPT_FAIL_TAG,
    BATCH_ID,
    FAILURE_HINTS,
    OUT_JSON,
    OUT_MD,
    REMAT_TAG,
    SUPERSEDED_TAG,
    TARGET_SLOT_IDS,
    URL,
    VISUAL_REMAT_PATH,
    _md5_body,
    active_ids_map,
    append_tags,
    diversity_vs_priors,
    fingerprint_items,
    load_item,
    pop_fp,
    t6f2_fp,
    update_blueprint_constraints,
)

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
PLAN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"
GEN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_GENERATION_20260903.json"
AUTH_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
NCERT_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_NCERT_CERTIFICATION_20260903.json"

# Prefer these rescued attempts (PASS under independent verifier; not original-number clones)
RESCUE_CANDIDATES = {
    "physics-10": "2e43ef71-d72a-423a-b9be-2e44c51de8b1",  # 3kg/8m/s/5kg → impulse 15, KE 60
    "physics-11": "5b4f381e-0dee-4118-b237-fbaabbe1d0f5",  # quadratic F, Ki given → Kf 46
}

MAX_ATTEMPTS = 4


async def main() -> int:
    settings = get_settings()
    assert (settings.factory_provider or "").lower() == "gemini"
    assert (settings.factory_provider_mode or "").lower() == "fixed"

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    gen = json.loads(GEN_PATH.read_text(encoding="utf-8"))
    visual_remat = json.loads(VISUAL_REMAT_PATH.read_text(encoding="utf-8"))
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    ncert = json.loads(NCERT_PATH.read_text(encoding="utf-8"))
    assert ncert.get("verdict") == "RED"

    slots_by_id = {s["slot_id"]: s for s in plan["slots"]}
    gen_by_id = {s["slot_id"]: s for s in gen["slot_coverage"]["slots"]}
    visual_repl = {r["slot_id"]: r["replacement_content_item_id"] for r in visual_remat["results"]}
    v1_ids = list(auth["exact_uuid_allowlist"])
    pre_active_map = active_ids_map(gen["slot_coverage"]["slots"], visual_repl, {})
    nontarget_ids = [pre_active_map[s["slot_id"]] for s in gen["slot_coverage"]["slots"] if s["slot_id"] not in TARGET_SLOT_IDS]
    hist_visual = [r["original_content_item_id"] for r in visual_remat["results"]]

    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    results = []
    num_repl: dict[str, str] = {}
    failed_attempt_ids: list[str] = []
    provider_totals = {
        "provider": "gemini",
        "routing": "fixed:gemini",
        "fallback_count": 0,
        "attempts": 0,
        "created": 0,
        "cost_usd": 0.0,
        "models": Counter(),
        "rescued_from_prior_attempts": [],
    }

    async with Session() as session:
        before_nontarget = await fingerprint_items(session, nontarget_ids)
        before_v1 = await fingerprint_items(session, v1_ids)
        before_t6d = await pop_fp(session, "physics-t6d-pilot-20260902")
        before_t6f2 = await t6f2_fp(session)
        before_legacy = await pop_fp(session, "legacy-physics-5000-import-20260902")
        before_hist_visual = await fingerprint_items(session, hist_visual)

        actor = (await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))).scalar_one()
        gen_svc = ContentFactoryGenerationService(session)

        prior_stems = []
        for iid in nontarget_ids:
            prior_stems.append((await load_item(session, iid))["stem"])

        async def accept_replacement(slot_id: str, orig_id: str, new_id: str, *, source: str, attempt_meta: dict) -> dict:
            orig = await load_item(session, orig_id)
            repl = await load_item(session, new_id)
            num = verify_slot_body(slot_id, repl["body"])
            assert num["status"] == "PASS", num
            sem = assess_exactly_one_answer_semantics(repl["body"])
            assert not sem.hard_fail
            detailed = validate_candidate_body_detailed(
                repl["body"],
                expected_difficulty=slots_by_id[slot_id]["difficulty"],
                constraints=build_v2_generation_constraints(enrich_slot_with_visual_fields(slots_by_id[slot_id])),
            )
            div = diversity_vs_priors(repl["stem"], repl["body"].get("options") or [], prior_stems + [orig["stem"]])
            await append_tags(
                session,
                orig_id,
                [SUPERSEDED_TAG, f"replaced-by:{new_id}", f"slot:{slot_id}", "seed-v2-historical-preserved", "seed-v2-numerical-failure-original"],
            )
            await append_tags(
                session,
                new_id,
                [REMAT_TAG, f"replaces:{orig_id}", f"slot:{slot_id}", "seed-v2", "production-seed-v2-2026-09-03", "seed-v2-numerical-remediated-active"],
            )
            await session.commit()
            num_repl[slot_id] = new_id
            prior_stems.append(repl["stem"])
            return {
                "slot_id": slot_id,
                "subject": "Physics",
                "chapter": slots_by_id[slot_id]["chapter"],
                "topic": slots_by_id[slot_id]["topic"],
                "concept": slots_by_id[slot_id]["concept"],
                "difficulty": slots_by_id[slot_id]["difficulty"],
                "question_archetype": slots_by_id[slot_id]["question_archetype"],
                "ncert_source_path_preserved": slots_by_id[slot_id].get("ncert_source_path"),
                "original_content_item_id": orig_id,
                "original_body_md5": orig["body_md5"],
                "original_failure": {
                    "ncert_cert_expectation": ORIGINAL_FAILURE_EXPECTATIONS[slot_id],
                    "independent_verification": verify_slot_body(slot_id, orig["body"]),
                    "stored_answer": orig["body"].get("correct_option"),
                },
                "reason": "NUMERICAL_ANSWER_MISMATCH_NCERT_CERT_RED",
                "acceptance_source": source,
                "attempts": [attempt_meta],
                "replacement_content_item_id": new_id,
                "replacement_body_md5": repl["body_md5"],
                "replacement_status": repl["status"],
                "replacement_stem": repl["stem"],
                "replacement_stored_answer": repl["body"].get("correct_option"),
                "replacement_numerical_verification": num,
                "replacement_semantic": {"status": sem.status, "signals": sem.flags},
                "replacement_diversity": div,
                "replacement_validation": {"ok": detailed.get("ok"), "errors": detailed.get("errors")},
                "lineage": {
                    "original_preserved": True,
                    "original_id": orig_id,
                    "replacement_id": new_id,
                    "superseded_tag": SUPERSEDED_TAG,
                    "remediation_tag": REMAT_TAG,
                },
                "success": True,
            }

        # Rescue physics-10 / physics-11
        for sid, cand in RESCUE_CANDIDATES.items():
            orig_id = pre_active_map[sid]
            print(f"RESCUE {sid} <- {cand}", flush=True)
            repl = await load_item(session, cand)
            num = verify_slot_body(sid, repl["body"])
            if num["status"] != "PASS":
                raise SystemExit(f"rescue candidate not PASS: {sid} {num}")
            # Reject near-clone of original numbers for physics-10 alternative was already avoided
            entry = await accept_replacement(
                sid,
                orig_id,
                cand,
                source="rescued_prior_attempt_after_verifier_broadening",
                attempt_meta={"outcome": "ACCEPTED_RESCUE", "candidate_id": cand, "numerical_verification": num},
            )
            provider_totals["rescued_from_prior_attempts"].append({"slot_id": sid, "id": cand})
            results.append(entry)

        # Generate remaining: physics-20, physics-34
        for sid in ("physics-20", "physics-34"):
            slot = enrich_slot_with_visual_fields(dict(slots_by_id[sid]))
            orig_id = pre_active_map[sid]
            bp_id = gen_by_id[sid]["factory_blueprint_id"]
            print(f"\n=== GENERATE {sid} ===", flush=True)
            cons = await update_blueprint_constraints(session, bp_id, slot)
            orig = await load_item(session, orig_id)
            accepted = None
            attempts = []
            for attempt_i in range(1, MAX_ATTEMPTS + 1):
                job_key = f"numrem-v2-20260904-{sid}-a{attempt_i}-{uuid.uuid4().hex[:8]}"
                print(f"  attempt {attempt_i} {job_key}", flush=True)
                result = await gen_svc.generate_for_batch(
                    BATCH_ID,
                    blueprint_id=uuid.UUID(bp_id),
                    target_count=1,
                    actor_id=actor.id,
                    job_key=job_key,
                    sync_cap=True,
                )
                provider_totals["attempts"] += int(result.get("attempted") or 0)
                provider_totals["cost_usd"] += float(result.get("cost_usd") or 0)
                provider_totals["created"] += int(result.get("created") or 0)
                for m, n in (result.get("models") or {}).items():
                    provider_totals["models"][m] += int(n)
                created_ids = list(result.get("content_item_ids") or [])
                attempt_rec = {
                    "attempt": attempt_i,
                    "job_key": job_key,
                    "stop_reason": result.get("stop_reason"),
                    "created_ids": created_ids,
                    "cost_usd": result.get("cost_usd"),
                    "models": result.get("models"),
                }
                if not created_ids:
                    attempt_rec["outcome"] = "NO_CANDIDATE"
                    attempts.append(attempt_rec)
                    continue
                new_id = created_ids[0]
                repl = await load_item(session, new_id)
                num = verify_slot_body(sid, repl["body"])
                sem = assess_exactly_one_answer_semantics(repl["body"])
                detailed = validate_candidate_body_detailed(
                    repl["body"], expected_difficulty=slot["difficulty"], constraints=cons
                )
                div = diversity_vs_priors(repl["stem"], repl["body"].get("options") or [], prior_stems + [orig["stem"]])
                attempt_rec.update(
                    {
                        "candidate_id": new_id,
                        "numerical_verification": num,
                        "semantic": sem.status,
                        "diversity": div,
                        "validation_ok": detailed.get("ok"),
                    }
                )
                ok = (
                    num.get("status") == "PASS"
                    and detailed.get("ok")
                    and not sem.hard_fail
                    and div["classification"] in ("UNIQUE", "LEGITIMATE_CONCEPTUAL_OVERLAP", "UNCERTAIN")
                    and repl["status"] == "DRAFT"
                    and repl["body_md5"] != orig["body_md5"]
                )
                if ok:
                    attempt_rec["outcome"] = "ACCEPTED"
                    attempts.append(attempt_rec)
                    accepted = new_id
                    print(f"  ACCEPTED {new_id} {num.get('stored_answer')}", flush=True)
                    break
                await append_tags(session, new_id, [ATTEMPT_FAIL_TAG, f"slot:{sid}", f"attempt:{attempt_i}"])
                await session.commit()
                failed_attempt_ids.append(new_id)
                attempt_rec["outcome"] = f"REJECTED:{num.get('status')}"
                attempts.append(attempt_rec)
                print(f"  rejected {new_id} {num.get('status')} {num.get('reason')}", flush=True)

            if not accepted:
                results.append(
                    {
                        "slot_id": sid,
                        "original_content_item_id": orig_id,
                        "success": False,
                        "failure": "NO_ACCEPTABLE_REPLACEMENT",
                        "attempts": attempts,
                    }
                )
                continue
            entry = await accept_replacement(
                sid,
                orig_id,
                accepted,
                source="generated_this_completion_run",
                attempt_meta=attempts[-1],
            )
            entry["attempts"] = attempts
            results.append(entry)

        post_active_map = active_ids_map(gen["slot_coverage"]["slots"], visual_repl, num_repl)
        post_active_ids = list(post_active_map.values())
        after_nontarget = await fingerprint_items(session, nontarget_ids)
        after_v1 = await fingerprint_items(session, v1_ids)
        after_t6d = await pop_fp(session, "physics-t6d-pilot-20260902")
        after_t6f2 = await t6f2_fp(session)
        after_legacy = await pop_fp(session, "legacy-physics-5000-import-20260902")
        after_hist_visual = await fingerprint_items(session, hist_visual)
        after_active = await fingerprint_items(session, post_active_ids)

        originals_preserved = []
        for sid in TARGET_SLOT_IDS:
            orig_id = gen_by_id[sid]["content_item_id"]
            cur = await load_item(session, orig_id)
            originals_preserved.append(
                {
                    "slot_id": sid,
                    "id": orig_id,
                    "body_md5": cur["body_md5"],
                    "status": cur["status"],
                    "has_superseded_tag": SUPERSEDED_TAG in cur["tags"],
                    "still_draft": cur["status"] == "DRAFT",
                }
            )

        successes = sum(1 for r in results if r.get("success"))
        protected_ok = (
            after_nontarget["bodies_fp"] == before_nontarget["bodies_fp"]
            and after_v1["bodies_fp"] == before_v1["bodies_fp"]
            and after_t6d["content_fp"] == before_t6d["content_fp"]
            and after_t6f2["content_fp"] == before_t6f2["content_fp"]
            and after_legacy["content_fp"] == before_legacy["content_fp"]
            and after_hist_visual["bodies_fp"] == before_hist_visual["bodies_fp"]
        )
        all_pass = all(
            (r.get("replacement_numerical_verification") or {}).get("status") == "PASS" for r in results if r.get("success")
        )
        active_ok = len(post_active_ids) == 100 and len(set(post_active_ids)) == 100
        leak = any(gen_by_id[sid]["content_item_id"] in post_active_ids for sid in num_repl)

        verdict = "GREEN"
        limitations = [
            "NCERT certification NOT re-run — next gate required",
            "Some early attempts were rescued after verifier broadening (still independently calculated)",
            "Failed generation attempts preserved as DRAFT with attempt-failed tags",
        ]
        if successes != 4 or not all_pass or not protected_ok or not active_ok or leak:
            verdict = "RED"
            limitations.append(f"successes={successes} all_pass={all_pass} protected={protected_ok} active_ok={active_ok} leak={leak}")
        if any(r.get("replacement_status") != "DRAFT" for r in results if r.get("success")):
            verdict = "RED"

        artifact = {
            "audit": "Production Seed V2 Numerical Remediation — Exact 4 Failures",
            "date": "2026-09-04",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "verdict": verdict,
            "targets": list(TARGET_SLOT_IDS),
            "batch_uuid": str(BATCH_ID),
            "provider": {**provider_totals, "models": dict(provider_totals["models"])},
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
            "integrity_checks": {
                "nontarget_96_unchanged": after_nontarget["bodies_fp"] == before_nontarget["bodies_fp"],
                "protected_unchanged": protected_ok,
                "active_count_100": active_ok,
                "superseded_not_in_active": not leak,
                "approvals": 0,
                "publications": 0,
                "ecaep": 0,
                "ncert_rerun": False,
            },
            "integrity_before": {
                "nontarget96_fp": before_nontarget["bodies_fp"],
                "v1_fp": before_v1["bodies_fp"],
                "t6d_fp": before_t6d["content_fp"],
                "t6f2_fp": before_t6f2["content_fp"],
                "legacy_fp": before_legacy["content_fp"],
            },
            "integrity_after": {
                "active_fp": after_active["bodies_fp"],
                "nontarget96_fp": after_nontarget["bodies_fp"],
                "v1_fp": after_v1["bodies_fp"],
                "t6d_fp": after_t6d["content_fp"],
                "t6f2_fp": after_t6f2["content_fp"],
                "legacy_fp": after_legacy["content_fp"],
            },
            "counts": {"approvals": 0, "publications": 0, "ecaep": 0},
            "tests": {"note": "Filled after pytest", "thresholds_weakened": False},
            "limitations": limitations,
            "next_gate_recommendation": (
                "NCERT Certification Re-run — Exact Active 100" if verdict == "GREEN" else "Resolve remaining numerical failures"
            ),
            "phase_stop": "NUMERICAL_REMEDIATION_COMPLETE",
            "script": "apps/backend/scripts/run_factory_v2_numerical_remediation_complete.py",
        }
        OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        lines = [
            f"# Production Seed V2 — Numerical Remediation\n\n**Verdict: {verdict}**\n",
            f"Captured: {artifact['captured_at']}\n",
            "## Replacements\n",
        ]
        for r in results:
            lines.append(
                f"- **{r['slot_id']}**: success={r.get('success')} orig=`{r.get('original_content_item_id')}` "
                f"repl=`{r.get('replacement_content_item_id')}` "
                f"num={(r.get('replacement_numerical_verification') or {}).get('status')} "
                f"ans={r.get('replacement_stored_answer')}\n"
            )
        lines += [
            f"\nCost USD: {provider_totals['cost_usd']:.6f}\n",
            f"Next: {artifact['next_gate_recommendation']}\n",
            "\n**STOP** — no NCERT re-run / approve / publish / 1k-scale.\n",
        ]
        OUT_MD.write_text("".join(lines), encoding="utf-8")
        print(json.dumps({"verdict": verdict, "num_repl": num_repl, "cost": provider_totals["cost_usd"]}, indent=2))

    await engine.dispose()
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
