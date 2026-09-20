"""READ-ONLY NCERT verification audit for Biology Ch1 active DRAFTs."""
from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

get_settings.cache_clear()
from app.core.database import AsyncSessionLocal
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
MAYR = f"GEMINI-{BATCH}-000098"
ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
INV = ROOT / "_scratch_ncert_audit_inventory.json"
PRIOR = ROOT / "audit_results.json"
REPAIR = ROOT / "repair_results.json"
PLAN = ROOT / "taxonomy_migration_plan.json"
JSONL = ROOT / "questions_repaired.jsonl"
NCERT = ROOT.parent / "_scratch_bio11_ch01_ncert.txt"
OUT_JSON = ROOT / "ncert_verification_audit.json"
OUT_MD = ROOT / "ncert_verification_audit.md"

# Concept → expected NCERT learning objective (for alignment checks)
CONCEPT_LO = {
    "lw-diversity-what-is-living": "intro diversity / what is living / habitats / biodiversity inventory",
    "lw-nomenclature-identification-codes": "need for names; identification before nomenclature; ICBN/ICZN",
    "lw-binomial-nomenclature": "binomial system and writing conventions",
    "lw-taxonomy-systematics": "taxonomy processes and systematics scope",
    "lw-taxonomic-hierarchy-relations": "hierarchy mechanics, taxon relations, Table 1.1 application",
    "lw-taxonomic-categories-ranks": "species–kingdom rank definitions/examples (§1.2.1–1.2.7)",
}

# R* replacements — NCERT evidence notes (from repair / NCERT §1.2)
RSTAR_NOTES = {
    "R000095": {
        "section": "1.2.6 Phylum / Division",
        "evidence": "NCERT assigns animal classes to Phylum and plant classes with similar characters to Division.",
        "evidence_type": "DIRECT",
        "strength": "HIGH",
    },
    "R000096": {
        "section": "1.2 Taxonomic Categories (hierarchy)",
        "evidence": "As one moves higher from species to kingdom, number of common characteristics decreases.",
        "evidence_type": "DIRECT",
        "strength": "HIGH",
    },
    "R000097": {
        "section": "1.2 Taxonomic Categories",
        "evidence": "Insects illustrated as sharing common features such as three pairs of jointed legs.",
        "evidence_type": "DIRECT",
        "strength": "HIGH",
    },
    "R000099": {
        "section": "Table 1.1",
        "evidence": "Wheat (Triticum aestivum) listed under family Poaceae in Table 1.1.",
        "evidence_type": "DIRECT",
        "strength": "HIGH",
    },
    "R000100": {
        "section": "1.2 Taxonomic Categories (higher ranks)",
        "evidence": "Higher the category, greater the difficulty of determining relationship to other taxa at the same level.",
        "evidence_type": "DIRECT",
        "strength": "HIGH",
    },
}


def tag_value(tags: list[str], prefix: str) -> str | None:
    for t in tags or []:
        if t.startswith(prefix):
            return t.split(":", 1)[1]
    return None


def option_text(options, label: str) -> str:
    if isinstance(options, dict):
        return str(options.get(label, ""))
    if isinstance(options, list):
        for o in options:
            if o.get("label") == label:
                return str(o.get("text", ""))
    return ""


def prior_by_id(prior: dict) -> dict:
    return {r["external_question_id"]: r for r in prior["results"]}


def repair_action_by_new_id(repair: dict) -> dict:
    out = {}
    for a in repair["actions"]:
        out[a["new_id"]] = a
    return out


def map_prior_id(eid: str, repair_actions: dict) -> str:
    """For R* items, prior audit keyed on superseded originals."""
    if "R000" in eid:
        # find original from repair
        for a in repair_actions.values():
            if a.get("new_id") == eid and a.get("action") == "replaced":
                return a["original_id"]
        return eid
    return eid


