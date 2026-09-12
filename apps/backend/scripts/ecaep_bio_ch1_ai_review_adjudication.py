"""READ-ONLY adjudication of 8 ECAEP AI review non-PASS findings."""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.academic.models import Concept
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
EXPECTED_TAX = {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}
EXPECTED_BIO = {"DRAFT": 0, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 100}
TARGET_SUFFIXES = [
    "000021",
    "000071",
    "000076",
    "000090",
    "000094",
    "000047",
    "000062",
    "000069",
]

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
NCERT_TXT = ROOT.parent / "_scratch_bio11_ch01_ncert.txt"
OUT_JSON = ROOT / "ecaep_ai_review_adjudication.json"
OUT_MD = ROOT / "ecaep_ai_review_adjudication.md"


def is_batch(i: ContentItem) -> bool:
    return BATCH in (i.tags or []) or bool(i.slug and "bio11-ch01-b001" in i.slug.lower())


def eid_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    m = f"GEMINI-{BATCH}-"
    if m not in slug:
        return None
    return f"GEMINI-{BATCH}-{slug.split(m, 1)[1]}"


def body_fp(body: dict | None) -> str:
    return hashlib.sha256(
        json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def opts_map(options) -> dict:
    if isinstance(options, dict):
        return {k: str(v) for k, v in options.items()}
    out = {}
    for o in options or []:
        out[o.get("label")] = o.get("text")
    return out


async def snap(session) -> dict:
    tax = (
        await session.execute(
            text(
                "SELECT (SELECT count(*) FROM academic.subjects WHERE deleted_at IS NULL),"
                "(SELECT count(*) FROM academic.chapters WHERE deleted_at IS NULL),"
                "(SELECT count(*) FROM academic.topics WHERE deleted_at IS NULL),"
                "(SELECT count(*) FROM academic.concepts WHERE deleted_at IS NULL)"
            )
        )
    ).one()
    items = (
        await session.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))
    ).scalars().all()
    bio = [i for i in items if is_batch(i)]
    phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
    bs = Counter(i.status for i in bio)
    repo = CmsRepository(session)
    hits = 0
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        hits += sum(1 for i in page if is_batch(i))
        off += 100
        if off >= tot or not page:
            break
    pool = set(await AssessmentRepository(session).published_question_ids_for_scope("FULL", None))
    nonpub = {i.id for i in bio if i.status != "PUBLISHED"}
    return {
        "taxonomy": {
            "subjects": tax[0],
            "chapters": tax[1],
            "topics": tax[2],
            "concepts": tax[3],
        },
        "biology": {
            "DRAFT": bs.get("DRAFT", 0),
            "SUPERSEDED": bs.get("SUPERSEDED", 0),
            "PUBLISHED": bs.get("PUBLISHED", 0),
            "APPROVED": bs.get("APPROVED", 0),
            "IN_REVIEW": bs.get("IN_REVIEW", 0),
        },
        "physics_DRAFT": Counter(i.status for i in phy).get("DRAFT", 0),
        "student_bio_hits": hits,
        "practice_nonpub_hits": len(nonpub & pool),
    }


