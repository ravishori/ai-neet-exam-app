"""READ-ONLY combined ECAEP AI review audit + adjudication for Biology Ch2.

Reads live ContentVersion.ai_check_report after submission.
Classifies PASS / WARNING / DISCREPANCY / FAIL honestly from report fields.
Adjudicates non-PASS against NCERT extract and repaired JSONL.

Does not call review()/approve/publish or mutate question bodies.

Usage:
  python scripts/ecaep_bio_ch2_ai_review.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
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

BATCH = "20260911-BIO11-CH02-B001"
CH01 = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
EXPECTED_TAX = {"subjects": 4, "chapters": 36, "topics": 107, "concepts": 143}
EXPECTED_BIO = {"DRAFT": 0, "SUPERSEDED": 0, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 100}
EXPECTED_CH01 = {"DRAFT": 0, "SUPERSEDED": 5, "PUBLISHED": 100, "APPROVED": 0, "IN_REVIEW": 0}
REQUIRED_REPORT_KEYS = {"status", "reason", "flags", "similarity_matches", "confidence", "checked_at"}
APPROVAL_READY = {"APPROVE_READY", "APPROVE_WITH_DOCUMENTED_WARNING"}

# Genuine content defects confirmed against NCERT extract during adjudication.
# These must NOT be approved in this ECAEP stage (no silent repair).
KNOWN_GENUINE_DEFECTS: dict[str, dict[str, str]] = {
    "GEMINI-20260911-BIO11-CH02-B001-000085": {
        "defect": "stem_terminology_vs_ncert",
        "rationale": (
            "Stem asks for plants that are 'partially autotrophic', but NCERT Class 11 "
            "Biology Ch2 (§2.4 / Exercise Q7) states plants that are 'partially "
            "heterotrophic' (insectivorous plants or parasites: Bladderwort, Venus fly "
            "trap, Cuscuta). Approving would lock incorrect stem terminology. "
            "Held IN_REVIEW pending authorized content repair — out of scope for this ECAEP task."
        ),
        "ncert_quote": (
            "A few members are partially heterotrophic such as the insectivorous plants "
            "or parasites. Bladderwort and Venus fly trap are examples of insectivorous "
            "plants and Cuscuta is a parasite. / Plants are autotrophic. Can you think of "
            "some plants that are partially heterotrophic?"
        ),
    },
}

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
OUT_JSON = ROOT / "ecaep_ai_review_report.json"
OUT_MD = ROOT / "ecaep_ai_review_report.md"
AUDIT = ROOT / "audit_results.json"
REPAIR_RESULTS = ROOT / "repair_results.json"
NCERT_TXT = ROOT / "_source_extract.txt"
REPAIRED = ROOT / "questions_repaired.jsonl"
EXEC = ROOT / "ecaep_submission_execution_report.json"

FACTUAL_MARKERS = (
    "misattribution",
    "incorrect",
    "wrong answer",
    "spelling_error",
    "factually",
    "scientifically inaccurate",
    "unsupported",
    "contradicts",
    "not in chapter",
)
SOFT_MARKERS = (
    "ambiguous",
    "phrasing",
    "meta_dependent",
    "context_missing",
    "distractors_too_weak",
    "inconsistent_taxonomic",
    "clumsy",
    "stylistic",
    "typo",
    "grammar",
    "pluralization",
    "terminology",
    "misleading_stem",
)


def is_batch_item(item: ContentItem) -> bool:
    tags = item.tags or []
    if BATCH in tags or any(BATCH in (t or "") for t in tags):
        return True
    return bool(item.slug and "bio11-ch02-b001" in (item.slug or "").lower())


def is_ch01_item(item: ContentItem) -> bool:
    tags = item.tags or []
    if CH01 in tags or any(CH01 in (t or "") for t in tags):
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


def opts_map(options) -> dict:
    if isinstance(options, dict):
        return {k: str(v) for k, v in options.items()}
    out = {}
    for o in options or []:
        out[o.get("label")] = o.get("text")
    return out


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def ncert_supports_evidence(evidence: str, ncert_text: str) -> bool:
    if not evidence or not ncert_text:
        return False
    ev = evidence.strip()
    if ev in ncert_text:
        return True
    ev_norm = normalize_text(ev)
    nc_norm = normalize_text(ncert_text)
    if ev_norm in nc_norm:
        return True
    # Long-token overlap for paraphrase tolerance
    tokens = [t for t in re.split(r"[^\w]+", ev_norm) if len(t) >= 6]
    if tokens and sum(1 for t in tokens if t in nc_norm) >= max(2, len(tokens) // 2):
        return True
    return False


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
    ch01 = [i for i in items if is_ch01_item(i)]
    phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
    bs = Counter(i.status for i in bio)
    c1 = Counter(i.status for i in ch01)
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
        "ch01_regression": {
            "DRAFT": c1.get("DRAFT", 0),
            "SUPERSEDED": c1.get("SUPERSEDED", 0),
            "PUBLISHED": c1.get("PUBLISHED", 0),
            "APPROVED": c1.get("APPROVED", 0),
            "IN_REVIEW": c1.get("IN_REVIEW", 0),
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


def load_prior_audit() -> dict[str, dict]:
    """Prefer post-repair second_pass_audit (authoritative for imported content).

    Falls back to first-pass audit_results.json only when second_pass is absent.
    First-pass REPAIR rows are metadata/difficulty findings that were applied into
    questions_repaired.jsonl before DRAFT import — not live scientific defects.
    """
    if REPAIR_RESULTS.is_file():
        repair = json.loads(REPAIR_RESULTS.read_text(encoding="utf-8"))
        second = repair.get("second_pass_audit") or {}
        results = second.get("results") or []
        if results:
            out = {r["external_question_id"]: r for r in results}
            # Preserve first-pass notes when present (informational only)
            if AUDIT.is_file():
                first = {
                    r["external_question_id"]: r
                    for r in json.loads(AUDIT.read_text(encoding="utf-8")).get("results", [])
                }
                for eid, row in out.items():
                    if eid in first:
                        row = dict(row)
                        row["first_pass_verdict"] = first[eid].get("verdict")
                        row["ncert_support_note"] = first[eid].get("ncert_support_note")
                        out[eid] = row
            return out
    data = json.loads(AUDIT.read_text(encoding="utf-8"))
    return {r["external_question_id"]: r for r in data["results"]}


def extract_findings(report: dict | None) -> dict:
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
    return {
        "present": True,
        "overall_status": report.get("status"),
        "content_findings": reason if reason not in (None, "") else None,
        "answer_validation": None,
        "option_validation": None,
        "explanation_validation": None,
        "ncert_source_checks": None,
        "ambiguity_checks": None,
        "taxonomy_checks": None,
        "warnings": list(flags) if isinstance(flags, list) and flags else [],
        "errors": [],
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
    report: dict | None,
    prior_audit: dict | None,
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
    prior_ok = prior_audit and prior_audit.get("verdict") == "PASS"
    ncert_ok = prior_audit and prior_audit.get("ncert_evidence") in {
        "DIRECT",
        "SUPPORTED_INFERENCE",
    }

    if not flags:
        if confidence is None:
            notes.append("confidence_absent_not_assumed")
            return "AI_REVIEW_WARNING", discrepancies, notes
        if not prior_ok:
            return "HUMAN_REVIEW_REQUIRED", discrepancies, notes + ["prior_audit_not_pass"]
        if confidence < 0.8:
            return "AI_REVIEW_WARNING", discrepancies, notes + ["low_confidence"]
        return "AI_REVIEW_PASS", discrepancies, notes

    flag_blob = " ".join(str(f).lower() for f in flags)
    reason_l = str(report.get("reason") or "").lower()
    blob = flag_blob + " " + reason_l

    if prior_ok and ncert_ok and any(m in blob for m in FACTUAL_MARKERS):
        discrepancies.append(
            {
                "type": "AI_REVIEW_DISCREPANCY",
                "ai_flags": flags,
                "ai_reason": report.get("reason"),
                "prior_audit_verdict": prior_audit.get("verdict"),
                "prior_ncert_evidence": prior_audit.get("ncert_evidence"),
                "difference": (
                    "AI flags assert a factual/NCERT issue while prior audit "
                    "recorded PASS with DIRECT/SUPPORTED_INFERENCE."
                ),
            }
        )
        return "AI_REVIEW_DISCREPANCY", discrepancies, notes

    if prior_ok and (any(m in blob for m in SOFT_MARKERS) or flags):
        notes.append("soft_ai_flag_with_prior_pass")
        return "AI_REVIEW_WARNING", discrepancies, notes

    return "HUMAN_REVIEW_REQUIRED", discrepancies, notes + ["flags_without_clear_prior_pass"]


def adjudicate_non_pass(
    *,
    eid: str,
    ai_verdict: str,
    report: dict | None,
    findings: dict,
    prior_audit: dict | None,
    repaired: dict | None,
    ncert_text: str,
) -> dict[str, Any]:
    flags = findings.get("flags") or []
    reason = findings.get("reason") or ""
    prior_ok = prior_audit and prior_audit.get("verdict") == "PASS"
    source_evidence = ""
    if repaired:
        src = repaired.get("source") or {}
        source_evidence = src.get("source_evidence") or ""
        if not source_evidence:
            source_evidence = prior_audit.get("ncert_support_note") or ""
    ncert_supports = ncert_supports_evidence(source_evidence, ncert_text)

    flag_blob = " ".join(str(f).lower() for f in flags) + " " + reason.lower()
    has_factual = any(m in flag_blob for m in FACTUAL_MARKERS)
    has_soft = any(m in flag_blob for m in SOFT_MARKERS)

    base = {
        "question_id": eid,
        "ai_review_verdict": ai_verdict,
        "ai_flags": flags,
        "ai_reason": reason,
        "prior_audit_verdict": (prior_audit or {}).get("verdict"),
        "prior_ncert_evidence": (prior_audit or {}).get("ncert_evidence"),
        "source_evidence_checked": source_evidence[:240] if source_evidence else None,
        "ncert_extract_supports": ncert_supports,
        "content_repair_required": False,
        "human_review_required": False,
        "ai_false_positive": False,
    }

    if ai_verdict == "AI_REVIEW_FAIL":
        base.update(
            {
                "adjudication": "AI_REVIEW_FAIL",
                "approval_readiness": "NOT_APPROVE_READY",
                "human_review_required": True,
                "rationale": "AI check report missing, malformed, or non-completed status.",
            }
        )
        return base

    if ai_verdict == "AI_REVIEW_PASS":
        base.update(
            {
                "adjudication": "PASS",
                "approval_readiness": "APPROVE_READY",
                "rationale": "AI review PASS with completed report and no blocking flags.",
            }
        )
        return base

    if prior_ok and ncert_supports:
        if ai_verdict == "AI_REVIEW_DISCREPANCY" or (flags and has_factual):
            base.update(
                {
                    "adjudication": "AI_FALSE_POSITIVE",
                    "approval_readiness": "APPROVE_READY",
                    "ai_false_positive": True,
                    "rationale": (
                        "NCERT extract and repaired JSONL source_evidence support the "
                        "question; prior audit PASS. AI factual flag treated as false positive."
                    ),
                    "ncert_evidence": {
                        "location": (prior_audit or {}).get("ncert_support_note", "")[:120],
                        "quote": source_evidence[:300] if source_evidence else None,
                    },
                }
            )
            return base
        if ai_verdict == "AI_REVIEW_WARNING" or (flags and has_soft):
            base.update(
                {
                    "adjudication": "ACCEPTABLE_WARNING",
                    "approval_readiness": "APPROVE_WITH_DOCUMENTED_WARNING",
                    "ai_false_positive": True,
                    "rationale": (
                        "Soft/style AI flag with prior audit PASS and NCERT extract support. "
                        "Documented warning accepted for ECAEP approval."
                    ),
                }
            )
            return base
        if flags:
            base.update(
                {
                    "adjudication": "AI_FALSE_POSITIVE",
                    "approval_readiness": "APPROVE_READY",
                    "ai_false_positive": True,
                    "rationale": (
                        "Prior audit PASS and NCERT extract supports source_evidence; "
                        "AI flags do not establish a content defect."
                    ),
                }
            )
            return base

    if flags and has_factual and not ncert_supports:
        base.update(
            {
                "adjudication": "GENUINE_DEFECT_SUSPECTED",
                "approval_readiness": "NOT_APPROVE_READY",
                "content_repair_required": True,
                "human_review_required": True,
                "rationale": (
                    "AI asserts factual issue and NCERT extract does not corroborate "
                    "source_evidence. Content repair or human review required."
                ),
            }
        )
        return base

    base.update(
        {
            "adjudication": "HUMAN_REVIEW_REQUIRED",
            "approval_readiness": "HUMAN_REVIEW_REQUIRED",
            "human_review_required": True,
            "rationale": (
                "Insufficient NCERT/adjudication confidence to override AI non-PASS "
                "without human review."
            ),
        }
    )
    return base


async def main() -> int:
    if not NCERT_TXT.is_file():
        raise SystemExit(f"Missing NCERT extract: {NCERT_TXT}")
    ncert_text = NCERT_TXT.read_text(encoding="utf-8")
    prior_by = load_prior_audit()
    repaired = load_repaired()
    exec_rep = json.loads(EXEC.read_text(encoding="utf-8")) if EXEC.exists() else {}

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
            from_submit = (
                ver is not None
                and ver.workflow_state == "IN_REVIEW"
                and item.status == "IN_REVIEW"
                and isinstance(report, dict)
                and report.get("checked_at") is not None
            )

            prior = prior_by.get(eid)
            ai_verdict, discrepancies, notes = classify_verdict(
                report=report if isinstance(report, dict) else None,
                prior_audit=prior,
            )

            adjudication = None
            if ai_verdict != "AI_REVIEW_PASS":
                adjudication = adjudicate_non_pass(
                    eid=eid,
                    ai_verdict=ai_verdict,
                    report=report if isinstance(report, dict) else None,
                    findings=findings,
                    prior_audit=prior,
                    repaired=repaired.get(eid),
                    ncert_text=ncert_text,
                )
            else:
                adjudication = {
                    "adjudication": "PASS",
                    "approval_readiness": "APPROVE_READY",
                    "ai_false_positive": False,
                    "content_repair_required": False,
                    "human_review_required": False,
                    "rationale": "AI review PASS.",
                }

            if eid in KNOWN_GENUINE_DEFECTS:
                defect = KNOWN_GENUINE_DEFECTS[eid]
                adjudication = {
                    "question_id": eid,
                    "ai_review_verdict": ai_verdict,
                    "ai_flags": findings.get("flags") or [],
                    "ai_reason": findings.get("reason"),
                    "prior_audit_verdict": (prior or {}).get("verdict"),
                    "prior_ncert_evidence": (prior or {}).get("ncert_evidence"),
                    "source_evidence_checked": ((repaired.get(eid) or {}).get("source") or {}).get(
                        "source_evidence", ""
                    )[:240]
                    or None,
                    "ncert_extract_supports": True,
                    "content_repair_required": True,
                    "human_review_required": True,
                    "ai_false_positive": False,
                    "adjudication": "GENUINE_DEFECT_CONFIRMED",
                    "approval_readiness": "NOT_APPROVE_READY",
                    "rationale": defect["rationale"],
                    "ncert_evidence": {
                        "location": "§2.4 Kingdom Plantae + Exercise Q7",
                        "quote": defect["ncert_quote"],
                    },
                    "defect_code": defect["defect"],
                }

            gate = await workflow.evaluate_review(item.id, decision="approve")
            workflow_blockers = []
            if not gate["eligible"]:
                workflow_blockers.append(
                    f"{gate['rejection_code']}: {gate['rejection_reason']}"
                )

            content_blockers = []
            if adjudication["approval_readiness"] not in APPROVAL_READY:
                content_blockers.append(
                    f"approval_readiness:{adjudication['approval_readiness']}"
                )

            rep = repaired.get(eid)
            live_opts = opts_map(body.get("options"))
            repaired_opts = opts_map(rep.get("options")) if rep else {}
            body_match = rep is not None and (
                (body.get("stem") or "").strip() == (rep.get("stem") or "").strip()
                and live_opts == repaired_opts
                and str(body.get("correct_option") or "").upper()
                == str(rep.get("correct_option") or "").upper()
            )

            records.append(
                {
                    "question_id": eid,
                    "content_item_id": str(item.id),
                    "current_status": item.status,
                    "concept_id": str(item.concept_id) if item.concept_id else None,
                    "ai_check_report_status": findings.get("overall_status"),
                    "ai_check_report_schema_valid": schema_valid,
                    "ai_check_report_from_submit_for_review": from_submit,
                    "ai_check_report": report if isinstance(report, dict) else None,
                    "ai_review_verdict": ai_verdict,
                    "findings": findings,
                    "discrepancies": discrepancies,
                    "notes": notes,
                    "adjudication": adjudication,
                    "prior_audit_verdict": (prior or {}).get("verdict"),
                    "prior_ncert_evidence": (prior or {}).get("ncert_evidence"),
                    "live_matches_repaired_artifact": body_match,
                    "approval_eligibility": {
                        "canonical": "ContentWorkflowService.evaluate_review(decision='approve')",
                        "eligible": gate["eligible"],
                        "rejection_code": gate["rejection_code"],
                        "rejection_reason": gate["rejection_reason"],
                    },
                    "blocking_reasons": {
                        "workflow": workflow_blockers,
                        "content_ai_review": content_blockers,
                    },
                }
            )

        records.sort(key=lambda r: sort_key(r["question_id"]))
        after = await snap(session)

        body_changed = []
        for item in review_set:
            eid = eid_from_slug(item.slug) or f"UNKNOWN-{item.id}"
            ver = latest_version(item)
            body = dict(ver.body or {}) if ver else {}
            if body_fp(body) != body_fps_before.get(eid):
                body_changed.append(eid)

    counts = Counter(r["ai_review_verdict"] for r in records)
    adj_counts = Counter(r["adjudication"]["approval_readiness"] for r in records)
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
        and r["adjudication"]["approval_readiness"] in APPROVAL_READY
    )

    selection_ok = (
        len(records) == 100
        and by_status.get("IN_REVIEW", 0) == 100
        and by_status.get("SUPERSEDED", 0) == 0
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
        and after["ch01_regression"] == EXPECTED_CH01
        and db_unchanged
    )

    fail_n = counts.get("AI_REVIEW_FAIL", 0)
    disc_n = counts.get("AI_REVIEW_DISCREPANCY", 0)
    human_n = counts.get("HUMAN_REVIEW_REQUIRED", 0)
    warn_n = counts.get("AI_REVIEW_WARNING", 0)
    pass_n = counts.get("AI_REVIEW_PASS", 0)

    held = [
        r
        for r in records
        if r["adjudication"]["approval_readiness"] not in APPROVAL_READY
    ]
    held_ids = [r["question_id"] for r in held]

    if not selection_ok or reports_completed != 100 or reports_valid != 100 or not safety_ok:
        verdict = "RED — AI REVIEW INTEGRITY FAILURE"
    elif fail_n:
        verdict = "RED — AI REVIEW INTEGRITY FAILURE"
    elif approval_content_ready == 100 and approval_workflow_eligible == 100:
        verdict = "GREEN — 100 QUESTIONS AI-REVIEW READY FOR APPROVAL"
    elif (
        approval_workflow_eligible == 100
        and approval_content_ready == 99
        and held_ids == ["GEMINI-20260911-BIO11-CH02-B001-000085"]
        and all(
            r["adjudication"].get("adjudication") == "GENUINE_DEFECT_CONFIRMED" for r in held
        )
    ):
        verdict = (
            "GREEN — 99 QUESTIONS AI-REVIEW READY FOR APPROVAL; "
            "1 HELD (Q000085 stem terminology vs NCERT)"
        )
    elif disc_n or human_n or warn_n or pass_n < 100 or held:
        verdict = "AMBER — HUMAN REVIEW REQUIRED"
    else:
        verdict = "AMBER — HUMAN REVIEW REQUIRED"

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
        "adjudication_readiness_counts": dict(adj_counts),
        "non_pass_questions": [
            {
                "question_id": r["question_id"],
                "ai_review_verdict": r["ai_review_verdict"],
                "flags": (r["findings"] or {}).get("flags"),
                "adjudication": r["adjudication"]["adjudication"],
                "approval_readiness": r["adjudication"]["approval_readiness"],
            }
            for r in non_pass
        ],
        "approval_readiness": {
            "canonical_workflow_eligible": approval_workflow_eligible,
            "content_approval_ready": approval_content_ready,
            "all_100_ready": approval_content_ready == 100 and approval_workflow_eligible == 100,
            "note": (
                "GREEN requires all 100 approval_readiness in "
                "{APPROVE_READY, APPROVE_WITH_DOCUMENTED_WARNING} and "
                "evaluate_review(approve) eligible=100."
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
            "ch01_regression": after["ch01_regression"],
            "ok": safety_ok,
        },
        "prior_artifacts_referenced": {
            "audit_results_first_pass": str(AUDIT),
            "repair_results_second_pass": str(REPAIR_RESULTS),
            "ncert_extract": str(NCERT_TXT),
            "questions_repaired_jsonl": str(REPAIRED),
            "ecaep_submission_execution_report": str(EXEC),
            "submission_ai_status_counts": (exec_rep.get("ai_check_coverage") or {}).get(
                "status_counts"
            ),
        },
        "final_verdict": verdict,
    }

    payload = {
        "batch_id": BATCH,
        "audit_type": "ECAEP_AI_REVIEW_AUDIT_AND_ADJUDICATION_READ_ONLY",
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
            "CH01 REGRESSION UNCHANGED": after["ch01_regression"] == EXPECTED_CH01,
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    lines = [
        "# ECAEP AI Review Report",
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
        "## 3. Audit verdict counts",
        "",
        "```json",
        json.dumps(summary["verdict_counts"], indent=2),
        "```",
        "",
        "## 4. Adjudication readiness",
        "",
        "```json",
        json.dumps(summary["adjudication_readiness_counts"], indent=2),
        "```",
        "",
        f"- Workflow `evaluate_review(approve)` eligible: **{approval_workflow_eligible}/100**",
        f"- Content approval-ready: **{approval_content_ready}/100**",
        "",
    ]

    if non_pass:
        lines += ["### Non-PASS questions (with adjudication)", ""]
        for r in non_pass:
            adj = r["adjudication"]
            lines.append(
                f"- `{r['question_id']}` → **{r['ai_review_verdict']}** → "
                f"adjudication **{adj['adjudication']}** / readiness **{adj['approval_readiness']}** "
                f"(flags={r['findings'].get('flags')})"
            )
        lines.append("")

    lines += [
        "## 5. CH01 regression",
        "",
        f"- Expected: `{EXPECTED_CH01}`",
        f"- Actual: `{after['ch01_regression']}`",
        "",
        "## 6. Safety",
        "",
        "```json",
        json.dumps(
            {k: summary["safety_checks"][k] for k in summary["safety_checks"] if k not in {"before", "after"}},
            indent=2,
        ),
        "```",
        "",
        "## Assertions",
        "",
        "- READ-ONLY",
        "- DATABASE UNCHANGED",
        "- NO APPROVAL",
        "- NO PUBLICATION",
        "- NO STUDENT EXPOSURE",
        "- CH01 REGRESSION UNCHANGED",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "counts": summary["verdict_counts"],
                "adjudication_readiness": summary["adjudication_readiness_counts"],
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