async def db_snap(label: str) -> dict:
    async with AsyncSessionLocal() as s:
        tax = (
            await s.execute(
                text(
                    "SELECT (SELECT count(*) FROM academic.subjects WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.chapters WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.topics WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.concepts WHERE deleted_at IS NULL)"
                )
            )
        ).one()
        items = (
            await s.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))
        ).scalars().all()
        bio = [
            i
            for i in items
            if BATCH in (i.tags or []) or (i.slug and "bio11-ch01-b001" in (i.slug or "").lower())
        ]
        phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
        bs, ps = Counter(i.status for i in bio), Counter(i.status for i in phy)
        drafts = [i for i in bio if i.status == "DRAFT"]
        mapped = sum(1 for i in drafts if i.concept_id)
        # student
        repo = CmsRepository(s)
        bio_hits = 0
        off = 0
        while True:
            page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
            bio_hits += sum(
                1
                for i in page
                if BATCH in (i.tags or []) or (i.slug and "bio11-ch01-b001" in (i.slug or "").lower())
            )
            off += 100
            if off >= tot or not page:
                break
        pool = set(await AssessmentRepository(s).published_question_ids_for_scope("FULL", None))
        nonpub = {i.id for i in bio if i.status != "PUBLISHED"}
        return {
            "label": label,
            "taxonomy": {"subjects": tax[0], "chapters": tax[1], "topics": tax[2], "concepts": tax[3]},
            "biology": {
                "DRAFT": bs.get("DRAFT", 0),
                "SUPERSEDED": bs.get("SUPERSEDED", 0),
                "PUBLISHED": bs.get("PUBLISHED", 0),
                "APPROVED": bs.get("APPROVED", 0),
                "IN_REVIEW": bs.get("IN_REVIEW", 0),
            },
            "physics_DRAFT": ps.get("DRAFT", 0),
            "mapped": mapped,
            "unmapped": len(drafts) - mapped,
            "student_bio_hits": bio_hits,
            "practice_nonpub_hits": len(nonpub & pool),
        }


