"""Execute atomic ECAEP submit_for_review for Biology Ch4 100 DRAFTs.

Uses ContentWorkflowService.submit_for_review(..., commit=False) for each
planned ID, then a single session.commit(). On any failure: session.rollback().

STOPS after submission. Does NOT adjudicate / certify NCERT / publish.

Usage (from apps/backend):
  python scripts/execute_bio_ch4_ecaep_submission.py --dry-preflight
  python scripts/execute_bio_ch4_ecaep_submission.py --commit
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.core.exceptions import AppError
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem, ContentVersion
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import (
    ContentWorkflowError,
    ContentWorkflowService,
)

BATCH = "20260912-BIO11-CH04-B001"
CH01 = "20260911-BIO11-CH01-B001"
CH02 = "20260911-BIO11-CH02-B001"
CH03 = "20260912-BIO11-CH03-B001"
PHY = "20260911-PHY11-CH02-B001"
EXPECTED_SHA = "743bbacfd1a744e85c0a25ff79ed1908c35446d68169efbd8213fd454451b0c9"
EXPECTED_TAX = {"subjects": 4, "chapters": 36, "topics": 125, "concepts": 192}
EXPECTED_CH04_PRE = {"DRAFT": 100, "SUPERSEDED": 0, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 0}
EXPECTED_CH04_POST = {"DRAFT": 0, "SUPERSEDED": 0, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 100}
EXPECTED_CH01 = {"DRAFT": 0, "SUPERSEDED": 5, "PUBLISHED": 100, "APPROVED": 0, "IN_REVIEW": 0}
EXPECTED_CH02 = {"DRAFT": 0, "SUPERSEDED": 1, "PUBLISHED": 100, "APPROVED": 0, "IN_REVIEW": 0}
EXPECTED_CH03 = {"DRAFT": 0, "SUPERSEDED": 0, "PUBLISHED": 100, "APPROVED": 0, "IN_REVIEW": 0}
MEDIUM_Q = {"Q000054", "Q000074", "Q000084", "Q000085"}
ATOMICITY_TEST_COUNT = 3

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
FINAL_JSONL = ROOT / "questions_repaired_final.jsonl"
COMMITTED_MAP = ROOT / "question_taxonomy_mapping_committed.json"
DRY_RUN = ROOT / "ecaep_submission_dry_run.json"
OUT_JSON = ROOT / "ecaep_submission_execution_report.json"
OUT_MD = ROOT / "ecaep_submission_execution_report.md"


class Abort(Exception):
    def __init__(self, condition: str, expected=None, actual=None):
        self.condition = condition
        self.expected = expected
        self.actual = actual
        super().__init__(f"ABORT: {condition} expected={expected!r} actual={actual!r}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_batch(item: ContentItem, batch: str, slug_bit: str) -> bool:
    tags = item.tags or []
    if batch in tags or any(batch in (t or "") for t in tags):
        return True
    return bool(item.slug and slug_bit in (item.slug or "").lower())


def is_ch04(item: ContentItem) -> bool:
    return is_batch(item, BATCH, "bio11-ch04-b001")


def eid_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    marker = f"GEMINI-{BATCH}-"
    if marker not in slug:
        return None
    return f"GEMINI-{BATCH}-{slug.split(marker, 1)[1]}"


def body_fp(body: dict | None) -> str:
    return hashlib.sha256(
        json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def ncert_level(body: dict | None) -> str | None:
    return ((body or {}).get("ncert_evidence") or {}).get("verification_level")


def status_bucket(items: list[ContentItem]) -> dict:
    c = Counter(i.status for i in items)
    return {
        "DRAFT": c.get("DRAFT", 0),
        "SUPERSEDED": c.get("SUPERSEDED", 0),
        "PUBLISHED": c.get("PUBLISHED", 0),
        "APPROVED": c.get("APPROVED", 0),
        "IN_REVIEW": c.get("IN_REVIEW", 0),
    }


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
    ch04 = [i for i in items if is_ch04(i)]
    ch01 = [i for i in items if is_batch(i, CH01, "bio11-ch01-b001")]
    ch02 = [i for i in items if is_batch(i, CH02, "bio11-ch02-b001")]
    ch03 = [i for i in items if is_batch(i, CH03, "bio11-ch03-b001")]
    phy = [i for i in items if is_batch(i, PHY, "phy11-ch02-b001")]
    drafts = [i for i in ch04 if i.status == "DRAFT"]
    repo = CmsRepository(session)
    student_hits = 0
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        student_hits += sum(1 for i in page if is_ch04(i))
        off += 100
        if off >= tot or not page:
            break
    pool = set(await AssessmentRepository(session).published_question_ids_for_scope("FULL", None))
    nonpub = {i.id for i in ch04 if i.status != "PUBLISHED"}
    return {
        "taxonomy": {
            "subjects": tax[0],
            "chapters": tax[1],
            "topics": tax[2],
            "concepts": tax[3],
        },
        "ch04": status_bucket(ch04),
        "ch04_total": len(ch04),
        "ch01_regression": status_bucket(ch01),
        "ch02_regression": status_bucket(ch02),
        "ch03_regression": status_bucket(ch03),
        "physics_DRAFT": Counter(i.status for i in phy).get("DRAFT", 0),
        "mapped_drafts": sum(1 for i in drafts if i.concept_id),
        "mapped_ch04": sum(1 for i in ch04 if i.concept_id),
        "student_ch04_hits": student_hits,
        "practice_nonpub_hits": len(nonpub & pool),
    }


async def load_item_map(session) -> dict[str, ContentItem]:
    items = (
        await session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.deleted_at.is_(None))
        )
    ).scalars().all()
    out: dict[str, ContentItem] = {}
    for i in items:
        if not is_ch04(i):
            continue
        eid = eid_from_slug(i.slug)
        if eid:
            out[eid] = i
    return out


def latest_body(item: ContentItem) -> dict:
    latest = next((v for v in item.versions if v.id == item.latest_version_id), None)
    return dict(latest.body or {}) if latest else {}


def latest_version(item: ContentItem) -> ContentVersion | None:
    return next((v for v in item.versions if v.id == item.latest_version_id), None)


def load_committed_mapping() -> dict:
    mapping = json.loads(COMMITTED_MAP.read_text(encoding="utf-8"))
    if mapping.get("batch_id") != BATCH:
        raise Abort("mapping_batch", BATCH, mapping.get("batch_id"))
    if mapping.get("authoritative_sha256") != EXPECTED_SHA:
        raise Abort("mapping_sha", EXPECTED_SHA, mapping.get("authoritative_sha256"))
    maps = mapping.get("mappings") or []
    if len(maps) != 100:
        raise Abort("mapping_count", 100, len(maps))
    return mapping


def build_plan_ids() -> list[str]:
    qs = [json.loads(l) for l in FINAL_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(qs) != 100:
        raise Abort("jsonl_count", 100, len(qs))
    ids = [q["external_question_id"] for q in qs]
    if len(set(ids)) != 100:
        raise Abort("jsonl_unique", 100, len(set(ids)))
    return ids


async def preflight(session) -> dict:
    sha = sha256_file(FINAL_JSONL)
    if sha != EXPECTED_SHA:
        raise Abort("artifact_sha", EXPECTED_SHA, sha)

    planned_ids = build_plan_ids()
    mapping = load_committed_mapping()
    map_by_eid = {m["question_id"]: m for m in mapping["mappings"]}
    med = {m["qnum"] for m in mapping["mappings"] if m["confidence"] == "MEDIUM"}
    if med != MEDIUM_Q:
        raise Abort("medium_q", sorted(MEDIUM_Q), sorted(med))

    pre = await snap(session)
    if pre["taxonomy"] != EXPECTED_TAX:
        raise Abort("taxonomy", EXPECTED_TAX, pre["taxonomy"])
    if pre["ch04"] != EXPECTED_CH04_PRE or pre["ch04_total"] != 100:
        raise Abort("ch04_pre", EXPECTED_CH04_PRE, pre["ch04"])
    if pre["physics_DRAFT"] != 24:
        raise Abort("physics_DRAFT", 24, pre["physics_DRAFT"])
    if pre["student_ch04_hits"] != 0 or pre["practice_nonpub_hits"] != 0:
        raise Abort("student_safety_pre", 0, pre)
    if pre["ch01_regression"] != EXPECTED_CH01:
        raise Abort("ch01_regression", EXPECTED_CH01, pre["ch01_regression"])
    if pre["ch02_regression"] != EXPECTED_CH02:
        raise Abort("ch02_regression", EXPECTED_CH02, pre["ch02_regression"])
    if pre["ch03_regression"] != EXPECTED_CH03:
        raise Abort("ch03_regression", EXPECTED_CH03, pre["ch03_regression"])
    if pre["mapped_ch04"] != 100:
        raise Abort("mapped_ch04", 100, pre["mapped_ch04"])

    by_eid = await load_item_map(session)
    if len(by_eid) != 100:
        raise Abort("live_item_count", 100, len(by_eid))
    if set(by_eid) != set(planned_ids):
        raise Abort(
            "eid_set_mismatch",
            sorted(set(planned_ids) - set(by_eid))[:5],
            sorted(set(by_eid) - set(planned_ids))[:5],
        )

    fingerprints: dict[str, dict] = {}
    medium_validation: dict = {}
    for eid in planned_ids:
        item = by_eid[eid]
        if item.status != "DRAFT":
            raise Abort("status_not_draft", "DRAFT", item.status)
        if item.deleted_at is not None:
            raise Abort("not_active", None, str(item.deleted_at))
        if item.concept_id is None:
            raise Abort("null_concept", eid, None)
        want = map_by_eid[eid]
        if str(item.concept_id) != want["concept_id"]:
            raise Abort(f"concept_mismatch:{eid}", want["concept_id"], str(item.concept_id))
        body = latest_body(item)
        if ncert_level(body) != "NOT_VERIFIED":
            raise Abort(f"ncert_level:{eid}", "NOT_VERIFIED", ncert_level(body))
        if (body.get("provenance") or {}).get("batch_id") != BATCH and BATCH not in (item.tags or []):
            raise Abort(f"batch_provenance:{eid}", BATCH, (body.get("provenance") or {}).get("batch_id"))
        fingerprints[eid] = {
            "content_item_id": str(item.id),
            "concept_id": str(item.concept_id),
            "topic_id": want["topic_id"],
            "topic_code": want["topic_code"],
            "concept_code": want["concept_code"],
            "qnum": want["qnum"],
            "confidence": want["confidence"],
            "body_sha256": body_fp(body),
            "verification_level": ncert_level(body),
            "status": item.status,
        }
        if want["qnum"] in MEDIUM_Q:
            medium_validation[want["qnum"]] = {
                "ok": True,
                "topic_code": want["topic_code"],
                "concept_code": want["concept_code"],
                "concept_id": want["concept_id"],
                "confidence": want["confidence"],
            }

    if len({f["content_item_id"] for f in fingerprints.values()}) != 100:
        raise Abort("duplicate_content_items", 100, "collision")

    workflow = ContentWorkflowService(session)
    eligibility = []
    for eid in planned_ids:
        item = by_eid[eid]
        gate = await workflow.evaluate_submit_for_review(item.id)
        eligibility.append(
            {
                "question_id": eid,
                "eligible": gate["eligible"],
                "rejection_code": gate["rejection_code"],
                "rejection_reason": gate["rejection_reason"],
            }
        )
        if not gate["eligible"]:
            raise Abort(
                f"eligibility_failed:{eid}",
                "ELIGIBLE",
                f"{gate['rejection_code']}: {gate['rejection_reason']}",
            )

    dry = {
        "batch_id": BATCH,
        "generated_at": datetime.now(UTC).isoformat(),
        "audit_type": "ECAEP_SUBMISSION_DRY_RUN_READ_ONLY",
        "canonical_eligibility": "ContentWorkflowService.evaluate_submit_for_review",
        "authoritative_sha256": sha,
        "selection_count": 100,
        "eligible_count": 100,
        "ineligible_count": 0,
        "deterministic_question_ids": planned_ids,
        "content_item_ids": [fingerprints[e]["content_item_id"] for e in planned_ids],
        "medium_validation": medium_validation,
        "pre_state": pre,
    }
    DRY_RUN.write_text(json.dumps(dry, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    return {
        "pre": pre,
        "fingerprints": fingerprints,
        "eligibility": eligibility,
        "planned_ids": planned_ids,
        "medium_validation": medium_validation,
        "sha": sha,
    }


async def atomicity_rollback_test(session, pf: dict) -> dict:
    workflow = ContentWorkflowService(session)
    test_ids = pf["planned_ids"][:ATOMICITY_TEST_COUNT]
    partial: list[str] = []
    induced = False
    try:
        session.info["defer_commit"] = True
        for eid in test_ids:
            item_id = uuid.UUID(pf["fingerprints"][eid]["content_item_id"])
            await workflow.submit_for_review(item_id, commit=False)
            partial.append(eid)
        raise RuntimeError("induced_submission_failure_after_3")
    except RuntimeError as exc:
        if "induced_submission_failure" in str(exc):
            induced = True
        else:
            raise
    finally:
        await session.rollback()
        session.info.pop("defer_commit", None)

    restored = await snap(session)
    ok = (
        induced
        and restored["ch04"] == EXPECTED_CH04_PRE
        and restored["ch04"]["IN_REVIEW"] == 0
        and restored["ch04"]["DRAFT"] == 100
    )
    return {
        "induced_failure": induced,
        "partial_submit_count": len(partial),
        "partial_question_ids": partial,
        "restored_ch04": restored["ch04"],
        "restored_to_pre": restored["ch04"] == EXPECTED_CH04_PRE,
        "ok": ok,
    }


async def post_verify(session, preflight_data: dict) -> dict:
    post = await snap(session)
    planned = preflight_data["planned_ids"]
    fps_before = preflight_data["fingerprints"]
    by_eid = await load_item_map(session)
    unexpected: list[str] = []
    ai_reports: list[dict] = []
    medium_post: dict = {}

    for eid in planned:
        item = by_eid.get(eid)
        if not item:
            unexpected.append(f"missing_after:{eid}")
            continue
        if item.status != "IN_REVIEW":
            unexpected.append(f"status:{eid}={item.status}")
        if str(item.concept_id) != fps_before[eid]["concept_id"]:
            unexpected.append(f"concept_changed:{eid}")
        body = latest_body(item)
        if body_fp(body) != fps_before[eid]["body_sha256"]:
            unexpected.append(f"body_changed:{eid}")
        if ncert_level(body) != "NOT_VERIFIED":
            unexpected.append(f"ncert_changed:{eid}:{ncert_level(body)}")
        ver = latest_version(item)
        report = ver.ai_check_report if ver else None
        ok_report = isinstance(report, dict) and "status" in report and "checked_at" in report
        ai_reports.append(
            {
                "question_id": eid,
                "ai_check_report_ok": ok_report,
                "ai_check_status": (report or {}).get("status") if isinstance(report, dict) else None,
                "workflow_state": ver.workflow_state if ver else None,
            }
        )
        if not ok_report:
            unexpected.append(f"ai_check_missing:{eid}")
        qnum = fps_before[eid]["qnum"]
        if qnum in MEDIUM_Q:
            medium_post[qnum] = {
                "ok": str(item.concept_id) == fps_before[eid]["concept_id"]
                and fps_before[eid]["confidence"] == "MEDIUM",
                "topic_code": fps_before[eid]["topic_code"],
                "concept_code": fps_before[eid]["concept_code"],
                "confidence": fps_before[eid]["confidence"],
            }

    in_review = sorted(eid for eid, i in by_eid.items() if i.status == "IN_REVIEW")
    if set(in_review) != set(planned):
        unexpected.append("in_review_set_mismatch")
    if post["ch04"] != EXPECTED_CH04_POST:
        unexpected.append(f"ch04_post={post['ch04']}")
    if post["taxonomy"] != EXPECTED_TAX:
        unexpected.append(f"taxonomy={post['taxonomy']}")
    if post["physics_DRAFT"] != 24:
        unexpected.append(f"physics={post['physics_DRAFT']}")
    if post["student_ch04_hits"] != 0 or post["practice_nonpub_hits"] != 0:
        unexpected.append("student_exposure")
    if post["ch01_regression"] != EXPECTED_CH01:
        unexpected.append(f"ch01={post['ch01_regression']}")
    if post["ch02_regression"] != EXPECTED_CH02:
        unexpected.append(f"ch02={post['ch02_regression']}")
    if post["ch03_regression"] != EXPECTED_CH03:
        unexpected.append(f"ch03={post['ch03_regression']}")
    for qn in sorted(MEDIUM_Q):
        if not (medium_post.get(qn) or {}).get("ok"):
            unexpected.append(f"medium_fail:{qn}")

    ai_ok = sum(1 for r in ai_reports if r["ai_check_report_ok"])
    return {
        "post": post,
        "ai_check_coverage": {
            "present_ok": ai_ok,
            "total": len(ai_reports),
            "all_ok": ai_ok == 100,
            "reports": ai_reports,
        },
        "medium_validation": medium_post,
        "in_review_ids": in_review,
        "unexpected_mutations": unexpected,
        "ok": len(unexpected) == 0 and post["ch04"] == EXPECTED_CH04_POST,
    }


async def idempotency_probe(session, sample_item_id: uuid.UUID) -> dict:
    workflow = ContentWorkflowService(session)
    gate = await workflow.evaluate_submit_for_review(sample_item_id)
    rejected = (
        not gate["eligible"]
        and gate["rejection_code"] == "INVALID_WORKFLOW_TRANSITION"
        and "IN_REVIEW" in (gate["rejection_reason"] or "")
    )
    submit_rejected = False
    submit_code = None
    submit_message = None
    try:
        await workflow.submit_for_review(sample_item_id, commit=True)
    except (ContentWorkflowError, AppError) as exc:
        submit_rejected = True
        submit_code = getattr(exc, "code", type(exc).__name__)
        submit_message = str(exc)
    item = await CmsRepository(session).get_item(sample_item_id)
    after = await snap(session)
    return {
        "sample_item_id": str(sample_item_id),
        "evaluate_rejected": rejected,
        "evaluate_code": gate["rejection_code"],
        "evaluate_reason": gate["rejection_reason"],
        "submit_rejected": submit_rejected,
        "submit_code": submit_code,
        "submit_message": submit_message,
        "status_unchanged_in_review": item.status == "IN_REVIEW" if item else False,
        "ch04_still_100_in_review": after["ch04"]["IN_REVIEW"] == 100,
        "ok": rejected
        and submit_rejected
        and item is not None
        and item.status == "IN_REVIEW"
        and after["ch04"]["IN_REVIEW"] == 100,
    }


def run_tests() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_ecaep_biology_workflow_gates.py",
        "-q",
        "--tb=line",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
            timeout=240,
        )
        return {
            "command": " ".join(cmd),
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-800:],
        }
    except Exception as exc:  # noqa: BLE001
        return {"passed": False, "error": str(exc), "command": " ".join(cmd)}


def write_report(payload: dict) -> None:
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    lines = [
        "# ECAEP Submission Execution Report — BIO11-CH04-B001",
        "",
        f"## Verdict: {payload['verdict']}",
        "",
        f"- Batch: `{BATCH}`",
        f"- Artifact SHA: `{payload.get('authoritative_sha256')}`",
        f"- Executed: `{payload.get('executed_at')}`",
        f"- Transaction: **{payload.get('transaction_result')}**",
        f"- Submitted: **{payload.get('submitted_count')}**",
        f"- Rollback: **{payload.get('rollback_status')}**",
        "",
        "## Pre-state",
        "",
        "```json",
        json.dumps(payload.get("pre_state"), indent=2),
        "```",
        "",
        "## Post-state",
        "",
        "```json",
        json.dumps(payload.get("post_state"), indent=2),
        "```",
        "",
        "## Exact DB mutations",
        "",
        "```json",
        json.dumps(payload.get("database_mutations"), indent=2),
        "```",
        "",
        f"- AI check reports OK: **{(payload.get('ai_check_coverage') or {}).get('present_ok')}/100**",
        f"- Student visibility: **{payload.get('student_visibility')}**",
        f"- Practice pool: **{payload.get('practice_nonpub_hits')}**",
        f"- Idempotency: `{payload.get('idempotency')}`",
        f"- Tests: `{payload.get('tests')}`",
        f"- Unexpected mutations: **{len(payload.get('unexpected_mutations') or [])}**",
        "",
        "## Medium-confidence mappings retained",
        "",
    ]
    for qn, v in (payload.get("medium_validation") or {}).items():
        lines.append(
            f"- {qn}: {'PASS' if v.get('ok') else 'FAIL'} · `{v.get('topic_code')}` → `{v.get('concept_code')}` · {v.get('confidence')}"
        )
    lines += [
        "",
        "## Mandatory stop",
        "",
        "Adjudication / NCERT certification / publication / student visibility — NOT EXECUTED.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(*, do_commit: bool) -> dict:
    executed_at = datetime.now(UTC).isoformat()
    async with AsyncSessionLocal() as session:
        try:
            pf = await preflight(session)
        except Abort as exc:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — ECAEP SUBMISSION FAILED",
                "transaction_result": "NO_COMMIT",
                "rollback_status": "N/A_PREFLIGHT_ABORT",
                "submitted_count": 0,
                "failure": {
                    "condition": exc.condition,
                    "expected": exc.expected,
                    "actual": exc.actual,
                },
            }
            write_report(payload)
            return payload

        if not do_commit:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "GREEN — PREFLIGHT READY (NO COMMIT)",
                "transaction_result": "NO_COMMIT",
                "rollback_status": "N/A",
                "submitted_count": 0,
                "authoritative_sha256": pf["sha"],
                "submitted_question_ids": pf["planned_ids"],
                "pre_state": pf["pre"],
                "eligibility_results": pf["eligibility"],
                "medium_validation": pf["medium_validation"],
                "atomicity_rollback_test": None,
                "failure": None,
            }
            write_report(payload)
            return payload

        try:
            rb_test = await atomicity_rollback_test(session, pf)
        except Exception as exc:  # noqa: BLE001
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — ATOMICITY ROLLBACK TEST FAILED",
                "transaction_result": "NO_COMMIT",
                "rollback_status": "ATOMICITY_TEST_ABORT",
                "submitted_count": 0,
                "authoritative_sha256": pf["sha"],
                "failure": {"error": str(exc)},
                "pre_state": pf["pre"],
            }
            write_report(payload)
            return payload

        if not rb_test["ok"]:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — ATOMICITY ROLLBACK TEST FAILED",
                "transaction_result": "NO_COMMIT",
                "rollback_status": "ATOMICITY_TEST_FAILED",
                "submitted_count": 0,
                "authoritative_sha256": pf["sha"],
                "atomicity_rollback_test": rb_test,
                "pre_state": pf["pre"],
                "failure": {"condition": "atomicity_rollback_test"},
            }
            write_report(payload)
            return payload

        workflow = ContentWorkflowService(session)
        submitted: list[dict] = []
        failure: dict | None = None
        try:
            session.info["defer_commit"] = True
            for eid in pf["planned_ids"]:
                item_id = uuid.UUID(pf["fingerprints"][eid]["content_item_id"])
                try:
                    item = await workflow.submit_for_review(item_id, commit=False)
                except Exception as exc:  # noqa: BLE001
                    failure = {
                        "question_id": eid,
                        "content_item_id": str(item_id),
                        "error_type": type(exc).__name__,
                        "error_code": getattr(exc, "code", None),
                        "error_message": str(exc),
                        "gate": "ContentWorkflowService.submit_for_review",
                    }
                    raise
                submitted.append(
                    {
                        "question_id": eid,
                        "content_item_id": str(item.id),
                        "status": item.status,
                    }
                )
            await session.commit()
            transaction_result = "COMMITTED"
            rollback_status = "NOT_REQUIRED"
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            transaction_result = "ROLLED_BACK"
            rollback_status = "ROLLED_BACK_TO_PRE_SUBMISSION"
            if failure is None:
                failure = {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "gate": "batch_transaction",
                }
            restored = await snap(session)
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — ECAEP SUBMISSION FAILED",
                "transaction_result": transaction_result,
                "rollback_status": rollback_status,
                "submitted_count": 0,
                "authoritative_sha256": pf["sha"],
                "partial_attempt_count": len(submitted),
                "pre_state": pf["pre"],
                "post_state": restored,
                "atomicity_rollback_test": rb_test,
                "failure": failure,
            }
            write_report(payload)
            return payload
        finally:
            session.info.pop("defer_commit", None)

        session.expire_all()
        post = await post_verify(session, pf)
        sample_id = uuid.UUID(pf["fingerprints"][pf["planned_ids"][0]]["content_item_id"])
        idem = await idempotency_probe(session, sample_id)
        tests = run_tests()

        ok = (
            post["ok"]
            and transaction_result == "COMMITTED"
            and len(submitted) == 100
            and all(s["status"] == "IN_REVIEW" for s in submitted)
            and idem["ok"]
            and rb_test["ok"]
            and tests.get("passed") is True
            and sha256_file(FINAL_JSONL) == EXPECTED_SHA
        )
        verdict = (
            "GREEN — 100 QUESTIONS SUBMITTED TO ECAEP"
            if ok
            else "AMBER — ECAEP SUBMISSION REQUIRES REVIEW"
            if transaction_result == "COMMITTED" and post["ok"] and idem["ok"] and not tests.get("passed")
            else "RED — ECAEP SUBMISSION FAILED"
        )
        # If import committed and validated but tests failed for env noise, still AMBER not RED
        if transaction_result == "COMMITTED" and post["ok"] and idem["ok"] and rb_test["ok"] and not tests.get("passed"):
            verdict = "AMBER — ECAEP SUBMISSION REQUIRES REVIEW"
        elif ok:
            verdict = "GREEN — 100 QUESTIONS SUBMITTED TO ECAEP"

        mutations = {
            "subjects_created": 0,
            "chapters_created": 0,
            "topics_created": 0,
            "concepts_created": 0,
            "content_items_created": 0,
            "content_items_status_DRAFT_to_IN_REVIEW": 100,
            "ai_check_reports_written": post["ai_check_coverage"]["present_ok"],
            "body_text_mutations": 0,
            "taxonomy_mutations": 0,
            "ncert_certification_mutations": 0,
            "publication_mutations": 0,
            "student_visibility_mutations": 0,
            "ecaep_adjudication_mutations": 0,
        }
        payload = {
            "batch_id": BATCH,
            "executed_at": executed_at,
            "verdict": verdict,
            "authoritative_artifact": "questions_repaired_final.jsonl",
            "authoritative_sha256": pf["sha"],
            "artifact_unchanged": sha256_file(FINAL_JSONL) == EXPECTED_SHA,
            "canonical_method": "ContentWorkflowService.submit_for_review",
            "transaction_result": transaction_result,
            "rollback_status": rollback_status,
            "submitted_count": len(submitted),
            "submitted_question_ids": [s["question_id"] for s in submitted],
            "submitted_content_item_ids": [s["content_item_id"] for s in submitted],
            "pre_state": pf["pre"],
            "post_state": post["post"],
            "eligibility_results_summary": {
                "eligible": sum(1 for e in pf["eligibility"] if e["eligible"]),
                "ineligible": sum(1 for e in pf["eligibility"] if not e["eligible"]),
            },
            "atomicity_rollback_test": rb_test,
            "ai_check_coverage": {
                "present_ok": post["ai_check_coverage"]["present_ok"],
                "total": post["ai_check_coverage"]["total"],
                "all_ok": post["ai_check_coverage"]["all_ok"],
                "status_counts": dict(
                    Counter(r["ai_check_status"] for r in post["ai_check_coverage"]["reports"])
                ),
            },
            "medium_validation": post["medium_validation"],
            "student_visibility": post["post"]["student_ch04_hits"],
            "practice_nonpub_hits": post["post"]["practice_nonpub_hits"],
            "physics_DRAFT": post["post"]["physics_DRAFT"],
            "ch01_regression": post["post"]["ch01_regression"],
            "ch02_regression": post["post"]["ch02_regression"],
            "ch03_regression": post["post"]["ch03_regression"],
            "taxonomy_invariant": post["post"]["taxonomy"] == EXPECTED_TAX,
            "unexpected_mutations": post["unexpected_mutations"],
            "idempotency": idem,
            "tests": tests,
            "database_mutations": mutations,
            "ncert_certification": 0,
            "publication": post["post"]["ch04"]["PUBLISHED"],
            "failure": None,
            "mandatory_stop": True,
            "assertions": {
                "ACTUAL ECAEP SUBMISSION PERFORMED": True,
                "EXACTLY 100 QUESTIONS": len(submitted) == 100,
                "DATABASE STATE VERIFIED": post["ok"],
                "NO PUBLICATION": post["post"]["ch04"]["PUBLISHED"] == 0,
                "NO STUDENT EXPOSURE": post["post"]["student_ch04_hits"] == 0,
                "NO TAXONOMY MUTATION": post["post"]["taxonomy"] == EXPECTED_TAX,
                "NO NCERT CERTIFICATION": True,
                "MEDIUM MAPPINGS RETAINED": all(v.get("ok") for v in post["medium_validation"].values()),
                "ATOMICITY ROLLBACK TEST PASSED": rb_test["ok"],
                "IDEMPOTENCY PASSED": idem["ok"],
                "TESTS PASSED": bool(tests.get("passed")),
            },
        }
        write_report(payload)
        return payload


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--commit", action="store_true")
    p.add_argument("--dry-preflight", action="store_true")
    args = p.parse_args()
    if not args.commit and not args.dry_preflight:
        print("Specify --commit or --dry-preflight")
        return 2
    result = await run(do_commit=bool(args.commit) and not args.dry_preflight)
    print(
        json.dumps(
            {
                "verdict": result.get("verdict"),
                "transaction_result": result.get("transaction_result"),
                "submitted_count": result.get("submitted_count"),
                "pre_ch04": (result.get("pre_state") or {}).get("ch04"),
                "post_ch04": (result.get("post_state") or {}).get("ch04"),
                "taxonomy": (result.get("post_state") or {}).get("taxonomy")
                or (result.get("pre_state") or {}).get("taxonomy"),
                "student_visibility": result.get("student_visibility"),
                "idempotency_ok": (result.get("idempotency") or {}).get("ok"),
                "tests_passed": (result.get("tests") or {}).get("passed"),
                "unexpected_mutations": result.get("unexpected_mutations"),
                "failure": result.get("failure"),
            },
            indent=2,
            default=str,
        )
    )
    if "PREFLIGHT READY" in str(result.get("verdict", "")):
        return 0
    return 0 if str(result.get("verdict", "")).startswith("GREEN") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