# Static adjudication grounded in NCERT extract quotes (source of truth #1)
ADJUDICATIONS: dict[str, dict] = {
    "GEMINI-20260911-BIO11-CH01-B001-000021": {
        "kind": "WARNING",
        "ai_finding_valid": False,
        "prior_audit_valid": True,
        "ncert_resolves": True,
        "question_defective": False,
        "content_repair_required": False,
        "ai_false_positive": True,
        "human_review_remains_necessary": False,
        "warning_adjudication": "ACCEPTABLE_WARNING",
        "discrepancy_adjudication": None,
        "approval_readiness": "APPROVE_WITH_DOCUMENTED_WARNING",
        "rationale": (
            "AI flags 'given in this chapter' as ambiguous. Project source of truth is "
            "NCERT Class 11 Biology Ch1; the stem is intentional chapter-scope framing. "
            "Extract (PDF_PAGE_INDEX=7): scientific name of human written as Homo sapiens. "
            "Answer A and explanation match. Stylistic preference ≠ content defect."
        ),
        "ncert_evidence": {
            "location": "PDF_PAGE_INDEX=7",
            "quote": (
                "Human beings belong to the species sapiens which is grouped in the genus "
                "Homo. The scientific name thus, for human being, is written as Homo sapiens."
            ),
            "external_knowledge_conflict": None,
        },
    },
    "GEMINI-20260911-BIO11-CH01-B001-000071": {
        "kind": "WARNING",
        "ai_finding_valid": False,
        "prior_audit_valid": True,
        "ncert_resolves": True,
        "question_defective": False,
        "content_repair_required": False,
        "ai_false_positive": True,
        "human_review_remains_necessary": False,
        "warning_adjudication": "ACCEPTABLE_WARNING",
        "discrepancy_adjudication": None,
        "approval_readiness": "APPROVE_WITH_DOCUMENTED_WARNING",
        "rationale": (
            "AI META_DEPENDENT_STEM: 'hierarchy examples' refers to Ch1 hierarchy / kingdoms. "
            "Extract (PDF_PAGE_INDEX=8) explicitly names Kingdom Animalia and Kingdom Plantae "
            "as the two kingdom categories in this chapter's hierarchy. Correct answer C is "
            "source-supported. Meta framing is chapter-pilot style, not a factual defect."
        ),
        "ncert_evidence": {
            "location": "PDF_PAGE_INDEX=8 §1.2.7 Kingdom",
            "quote": (
                "All animals belonging to various phyla are assigned to the highest category "
                "called Kingdom Animalia... The Kingdom Plantae, on the other hand, is distinct..."
            ),
            "external_knowledge_conflict": None,
        },
    },
    "GEMINI-20260911-BIO11-CH01-B001-000076": {
        "kind": "WARNING",
        "ai_finding_valid": False,
        "prior_audit_valid": True,
        "ncert_resolves": True,
        "question_defective": False,
        "content_repair_required": False,
        "ai_false_positive": True,
        "human_review_remains_necessary": False,
        "warning_adjudication": "ACCEPTABLE_WARNING",
        "discrepancy_adjudication": None,
        "approval_readiness": "APPROVE_WITH_DOCUMENTED_WARNING",
        "rationale": (
            "AI STRICT_STEM_CONTEXT_MISSING for 'in the table'. Project extract includes "
            "Table 1.1 hierarchy examples with housefly → Musca domestica. Stem is "
            "table-referential within Ch1 pilot context; answer D is exact. Not a content defect."
        ),
        "ncert_evidence": {
            "location": "PDF_PAGE_INDEX=8 Table 1.1 / hierarchy examples",
            "quote": (
                "Look at the hierarchy... common organisms like housefly, man, mango and wheat... "
                "Housefly / Musca / Musca domestica (table listing in extract)."
            ),
            "external_knowledge_conflict": None,
        },
    },
    "GEMINI-20260911-BIO11-CH01-B001-000090": {
        "kind": "WARNING",
        "ai_finding_valid": False,
        "prior_audit_valid": True,
        "ncert_resolves": True,
        "question_defective": False,
        "content_repair_required": False,
        "ai_false_positive": True,
        "human_review_remains_necessary": False,
        "warning_adjudication": "ACCEPTABLE_WARNING",
        "discrepancy_adjudication": None,
        "approval_readiness": "APPROVE_WITH_DOCUMENTED_WARNING",
        "rationale": (
            "AI INCONSISTENT_TAXONOMIC_LEVELS_IN_OPTIONS: Option B is two genera "
            "(Panthera and Felis), which is exactly what the stem tests (share family, "
            "not genus). Extract (PDF_PAGE_INDEX=7): Panthera with Felis in Felidae; "
            "species of Panthera share genus. Mixed option levels are intentional for "
            "comparison, not a defect."
        ),
        "ncert_evidence": {
            "location": "PDF_PAGE_INDEX=7 Family / Genus",
            "quote": (
                "genus Panthera... is put along with genus, Felis (cats) in the family Felidae. "
                "Lion (Panthera leo)... tiger (P. tigris)... are all species of the genus Panthera."
            ),
            "external_knowledge_conflict": None,
        },
    },
    "GEMINI-20260911-BIO11-CH01-B001-000094": {
        "kind": "WARNING",
        "ai_finding_valid": False,
        "prior_audit_valid": True,
        "ncert_resolves": True,
        "question_defective": False,
        "content_repair_required": False,
        "ai_false_positive": True,
        "human_review_remains_necessary": False,
        "warning_adjudication": "ACCEPTABLE_WARNING",
        "discrepancy_adjudication": None,
        "approval_readiness": "APPROVE_WITH_DOCUMENTED_WARNING",
        "rationale": (
            "AI DISTRACTORS_TOO_WEAK is a NEET-style preference. Extract SUMMARY "
            "(PDF_PAGE_INDEX=9) states taxonomic studies are useful in forestry and "
            "bio-resources. Answer B is source-direct. Weak distractors ≠ factual error "
            "or repair requirement for this pilot."
        ),
        "ncert_evidence": {
            "location": "PDF_PAGE_INDEX=9 SUMMARY",
            "quote": (
                "The taxonomic studies of various species of plants and animals are useful "
                "in agriculture, forestry, industry and in general for knowing our bio-resources "
                "and their diversity."
            ),
            "external_knowledge_conflict": None,
        },
    },
    "GEMINI-20260911-BIO11-CH01-B001-000047": {
        "kind": "DISCREPANCY",
        "ai_finding_valid": False,
        "prior_audit_valid": True,
        "ncert_resolves": True,
        "question_defective": False,
        "content_repair_required": False,
        "ai_false_positive": True,
        "human_review_remains_necessary": False,
        "warning_adjudication": None,
        "discrepancy_adjudication": "SOURCE_SUPPORTS_QUESTION",
        "approval_readiness": "APPROVE_READY",
        "rationale": (
            "AI claims explanation wrongly calls 'Panthera leo' a species name (vs epithet "
            "'leo'). NCERT Ch1 uses both: it names specific epithets (indica, tuberosum, leo) "
            "AND states 'Lion (Panthera leo)... are all species of the genus Panthera' and "
            "writes scientific names as binomials (Homo sapiens). Stem 'species of Panthera' "
            "matches NCERT wording. Explanation 'Panthera leo is the species name used for "
            "lion' is consistent with Ch1 scientific-name usage. AI criticism is pedantic "
            "false-positive relative to project source; prior VERIFIED_DIRECT stands."
        ),
        "ncert_evidence": {
            "location": "PDF_PAGE_INDEX=6–7 §1.2.1 Species / §1.2.2 Genus",
            "quote": (
                "Let us consider Mangifera indica, Solanum tuberosum (potato) and Panthera leo "
                "(lion). All the three names, indica, tuberosum and leo, represent the specific "
                "epithets... Lion (Panthera leo), leopard (P. pardus) and tiger (P. tigris)... "
                "are all species of the genus Panthera."
            ),
            "external_knowledge_conflict": (
                "External taxonomic pedantry distinguishing epithet vs binomial does not "
                "override NCERT Ch1's own use of binomials as species/scientific names."
            ),
        },
    },
    "GEMINI-20260911-BIO11-CH01-B001-000062": {
        "kind": "DISCREPANCY",
        "ai_finding_valid": False,
        "prior_audit_valid": True,
        "ncert_resolves": True,
        "question_defective": False,
        "content_repair_required": False,
        "ai_false_positive": True,
        "human_review_remains_necessary": False,
        "warning_adjudication": None,
        "discrepancy_adjudication": "SOURCE_SUPPORTS_QUESTION",
        "approval_readiness": "APPROVE_READY",
        "rationale": (
            "AI flags Polymoniales as typo for Polemoniales. Project NCERT extract "
            "literally prints 'Polymoniales' (PDF_PAGE_INDEX=7). Question option B and "
            "explanation match the extract exactly. Spelling was NOT silently normalized. "
            "External 'correct' botanical spelling conflicts with project source — recorded; "
            "source wins for this pilot."
        ),
        "ncert_evidence": {
            "location": "PDF_PAGE_INDEX=7 §1.2.4 Order",
            "quote": (
                "Plant families like Convolvulaceae, Solanaceae are included in the order "
                "Polymoniales mainly based on the floral characters."
            ),
            "external_knowledge_conflict": (
                "External/general knowledge often spells the order Polemoniales; the project "
                "NCERT 2024-25 extract used for all prior audits prints Polymoniales. "
                "Do not normalize away from the extract."
            ),
        },
    },
    "GEMINI-20260911-BIO11-CH01-B001-000069": {
        "kind": "DISCREPANCY",
        "ai_finding_valid": False,
        "prior_audit_valid": True,
        "ncert_resolves": True,
        "question_defective": False,
        "content_repair_required": False,
        "ai_false_positive": True,
        "human_review_remains_necessary": False,
        "warning_adjudication": None,
        "discrepancy_adjudication": "SOURCE_SUPPORTS_QUESTION",
        "approval_readiness": "APPROVE_READY",
        "rationale": (
            "AI claims Chordata diagnostic features belong to Animal Kingdom (Ch4), not "
            "The Living World. Project extract PDF_PAGE_INDEX=8 §1.2.6 Phylum explicitly "
            "includes fishes–mammals in phylum Chordata 'based on the common features like "
            "presence of notochord and dorsal hollow neural system' inside Chapter 1. "
            "AI classification is a false-positive source conflict, not an actual Ch1 gap."
        ),
        "ncert_evidence": {
            "location": "PDF_PAGE_INDEX=8 §1.2.6 Phylum",
            "quote": (
                "Classes comprising animals like fishes, amphibians, reptiles, birds along "
                "with mammals constitute the next higher category called Phylum. All these, "
                "based on the common features like presence of notochord and dorsal hollow "
                "neural system, are included in phylum Chordata."
            ),
            "external_knowledge_conflict": (
                "Later Animal Kingdom chapters expand chordate morphology; that does not "
                "remove the explicit Ch1 statement in the project extract."
            ),
        },
    },
}