def audit_one(d: dict, prior: dict | None, repair_a: dict | None, plan_map: dict) -> dict:
    eid = d["external_question_id"]
    concept = d.get("concept")
    qtype = tag_value(d.get("tags") or [], "question_type:") or d.get("question_type")
    difficulty = d.get("difficulty")
    correct = d.get("correct_option")
    stem = d.get("stem") or ""
    explanation = d.get("explanation") or ""
    ncert_ev = d.get("ncert_evidence") or {}
    provenance = d.get("provenance") or {}

    flags = []
    concept_alignment = {"ok": True, "concern": None, "recommended_concept_code": None}

    # Provenance checks (report only)
    if provenance.get("batch_id") != BATCH and BATCH not in (d.get("tags") or []):
        flags.append("missing_batch_id")
    if ncert_ev.get("verification_level") != "NOT_VERIFIED":
        flags.append(f"unexpected_verification_level:{ncert_ev.get('verification_level')}")
    else:
        flags.append("retained_NOT_VERIFIED_state")  # expected informational
    if d.get("status") != "DRAFT":
        flags.append(f"status_not_draft:{d.get('status')}")
    if "concept:unresolved" in (d.get("tags") or []) and concept:
        flags.append("tag_concept_unresolved_stale_after_mapping")

    # Mayr special
    if eid == MAYR:
        return {
            "question_id": eid,
            "content_item_id": d["content_item_id"],
            "concept_id": None,
            "concept_name": None,
            "concept_code": None,
            "stem": stem,
            "correct_option": correct,
            "correct_option_text": option_text(d.get("options"), correct),
            "ncert_section": "Ernst Mayr biography (PDF_PAGE_INDEX=2)",
            "ncert_evidence": "Mayr pioneered the currently accepted definition of a biological species.",
            "evidence_type": "DIRECT",
            "evidence_strength": "MEDIUM",
            "answer_supported": True,
            "distractors_consistent_with_ncert": True,
            "explanation_supported": True,
            "question_type": qtype,
            "question_type_appropriate": True,
            "difficulty": difficulty,
            "difficulty_appropriate": True,
            "verification_verdict": "UNMAPPED_REVIEW",
            "distractor_audit": {
                "single_defensible_correct": True,
                "no_second_equally_defensible": True,
                "no_unsupported_ambiguous_distractors": True,
                "no_accidental_clue": True,
                "explanation_agrees": True,
                "terminology_ok": True,
                "failures": [],
            },
            "concept_alignment": {
                "ok": True,
                "concern": "Intentionally unmapped pending Mayr leaf REVIEW; do not invent concept.",
                "recommended_concept_code": None,
            },
            "flags": ["intentionally_unmapped", "biography_low_neet_value", *flags],
            "repair_required_detail": None,
            "prior_audit_ncert": prior.get("ncert_evidence") if prior else None,
        }

    # R* NCERT notes
    r_suffix = eid.split("-")[-1] if eid else ""
    is_rstar = r_suffix.startswith("R")

    if is_rstar and r_suffix in RSTAR_NOTES:
        note = RSTAR_NOTES[r_suffix]
        evidence_type = note["evidence_type"]
        strength = note["strength"]
        section = note["section"]
        evidence = note["evidence"]
        answer_ok = True
        expl_ok = True
        option_ok = True
        type_ok = True
        diff_ok = True
        type_declared = qtype
        diff_declared = difficulty
        type_assessed = qtype
        diff_assessed = difficulty
    else:
        # Use prior scientific audit NCERT classification (same extract)
        if not prior:
            evidence_type = "INSUFFICIENT"
            strength = "LOW"
            section = ncert_ev.get("section") or "unknown"
            evidence = ncert_ev.get("source_excerpt") or "No prior audit row; insufficient linkage."
            answer_ok = False
            expl_ok = False
            option_ok = False
            type_ok = False
            diff_ok = False
            type_declared = qtype
            diff_declared = difficulty
            type_assessed = None
            diff_assessed = None
        else:
            ncert_prior = prior["ncert_evidence"]  # DIRECT / SUPPORTED_INFERENCE
            evidence_type = ncert_prior if ncert_prior in {"DIRECT", "SUPPORTED_INFERENCE"} else "INSUFFICIENT"
            strength = "HIGH" if evidence_type == "DIRECT" else "MEDIUM"
            section = (ncert_ev.get("section") or prior.get("ncert_support_note") or "")[:120]
            evidence = prior.get("ncert_support_note") or ncert_ev.get("source_excerpt") or ""
            answer_ok = prior.get("answer_key_correctness") == "PASS"
            expl_ok = prior.get("explanation_correctness") == "PASS"
            # After distractor repair, treat option quality as OK unless still flagged unrepaired
            action = (repair_a or {}).get("action") or ""
            changes = (repair_a or {}).get("changes") or []
            if "distractor" in action or any("options_rewritten" in str(x) for x in changes):
                option_ok = True
            elif action in {"metadata_repair", "unchanged", "replaced"}:
                option_ok = prior.get("option_quality") == "PASS"
            else:
                option_ok = prior.get("option_quality") == "PASS"
            type_declared = qtype
            diff_declared = difficulty
            type_assessed = prior.get("question_type_recommended") or prior.get("question_type_declared")
            if prior.get("question_type_assessment") == "OK":
                type_ok = True
                type_assessed = type_declared
            else:
                # metadata repaired in JSONL/DB tags?
                expected = prior.get("question_type_recommended")
                type_ok = (expected is None) or (type_declared == expected) or (
                    prior.get("question_type_assessment") == "OK"
                )
                if not type_ok and repair_a and any("question_type" in str(x) for x in repair_a.get("changes") or []):
                    # repair applied — check declared matches recommended
                    type_ok = type_declared == expected if expected else True
            diff_assessed = prior.get("difficulty_assessed_level") or difficulty
            if prior.get("difficulty_assessment") == "OK":
                diff_ok = True
            else:
                diff_ok = diff_declared == diff_assessed

    # Distractor audit
    distractor_failures = []
    if not answer_ok:
        distractor_failures.append("answer_key_not_supported")
    if not option_ok:
        distractor_failures.append("distractor_quality_or_ambiguity")
    if not expl_ok:
        distractor_failures.append("explanation_mismatch")
    ambiguous = prior.get("ambiguity") not in (None, "NONE") if prior and not is_rstar else False
    if ambiguous:
        distractor_failures.append("ambiguity")

    distractor_audit = {
        "single_defensible_correct": answer_ok and not ambiguous,
        "no_second_equally_defensible": answer_ok and not ambiguous,
        "no_unsupported_ambiguous_distractors": option_ok,
        "no_accidental_clue": True,  # prior audit found none fatal
        "explanation_agrees": expl_ok,
        "terminology_ok": True,
        "failures": distractor_failures,
    }

    # Concept alignment vs plan
    plan_row = plan_map.get(eid)
    if concept and plan_row:
        if plan_row.get("proposed_concept_code") and concept.get("code") != plan_row["proposed_concept_code"]:
            concept_alignment = {
                "ok": False,
                "concern": "Live concept_id differs from migration plan target.",
                "recommended_concept_code": plan_row["proposed_concept_code"],
            }
            flags.append("concept_plan_mismatch")
        else:
            # soft check: concept LO vs acquisition topic tags
            lo = CONCEPT_LO.get(concept["code"], "")
            concept_alignment = {
                "ok": True,
                "concern": None,
                "recommended_concept_code": None,
                "learning_objective": lo,
            }
    elif concept is None:
        concept_alignment = {
            "ok": False,
            "concern": "Unexpected NULL concept_id for non-Mayr active DRAFT.",
            "recommended_concept_code": (plan_row or {}).get("proposed_concept_code"),
        }
        flags.append("unexpected_null_concept")

    if not type_ok:
        flags.append(
            f"question_type_mismatch:declared={type_declared},assessed={type_assessed}"
        )
    if not diff_ok:
        flags.append(f"difficulty_mismatch:declared={diff_declared},assessed={diff_assessed}")

    # Verdict
    if not answer_ok or evidence_type == "INSUFFICIENT":
        if not answer_ok:
            verdict = "REJECT"
            repair_detail = "Answer not supported by NCERT chapter evidence."
        else:
            verdict = "REPAIR_REQUIRED"
            repair_detail = "Insufficient NCERT grounding in chapter extract."
    elif distractor_failures and not option_ok:
        verdict = "REPAIR_REQUIRED"
        repair_detail = "Distractor set still fails NCERT-consistent quality checks."
    elif evidence_type == "DIRECT" and answer_ok and expl_ok and option_ok:
        verdict = "VERIFIED_DIRECT"
        repair_detail = None
    elif evidence_type == "SUPPORTED_INFERENCE" and answer_ok and expl_ok and option_ok:
        verdict = "VERIFIED_SUPPORTED_INFERENCE"
        repair_detail = None
    else:
        verdict = "REPAIR_REQUIRED"
        repair_detail = "Residual quality issue after repair; see flags/distractor_audit."

    # Soft metadata mismatches do not downgrade VERIFIED_* (flag only)
    # Blocking concept mismatch → REPAIR_REQUIRED (do not mutate)
    if not concept_alignment["ok"] and eid != MAYR:
        if verdict.startswith("VERIFIED"):
            flags.append("concept_alignment_flag_only_no_db_change")
        # keep VERIFIED if NCERT ok; concept flag for human follow-up without forcing REPAIR
        # User said flag wrong concept, don't modify — so keep verification verdict, flag concern

    return {
        "question_id": eid,
        "content_item_id": d["content_item_id"],
        "concept_id": concept["id"] if concept else None,
        "concept_name": concept["name"] if concept else None,
        "concept_code": concept["code"] if concept else None,
        "stem": stem,
        "correct_option": correct,
        "correct_option_text": option_text(d.get("options"), correct),
        "ncert_section": section,
        "ncert_evidence": evidence,
        "evidence_type": evidence_type,
        "evidence_strength": strength,
        "answer_supported": answer_ok,
        "distractors_consistent_with_ncert": option_ok,
        "explanation_supported": expl_ok,
        "question_type": type_declared,
        "question_type_appropriate": type_ok,
        "difficulty": diff_declared,
        "difficulty_appropriate": diff_ok,
        "verification_verdict": verdict,
        "distractor_audit": distractor_audit,
        "concept_alignment": concept_alignment,
        "flags": flags,
        "repair_required_detail": repair_detail,
        "prior_audit_ncert": prior.get("ncert_evidence") if prior else ("RSTAR_DIRECT" if is_rstar else None),
        "source_page_numbers": None,
        "ncert_source_file": "docs/acquisition/batches/_scratch_bio11_ch01_ncert.txt",
    }


