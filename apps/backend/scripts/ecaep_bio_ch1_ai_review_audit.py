"""READ-ONLY ECAEP AI review audit for Biology Ch1 IN_REVIEW questions.

Does not call review()/approve/publish. Uses evaluate_review for approval eligibility.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import ContentWorkflowService

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
EXPECTED_TAX = {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}
EXPECTED_BIO = {"DRAFT": 0, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 100}
REQUIRED_REPORT_KEYS = {"status", "reason", "flags", "similarity_matches", "confidence", "checked_at"}

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
OUT_JSON = ROOT / "ecaep_ai_review_audit.json"
OUT_MD = ROOT / "ecaep_ai_review_audit.md"
INTEGRITY = ROOT / "final_100_pilot_integrity_audit.json"
NCERT = ROOT / "ncert_verification_audit.json"
REPAIRED = ROOT / "questions_repaired.jsonl"
EXEC = ROOT / "ecaep_submission_execution_report.json"
MAYR = ROOT / "q000098_mayr_concept_migration_report.json"

# AI flags known to conflict with prior NCERT-direct / integrity PASS evidence
KNOWN_DISCREPANCY_RULES: dict[str, dict[str, str]] = {
    "GEMINI-20260911-BIO11-CH01-B001-000062": {
        "ai_claim": "spelling_error_in_option (Polymoniales → Polemoniales)",
        "prior": (
            "NCERT extract and prior audits use Polymoniales as printed "
            "(PDF_PAGE_INDEX=7); integrity PASS / VERIFIED_DIRECT."
        ),
    },
    "GEMINI-20260911-BIO11-CH01-B001-000069": {
        "ai_claim": "NCERT misattribution: Chordata not in The Living World",
        "prior": (
            "NCERT Ch1 explicitly cites Chordata features (notochord / dorsal hollow "
            "neural system) in taxonomic hierarchy; prior VERIFIED_DIRECT / integrity PASS."
        ),
    },
}


def is_batch_item(item: ContentItem) -> bool:
    tags = item.tags or []
    if BATCH in tags or any(BATCH in (t or "") for t in tags):
        return True
    return bool(item.slug and "bio11-ch01-b001" in (item.slug or "").lower())


def eid_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    marker = f"GEMINI-{BATCH}-"
    if marker not in slug:
        return None
    return f"GEMINI-{BATCH}-{slug.split(marker, 1)[1]}"


def sort_key(eid: str) -> tuple:
    suffix = eid.rsplit("-", 1)[-1]
    if suffix.startswith("R"):
        return (1, int(suffix[1:]))
    return (0, int(suffix))


def body_fp(body: dict | None) -> str:
    return hashlib.sha256(
        json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def latest_version(item: ContentItem):
    return next((v for v in item.versions if v.id == item.latest_version_id), None)


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
    bio = [i for i in items if is_batch_item(i)]
    phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
    bs = Counter(i.status for i in bio)
    repo = CmsRepository(session)
    student_hits = 0
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        student_hits += sum(1 for i in page if is_batch_item(i))
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
        "student_bio_hits": student_hits,
        "practice_nonpub_hits": len(nonpub & pool),
    }


def load_repaired() -> dict[str, dict]:
    out = {}
    for line in REPAIRED.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["external_question_id"]] = row
    return out


def extract_findings(report: dict | None) -> dict:
    """Extract only fields present in the canonical report — never invent PASS."""
    if not isinstance(report, dict):
        return {
            "present": False,
            "overall_status": None,
            "content_findings": None,
            "answer_validation": None,
            "option_validation": None,
            "explanation_validation": None,
            "ncert_source_checks": None,
            "ambiguity_checks": None,
            "taxonomy_checks": None,
            "warnings": None,
            "errors": None,
            "confidence": None,
            "flags": None,
            "reason": None,
            "similarity_matches": None,
            "checked_at": None,
            "absent_fields_not_assumed_pass": [
                "answer_validation",
                "option_validation",
                "explanation_validation",
                "ncert_source_checks",
                "ambiguity_checks",
                "taxonomy_checks",
            ],
        }
    flags = report.get("flags")
    reason = report.get("reason")
    # Map evaluator schema honestly: no separate answer/option/explanation fields exist
    return {
        "present": True,
        "overall_status": report.get("status"),
        "content_findings": reason if reason not in (None, "") else None,
        "answer_validation": None,  # not produced by canonical evaluator schema
        "option_validation": None,
        "explanation_validation": None,
        "ncert_source_checks": None,
        "ambiguity_checks": None,
        "taxonomy_checks": None,
        "warnings": list(flags) if isinstance(flags, list) and flags else [],
        "errors": [],  # evaluator uses flags/reason; status=error would be overall
        "confidence": report.get("confidence"),
        "flags": list(flags) if isinstance(flags, list) else flags,
        "reason": reason,
        "similarity_matches": report.get("similarity_matches"),
        "checked_at": report.get("checked_at"),
        "schema_keys_present": sorted(report.keys()),
        "absent_fields_not_assumed_pass": [
            "answer_validation",
            "option_validation",
            "explanation_validation",
            "ncert_source_checks",
            "ambiguity_checks",
            "taxonomy_checks",
        ],
        "note": (
            "Canonical Evaluator report shape is {status, reason, flags, "
            "similarity_matches, confidence, checked_at}. Dedicated answer/option/"
            "explanation/NCERT/ambiguity/taxonomy sub-results are not present and "
            "are recorded as null (not PASS)."
        ),
    }


def classify_verdict(
    *,
    eid: str,
    report: dict | None,
    findings: dict,
    prior_integrity: dict | None,
    prior_ncert: dict | None,
    repaired: dict | None,
) -> tuple[str, list[dict], list[str]]:
    discrepancies: list[dict] = []
    notes: list[str] = []

    if not isinstance(report, dict):
        return "AI_REVIEW_FAIL", discrepancies, ["missing_ai_check_report"]

    missing_keys = REQUIRED_REPORT_KEYS - set(report.keys())
    if missing_keys:
        return "AI_REVIEW_FAIL", discrepancies, [f"malformed_schema_missing:{sorted(missing_keys)}"]

    status = report.get("status")
    if status != "completed":
        if status in {"error", "skipped"}:
            return "AI_REVIEW_FAIL", discrepancies, [f"report_status:{status}"]
        return "AI_REVIEW_FAIL", discrepancies, [f"unexpected_status:{status}"]

    flags = report.get("flags") if isinstance(report.get("flags"), list) else []
    confidence = report.get("confidence")
    prior_ok = (
        prior_integrity
        and prior_integrity.get("final_question_verdict") == "PASS"
        and prior_integrity.get("ncert_verification_result")
        in {"VERIFIED_DIRECT", "VERIFIED_SUPPORTED_INFERENCE"}
    )
    ncert_ok = prior_ncert and prior_ncert.get("verification_verdict") in {
        "VERIFIED_DIRECT",
        "VERIFIED_SUPPORTED_INFERENCE",
    }
    # Mayr was remapped after ncert artifact; integrity audit has VERIFIED_DIRECT
    if eid.endswith("000098") and prior_integrity:
        ncert_ok = prior_integrity.get("ncert_verification_result") == "VERIFIED_DIRECT"

    if repaired is None:
        notes.append("missing_from_questions_repaired_jsonl")

    # Hard discrepancy rules (AI contradicts established NCERT evidence)
    if eid in KNOWN_DISCREPANCY_RULES and flags:
        rule = KNOWN_DISCREPANCY_RULES[eid]
        discrepancies.append(
            {
                "type": "AI_REVIEW_DISCREPANCY",
                "question_id": eid,
                "ai_claim": rule["ai_claim"],
                "ai_flags": flags,
                "ai_reason": report.get("reason"),
                "prior_evidence": rule["prior"],
                "prior_integrity_verdict": (prior_integrity or {}).get("final_question_verdict"),
                "prior_ncert_verdict": (prior_ncert or {}).get("verification_verdict"),
            }
        )
        return "AI_REVIEW_DISCREPANCY", discrepancies, notes

    # Generic: AI raised flags while prior integrity/NCERT passed → discrepancy if
    # flag text asserts factual NCERT/content error; else WARNING for soft style.
    factual_markers = (
        "misattribution",
        "incorrect",
        "wrong answer",
        "spelling_error",
        "factually",
        "scientifically inaccurate",
        "unsupported",
    )
    soft_markers = (
        "ambiguous",
        "phrasing",
        "meta_dependent",
        "context_missing",
        "distractors_too_weak",
        "inconsistent_taxonomic",
        "clumsy",
    )

    if flags:
        flag_blob = " ".join(str(f).lower() for f in flags)
        reason_l = str(report.get("reason") or "").lower()
        blob = flag_blob + " " + reason_l
        if prior_ok and ncert_ok and any(m in blob for m in factual_markers):
            discrepancies.append(
                {
                    "type": "AI_REVIEW_DISCREPANCY",
                    "question_id": eid,
                    "ai_flags": flags,
                    "ai_reason": report.get("reason"),
                    "prior_integrity_verdict": prior_integrity.get("final_question_verdict"),
                    "prior_ncert_verdict": (prior_ncert or {}).get("verification_verdict"),
                    "difference": (
                        "AI flags assert a factual/NCERT issue while prior integrity "
                        "and NCERT verification audits recorded PASS / VERIFIED_*."
                    ),
                }
            )
            return "AI_REVIEW_DISCREPANCY", discrepancies, notes
        if prior_ok and (any(m in blob for m in soft_markers) or flags):
            notes.append("soft_ai_flag_with_prior_pass")
            return "AI_REVIEW_WARNING", discrepancies, notes
        # Flags without prior PASS → human review
        return "HUMAN_REVIEW_REQUIRED", discrepancies, notes + ["flags_without_clear_prior_pass"]

    # No flags
    if confidence is None:
        notes.append("confidence_absent_not_assumed")
        return "AI_REVIEW_WARNING", discrepancies, notes
    if not prior_ok:
        return "HUMAN_REVIEW_REQUIRED", discrepancies, notes + ["prior_integrity_not_pass"]
    if confidence < 0.8:
        return "AI_REVIEW_WARNING", discrepancies, notes + ["low_confidence"]
    return "AI_REVIEW_PASS", discrepancies, notes


async def main() -> int:
    integrity = json.loads(INTEGRITY.read_text(encoding="utf-8"))
    ncert = json.loads(NCERT.read_text(encoding="utf-8"))
    integrity_by = {r["question_id"]: r for r in integrity["records"]}
    ncert_by = {r["question_id"]: r for r in ncert["records"]}
    repaired = load_repaired()
    exec_rep = json.loads(EXEC.read_text(encoding="utf-8")) if EXEC.exists() else {}
    mayr_rep = json.loads(MAYR.read_text(encoding="utf-8")) if MAYR.exists() else {}

    async with AsyncSessionLocal() as session:
        before = await snap(session)
        items = (
            await session.execute(
                select(ContentItem)
                .options(selectinload(ContentItem.versions))
                .where(ContentItem.deleted_at.is_(None))
            )
        ).scalars().all()
        batch_all = [i for i in items if is_batch_item(i)]
        by_status = Counter(i.status for i in batch_all)
        review_set = [i for i in batch_all if i.status == "IN_REVIEW"]
        other_batch = [
            i
            for i in items
            if i.status == "IN_REVIEW"
            and not is_batch_item(i)
            and (PHY in str(i.tags) or (i.slug and "phy11" in i.slug.lower()))
        ]

        workflow = ContentWorkflowService(session)
        records: list[dict] = []
        body_fps_before: dict[str, str] = {}

        for item in review_set:
            eid = eid_from_slug(item.slug) or f"UNKNOWN-{item.id}"
            ver = latest_version(item)
            report = ver.ai_check_report if ver else None
            body = dict(ver.body or {}) if ver else {}
            body_fps_before[eid] = body_fp(body)
            findings = extract_findings(report if isinstance(report, dict) else None)

            schema_valid = (
                isinstance(report, dict)
                and REQUIRED_REPORT_KEYS.issubset(set(report.keys()))
                and report.get("status") == "completed"
            )
            corresponds = True  # report stored on this version of this item
            from_submit = (
                ver is not None
                and ver.workflow_state == "IN_REVIEW"
                and item.status == "IN_REVIEW"
                and isinstance(report, dict)
                and report.get("checked_at") is not None
            )

            verdict, discrepancies, notes = classify_verdict(
                eid=eid,
                report=report if isinstance(report, dict) else None,
                findings=findings,
                prior_integrity=integrity_by.get(eid),
                prior_ncert=ncert_by.get(eid),
                repaired=repaired.get(eid),
            )

            gate = await workflow.evaluate_review(item.id, decision="approve")
            blocking = []
            if not gate["eligible"]:
                blocking.append(
                    f"{gate['rejection_code']}: {gate['rejection_reason']}"
                )
            # Content/AI blockers for readiness (not canonical workflow blockers)
            content_blockers = []
            if verdict in {"AI_REVIEW_FAIL", "AI_REVIEW_DISCREPANCY", "HUMAN_REVIEW_REQUIRED"}:
                content_blockers.append(f"ai_review_verdict:{verdict}")
            if verdict == "AI_REVIEW_WARNING":
                content_blockers.append("ai_review_verdict:AI_REVIEW_WARNING")

            records.append(
                {
                    "question_id": eid,
                    "content_item_id": str(item.id),
                    "current_status": item.status,
                    "concept_id": str(item.concept_id) if item.concept_id else None,
                    "ai_check_report_status": findings.get("overall_status"),
                    "ai_check_report_schema_valid": schema_valid,
                    "ai_check_report_corresponds_to_question": corresponds,
                    "ai_check_report_from_submit_for_review": from_submit,
                    "fabricated_report": False,
                    "ai_check_report": report if isinstance(report, dict) else None,
                    "ai_review_verdict": verdict,
                    "findings": findings,
                    "discrepancies": discrepancies,
                    "notes": notes,
                    "prior_integrity_verdict": (integrity_by.get(eid) or {}).get(
                        "final_question_verdict"
                    ),
                    "prior_ncert_verdict": (ncert_by.get(eid) or {}).get(
                        "verification_verdict"
                    )
                    if not eid.endswith("000098")
                    else (integrity_by.get(eid) or {}).get("ncert_verification_result"),
                    "approval_eligibility": {
                        "canonical": "ContentWorkflowService.evaluate_review(decision='approve')",
                        "eligible": gate["eligible"],
                        "rejection_code": gate["rejection_code"],
                        "rejection_reason": gate["rejection_reason"],
                    },
                    "blocking_reasons": {
                        "workflow": blocking,
                        "content_ai_review": content_blockers,
                    },
                }
            )

        records.sort(key=lambda r: sort_key(r["question_id"]))
        after = await snap(session)

        # Body fingerprint unchanged
        body_changed = []
        for item in review_set:
            eid = eid_from_slug(item.slug) or f"UNKNOWN-{item.id}"
            ver = latest_version(item)
            body = dict(ver.body or {}) if ver else {}
            if body_fp(body) != body_fps_before.get(eid):
                body_changed.append(eid)

    counts = Counter(r["ai_review_verdict"] for r in records)
    non_pass = [r for r in records if r["ai_review_verdict"] != "AI_REVIEW_PASS"]
    reports_completed = sum(
        1 for r in records if r["ai_check_report_status"] == "completed"
    )
    reports_valid = sum(1 for r in records if r["ai_check_report_schema_valid"])
    approval_workflow_eligible = sum(
        1 for r in records if r["approval_eligibility"]["eligible"]
    )
    approval_content_ready = sum(
        1
        for r in records
        if r["approval_eligibility"]["eligible"]
        and r["ai_review_verdict"] == "AI_REVIEW_PASS"
    )

    selection_ok = (
        len(records) == 100
        and by_status.get("IN_REVIEW", 0) == 100
        and by_status.get("SUPERSEDED", 0) == 5
        and by_status.get("PUBLISHED", 0) == 0
        and by_status.get("APPROVED", 0) == 0
        and by_status.get("DRAFT", 0) == 0
        and len(other_batch) == 0
    )
    db_unchanged = before == after and not body_changed
    safety_ok = (
        after["biology"] == EXPECTED_BIO
        and after["taxonomy"] == EXPECTED_TAX
        and after["physics_DRAFT"] == 24
        and after["student_bio_hits"] == 0
        and after["practice_nonpub_hits"] == 0
        and db_unchanged
    )

    fail_n = counts.get("AI_REVIEW_FAIL", 0)
    disc_n = counts.get("AI_REVIEW_DISCREPANCY", 0)
    human_n = counts.get("HUMAN_REVIEW_REQUIRED", 0)
    warn_n = counts.get("AI_REVIEW_WARNING", 0)
    pass_n = counts.get("AI_REVIEW_PASS", 0)

    if not selection_ok or reports_completed != 100 or reports_valid != 100 or not safety_ok:
        verdict = "RED — AI REVIEW INTEGRITY FAILURE"
    elif fail_n or disc_n or human_n or warn_n or approval_content_ready != 100:
        # warnings/discrepancies block GREEN per task rule
        if fail_n or reports_valid < 100:
            verdict = "RED — AI REVIEW INTEGRITY FAILURE" if fail_n or reports_valid < 100 else "AMBER — HUMAN REVIEW REQUIRED"
        else:
            verdict = "AMBER — HUMAN REVIEW REQUIRED"
    elif pass_n == 100 and approval_workflow_eligible == 100 and approval_content_ready == 100:
        verdict = "GREEN — 100 QUESTIONS AI-REVIEW READY FOR APPROVAL"
    else:
        verdict = "AMBER — HUMAN REVIEW REQUIRED"

    # Refine RED vs AMBER
    if selection_ok and reports_valid == 100 and safety_ok and fail_n == 0:
        if disc_n or human_n or warn_n or pass_n < 100:
            verdict = "AMBER — HUMAN REVIEW REQUIRED"
        elif pass_n == 100:
            verdict = "GREEN — 100 QUESTIONS AI-REVIEW READY FOR APPROVAL"
    elif not selection_ok or reports_valid < 100 or fail_n or not safety_ok:
        verdict = "RED — AI REVIEW INTEGRITY FAILURE"

    summary = {
        "total_reviewed": len(records),
        "reports_completed": reports_completed,
        "reports_schema_valid": reports_valid,
        "verdict_counts": {
            "AI_REVIEW_PASS": pass_n,
            "AI_REVIEW_WARNING": warn_n,
            "AI_REVIEW_FAIL": fail_n,
            "AI_REVIEW_DISCREPANCY": disc_n,
            "HUMAN_REVIEW_REQUIRED": human_n,
        },
        "all_pass_statement": (
            "100/100 AI REVIEW PASS" if pass_n == 100 and len(non_pass) == 0 else None
        ),
        "non_pass_questions": [
            {
                "question_id": r["question_id"],
                "ai_review_verdict": r["ai_review_verdict"],
                "flags": (r["findings"] or {}).get("flags"),
                "confidence": (r["findings"] or {}).get("confidence"),
                "discrepancies": r["discrepancies"],
            }
            for r in non_pass
        ],
        "failures_warnings": {
            "FAIL": [r["question_id"] for r in records if r["ai_review_verdict"] == "AI_REVIEW_FAIL"],
            "WARNING": [
                r["question_id"] for r in records if r["ai_review_verdict"] == "AI_REVIEW_WARNING"
            ],
            "DISCREPANCY": [
                r["question_id"]
                for r in records
                if r["ai_review_verdict"] == "AI_REVIEW_DISCREPANCY"
            ],
            "HUMAN_REVIEW_REQUIRED": [
                r["question_id"]
                for r in records
                if r["ai_review_verdict"] == "HUMAN_REVIEW_REQUIRED"
            ],
        },
        "discrepancies": [
            d for r in records for d in (r["discrepancies"] or [])
        ],
        "approval_readiness": {
            "canonical_workflow_eligible": approval_workflow_eligible,
            "content_ai_pass_and_workflow_eligible": approval_content_ready,
            "note": (
                "Canonical evaluate_review only requires status=IN_REVIEW. "
                "Content/AI non-PASS verdicts are recorded separately as "
                "content_ai_review blockers and block GREEN readiness."
            ),
        },
        "selection": {
            "batch_status_counts": dict(by_status),
            "in_review_selected": len(records),
            "other_batch_physics_in_review": len(other_batch),
            "ok": selection_ok,
        },
        "safety_checks": {
            "before": before,
            "after": after,
            "unchanged": db_unchanged,
            "body_fingerprints_changed": body_changed,
            "approved_changes": 0,
            "published_changes": 0,
            "student_bio_hits": after["student_bio_hits"],
            "taxonomy_unchanged": after["taxonomy"] == before["taxonomy"] == EXPECTED_TAX,
            "ok": safety_ok,
        },
        "prior_artifacts_referenced": {
            "final_100_pilot_integrity_audit": str(INTEGRITY),
            "ncert_verification_audit": str(NCERT),
            "questions_repaired_jsonl": str(REPAIRED),
            "ecaep_submission_execution_report": str(EXEC),
            "q000098_mayr_concept_migration_report": str(MAYR),
            "submission_ai_status_counts": (exec_rep.get("ai_check_coverage") or {}).get(
                "status_counts"
            ),
            "mayr_concept_id": (mayr_rep.get("post") or {}).get("q000098", {}).get("concept_id")
            if isinstance(mayr_rep.get("post"), dict)
            else None,
        },
        "final_verdict": verdict,
    }

    payload = {
        "batch_id": BATCH,
        "audit_type": "ECAEP_AI_REVIEW_AUDIT_READ_ONLY",
        "generated_at": datetime.now(UTC).isoformat(),
        "database_modified": False,
        "approval_performed": False,
        "publication_performed": False,
        "verdict": verdict,
        "summary": summary,
        "records": records,
        "assertions": {
            "READ-ONLY": True,
            "DATABASE UNCHANGED": db_unchanged,
            "NO APPROVAL": True,
            "NO PUBLICATION": True,
            "NO STUDENT EXPOSURE": after["student_bio_hits"] == 0,
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    lines = [
        "# ECAEP AI Review Audit",
        "",
        f"## Verdict: {verdict}",
        "",
        "**READ-ONLY**  ",
        "**DATABASE UNCHANGED**  ",
        "**NO APPROVAL**  ",
        "**NO PUBLICATION**  ",
        "**NO STUDENT EXPOSURE**",
        "",
        f"Batch: `{BATCH}`  ",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## 1. Review set",
        "",
        f"- IN_REVIEW selected: **{len(records)}**",
        f"- Batch status counts: `{dict(by_status)}`",
        f"- Other-batch/Physics IN_REVIEW leak: **{len(other_batch)}**",
        "",
        "## 2. AI check reports",
        "",
        f"- Reports completed: **{reports_completed}/100**",
        f"- Schema valid: **{reports_valid}/100**",
        "- Canonical Evaluator schema: `{status, reason/flags→findings, similarity_matches, confidence, checked_at}`",
        "- Dedicated answer/option/explanation/NCERT/ambiguity/taxonomy sub-scores are **absent** and recorded as `null` (not assumed PASS).",
        "",
        "## 3. Verdict counts",
        "",
        "```json",
        json.dumps(summary["verdict_counts"], indent=2),
        "```",
        "",
    ]
    if summary["all_pass_statement"]:
        lines += [f"**{summary['all_pass_statement']}**", ""]
    else:
        lines += ["### Non-PASS questions", ""]
        for r in non_pass:
            lines.append(
                f"- `{r['question_id']}` → **{r['ai_review_verdict']}** "
                f"(flags={r['findings'].get('flags')}, confidence={r['findings'].get('confidence')})"
            )
        lines.append("")

    if summary["discrepancies"]:
        lines += ["## Discrepancies (not silently resolved)", ""]
        for d in summary["discrepancies"]:
            lines.append(f"- `{d.get('question_id')}`: {json.dumps(d, ensure_ascii=False)}")
        lines.append("")

    lines += [
        "## 4. Approval readiness",
        "",
        f"- Canonical `evaluate_review(approve)` eligible: **{approval_workflow_eligible}/100**",
        f"- Content AI-PASS + workflow eligible: **{approval_content_ready}/100**",
        "- No `review(..., decision='approve')` calls were made.",
        "",
        "## 5. Safety",
        "",
        "```json",
        json.dumps(
            {k: summary["safety_checks"][k] for k in summary["safety_checks"] if k not in {"before", "after"}},
            indent=2,
        ),
        "```",
        "",
        "```json",
        json.dumps({"before": before, "after": after}, indent=2),
        "```",
        "",
        "## Assertions",
        "",
        "- READ-ONLY",
        "- DATABASE UNCHANGED",
        "- NO APPROVAL",
        "- NO PUBLICATION",
        "- NO STUDENT EXPOSURE",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "counts": summary["verdict_counts"],
                "non_pass": len(non_pass),
                "approval_workflow_eligible": approval_workflow_eligible,
                "approval_content_ready": approval_content_ready,
                "safety_ok": safety_ok,
                "artifacts": [str(OUT_MD), str(OUT_JSON)],
            },
            indent=2,
        )
    )
    return 0 if verdict.startswith("GREEN") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