async def main() -> int:
    repaired = {}
    for line in (ROOT / "questions_repaired.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            repaired[row["external_question_id"]] = row
    integrity = {
        r["question_id"]: r
        for r in json.loads((ROOT / "final_100_pilot_integrity_audit.json").read_text(encoding="utf-8"))[
            "records"
        ]
    }
    ncert_audit = {
        r["question_id"]: r
        for r in json.loads((ROOT / "ncert_verification_audit.json").read_text(encoding="utf-8"))[
            "records"
        ]
    }
    ai_audit = {
        r["question_id"]: r
        for r in json.loads((ROOT / "ecaep_ai_review_audit.json").read_text(encoding="utf-8"))[
            "records"
        ]
    }
    assert NCERT_TXT.is_file()
    ncert_text = NCERT_TXT.read_text(encoding="utf-8")
    # Prove Polymoniales / Chordata strings exist in extract
    assert "Polymoniales" in ncert_text
    assert "Polemoniales" not in ncert_text
    assert "notochord" in ncert_text.lower() and "Chordata" in ncert_text

    async with AsyncSessionLocal() as session:
        before = await snap(session)
        items = (
            await session.execute(
                select(ContentItem)
                .options(selectinload(ContentItem.versions))
                .where(ContentItem.deleted_at.is_(None))
            )
        ).scalars().all()
        live_by = {}
        for i in items:
            if not is_batch(i):
                continue
            e = eid_from_slug(i.slug)
            if e:
                live_by[e] = i
        records = []
        fps_before = {}
        for suffix in TARGET_SUFFIXES:
            eid = f"GEMINI-{BATCH}-{suffix}"
            adj = ADJUDICATIONS[eid]
            q = repaired[eid]
            live = live_by[eid]
            ver = next((v for v in live.versions if v.id == live.latest_version_id), None)
            body = dict(ver.body or {}) if ver else {}
            fps_before[eid] = body_fp(body)
            concept = None
            if live.concept_id:
                row = (
                    await session.execute(
                        select(Concept.id, Concept.code, Concept.name).where(
                            Concept.id == live.concept_id
                        )
                    )
                ).one_or_none()
                if row:
                    concept = {"id": str(row[0]), "code": row[1], "name": row[2]}
            ai = ai_audit[eid]
            fin = integrity[eid]
            nca = ncert_audit[eid]
            live_opts = opts_map(body.get("options"))
            repaired_opts = opts_map(q.get("options"))
            body_match = (
                (body.get("stem") or "").strip() == (q.get("stem") or "").strip()
                and live_opts == repaired_opts
                and str(body.get("correct_option") or "").upper()
                == str(q.get("correct_option") or "").upper()
                and (body.get("explanation") or "").strip() == (q.get("explanation") or "").strip()
            )
            records.append(
                {
                    "question_id": eid,
                    "display_id": f"Q{suffix}",
                    "stem": q["stem"],
                    "options": repaired_opts,
                    "answer": q["correct_option"],
                    "explanation": q["explanation"],
                    "question_type": q.get("question_type"),
                    "difficulty": q.get("difficulty"),
                    "concept_id": concept["id"] if concept else None,
                    "concept_code": concept["code"] if concept else None,
                    "concept_name": concept["name"] if concept else None,
                    "status": live.status,
                    "live_matches_repaired_artifact": body_match,
                    "ai_finding": {
                        "prior_ai_review_verdict": ai["ai_review_verdict"],
                        "flags": (ai.get("findings") or {}).get("flags"),
                        "reason": (ai.get("ai_check_report") or {}).get("reason"),
                        "confidence": (ai.get("findings") or {}).get("confidence"),
                        "status": (ai.get("ai_check_report") or {}).get("status"),
                    },
                    "prior_audit_result": {
                        "final_integrity_verdict": fin.get("final_question_verdict"),
                        "ncert_verification_result": fin.get("ncert_verification_result"),
                        "ncert_audit_verdict": nca.get("verification_verdict"),
                        "ncert_audit_evidence": nca.get("ncert_evidence"),
                    },
                    "ncert_evidence": adj["ncert_evidence"],
                    "answers_to_checklist": {
                        "A_ai_finding_valid": adj["ai_finding_valid"],
                        "B_prior_audit_valid": adj["prior_audit_valid"],
                        "C_ncert_resolves": adj["ncert_resolves"],
                        "D_question_defective": adj["question_defective"],
                        "E_content_repair_required": adj["content_repair_required"],
                        "F_ai_false_positive": adj["ai_false_positive"],
                        "G_human_review_remains_necessary": adj[
                            "human_review_remains_necessary"
                        ],
                    },
                    "adjudication": adj["warning_adjudication"]
                    or adj["discrepancy_adjudication"],
                    "warning_adjudication": adj["warning_adjudication"],
                    "discrepancy_adjudication": adj["discrepancy_adjudication"],
                    "rationale": adj["rationale"],
                    "approval_readiness": adj["approval_readiness"],
                    "repair_required": adj["content_repair_required"],
                    "human_review_required": adj["human_review_remains_necessary"],
                }
            )

        after = await snap(session)
        # re-check body fps unchanged within same session read
        fps_after = {}
        for suffix in TARGET_SUFFIXES:
            eid = f"GEMINI-{BATCH}-{suffix}"
            live = live_by[eid]
            ver = next((v for v in live.versions if v.id == live.latest_version_id), None)
            fps_after[eid] = body_fp(dict(ver.body or {}) if ver else {})

    body_unchanged = fps_before == fps_after
    db_ok = (
        before == after
        and after["biology"] == EXPECTED_BIO
        and after["taxonomy"] == EXPECTED_TAX
        and after["physics_DRAFT"] == 24
        and after["student_bio_hits"] == 0
        and body_unchanged
        and all(r["live_matches_repaired_artifact"] for r in records)
        and all(r["status"] == "IN_REVIEW" for r in records)
    )

    warn_rows = [r for r in records if r["warning_adjudication"]]
    disc_rows = [r for r in records if r["discrepancy_adjudication"]]
    unresolved_warn = [
        r
        for r in warn_rows
        if r["warning_adjudication"]
        not in {"ACCEPTABLE_WARNING", "FALSE_POSITIVE"}
        or r["human_review_required"]
        or r["repair_required"]
    ]
    unresolved_disc = [
        r
        for r in disc_rows
        if r["discrepancy_adjudication"]
        not in {"SOURCE_SUPPORTS_QUESTION", "AI_FALSE_POSITIVE"}
        or r["human_review_required"]
        or r["repair_required"]
    ]
    repair_n = sum(1 for r in records if r["repair_required"])
    human_n = sum(1 for r in records if r["human_review_required"])
    false_pos = sum(1 for r in records if r["answers_to_checklist"]["F_ai_false_positive"])
    valid_ai = sum(1 for r in records if r["answers_to_checklist"]["A_ai_finding_valid"])
    approve_ready = sum(
        1
        for r in records
        if r["approval_readiness"] in {"APPROVE_READY", "APPROVE_WITH_DOCUMENTED_WARNING"}
    )

    if (
        db_ok
        and len(records) == 8
        and not unresolved_warn
        and not unresolved_disc
        and repair_n == 0
        and human_n == 0
        and approve_ready == 8
    ):
        verdict = "GREEN — ALL AI FINDINGS ADJUDICATED"
    else:
        verdict = "AMBER — HUMAN/CONTENT REVIEW REQUIRED"

    summary = {
        "warnings": {
            "count": len(warn_rows),
            "ids": [r["question_id"] for r in warn_rows],
            "classifications": {
                r["display_id"]: r["warning_adjudication"] for r in warn_rows
            },
            "unresolved": [r["question_id"] for r in unresolved_warn],
        },
        "discrepancies": {
            "count": len(disc_rows),
            "ids": [r["question_id"] for r in disc_rows],
            "classifications": {
                r["display_id"]: r["discrepancy_adjudication"] for r in disc_rows
            },
            "unresolved": [r["question_id"] for r in unresolved_disc],
        },
        "false_positives": false_pos,
        "valid_ai_findings": valid_ai,
        "repairs_required": repair_n,
        "human_review_required": human_n,
        "final_approval_ready_count": approve_ready,
        "approval_readiness_breakdown": dict(
            Counter(r["approval_readiness"] for r in records)
        ),
        "database_safety": {
            "before": before,
            "after": after,
            "unchanged": before == after and body_unchanged,
            "ok": db_ok,
        },
        "final_verdict": verdict,
    }

    payload = {
        "batch_id": BATCH,
        "audit_type": "ECAEP_AI_REVIEW_ADJUDICATION_READ_ONLY",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_of_truth_order": [
            str(NCERT_TXT),
            str(ROOT / "questions_repaired.jsonl"),
            str(ROOT / "final_100_pilot_integrity_audit.json"),
            "live ContentVersion.ai_check_report / ecaep_ai_review_audit.json",
        ],
        "database_modified": False,
        "approval_performed": False,
        "publication_performed": False,
        "verdict": verdict,
        "summary": summary,
        "records": records,
        "assertions": {
            "READ-ONLY": True,
            "DATABASE UNCHANGED": db_ok,
            "NO APPROVAL": True,
            "NO PUBLICATION": True,
        },
    }
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# ECAEP AI Review Adjudication",
        "",
        f"## Verdict: {verdict}",
        "",
        "**READ-ONLY**  ",
        "**DATABASE UNCHANGED**  ",
        "**NO APPROVAL**  ",
        "**NO PUBLICATION**",
        "",
        f"Generated: `{payload['generated_at']}`  ",
        "Source-of-truth order: NCERT extract → questions_repaired.jsonl → "
        "final integrity audit → AI check report.",
        "",
        "## Summary",
        "",
        f"- Warnings adjudicated: **{len(warn_rows)}** (unresolved: {len(unresolved_warn)})",
        f"- Discrepancies adjudicated: **{len(disc_rows)}** (unresolved: {len(unresolved_disc)})",
        f"- AI false positives: **{false_pos}**",
        f"- Valid AI findings: **{valid_ai}**",
        f"- Repair required: **{repair_n}**",
        f"- Human review required: **{human_n}**",
        f"- Approval-ready (incl. documented warning): **{approve_ready}/8**",
        "",
        "```json",
        json.dumps(summary["approval_readiness_breakdown"], indent=2),
        "```",
        "",
        "## Warning adjudications",
        "",
    ]
    for r in warn_rows:
        lines += [
            f"### {r['display_id']}",
            f"- AI finding: `{r['ai_finding']['flags']}`",
            f"- Adjudication: **{r['warning_adjudication']}**",
            f"- Approval readiness: **{r['approval_readiness']}**",
            f"- Rationale: {r['rationale']}",
            f"- NCERT: {r['ncert_evidence']['location']} — {r['ncert_evidence']['quote'][:180]}...",
            "",
        ]
    lines += ["## Discrepancy adjudications", ""]
    for r in disc_rows:
        lines += [
            f"### {r['display_id']}",
            f"- AI finding: `{r['ai_finding']['flags']}`",
            f"- Adjudication: **{r['discrepancy_adjudication']}**",
            f"- Approval readiness: **{r['approval_readiness']}**",
            f"- Rationale: {r['rationale']}",
            f"- NCERT: {r['ncert_evidence']['location']} — {r['ncert_evidence']['quote'][:220]}...",
            f"- External conflict: {r['ncert_evidence'].get('external_knowledge_conflict')}",
            "",
        ]
    lines += [
        "## Database safety",
        "",
        "```json",
        json.dumps({"before": before, "after": after, "body_fps_unchanged": body_unchanged}, indent=2),
        "```",
        "",
        "## Assertions",
        "",
        "- READ-ONLY",
        "- DATABASE UNCHANGED",
        "- NO APPROVAL",
        "- NO PUBLICATION",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": verdict,
                "approve_ready": approve_ready,
                "unresolved_warn": len(unresolved_warn),
                "unresolved_disc": len(unresolved_disc),
                "repair": repair_n,
                "human": human_n,
                "db_ok": db_ok,
                "artifacts": [str(OUT_MD), str(OUT_JSON)],
            },
            indent=2,
        )
    )
    return 0 if verdict.startswith("GREEN") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