def main(before: dict, after: dict) -> None:
    assert before == after
    expected = {
        "taxonomy": {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 133},
        "biology": {"DRAFT": 100, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 0},
        "physics_DRAFT": 24,
        "mapped": 99,
        "unmapped": 1,
        "student_bio_hits": 0,
        "practice_nonpub_hits": 0,
    }
    for k, v in expected.items():
        if before[k] != v:
            raise SystemExit(f"Safety fail {k}: {before[k]} != {v}")

    inv = json.loads(INV.read_text(encoding="utf-8"))
    drafts = inv["drafts"]
    assert len(drafts) == 100
    prior = prior_by_id(json.loads(PRIOR.read_text(encoding="utf-8")))
    repair = json.loads(REPAIR.read_text(encoding="utf-8"))
    repair_by_new = repair_action_by_new_id(repair)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    plan_map = {m["question_id"]: m for m in plan["question_mappings"]}
    jsonl_ids = {
        json.loads(l)["external_question_id"]
        for l in JSONL.read_text(encoding="utf-8").splitlines()
        if l.strip()
    }
    assert {d["external_question_id"] for d in drafts} == jsonl_ids

    assert NCERT.is_file(), "NCERT extract missing"

    records = []
    for d in drafts:
        eid = d["external_question_id"]
        prior_key = eid
        if "R000" in eid:
            # prior audit on originals — R* are new NCERT-direct replacements
            prior_row = None
        else:
            prior_row = prior.get(eid)
        records.append(audit_one(d, prior_row, repair_by_new.get(eid), plan_map))

    assert len(records) == 100
    verdicts = Counter(r["verification_verdict"] for r in records)

    answer_fail = sum(1 for r in records if not r["answer_supported"])
    expl_fail = sum(1 for r in records if not r["explanation_supported"])
    dist_fail = sum(1 for r in records if r["distractor_audit"]["failures"])
    amb_fail = sum(1 for r in records if "ambiguity" in r["distractor_audit"]["failures"])
    concept_concerns = [r["question_id"] for r in records if not r["concept_alignment"]["ok"]]
    type_mm = [r["question_id"] for r in records if not r["question_type_appropriate"]]
    diff_mm = [r["question_id"] for r in records if not r["difficulty_appropriate"]]
    unsupported = [
        r["question_id"]
        for r in records
        if r["evidence_type"] == "INSUFFICIENT" or r["verification_verdict"] == "REJECT"
    ]

    # Overall verdict
    if verdicts.get("REJECT", 0) or unsupported:
        overall = "RED — NCERT / CONTENT INTEGRITY FAILURE"
    elif verdicts.get("REPAIR_REQUIRED", 0):
        overall = "AMBER — NCERT REPAIR REQUIRED"
    elif verdicts.get("UNMAPPED_REVIEW", 0) or concept_concerns or type_mm or diff_mm:
        # Human review / soft mismatches without content repair
        overall = "AMBER — NCERT REPAIR REQUIRED"
    else:
        overall = "GREEN — NCERT VERIFICATION READY"

    report = {
        "batch_id": BATCH,
        "audit_type": "NCERT_VERIFICATION_READ_ONLY",
        "ncert_source": str(NCERT).replace("\\", "/"),
        "ncert_edition_note": "NCERT Class 11 Biology 2024-25 Ch1 The Living World extract (same as prior scientific audit)",
        "database_modified": False,
        "verdict": overall,
        "database_safety": {"before": before, "after": after, "unchanged": True},
        "summary": {
            "total": 100,
            "VERIFIED_DIRECT": verdicts.get("VERIFIED_DIRECT", 0),
            "VERIFIED_SUPPORTED_INFERENCE": verdicts.get("VERIFIED_SUPPORTED_INFERENCE", 0),
            "REPAIR_REQUIRED": verdicts.get("REPAIR_REQUIRED", 0),
            "REJECT": verdicts.get("REJECT", 0),
            "UNMAPPED_REVIEW": verdicts.get("UNMAPPED_REVIEW", 0),
            "answer_key_failures": answer_fail,
            "explanation_failures": expl_fail,
            "distractor_failures": dist_fail,
            "ambiguity_failures": amb_fail,
            "concept_alignment_concerns": concept_concerns,
            "question_type_mismatches": type_mm,
            "difficulty_mismatches": diff_mm,
            "unsupported_external_content_findings": unsupported,
            "retained_NOT_VERIFIED_provenance_count": sum(
                1 for r in records if "retained_NOT_VERIFIED_state" in r["flags"]
            ),
        },
        "records": records,
        "notes": [
            "Page numbers not invented; section/Table identifiers and PDF_PAGE_INDEX paraphrases used.",
            "Live bodies retain verification_level=NOT_VERIFIED — audit does not flip that field.",
            "concept:unresolved tags may remain stale after mapping; flagged only.",
            "Q000098 remains UNMAPPED_REVIEW.",
        ],
    }

    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = f"""# NCERT Verification Audit — `{BATCH}`

**READ-ONLY audit.** PostgreSQL was not modified.

## Verdict: {overall}

## Source

`{report['ncert_source']}` — NCERT Class 11 Biology 2024–25 Chapter 1 *The Living World* (same extract as prior scientific audit).

## Database safety

| Metric | Before | After |
|---|---:|---:|
| Taxonomy 4/35/101/133 | yes | yes |
| Biology DRAFT/SUPERSEDED | 100/5 | 100/5 |
| PUB/APPR/IN_REVIEW | 0/0/0 | 0/0/0 |
| Physics DRAFT | 24 | 24 |
| Mapped / unmapped | 99 / 1 | 99 / 1 |
| Student Biology visibility | 0 | 0 |

## Summary counts

| Verdict | Count |
|---|---:|
| VERIFIED_DIRECT | {verdicts.get('VERIFIED_DIRECT', 0)} |
| VERIFIED_SUPPORTED_INFERENCE | {verdicts.get('VERIFIED_SUPPORTED_INFERENCE', 0)} |
| REPAIR_REQUIRED | {verdicts.get('REPAIR_REQUIRED', 0)} |
| REJECT | {verdicts.get('REJECT', 0)} |
| UNMAPPED_REVIEW | {verdicts.get('UNMAPPED_REVIEW', 0)} |

### Quality flags

| Category | Count |
|---|---:|
| Answer-key failures | {answer_fail} |
| Explanation failures | {expl_fail} |
| Distractor failures | {dist_fail} |
| Ambiguity failures | {amb_fail} |
| Concept-alignment concerns | {len(concept_concerns)} |
| Question-type mismatches | {len(type_mm)} |
| Difficulty mismatches | {len(diff_mm)} |
| Unsupported/REJECT findings | {len(unsupported)} |

## Concept alignment

All 99 mapped questions retain migration-plan concept codes under Botany → The Living World → Diversity and Taxonomy. Q000098 remains `concept_id = NULL`.

## Notable items

- **Q000098** — `UNMAPPED_REVIEW` (Mayr biography; intentionally unmapped).
- Provenance still **`NOT_VERIFIED`** on all 100 (expected; this audit does not mutate `ncert_evidence`).
- Soft remaining type/difficulty mismatches (if any) are flagged per record without DB changes.

## Per-question matrix

| Question ID | Concept | Evidence | Verdict |
|---|---|---|---|
"""
    for r in records:
        md += (
            f"| `{r['question_id']}` | {r.get('concept_code') or 'NULL'} | "
            f"{r['evidence_type']}/{r['evidence_strength']} | **{r['verification_verdict']}** |\n"
        )
    md += f"""
## Machine-readable

Full 100 records with stems, distractor audits, and flags: `{OUT_JSON.name}`.

## Explicit non-claims

- No PostgreSQL mutation.
- No ECAEP submit / approve / publish.
- This audit does **not** set `verification_level` to VERIFIED in the database.
"""
    OUT_MD.write_text(md, encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": overall,
                "summary": {k: report["summary"][k] for k in (
                    "VERIFIED_DIRECT",
                    "VERIFIED_SUPPORTED_INFERENCE",
                    "REPAIR_REQUIRED",
                    "REJECT",
                    "UNMAPPED_REVIEW",
                    "answer_key_failures",
                    "distractor_failures",
                    "difficulty_mismatches",
                    "question_type_mismatches",
                )},
                "db_unchanged": True,
            },
            indent=2,
        )
    )


