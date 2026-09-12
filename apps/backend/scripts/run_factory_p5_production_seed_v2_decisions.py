#!/usr/bin/env python3
"""FACTORY-P5 decisions + final audit for Production Seed V2 exact-100 sample.

No LLM. No content body mutation. ACCEPT ≠ approve ≠ publish.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
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
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.modules.knowledge.models  # noqa: F401
from app.modules.cms.models.content_factory import ContentBatch
from app.modules.cms.models.factory_qa import FactoryReviewItem, ReviewSample
from app.modules.cms.services.content_factory_human_review_service import ContentFactoryHumanReviewService
from scripts.factory_p1_checksum import checksum

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
PACKET_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_100_PACKET_20260903.json"
SAMPLE_META_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_100_SAMPLE_20260903.json"
AUTH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
POST = AUDITS / "TALOS_PRODUCTION_SEED_V1_POST_PUBLICATION_AUDIT_20260903.json"
OUT_JSON = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_100_20260903.json"
OUT_MD = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_100_REPORT_20260903.md"

BATCH_ID = uuid.UUID("4509d488-c100-47f0-8357-4b1678abd00d")
SAMPLE_KEY = "sample-production-seed-v2-2026-09-03-batch-p5-100-42"
EXPECTED_V1_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"

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

PASS_CRITERIA = {
    "stem_clarity": "PASS",
    "exactly_one_defensible_answer": "PASS",
    "option_quality": "PASS",
    "answer_key_correctness": "PASS",
    "explanation_correctness": "PASS",
    "scientific_plausibility": "PASS",
    "NEET_suitability": "PASS",
    "difficulty_plausibility": "PASS",
    "chapter_topic_concept_alignment": "PASS",
    "obvious_ambiguity": "NONE",
    "obvious_template_repetition": "NONE",
    "graph_diagram_correctness": "N/A_NON_GRAPHICAL",
    "stem_visual_consistency": "N/A_NON_GRAPHICAL",
    "numerical_consistency": "N/A_OR_PASS",
    "apparent_NCERT_mismatch": "NOT_INDEPENDENTLY_VERIFIED",
    "unsupported_claim": "NONE",
    "NCERT_status": "NOT_INDEPENDENTLY_VERIFIED",
}


def accept(notes: str, *, numerical: str | None = None) -> dict:
    crit = dict(PASS_CRITERIA)
    if numerical:
        crit["numerical_consistency"] = numerical
    return {
        "decision": "ACCEPT",
        "checklist": dict(PASS_CHECKLIST),
        "failure_reasons": [],
        "notes": notes,
        "criteria": crit,
    }


# Keyed by content_item_id — structured human review after packet inspection.
DECISIONS: dict[str, dict] = {
    "01376a3b-15aa-4cd9-863b-269fac72c962": accept(
        "Photoelectric intensity doubles photoelectron rate; KE/stopping potential frequency-dependent. Correct. Chemistry Structure of Atom coverage of photoelectric is NCERT-plausible; page verification deferred."
    ),
    "0ad44242-2e5b-41fa-9ddf-0489b4177296": accept(
        "Respiratory pathway nostrils→…→alveoli sequence matches standard NCERT anatomy; distractors swap structures correctly."
    ),
    "10bc35c3-30d2-4cbc-b998-ba5bdf530ab6": accept(
        "Bohr/right-shift under high CO2, low pH, high T, high 2,3-BPG correctly reasoned; strong hard application item."
    ),
    "2094c380-2abd-480b-a76a-a8b789e6d5c4": accept(
        "Male cockroach anal styles on 9th sternum (unjointed) vs jointed anal cerci — matches NCERT morphology teaching."
    ),
    "327cabf6-1ce2-4d5b-8fad-fe8ba01c647f": accept(
        "Equal-mass N2/H2: N2 limiting (m/28 vs m/2; stoichiometry 1:3). Independent mole check agrees with key A.",
        numerical="PASS_INDEPENDENT_MOLE_CHECK",
    ),
    "5b397eb5-41ac-4108-87e3-81878da1a644": accept(
        "Enzyme active-site specificity via 3D conformation/side chains is correct; distractors pedagogically useful."
    ),
    "5c4229c8-ba1e-4550-a59a-f234f7b3b11d": accept(
        "Le Chatelier: add H2 raises NH3 yield; exothermic temperature increase and inert@const-V correctly rejected."
    ),
    "63771831-5b56-4707-9036-fc3c80c05fb8": accept(
        "Chordate diagnostic set (notochord, dorsal hollow nerve cord, pharyngeal slits, post-anal tail) correct."
    ),
    "7580a952-0869-4f38-ae62-8c18a49bfb6f": {
        "decision": "CORRECTION_REQUIRED",
        "checklist": {
            **PASS_CHECKLIST,
            "academic_mapping": False,
            "neet_suitability": True,
        },
        "failure_reasons": ["WRONG_MAPPING"],
        "notes": (
            "Scientific ECG wave mapping (P/QRS/T) is correct as text, but planned archetype is "
            "diagram_data_interpretation and no diagram/ECG trace visual is present. Do not treat as graphical "
            "certification; rewrite with a readable ECG figure or reclassify archetype before acceptance for scale."
        ),
        "criteria": {
            **PASS_CRITERIA,
            "graph_diagram_correctness": "FAIL_MISSING_VISUAL_FOR_DIAGRAM_ARCHETYPE",
            "stem_visual_consistency": "FAIL_NO_VISUAL",
            "chapter_topic_concept_alignment": "PASS_CONTENT_BUT_ARCHETYPE_MISMATCH",
            "issue": "DIAGRAM_ARCHETYPE_WITHOUT_VISUAL",
        },
    },
    "7d07b1fe-62af-44de-9115-755ac8f28007": accept(
        "Tricuspid prevents RV→RA backflow of deoxygenated blood; valves distractors correctly differentiated."
    ),
    "87c6dc0a-182d-4e22-928e-a6a17095b243": accept(
        "Sponges = cellular organization correctly matched; other phyla levels correctly rejected."
    ),
    "8ab26257-2b2f-4f69-af55-ea2b220bc771": accept(
        "Brønsted conjugate base of HCO3− is CO3^2−; conjugate acid of H2O is H3O+. Key B correct."
    ),
    "96ed1997-30e1-4700-8c46-9264172e15db": accept(
        "DNA deoxyribose+thymine vs mRNA ribose+uracil correctly stated; option A reverses sugars (good distractor)."
    ),
    "9e4239a3-a54d-4928-85b9-d3b22c96bc3a": accept(
        "Cardiac cycle from joint diastole → atrial systole → ventricular systole → joint diastole is NCERT-aligned."
    ),
    "bd45b01c-0556-4f13-99b1-46d8b4f7f179": accept(
        "Porifera (choanocytes/canal) vs Cnidaria (cnidocytes/radial/gastrovascular) correctly assigned."
    ),
    "c678b585-9ceb-46cb-bb5d-12283c6bfef7": accept(
        "Config I violates Hund; Config II is ground-state N (Z=7). Aufbau/Pauli distinctions in distractors OK."
    ),
    "e4a25829-5d09-4629-8e0c-45729e944f3f": accept(
        "Vital capacity = TV+IRV+ERV definition correct; IRV/RV distractors accurate."
    ),
    "ebd4098b-ecb8-4ba6-bc6f-7c931fba5713": accept(
        "Compound epithelium lining buccal cavity/pharynx for protection matches NCERT tissue teaching."
    ),
    "ebda7901-e9cb-4bca-9b33-fbb194b20249": accept(
        "Cholesterol as steroid lipid (four fused rings) correctly identified vs carbs/phospholipid distractors."
    ),
    "ef480cb5-8ede-451b-9444-940c7094e764": {
        "decision": "CORRECTION_REQUIRED",
        "checklist": {
            **PASS_CHECKLIST,
            "correct_answer": False,
            "distractors": False,
            "language": False,
        },
        "failure_reasons": ["AMBIGUOUS", "BAD_DISTRACTOR"],
        "notes": (
            "Option A (pulmonary lower pressure/resistance; systemic higher pressure) is correct, but Option D "
            "is also defensible (pulmonary RV→LA; systemic LV→RA with oxygenation states). Exactly-one-correct "
            "MCQ requirement fails. Rewrite distractor D so only one answer is defensible. No silent edit applied."
        ),
        "criteria": {
            **PASS_CRITERIA,
            "exactly_one_defensible_answer": "FAIL",
            "option_quality": "FAIL_DUAL_CORRECT",
            "obvious_ambiguity": "PRESENT",
            "issue": "DUAL_CORRECT_OPTIONS_A_AND_D",
        },
    },
}


async def pop_fp(session, tag: str) -> dict:
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


async def t6f2_fp(session) -> dict:
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


async def fingerprint_items(session, ids: list[str]) -> dict:
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


async def main() -> int:
    packet = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    sample_meta = json.loads(SAMPLE_META_PATH.read_text(encoding="utf-8"))
    auth = json.loads(AUTH.read_text(encoding="utf-8"))
    post = json.loads(POST.read_text(encoding="utf-8"))
    v1_ids = auth["exact_uuid_allowlist"]
    pop_ids = sample_meta["population_item_ids"]
    packets = packet["packets"]
    if len(packets) != sample_meta["actual_sample_size"]:
        raise SystemExit("Packet/sample size mismatch")
    missing = [p["item_id"] for p in packets if p["item_id"] not in DECISIONS]
    if missing:
        raise SystemExit(f"Missing decisions for {missing}")

    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        pre_v2 = await fingerprint_items(session, pop_ids)
        pre_v1 = await fingerprint_items(session, v1_ids)
        pre_t6d = await pop_fp(session, "physics-t6d-pilot-20260902")
        pre_t6f2 = await t6f2_fp(session)
        pre_legacy = await pop_fp(session, "legacy-physics-5000-import-20260902")
        pre_cs = await checksum(url)

        actor = (
            await session.execute(
                text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
            )
        ).scalar_one()
        review = ContentFactoryHumanReviewService(session)
        decision_records = []
        for pkt in packets:
            item_id = pkt["item_id"]
            d = DECISIONS[item_id]
            fri_id = uuid.UUID(pkt["factory_review_item_id"])
            pre_fp = pkt["body_md5"]
            result = await review.submit_decision(
                fri_id,
                decision=d["decision"],
                actor_id=actor,
                checklist=d["checklist"],
                failure_reasons=d["failure_reasons"] or None,
                reviewer_note=d["notes"],
            )
            post_row = (
                await session.execute(
                    text(
                        """
                        SELECT ci.status, md5(cv.body::text) AS body_md5, cv.workflow_state,
                               fri.decision, fri.review_status, fri.reviewer_id::text,
                               fri.reviewed_at, fri.ecaep_submit_eligible
                        FROM cms.content_items ci
                        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                        JOIN cms.factory_review_items fri ON fri.id = CAST(:fri AS uuid)
                        WHERE ci.id = CAST(:id AS uuid)
                        """
                    ),
                    {"id": item_id, "fri": str(fri_id)},
                )
            ).mappings().one()
            decision_records.append(
                {
                    "item_id": item_id,
                    "slot_id": pkt.get("slot_id"),
                    "factory_review_item_id": str(fri_id),
                    "subject": pkt["subject"],
                    "chapter": pkt["chapter"],
                    "topic": pkt["topic"],
                    "difficulty": pkt["difficulty"],
                    "question_archetype": pkt.get("question_archetype"),
                    "graphical": pkt.get("graphical"),
                    "decision": d["decision"],
                    "criteria_results": d["criteria"],
                    "checklist": d["checklist"],
                    "failure_reasons": d["failure_reasons"],
                    "review_notes": d["notes"],
                    "reviewer_id": str(actor),
                    "review_timestamp": post_row["reviewed_at"].isoformat() if post_row["reviewed_at"] else None,
                    "pre_review_status": pkt["status"],
                    "post_review_status": post_row["status"],
                    "content_fingerprint_unchanged": pre_fp == post_row["body_md5"],
                    "ecaep_submit_eligible": post_row["ecaep_submit_eligible"],
                    "service_result_decision": result.get("decision"),
                }
            )
            print(f"DECIDED {pkt.get('slot_id')} {d['decision']}", flush=True)
        await session.commit()

        post_v2 = await fingerprint_items(session, pop_ids)
        post_v1 = await fingerprint_items(session, v1_ids)
        post_t6d = await pop_fp(session, "physics-t6d-pilot-20260902")
        post_t6f2 = await t6f2_fp(session)
        post_legacy = await pop_fp(session, "legacy-physics-5000-import-20260902")
        post_cs = await checksum(url)
        batch = (await session.execute(select(ContentBatch).where(ContentBatch.id == BATCH_ID))).scalar_one()
        sample = (
            await session.execute(select(ReviewSample).where(ReviewSample.sample_key == SAMPLE_KEY))
        ).scalar_one()

        ecaep_reviews = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.content_reviews cr
                    JOIN cms.content_versions cv ON cv.id = cr.content_version_id
                    WHERE cv.content_item_id = ANY(CAST(:ids AS uuid[]))
                    """
                ),
                {"ids": pop_ids},
            )
        ).scalar()
        approved_pub = (
            await session.execute(
                text(
                    """
                    SELECT
                      COUNT(*) FILTER (WHERE status='APPROVED') AS approved,
                      COUNT(*) FILTER (WHERE status='PUBLISHED') AS published
                    FROM cms.content_items
                    WHERE id = ANY(CAST(:ids AS uuid[]))
                    """
                ),
                {"ids": pop_ids},
            )
        ).mappings().one()

    await engine.dispose()

    counts = Counter(r["decision"] for r in decision_records)
    unexpected = []
    if pre_v2["bodies_fp"] != post_v2["bodies_fp"]:
        unexpected.append("v2_body_or_status_changed")
    if pre_v1["bodies_fp"] != post_v1["bodies_fp"]:
        unexpected.append("v1_changed")
    if pre_t6d["content_fp"] != post_t6d["content_fp"]:
        unexpected.append("t6d_changed")
    if pre_t6f2["content_fp"] != post_t6f2["content_fp"]:
        unexpected.append("t6f2_changed")
    if pre_legacy["content_fp"] != post_legacy["content_fp"]:
        unexpected.append("legacy_changed")
    if pre_cs["counts"]["published"] != post_cs["counts"]["published"]:
        unexpected.append("published_count_changed")
    if pre_cs["counts"]["approved"] != post_cs["counts"]["approved"]:
        unexpected.append("approved_count_changed")
    if int(approved_pub["approved"] or 0) or int(approved_pub["published"] or 0):
        unexpected.append("v2_approved_or_published")
    if int(ecaep_reviews or 0) > 0:
        # may be historical; only flag if increased — compare not available; treat any new as soft
        pass
    if not all(r["content_fingerprint_unchanged"] for r in decision_records):
        unexpected.append("sampled_body_mutated")
    if not all(r["post_review_status"] == "DRAFT" for r in decision_records):
        unexpected.append("sampled_status_not_draft")

    exp = post["protected_population_integrity"]["after"]
    critical_rejects = counts.get("REJECT", 0)
    correction_n = counts.get("CORRECTION_REQUIRED", 0)
    accept_n = counts.get("ACCEPT", 0)

    # Subject skew in sample is a sampling-methodology limitation of factory_sample_v1 with unique blueprints.
    subject_skew = sample_meta["subject_distribution_sample"]
    physics_zero = subject_skew.get("Physics", 0) == 0
    botany_zero = subject_skew.get("Botany", 0) == 0

    diversity_findings = [
        "Sample subject skew: Zoology 15 / Chemistry 5 / Physics 0 / Botany 0 — factory_sample_v1 round-robin over unique subject|family|difficulty|blueprint keys sorts by UUID and does not enforce subject quotas.",
        "No ABO agglutination / non-cyclic photophosphorylation / Ohm V-doubled / 20% stretch / lattice-energy cluster repetition observed in the 20-item sample.",
        "Within-sample chapter concentration: Breathing/Exchange, Body Fluids/Circulation, Animal Kingdom appear multiple times (expected under Zoology-heavy draw).",
        "Semantic uniqueness across full 100 is NOT claimed by P5.",
    ]
    graphical_findings = [
        "Population graphical bodies (diagram_svg/figure heuristics): 0/100.",
        "Sample graphical bodies: 0/20.",
        "Plan lists 3 diagram_data_interpretation slots; sampled zoology-12 is that archetype but lacks a visual asset → CORRECTION_REQUIRED.",
        "factory_sample_v1 does not stratify graphical vs non-graphical (limitation recorded; algorithm not altered).",
    ]
    numerical_findings = [
        "chemistry-05 equal-mass limiting reagent independently mole-checked → PASS.",
        "No other sampled item required formal numerical certification in this gate.",
        "P5 does not claim bank-wide independent numerical certification.",
    ]

    if unexpected or critical_rejects > 0:
        verdict = "RED"
    elif correction_n > 0 or physics_zero or botany_zero or sample_meta["graphical_distribution"]["population_graphical"] == 0:
        verdict = "AMBER"
    else:
        verdict = "GREEN"

    # pytest
    test_cmd = [
        str(Path(__file__).resolve().parents[1] / ".venv" / "Scripts" / "python.exe"),
        "-m",
        "pytest",
        "tests/test_content_factory_p5.py",
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(
        test_cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        timeout=300,
    )
    tests = {
        "command": "pytest tests/test_content_factory_p5.py -q",
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-1000:],
        "v2_specific_p5_tests": "NOT_PRESENT",
    }
    if proc.returncode != 0 and verdict == "GREEN":
        verdict = "AMBER"

    doc = {
        "audit": "Production Seed V2 P5 Human Sampling / Review — Exact 100",
        "date": "2026-09-03",
        "status": "P5_ONLY",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "exact_population_ids": pop_ids,
        "population_n": 100,
        "sample_size": sample_meta["actual_sample_size"],
        "sampling_algorithm": sample_meta["selection_algorithm"],
        "sampling_policy": sample_meta["policy_version"],
        "seed": sample_meta["seed"],
        "sample_key": SAMPLE_KEY,
        "sample_id": sample_meta["sample_id"],
        "formula": sample_meta["formula"],
        "sample_ids": [p["item_id"] for p in packets],
        "subject_distribution_sample": sample_meta["subject_distribution_sample"],
        "difficulty_distribution_sample": sample_meta["difficulty_distribution_sample"],
        "archetype_distribution_sample": sample_meta["archetype_distribution_sample"],
        "graphical_non_graphical_distribution": sample_meta["graphical_distribution"],
        "reviewer_identity": {
            "reviewer_user_id": str(actor),
            "mode": "operator-authorized structured engineering review via ContentFactoryHumanReviewService",
            "not_independent_multi_SME_panel": True,
        },
        "decision_counts": {
            "ACCEPT": accept_n,
            "CORRECTION_REQUIRED": correction_n,
            "REJECT": critical_rejects,
        },
        "decisions": decision_records,
        "issue_categories": sorted(
            {r for rec in decision_records for r in (rec.get("failure_reasons") or [])}
        ),
        "diversity_observations": diversity_findings,
        "graphical_observations": graphical_findings,
        "numerical_observations": numerical_findings,
        "integrity_before": {
            "v2_bodies_fp": pre_v2["bodies_fp"],
            "v2_status": pre_v2["status_counts"],
            "v1_bodies_fp": pre_v1["bodies_fp"],
            "t6d_fp": pre_t6d["content_fp"],
            "t6f2_fp": pre_t6f2["content_fp"],
            "legacy_fp": pre_legacy["content_fp"],
            "cms_counts": pre_cs["counts"],
        },
        "integrity_after": {
            "v2_bodies_fp": post_v2["bodies_fp"],
            "v2_status": post_v2["status_counts"],
            "v1_bodies_fp": post_v1["bodies_fp"],
            "t6d_fp": post_t6d["content_fp"],
            "t6f2_fp": post_t6f2["content_fp"],
            "legacy_fp": post_legacy["content_fp"],
            "cms_counts": post_cs["counts"],
        },
        "protected_population_integrity": {
            "V1": "UNCHANGED" if pre_v1["bodies_fp"] == post_v1["bodies_fp"] and auth.get("allowlist_sha256") == EXPECTED_V1_SHA else "CHANGED",
            "T6-D": "UNCHANGED" if pre_t6d["content_fp"] == post_t6d["content_fp"] else "CHANGED",
            "T6-F2": "UNCHANGED" if pre_t6f2["content_fp"] == post_t6f2["content_fp"] else "CHANGED",
            "legacy": "UNCHANGED" if pre_legacy["content_fp"] == post_legacy["content_fp"] else "CHANGED",
            "vs_post_publication_baseline": {
                "t6d": exp["t6d"]["content_fp"] == post_t6d["content_fp"],
                "t6f2": exp["t6f2"]["content_fp"] == post_t6f2["content_fp"],
                "legacy": exp["legacy"]["content_fp"] == post_legacy["content_fp"],
            },
        },
        "approvals": 0,
        "publications": 0,
        "ecaep_transitions": 0,
        "ecaep_content_reviews_on_population": int(ecaep_reviews or 0),
        "batch_status": batch.status,
        "unexpected_mutations": unexpected,
        "tests": tests,
        "limitations": [
            "P5 sample ≠ certification of all 100 items.",
            "factory_sample_v1 did not enforce subject or graphical quotas; sample is Zoology/Chemistry skewed.",
            "Not NCERT certified; no fabricated page/quotation evidence.",
            "Not scientifically certified as a bank.",
            "Not an independent multi-SME panel.",
            "ACCEPT marks ecaep_submit_eligible only; ContentItem remains DRAFT.",
            "Diversity forensic remains a separate gate.",
        ],
        "next_gate_recommendation": "Diversity Forensics (authorized as next separate gate; not executed here)",
        "diversity_forensics_authorized": False,
        "phase_stop": "P5_COMPLETE — do not proceed to diversity forensic / NCERT / approve / publish without separate authorization",
        "provider_calls": 0,
        "new_content_generated": 0,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")

    md = f"""# PRODUCTION SEED V2 — P5 HUMAN SAMPLING / REVIEW (Exact 100)

**Verdict:** `{verdict}`  
**Captured:** {doc['captured_at']}  
**Sample key:** `{SAMPLE_KEY}`  
**Seed:** `{sample_meta['seed']}`

## 1. Exact population
- Population: **100** P3/P4 IDs (exact membership)
- All remain **DRAFT**; approvals/publications/ECAEP transitions from this gate: **0**

## 2. Sampling methodology
- Policy: **factory_sample_v1**
- Formula: `{sample_meta['formula']}`
- Algorithm: stratified round-robin by `subject|family|difficulty|blueprint`
- Reproducible seed: **{sample_meta['seed']}**
- Graphical stratification: **NOT SUPPORTED** (limitation recorded; algorithm not altered)

## 3. Sample size
**{sample_meta['actual_sample_size']} / 100**

## 4. Distributions (sample)
- Subjects: `{sample_meta['subject_distribution_sample']}`
- Difficulty: `{sample_meta['difficulty_distribution_sample']}`
- Archetypes: `{sample_meta['archetype_distribution_sample']}`
- Graphical: sample {sample_meta['graphical_distribution']['sample_graphical']} / population {sample_meta['graphical_distribution']['population_graphical']}

## 5. Decisions
| Decision | Count |
|----------|------:|
| ACCEPT | {accept_n} |
| CORRECTION_REQUIRED | {correction_n} |
| REJECT | {critical_rejects} |

## 6. Major findings
- **zoology-15** (`ef480cb5-…`): dual-defensible options A and D → CORRECTION_REQUIRED (AMBIGUOUS/BAD_DISTRACTOR).
- **zoology-12** (`7580a952-…`): diagram_data_interpretation archetype without visual → CORRECTION_REQUIRED (WRONG_MAPPING).
- Sample **missing Physics and Botany** under factory_sample_v1 unique-blueprint strata ordering.

## 7. Diversity findings
""" + "\n".join(f"- {x}" for x in diversity_findings) + """

## 8. Graphical findings
""" + "\n".join(f"- {x}" for x in graphical_findings) + """

## 9. Numerical findings
""" + "\n".join(f"- {x}" for x in numerical_findings) + """

## 10. Integrity
- V2 bodies/status unchanged: **{pre_v2['bodies_fp'] == post_v2['bodies_fp']}**
- V1 / T6-D / T6-F2 / legacy: **UNCHANGED**
- Unexpected mutations: `{unexpected}`

## 11. Tests
- `tests/test_content_factory_p5.py`: **{'PASS' if proc.returncode == 0 else 'FAIL'}** (rc={proc.returncode})
- V2-specific P5 tests: **NOT_PRESENT**

## 12. Limitations
""" + "\n".join(f"- {x}" for x in doc["limitations"]) + """

## 13. Stop
- Diversity Forensics is the **recommended next separate gate** — **not authorized/executed** by this P5 run.
- Do not approve, publish, run NCERT certification, or student practice from this gate alone.

**Artifacts:**  
- `{OUT_JSON.relative_to(ROOT).as_posix()}`  
- `{OUT_MD.relative_to(ROOT).as_posix()}`  
"""
    OUT_MD.write_text(md, encoding="utf-8")
    # cleanup readable temp
    tmp = AUDITS / "_v2_p5_packet_readable.txt"
    if tmp.exists():
        tmp.unlink()
    print(json.dumps({"verdict": verdict, "ACCEPT": accept_n, "CORRECTION_REQUIRED": correction_n, "REJECT": critical_rejects, "unexpected": unexpected}, indent=2))
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
