#!/usr/bin/env python3
"""Production Seed V2 — NCERT Certification RE-RUN (exact active 100).

Uses finalized numerical-remediation replacements (2026-09-04), not superseded
numerical failures. Writes ONLY ncert_evidence metadata. No generate/approve/publish.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.cms.services.factory_v2_answer_ambiguity import assess_exactly_one_answer_semantics
from app.modules.cms.services.factory_v2_numerical_verify import verify_slot_body
from app.modules.cms.services.factory_v2_visual import V2_VISUAL_SLOT_SPECS

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
STUDY = ROOT / "StudyMaterial"
PLAN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"
GEN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_GENERATION_20260903.json"
VISUAL_REMAT_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_CONTROLLED_REMATERIALIZATION_20260903.json"
DIV_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_DIVERSITY_FORENSICS_20260903.json"
AUTH_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
NUM_REMAT_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_NUMERICAL_REMEDIATION_20260904.json"
PRIOR_NCERT_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_NCERT_CERTIFICATION_20260903.json"
OUT_JSON = AUDITS / "TALOS_PRODUCTION_SEED_V2_NCERT_CERTIFICATION_RERUN_20260904.json"
OUT_MD = AUDITS / "TALOS_PRODUCTION_SEED_V2_NCERT_CERTIFICATION_RERUN_20260904.md"

DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
VISUAL_SUPERSEDED = "seed-v2-rematerialization-superseded-20260903"
NUM_SUPERSEDED = "seed-v2-numerical-remediation-superseded-20260904"
NUM_REMAT_SLOTS = ("physics-10", "physics-11", "physics-20", "physics-34")

_spec = importlib.util.spec_from_file_location(
    "v2_ncert_cert",
    Path(__file__).with_name("run_factory_v2_ncert_certification.py"),
)
ncert = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ncert)


def apply_numerical_remat_certification(verdict: dict, *, slot_id: str, body: dict, hit) -> dict:
    """Re-evaluate remat slots with independent solvers; do not inherit prior FAIL."""
    nv = verify_slot_body(slot_id, body)
    sem = assess_exactly_one_answer_semantics(body)
    limitations = list(verdict.get("limitations") or [])
    review_notes = list(verdict.get("review_notes") or [])
    failure_codes = [c for c in (verdict.get("failure_codes") or []) if c != "NUMERICAL_ANSWER_MISMATCH"]
    limitations.append(
        "Numerical replacement evaluated independently in re-run (not inherited from 2026-09-03 FAIL)"
    )
    limitations.append(
        f"Deterministic family verifier status={nv.get('status')} stored={nv.get('stored_answer')} "
        f"expected={nv.get('expected_option')}"
    )
    if sem.status == "SEMANTIC_REVIEW_REQUIRED":
        limitations.append(
            "SEMANTIC_REVIEW_REQUIRED (soft; hard_fail=False). Not claimed as full semantic uniqueness."
        )
        review_notes.append(f"semantic_signals={sem.flags}")

    verdict = dict(verdict)
    verdict["numerical_verification"] = nv.get("status")
    verdict["numerical_details"] = nv
    verdict["semantic_assessment"] = {
        "status": sem.status,
        "hard_fail": sem.hard_fail,
        "signals": sem.flags,
    }

    if nv.get("status") != "PASS":
        failure_codes.append("NUMERICAL_ANSWER_MISMATCH" if nv.get("status") == "FAIL" else "NUMERICAL_REQUIRES_REVIEW")
        verdict["failure_codes"] = failure_codes
        verdict["answer_supported"] = False if nv.get("status") == "FAIL" else None
        verdict["answer_match"] = "MISMATCH" if nv.get("status") == "FAIL" else "UNCERTAIN"
        if nv.get("status") == "FAIL" or sem.hard_fail:
            verdict["certification_decision"] = "FAIL"
            verdict["evidence_status"] = "FAIL"
            verdict["evidence_type"] = "FAIL"
            verdict["write_evidence"] = False
        else:
            verdict["certification_decision"] = "REQUIRES_HUMAN_REVIEW"
            verdict["evidence_status"] = "REQUIRES_HUMAN_REVIEW"
            verdict["evidence_type"] = "REQUIRES_HUMAN_REVIEW"
            verdict["write_evidence"] = False
        verdict["limitations"] = limitations
        verdict["review_notes"] = review_notes
        return verdict

    # PASS independently
    verdict["answer_supported"] = True
    verdict["answer_match"] = "MATCH"
    verdict["ncert_classification"] = "NCERT_DERIVED"
    limitations.append(
        "Numerical: formula/principle NCERT-supported; specific numbers independently verified in-gate"
    )

    if sem.hard_fail:
        verdict["certification_decision"] = "FAIL"
        verdict["evidence_status"] = "FAIL"
        verdict["evidence_type"] = "FAIL"
        verdict["write_evidence"] = False
        failure_codes.append("SEMANTIC_AMBIGUITY_DETECTED")
    elif not hit:
        verdict["certification_decision"] = "REQUIRES_HUMAN_REVIEW"
        verdict["evidence_status"] = "REQUIRES_HUMAN_REVIEW"
        verdict["evidence_type"] = "REQUIRES_HUMAN_REVIEW"
        verdict["write_evidence"] = False
        review_notes.append("Independent numerical PASS but NCERT source-text hit missing")
    else:
        # Soft semantic review does not block certification-with-limitation when
        # NCERT source text supports the principle and the answer is independently correct.
        verdict["certification_decision"] = "CERTIFIED_WITH_LIMITATION"
        verdict["evidence_status"] = "SOURCE_TEXT_VERIFIED"
        verdict["evidence_type"] = "SOURCE_TEXT_VERIFIED"
        verdict["write_evidence"] = True
        if sem.status == "SEMANTIC_REVIEW_REQUIRED":
            review_notes.append(
                "CERTIFIED_WITH_LIMITATION despite SEMANTIC_REVIEW_REQUIRED: numerical uniqueness "
                "established by independent calculation; lexical overlap is a documented limitation"
            )
        else:
            review_notes.append("Supported by mapped NCERT PDF source text; page-level printed number not claimed")

    verdict["failure_codes"] = failure_codes
    verdict["limitations"] = limitations
    verdict["review_notes"] = review_notes
    return verdict


def main() -> int:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    gen = json.loads(GEN_PATH.read_text(encoding="utf-8"))
    visual_remat = json.loads(VISUAL_REMAT_PATH.read_text(encoding="utf-8"))
    diversity = json.loads(DIV_PATH.read_text(encoding="utf-8"))
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    num_remat = json.loads(NUM_REMAT_PATH.read_text(encoding="utf-8"))
    prior_ncert = json.loads(PRIOR_NCERT_PATH.read_text(encoding="utf-8"))

    if diversity.get("verdict") != "GREEN":
        raise SystemExit("Diversity forensics not GREEN — refuse NCERT gate")
    if visual_remat.get("verdict") != "GREEN":
        raise SystemExit("Visual rematerialization not GREEN")
    if num_remat.get("verdict") not in ("GREEN", "AMBER"):
        raise SystemExit(f"Numerical remediation not finalized (verdict={num_remat.get('verdict')})")
    if prior_ncert.get("verdict") != "RED":
        raise SystemExit("Expected prior NCERT certification RED as historical input")

    planned = {s["slot_id"]: s for s in plan["slots"]}
    visual_repl = {r["slot_id"]: r["replacement_content_item_id"] for r in visual_remat["results"]}
    visual_orig = {r["slot_id"]: r["original_content_item_id"] for r in visual_remat["results"]}
    num_repl = dict(num_remat["active_population"]["numerical_replacements"])
    if set(num_repl) != set(NUM_REMAT_SLOTS):
        raise SystemExit(f"unexpected numerical remat slots: {num_repl}")
    num_orig = {r["slot_id"]: r["original_content_item_id"] for r in num_remat["results"]}
    hist_ids = list(visual_orig.values()) + list(num_orig.values())
    v1_ids = list(auth["exact_uuid_allowlist"])

    expected_active = dict(num_remat["active_population"]["after_ids_by_slot"])
    if len(expected_active) != 100:
        raise SystemExit(f"remediation active map != 100: {len(expected_active)}")

    active: list[dict] = []
    for g in gen["slot_coverage"]["slots"]:
        sid = g["slot_id"]
        pl = planned[sid]
        iid = num_repl.get(sid) or visual_repl.get(sid) or g["content_item_id"]
        if expected_active.get(sid) != iid:
            raise SystemExit(f"active ID mismatch {sid}: {iid} vs remat map {expected_active.get(sid)}")
        active.append(
            {
                "slot_id": sid,
                "id": iid,
                "is_visual_replacement": sid in visual_repl,
                "is_numerical_replacement": sid in num_repl,
                "is_replacement": sid in visual_repl or sid in num_repl,
                "plan": pl,
            }
        )
    if len(active) != 100:
        raise SystemExit(f"active != 100: {len(active)}")
    active_ids = [a["id"] for a in active]
    if len(set(active_ids)) != 100:
        raise SystemExit("duplicate active IDs")
    if set(hist_ids) & set(active_ids):
        raise SystemExit("superseded originals in active set")
    subj = Counter(a["plan"]["subject"] for a in active)
    if dict(subj) != {"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15}:
        raise SystemExit(f"subject distribution mismatch: {dict(subj)}")

    pdfs = sorted(p.relative_to(STUDY).as_posix() for p in STUDY.rglob("ncert*.pdf"))
    source_inventory = {
        "study_material_dir": str(STUDY),
        "primary_ncert_pdf_count": len(pdfs),
        "mapping_basis": [
            "V2 plan ncert_source_path per slot",
            "PDF chapter-title token verification",
            "PDF text search for concept/topic/stem terms",
            "No invented printed page numbers",
            "Numerical remat slots re-verified with factory_v2_numerical_verify",
        ],
        "keph_status": "SUPERSEDED_NOT_USED",
    }

    results: list[dict] = []
    writes = 0

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            before_active = ncert.items_core_fp(cur, active_ids)
            before_hist = ncert.items_core_fp(cur, hist_ids)
            before_v1 = ncert.items_core_fp(cur, v1_ids)
            before_t6d = ncert.pop_fp(cur, "physics-t6d-pilot-20260902")
            before_t6f2 = ncert.t6f2_fp(cur)
            before_legacy = ncert.pop_fp(cur, "legacy-physics-5000-import-20260902")
            if before_active["n"] != 100:
                raise SystemExit(f"integrity before n active={before_active['n']}")
            if before_hist["n"] != 8:
                raise SystemExit(f"expected 8 historical superseded (4 visual + 4 numerical), got {before_hist['n']}")

            cur.execute(
                """
                SELECT ci.id::text, ci.status, ci.tags, cv.id::text, cv.body
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = ANY(%s::uuid[])
                """,
                (active_ids,),
            )
            by_id = {}
            for iid, status, tags, vid, body in cur.fetchall():
                if isinstance(body, str):
                    body = json.loads(body)
                by_id[iid] = {"status": status, "tags": tags or [], "version_id": vid, "body": body}

            for a in active:
                iid = a["id"]
                slot = a["plan"]
                db = by_id[iid]
                tags = db["tags"] or []
                if VISUAL_SUPERSEDED in tags or NUM_SUPERSEDED in tags:
                    raise SystemExit(f"active has superseded tag: {iid}")
                if db["status"] != "DRAFT":
                    raise SystemExit(f"non-DRAFT active item: {iid} {db['status']}")
                body = db["body"]
                core_before = ncert.content_core_fp(body)
                rel = slot["ncert_source_path"].replace("\\", "/")
                pdf_path = ROOT / rel
                title_ok, title_detail = (
                    ncert.chapter_title_ok(slot["chapter"], pdf_path) if pdf_path.is_file() else (False, "MISSING")
                )
                terms = ncert.search_terms(slot, body.get("stem") or "")
                hit = ncert.find_ncert_hit(pdf_path, terms) if pdf_path.is_file() else None
                verdict = ncert.classify_item(
                    slot=slot,
                    body=body,
                    pdf_path=pdf_path,
                    title_ok=title_ok,
                    title_detail=title_detail,
                    hit=hit,
                )
                if a["is_numerical_replacement"]:
                    verdict = apply_numerical_remat_certification(
                        verdict, slot_id=slot["slot_id"], body=body, hit=hit
                    )

                class_level = ncert.class_level_from_plan(str(slot.get("class") or ""), rel)
                evidence_after = body.get("ncert_evidence")
                if verdict["write_evidence"] and hit:
                    evidence_after = ncert.build_evidence(slot, hit, class_level)
                    cur.execute(
                        """
                        UPDATE cms.content_versions
                        SET body = jsonb_set(
                          COALESCE(body, '{}'::jsonb),
                          '{ncert_evidence}',
                          %s::jsonb,
                          true
                        )
                        WHERE id = %s::uuid
                        """,
                        (json.dumps(evidence_after), db["version_id"]),
                    )
                    writes += 1
                elif not verdict["write_evidence"]:
                    cur.execute(
                        """
                        UPDATE cms.content_versions
                        SET body = jsonb_set(
                          COALESCE(body, '{}'::jsonb),
                          '{ncert_evidence}',
                          'null'::jsonb,
                          true
                        )
                        WHERE id = %s::uuid
                        """,
                        (db["version_id"],),
                    )
                    evidence_after = None

                results.append(
                    {
                        "slot_id": slot["slot_id"],
                        "item_id": iid,
                        "is_replacement": a["is_replacement"],
                        "is_visual_replacement": a["is_visual_replacement"],
                        "is_numerical_replacement": a["is_numerical_replacement"],
                        "subject": slot["subject"],
                        "class": slot.get("class"),
                        "chapter": slot["chapter"],
                        "topic": slot["topic"],
                        "concept": slot["concept"],
                        "question_archetype": slot.get("question_archetype"),
                        "visual_required": bool(slot.get("visual_required")) or slot["slot_id"] in V2_VISUAL_SLOT_SPECS,
                        "independent_verification_required": bool(slot.get("independent_verification_required")),
                        "source_file": rel,
                        "source_document": slot.get("ncert_source_document"),
                        "source_section": None,
                        "source_page": None,
                        "pdf_page_index": (hit or {}).get("pdf_page_index"),
                        "page_verified": False,
                        "chapter_title_ok": title_ok,
                        "chapter_title_detail": title_detail,
                        "search_terms": terms,
                        "search_hits_summary": {
                            "keywords": (hit or {}).get("matched_terms"),
                            "hit_pages": [(hit or {}).get("pdf_page_index")] if hit else [],
                            "score": (hit or {}).get("score"),
                            "excerpt": (hit or {}).get("excerpt"),
                        }
                        if hit
                        else None,
                        "ncert_classification": verdict["ncert_classification"],
                        "evidence_type": verdict["evidence_type"],
                        "evidence_status": verdict["evidence_status"],
                        "stem_supported": verdict["stem_supported"],
                        "answer_supported": verdict["answer_supported"],
                        "answer_match": verdict.get("answer_match"),
                        "explanation_supported": verdict["explanation_supported"],
                        "outside_mapped_source": verdict["outside_mapped_source"],
                        "numerical_verification": verdict["numerical_verification"],
                        "numerical_details": verdict.get("numerical_details"),
                        "semantic_assessment": verdict.get("semantic_assessment"),
                        "stored_answer": (body.get("correct_option") or "").upper(),
                        "certification_decision": verdict["certification_decision"],
                        "failure_codes": verdict["failure_codes"],
                        "review_notes": verdict["review_notes"],
                        "limitations": verdict["limitations"],
                        "ncert_evidence_written": verdict["write_evidence"],
                        "ncert_evidence_after": evidence_after if verdict["write_evidence"] else None,
                        "content_core_fp_before": core_before,
                        "visual_is_ncert_evidence": False,
                        "visual_note": (
                            "Factory SVG/spec is original deterministic rendering of NCERT-supported concept; "
                            "not NCERT page evidence"
                            if (bool(slot.get("visual_required")) or slot["slot_id"] in V2_VISUAL_SLOT_SPECS)
                            else None
                        ),
                    }
                )

            conn.commit()

            after_active = ncert.items_core_fp(cur, active_ids)
            after_hist = ncert.items_core_fp(cur, hist_ids)
            after_v1 = ncert.items_core_fp(cur, v1_ids)
            after_t6d = ncert.pop_fp(cur, "physics-t6d-pilot-20260902")
            after_t6f2 = ncert.t6f2_fp(cur)
            after_legacy = ncert.pop_fp(cur, "legacy-physics-5000-import-20260902")

            cur.execute(
                """
                SELECT ci.id::text, cv.body
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = ANY(%s::uuid[])
                """,
                (active_ids,),
            )
            after_bodies = {}
            for iid, body in cur.fetchall():
                if isinstance(body, str):
                    body = json.loads(body)
                after_bodies[iid] = body

            cur.execute(
                "SELECT COUNT(*) FROM cms.content_items WHERE content_type='QUESTION' AND status='APPROVED' "
                "AND ('production-seed-v2-2026-09-03' = ANY(tags) OR 'seed-v2' = ANY(tags) "
                "OR 'seed-v2-numerical-remediated-active' = ANY(tags))"
            )
            approvals_n = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM cms.content_items WHERE content_type='QUESTION' AND status='PUBLISHED' "
                "AND ('production-seed-v2-2026-09-03' = ANY(tags) OR 'seed-v2' = ANY(tags) "
                "OR 'seed-v2-numerical-remediated-active' = ANY(tags))"
            )
            v2_pub = cur.fetchone()[0]

    core_mutations = []
    for r in results:
        iid = r["item_id"]
        body = after_bodies[iid]
        core_after = ncert.content_core_fp(body)
        r["content_core_fp_after"] = core_after
        if core_after != r["content_core_fp_before"]:
            core_mutations.append(iid)
        if r["ncert_evidence_written"]:
            ev = body.get("ncert_evidence") or {}
            if ev.get("verification_level") != "SOURCE_TEXT_VERIFIED":
                core_mutations.append(f"ncert_missing:{iid}")
            if ev.get("page_number") is not None:
                core_mutations.append(f"fabricated_page:{iid}")
            if ev.get("section"):
                core_mutations.append(f"fabricated_section:{iid}")

    if core_mutations:
        raise SystemExit(f"RED — content core mutation or evidence write failure: {core_mutations[:10]}")

    decision_counts = dict(Counter(r["certification_decision"] for r in results))
    evidence_type_counts = dict(Counter(r["evidence_type"] for r in results))
    subject_counts = dict(Counter(r["subject"] for r in results))
    page_verified_n = sum(1 for r in results if r["page_verified"])
    failures = [r for r in results if r["certification_decision"] == "FAIL"]
    reviews = [r for r in results if r["certification_decision"] == "REQUIRES_HUMAN_REVIEW"]
    visual_results = [r for r in results if r["visual_required"]]
    numerical_results = [
        r for r in results if r["question_archetype"] == "numerical_calculation" or r["independent_verification_required"]
    ]
    num_repl_results = [r for r in results if r["is_numerical_replacement"]]

    integrity_ok = (
        before_active["core_fp"] == after_active["core_fp"]
        and before_hist["core_fp"] == after_hist["core_fp"]
        and before_v1["core_fp"] == after_v1["core_fp"]
        and before_t6d["content_fp"] == after_t6d["content_fp"]
        and before_t6f2["content_fp"] == after_t6f2["content_fp"]
        and before_legacy["content_fp"] == after_legacy["content_fp"]
        and after_active["n"] == 100
        and after_hist["n"] == 8
        and not core_mutations
        and approvals_n == 0
        and v2_pub == 0
    )

    if not integrity_ok or failures:
        verdict = "RED"
    elif reviews:
        verdict = "AMBER"
    elif decision_counts.get("CERTIFIED", 0) + decision_counts.get("CERTIFIED_WITH_LIMITATION", 0) == 100:
        verdict = "GREEN"
    else:
        verdict = "AMBER"

    limitations = [
        "INDEPENDENCE LIMITATION: agent StudyMaterial PDF text search + limited numerical patterns — not human NCERT certification",
        "page_verified=false for all items; PDF page index ≠ printed NCERT page",
        "No SECTION_VERIFIED claims (section titles not invented)",
        "No PAGE_VERIFIED claims",
        "Generated visuals are not NCERT evidence",
        "SEMANTIC_DEDUPE_NOT_AVAILABLE (diversity) is not converted into an NCERT claim",
        "physics-10/physics-11: SEMANTIC_REVIEW_REQUIRED is a documented limitation, not uniqueness certification",
        "Numerical remat evaluated independently; 2026-09-03 FAIL status was not inherited",
        "V2 cohort evidence only — does not certify the global question bank",
    ]

    artifact = {
        "audit": "Production Seed V2 NCERT Certification RE-RUN — Exact Active 100",
        "date": "2026-09-04",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "mode": "NCERT_EVIDENCE_METADATA_WRITE_ONLY_ZERO_APPROVAL_ZERO_PUBLICATION",
        "supersedes": "docs/audits/TALOS_PRODUCTION_SEED_V2_NCERT_CERTIFICATION_20260903.json",
        "numerical_remediation_artifact": str(NUM_REMAT_PATH.as_posix()),
        "numerical_remediation_verdict": num_remat.get("verdict"),
        "verdict": verdict,
        "independence": {
            "limitation": "INDEPENDENCE LIMITATION",
            "note": "Coding agent certification against StudyMaterial NCERT PDFs. Not independent human NCERT certification.",
        },
        "active_population": {
            "n": 100,
            "subject_counts": subject_counts,
            "item_ids": active_ids,
            "ids_by_slot": {a["slot_id"]: a["id"] for a in active},
            "visual_replacements": visual_repl,
            "numerical_replacements": num_repl,
            "historical_excluded": hist_ids,
        },
        "source_inventory": source_inventory,
        "decision_counts": decision_counts,
        "evidence_type_counts": evidence_type_counts,
        "page_verification": {
            "page_verified_true": page_verified_n,
            "page_verified_false": 100 - page_verified_n,
            "policy": "Never claim PAGE_VERIFIED without verified printed page_number",
        },
        "failures": [
            {"slot_id": r["slot_id"], "item_id": r["item_id"], "codes": r["failure_codes"], "notes": r["review_notes"]}
            for r in failures
        ],
        "human_review_requirements": [
            {"slot_id": r["slot_id"], "item_id": r["item_id"], "codes": r["failure_codes"], "notes": r["review_notes"]}
            for r in reviews
        ],
        "visual_questions": [
            {
                "slot_id": r["slot_id"],
                "item_id": r["item_id"],
                "decision": r["certification_decision"],
                "ncert_classification": r["ncert_classification"],
                "visual_is_ncert_evidence": False,
                "note": r["visual_note"],
            }
            for r in visual_results
        ],
        "numerical_questions": [
            {
                "slot_id": r["slot_id"],
                "item_id": r["item_id"],
                "decision": r["certification_decision"],
                "numerical_verification": r["numerical_verification"],
                "answer_match": r["answer_match"],
                "is_numerical_replacement": r["is_numerical_replacement"],
            }
            for r in numerical_results
        ],
        "numerical_replacement_results": [
            {
                "slot_id": r["slot_id"],
                "item_id": r["item_id"],
                "decision": r["certification_decision"],
                "numerical_verification": r["numerical_verification"],
                "stored_answer": r["stored_answer"],
                "answer_match": r["answer_match"],
                "semantic_assessment": r.get("semantic_assessment"),
                "source_file": r["source_file"],
                "ncert_evidence_written": r["ncert_evidence_written"],
            }
            for r in num_repl_results
        ],
        "ncert_evidence_writes": writes,
        "items": results,
        "integrity_before": {
            "active_core_fp": before_active["core_fp"],
            "active_n": before_active["n"],
            "active_status": before_active["status_counts"],
            "historical_core_fp": before_hist["core_fp"],
            "historical_n": before_hist["n"],
            "v1_core_fp": before_v1["core_fp"],
            "t6d_fp": before_t6d["content_fp"],
            "t6f2_fp": before_t6f2["content_fp"],
            "legacy_fp": before_legacy["content_fp"],
        },
        "integrity_after": {
            "active_core_fp": after_active["core_fp"],
            "active_n": after_active["n"],
            "active_status": after_active["status_counts"],
            "historical_core_fp": after_hist["core_fp"],
            "historical_n": after_hist["n"],
            "v1_core_fp": after_v1["core_fp"],
            "t6d_fp": after_t6d["content_fp"],
            "t6f2_fp": after_t6f2["content_fp"],
            "legacy_fp": after_legacy["content_fp"],
        },
        "integrity_checks": {
            "active_core_unchanged": before_active["core_fp"] == after_active["core_fp"],
            "historical_unchanged": before_hist["core_fp"] == after_hist["core_fp"],
            "protected_unchanged": integrity_ok,
            "approvals": approvals_n,
            "v2_publications": v2_pub,
            "ecaep": 0,
            "stem_option_answer_explanation_mutations": 0,
            "ncert_evidence_metadata_writes_only": True,
        },
        "tests": {"note": "Filled after pytest", "thresholds_weakened": False},
        "limitations": limitations,
        "publication_authorization_ready": verdict == "GREEN",
        "next_gate_recommendation": (
            "Separate Publication Authorization — Exact Active 100 (still no auto-approve/publish from this gate)"
            if verdict == "GREEN"
            else "Resolve REQUIRES_HUMAN_REVIEW / FAIL / AMBER limitations before publication authorization"
        ),
        "phase_stop": "NCERT_CERTIFICATION_RERUN_COMPLETE",
        "counts": {"approvals": 0, "publications": 0, "ecaep": 0, "generation": 0},
        "script": "apps/backend/scripts/run_factory_v2_ncert_certification_rerun.py",
    }
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    md = [
        "# Production Seed V2 — NCERT Certification Re-run (Exact Active 100)",
        "",
        f"**Verdict: {verdict}**  ",
        f"**Captured:** {artifact['captured_at']}  ",
        "**Mode:** NCERT evidence metadata write only — no approve / publish / ECAEP / generation / content mutation",
        "",
        "Supersedes `TALOS_PRODUCTION_SEED_V2_NCERT_CERTIFICATION_20260903.json` (prior RED on four numerical failures).",
        "Active IDs follow finalized numerical remediation AMBER artifact.",
        "",
        "## 1. Population",
        f"Active **100** (Physics {subject_counts.get('Physics')} / Chemistry {subject_counts.get('Chemistry')} / "
        f"Botany {subject_counts.get('Botany')} / Zoology {subject_counts.get('Zoology')})  ",
        f"Historical superseded excluded: **{len(hist_ids)}** (4 visual + 4 numerical)",
        "",
        "## 2. Decision summary",
        "| State | Count |",
        "|-------|------:|",
        f"| CERTIFIED | {decision_counts.get('CERTIFIED', 0)} |",
        f"| CERTIFIED_WITH_LIMITATION | {decision_counts.get('CERTIFIED_WITH_LIMITATION', 0)} |",
        f"| REQUIRES_HUMAN_REVIEW | {decision_counts.get('REQUIRES_HUMAN_REVIEW', 0)} |",
        f"| FAIL | {decision_counts.get('FAIL', 0)} |",
        "",
        "## 3. Four numerical replacements",
    ]
    for r in num_repl_results:
        md.append(
            f"- **{r['slot_id']}** `{r['item_id']}`: {r['certification_decision']} · "
            f"numerical={r['numerical_verification']} stored={r['stored_answer']} "
            f"semantic={(r.get('semantic_assessment') or {}).get('status')}"
        )
    md += [
        "",
        "## 4. Visual questions (SVG ≠ NCERT evidence)",
    ]
    for r in visual_results:
        md.append(
            f"- `{r['slot_id']}` `{r['item_id']}` → {r['certification_decision']} · "
            f"{r['ncert_classification']} · visual **not** NCERT evidence"
        )
    md += [
        "",
        "## 5. Page verification",
        f"page_verified=true: **{page_verified_n}** · false: **{100 - page_verified_n}**",
        "",
        "## 6. Human review / failures",
        f"FAIL: {len(failures)} · REQUIRES_HUMAN_REVIEW: {len(reviews)}",
        "",
        "## 7. Integrity",
        f"Active core unchanged: **{before_active['core_fp'] == after_active['core_fp']}**  ",
        f"Protected unchanged: **{integrity_ok}**  ",
        f"Approvals/V2 publications/ECAEP: **{approvals_n} / {v2_pub} / 0**",
        "",
        "## 8. Publication authorization readiness",
        f"**{artifact['publication_authorization_ready']}**",
        "",
        f"**Next:** {artifact['next_gate_recommendation']}",
        "",
        "---",
        "**STOP** — NCERT certification re-run complete. Do not approve / publish / generate / start 1,000-scale / deploy.",
        "",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": verdict,
                "decision_counts": decision_counts,
                "num_repl": {r["slot_id"]: r["certification_decision"] for r in num_repl_results},
                "writes": writes,
                "integrity_ok": integrity_ok,
            },
            indent=2,
        )
    )
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