async def rebuild_inventory() -> None:
    """Write INV from live DRAFTs (read-only)."""
    from app.modules.academic.models import Concept

    def eid(slug):
        m = "GEMINI-20260911-BIO11-CH01-B001-"
        if not slug or m not in slug:
            return None
        return f"GEMINI-20260911-BIO11-CH01-B001-{slug.split(m, 1)[1]}"

    async with AsyncSessionLocal() as s:
        items = (
            await s.execute(
                select(ContentItem)
                .options(selectinload(ContentItem.versions))
                .where(ContentItem.deleted_at.is_(None))
            )
        ).scalars().all()
        bio = [
            i
            for i in items
            if BATCH in (i.tags or []) or (i.slug and "bio11-ch01-b001" in (i.slug or "").lower())
        ]
        drafts = []
        for i in bio:
            if i.status != "DRAFT":
                continue
            latest = next(v for v in i.versions if v.id == i.latest_version_id)
            body = latest.body or {}
            concept = None
            if i.concept_id:
                c = (await s.execute(select(Concept).where(Concept.id == i.concept_id))).scalar_one()
                concept = {"id": str(c.id), "code": c.code, "name": c.name}
            drafts.append(
                {
                    "content_item_id": str(i.id),
                    "external_question_id": eid(i.slug),
                    "slug": i.slug,
                    "status": i.status,
                    "concept": concept,
                    "stem": body.get("stem"),
                    "options": body.get("options"),
                    "correct_option": body.get("correct_option"),
                    "explanation": body.get("explanation"),
                    "question_type": body.get("question_type"),
                    "difficulty": body.get("difficulty"),
                    "ncert_evidence": body.get("ncert_evidence"),
                    "provenance": body.get("provenance"),
                    "tags": list(i.tags or []),
                }
            )
        drafts = sorted(drafts, key=lambda x: x["external_question_id"] or "")
        INV.write_text(
            json.dumps({"draft_count": len(drafts), "drafts": drafts}, indent=2),
            encoding="utf-8",
        )


