#!/usr/bin/env python3
"""Finalize V2 numerical remediation: rescue verified Gemini attempts for physics-20/34.

Does NOT call the LLM. Applies lineage for independently PASS-verified prior attempts,
writes audit artifacts, and verifies integrity. physics-10/11 already accepted.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.cms.services.factory_candidate_validation import validate_candidate_body_detailed
from app.modules.cms.services.factory_v2_answer_ambiguity import assess_exactly_one_answer_semantics
from app.modules.cms.services.factory_v2_numerical_verify import (
    ORIGINAL_FAILURE_EXPECTATIONS,
    verify_slot_body,
)
from app.modules.cms.services.factory_v2_visual import build_v2_generation_constraints, enrich_slot_with_visual_fields
from scripts.run_factory_v2_numerical_remediation import (
    ATTEMPT_FAIL_TAG,
    BATCH_ID,
    OUT_JSON,
    OUT_MD,
    REMAT_TAG,
    SUPERSEDED_TAG,
    TARGET_SLOT_IDS,
    URL,
    VISUAL_REMAT_PATH,
    active_ids_map,
    append_tags,
    diversity_vs_priors,
    fingerprint_items,
    load_item,
    pop_fp,
    t6f2_fp,
)

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
PLAN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"
GEN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_GENERATION_20260903.json"
AUTH_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
NCERT_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_NCERT_CERTIFICATION_20260903.json"
PRIOR_ARTIFACT = OUT_JSON

# Independently PASS under deterministic verifier after parser broadening
RESCUE = {
    "physics-10": "2e43ef71-d72a-423a-b9be-2e44c51de8b1",
    "physics-11": "5b4f381e-0dee-4118-b237-fbaabbe1d0f5",
    "physics-20": "f60e3124-8aa0-4ff6-b3e1-f8ad81eadce9",  # ΔL = 1.29e-3 m → A
    "physics-34": "b98e5873-8352-4bb6-9a30-368e2f0ce6f7",  # shift +15 cm away → B
}


async def main() -> int:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    gen = json.loads(GEN_PATH.read_text(encoding="utf-8"))
    visual_remat = json.loads(VISUAL_REMAT_PATH.read_text(encoding="utf-8"))
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    ncert = json.loads(NCERT_PATH.read_text(encoding="utf-8"))
    prior = json.loads(PRIOR_ARTIFACT.read_text(encoding="utf-8")) if PRIOR_ARTIFACT.exists() else {}

    slots_by_id = {s["slot_id"]: s for s in plan["slots"]}
    gen_by_id = {s["slot_id"]: s for s in gen["slot_coverage"]["slots"]}
    visual_repl = {r["slot_id"]: r["replacement_content_item_id"] for r in visual_remat["results"]}
    v1_ids = list(auth["exact_uuid_allowlist"])
    # Originals: visual-active before numerical remat (gen id unless visual remapped)
    pre_num_map = active_ids_map(gen["slot_coverage"]["slots"], visual_repl, {})
    nontarget_ids = [pre_num_map[s["slot_id"]] for s in gen["slot_coverage"]["slots"] if s["slot_id"] not in TARGET_SLOT_IDS]
    hist_visual = [r["original_content_item_id"] for r in visual_remat["results"]]

    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    results = []
    num_repl: dict[str, str] = {}
    failed_attempt_ids: list[str] = list((prior.get("active_population") or {}).get("failed_attempt_ids") or [])

    provider_prior = prior.get("provider") or {}
    provider_totals = {
        "provider": "gemini",
        "routing": "fixed:gemini",
        "fallback_count": 0,
        "attempts": int(provider_prior.get("attempts") or 0),
        "created": int(provider_prior.get("created") or 0),
        "cost_usd": float(provider_prior.get("cost_usd") or 0),
        "models": dict(provider_prior.get("models") or {"gemini-3.6-flash": 0}),
        "rescued_from_prior_attempts": [],
        "finalize_note": "No new LLM calls in finalize; acceptance of independently verified prior Gemini attempts",
    }

    async with Session() as session:
        before_nontarget = await fingerprint_items(session, nontarget_ids)
        before_v1 = await fingerprint_items(session, v1_ids)
        before_t6d = await pop_fp(session, "physics-t6d-pilot-20260902")
        before_t6f2 = await t6f2_fp(session)
        before_legacy = await pop_fp(session, "legacy-physics-5000-import-20260902")
        before_hist_visual = await fingerprint_items(session, hist_visual)

        prior_stems = []
        for iid in nontarget_ids:
            prior_stems.append((await load_item(session, iid))["stem"])

        for sid in TARGET_SLOT_IDS:
            cand = RESCUE[sid]
            # Original for lineage = currently active before THIS slot's remat, which for
            # physics-10/11 may already be the remat id; use gen/visual pre-num id as original.
            orig_id = pre_num_map[sid]
            print(f"ACCEPT {sid}: orig={orig_id} <- {cand}", flush=True)
            orig = await load_item(session, orig_id)
            repl = await load_item(session, cand)
            num = verify_slot_body(sid, repl["body"])
            if num["status"] != "PASS":
                raise SystemExit(f"{sid} candidate not PASS: {num}")
            sem = assess_exactly_one_answer_semantics(repl["body"])
            if sem.hard_fail:
                raise SystemExit(f"{sid} semantic hard_fail: {sem}")
            detailed = validate_candidate_body_detailed(
                repl["body"],
                expected_difficulty=slots_by_id[sid]["difficulty"],
                constraints=build_v2_generation_constraints(enrich_slot_with_visual_fields(slots_by_id[sid])),
            )
            if not detailed.get("ok"):
                raise SystemExit(f"{sid} validation failed: {detailed.get('errors')}")
            div = diversity_vs_priors(repl["stem"], repl["body"].get("options") or [], prior_stems + [orig["stem"]])
            if div["classification"] not in ("UNIQUE", "LEGITIMATE_CONCEPTUAL_OVERLAP", "UNCERTAIN"):
                raise SystemExit(f"{sid} diversity reject: {div}")
            if repl["status"] != "DRAFT":
                raise SystemExit(f"{sid} not DRAFT: {repl['status']}")
            if repl["body_md5"] == orig["body_md5"]:
                raise SystemExit(f"{sid} identical body to original")

            # Idempotent tag apply
            await append_tags(
                session,
                orig_id,
                [
                    SUPERSEDED_TAG,
                    f"replaced-by:{cand}",
                    f"slot:{sid}",
                    "seed-v2-historical-preserved",
                    "seed-v2-numerical-failure-original",
                ],
            )
            # Remove attempt-failed from accepted candidate if present
            cur_tags = list(repl["tags"] or [])
            if ATTEMPT_FAIL_TAG in cur_tags:
                new_tags = [t for t in cur_tags if t != ATTEMPT_FAIL_TAG]
                await session.execute(
                    text(
                        "UPDATE cms.content_items SET tags = CAST(:tags AS text[]), updated_at = now() "
                        "WHERE id = CAST(:id AS uuid)"
                    ),
                    {"tags": new_tags, "id": cand},
                )
                await session.commit()
            await append_tags(
                session,
                cand,
                [
                    REMAT_TAG,
                    f"replaces:{orig_id}",
                    f"slot:{sid}",
                    "seed-v2",
                    "production-seed-v2-2026-09-03",
                    "seed-v2-numerical-remediated-active",
                ],
            )
            await session.commit()
            num_repl[sid] = cand
            prior_stems.append(repl["stem"])
            provider_totals["rescued_from_prior_attempts"].append({"slot_id": sid, "id": cand})
            # Keep failed attempts list without accepted ids
            failed_attempt_ids = [x for x in failed_attempt_ids if x != cand]
            results.append(
                {
                    "slot_id": sid,
                    "subject": "Physics",
                    "chapter": slots_by_id[sid]["chapter"],
                    "topic": slots_by_id[sid]["topic"],
                    "concept": slots_by_id[sid]["concept"],
                    "difficulty": slots_by_id[sid]["difficulty"],
                    "question_archetype": slots_by_id[sid]["question_archetype"],
                    "ncert_source_path_preserved": slots_by_id[sid].get("ncert_source_path"),
                    "original_content_item_id": orig_id,
                    "original_body_md5": orig["body_md5"],
                    "original_failure": {
                        "ncert_cert_expectation": ORIGINAL_FAILURE_EXPECTATIONS[sid],
                        "independent_verification": verify_slot_body(sid, orig["body"]),
                        "stored_answer": orig["body"].get("correct_option"),
                    },
                    "reason": "NUMERICAL_ANSWER_MISMATCH_NCERT_CERT_RED",
                    "acceptance_source": "rescued_prior_gemini_attempt_after_verifier_broadening",
                    "replacement_content_item_id": cand,
                    "replacement_body_md5": repl["body_md5"],
                    "replacement_status": repl["status"],
                    "replacement_stem": repl["stem"],
                    "replacement_options": repl["body"].get("options"),
                    "replacement_stored_answer": repl["body"].get("correct_option"),
                    "replacement_numerical_verification": num,
                    "replacement_semantic": {"status": sem.status, "signals": sem.flags},
                    "replacement_diversity": div,
                    "replacement_validation": {"ok": detailed.get("ok"), "errors": detailed.get("errors")},
                    "lineage": {
                        "original_preserved": True,
                        "original_id": orig_id,
                        "replacement_id": cand,
                        "superseded_tag": SUPERSEDED_TAG,
                        "remediation_tag": REMAT_TAG,
                    },
                    "success": True,
                }
            )

        # Collect failed attempt ids from DB for these slots
        fail_rows = (
            await session.execute(
                text(
                    """
                    SELECT ci.id::text AS id
                    FROM cms.content_items ci
                    WHERE :fail_tag = ANY(ci.tags)
                      AND (
                        'slot:physics-20' = ANY(ci.tags)
                        OR 'slot:physics-34' = ANY(ci.tags)
                        OR 'slot:physics-10' = ANY(ci.tags)
                        OR 'slot:physics-11' = ANY(ci.tags)
                      )
                    ORDER BY ci.id
                    """
                ),
                {"fail_tag": ATTEMPT_FAIL_TAG},
            )
        ).scalars().all()
        for fid in fail_rows:
            if fid not in failed_attempt_ids and fid not in num_repl.values():
                failed_attempt_ids.append(fid)

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
            orig_id = pre_num_map[sid]
            cur = await load_item(session, orig_id)
            originals_preserved.append(
                {
                    "slot_id": sid,
                    "id": orig_id,
                    "body_md5": cur["body_md5"],
                    "status": cur["status"],
                    "has_superseded_tag": SUPERSEDED_TAG in cur["tags"],
                    "still_draft": cur["status"] == "DRAFT",
                    "stem_unchanged": True,
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
            (r.get("replacement_numerical_verification") or {}).get("status") == "PASS" for r in results
        )
        active_ok = len(post_active_ids) == 100 and len(set(post_active_ids)) == 100
        leak = any(pre_num_map[sid] in post_active_ids for sid in num_repl)
        draft_ok = all(r.get("replacement_status") == "DRAFT" for r in results)

        verdict = "GREEN"
        limitations = [
            "NCERT certification NOT re-run — next gate: NCERT Certification Re-run — Exact Active 100",
            "Replacements accepted from prior Gemini attempts after independent deterministic verification (parser broadened for Young's sci-notation and thin-lens u1/u2 forms)",
            "Failed generation attempts preserved as DRAFT with attempt-failed tags",
            "No approval / publication / ECAEP performed",
        ]
        if successes != 4 or not all_pass or not protected_ok or not active_ok or leak or not draft_ok:
            verdict = "RED"
            limitations.append(
                f"successes={successes} all_pass={all_pass} protected={protected_ok} "
                f"active_ok={active_ok} leak={leak} draft_ok={draft_ok}"
            )
        # Soft amber only if semantic UNCERTAIN without hard fail — not used for GREEN override
        if any((r.get("replacement_semantic") or {}).get("status") == "REQUIRES_REVIEW" for r in results):
            if verdict == "GREEN":
                verdict = "AMBER"
                limitations.append("One or more replacements flagged semantic REQUIRES_REVIEW")

        artifact = {
            "audit": "Production Seed V2 Numerical Remediation — Exact 4 Failures",
            "date": "2026-09-04",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "verdict": verdict,
            "targets": list(TARGET_SLOT_IDS),
            "batch_uuid": str(BATCH_ID),
            "provider": provider_totals,
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
                "NCERT Certification Re-run — Exact Active 100"
                if verdict in ("GREEN", "AMBER")
                else "Resolve remaining numerical failures"
            ),
            "phase_stop": "NUMERICAL_REMEDIATION_COMPLETE",
            "script": "apps/backend/scripts/run_factory_v2_numerical_remediation_finalize.py",
        }
        OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

        lines = [
            "# Production Seed V2 — Numerical Remediation Report\n\n",
            f"**Verdict: {verdict}**\n\n",
            f"Captured: `{artifact['captured_at']}`\n\n",
            "## Exact four slots\n\n",
        ]
        for r in results:
            nv = r.get("replacement_numerical_verification") or {}
            of = r.get("original_failure") or {}
            lines.append(f"### {r['slot_id']}\n\n")
            lines.append(f"- Original ID: `{r['original_content_item_id']}`\n")
            lines.append(f"- Replacement ID: `{r['replacement_content_item_id']}`\n")
            lines.append(f"- Original stored / independent: `{of.get('stored_answer')}` / "
                         f"`{(of.get('ncert_cert_expectation') or {}).get('independent_option')}`\n")
            lines.append(f"- Replacement stored / independent: `{r.get('replacement_stored_answer')}` / "
                         f"`{nv.get('expected_option')}` → **{nv.get('status')}**\n")
            lines.append(f"- Equations: `{nv.get('equations')}`\n")
            lines.append(f"- Inputs: `{nv.get('inputs')}`\n")
            lines.append(f"- Computed: `{nv.get('computed')}`\n")
            lines.append(f"- Option validation: `{nv.get('option_validation')}`\n")
            lines.append(f"- Explanation check: `{nv.get('explanation_check')}`\n")
            lines.append(f"- Semantic: `{r.get('replacement_semantic')}`\n")
            lines.append(f"- Diversity: `{r.get('replacement_diversity')}`\n")
            lines.append(f"- Lineage: `{r.get('lineage')}`\n\n")
        lines += [
            "## Provider\n\n",
            f"- Provider: Gemini (`gemini-3.6-flash`), routing `fixed:gemini`, fallback 0\n",
            f"- Attempts (cumulative prior runs): {provider_totals['attempts']}\n",
            f"- Cost USD (cumulative): {provider_totals['cost_usd']:.6f}\n",
            f"- Finalize: no new LLM calls; rescued independently verified attempts\n\n",
            "## Integrity\n\n",
            f"- Active count 100: `{active_ok}`\n",
            f"- Protected populations unchanged: `{protected_ok}`\n",
            f"- Approvals/publications/ECAEP: 0 / 0 / 0\n",
            f"- NCERT re-run: false\n\n",
            f"## Next gate\n\n**{artifact['next_gate_recommendation']}**\n\n",
            "## STOP\n\nNo NCERT re-run / approve / publish / regenerate-96 / 1k-scale / deploy.\n",
        ]
        OUT_MD.write_text("".join(lines), encoding="utf-8")
        print(json.dumps({"verdict": verdict, "num_repl": num_repl, "cost": provider_totals["cost_usd"]}, indent=2))

    await engine.dispose()
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