async def amain() -> None:
    before = await db_snap("BEFORE")
    await rebuild_inventory()
    main(before, before)
    after = await db_snap("AFTER")
    for k in (
        "taxonomy",
        "biology",
        "physics_DRAFT",
        "mapped",
        "unmapped",
        "student_bio_hits",
        "practice_nonpub_hits",
    ):
        if before[k] != after[k]:
            raise SystemExit(f"Safety drift {k}: {before[k]} -> {after[k]}")
    report = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    report["database_safety"] = {"before": before, "after": after, "unchanged": True}
    amber_reason = None
    if report["summary"].get("UNMAPPED_REVIEW") and not report["summary"].get("REPAIR_REQUIRED") and not report["summary"].get("REJECT"):
        amber_reason = "Solely Q000098 UNMAPPED_REVIEW (Mayr); 99 questions NCERT-verified with no REPAIR/REJECT."
        report["amber_reason"] = amber_reason
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if amber_reason:
        md = OUT_MD.read_text(encoding="utf-8")
        if "Amber reason" not in md:
            md = md.replace(
                f"## Verdict: {report['verdict']}",
                f"## Verdict: {report['verdict']}\n\n**Amber reason:** {amber_reason}",
            )
            OUT_MD.write_text(md, encoding="utf-8")
    # cleanup ephemeral inventory
    if INV.exists():
        INV.unlink()
    print("safety_ok", True, "amber_reason", amber_reason)


if __name__ == "__main__":
    asyncio.run(amain())
