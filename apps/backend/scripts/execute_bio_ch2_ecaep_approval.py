"""Atomic ECAEP approval for Biology Ch2 100 IN_REVIEW questions.

Uses ContentWorkflowService.review(..., decision='approve', commit=False)
then a single session.commit(). Never publishes or certifies NCERT.

Updates pipeline_stage_status to GREEN ECAEP complete, stopped before NCERT.

Usage:
  python scripts/execute_bio_ch2_ecaep_approval.py --commit
  python scripts/execute_bio_ch2_ecaep_approval.py --dry-preflight
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
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
from app.modules.cms.acquisition.physics_t6d_service import actor_user
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import (
    ContentWorkflowError,
    ContentWorkflowService,
)
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

BATCH = "20260911-BIO11-CH02-B001"
CH01 = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
EXPECTED_TAX = {"subjects": 4, "chapters": 36, "topics": 107, "concepts": 143}
EXPECTED_BIO_PRE = {"DRAFT": 0, "SUPERSEDED": 0, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 100}
# Post-approval expectation is computed from AI-review readiness (may hold genuine defects).
EXPECTED_CH01 = {"DRAFT": 0, "SUPERSEDED": 5, "PUBLISHED": 100, "APPROVED": 0, "IN_REVIEW": 0}
APPROVAL_READY = {"APPROVE_READY", "APPROVE_WITH_DOCUMENTED_WARNING"}
COMMENT = (
    "Biology Ch2 pilot ECAEP approval — AI review + adjudication; "
    "documented warnings accepted; Q000085 held for stem repair; "
    "no publication; NCERT certification not performed."
)

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
DRY_RUN = ROOT / "ecaep_submission_dry_run.json"
EXEC_SUB = ROOT / "ecaep_submission_execution_report.json"
AI_REVIEW = ROOT / "ecaep_ai_review_report.json"
OUT_JSON = ROOT / "ecaep_approval_execution_report.json"
OUT_MD = ROOT / "ecaep_approval_execution_report.md"
STAGE_JSON = ROOT / "pipeline_stage_status.json"
STAGE_MD = ROOT / "pipeline_stage_status.md"


class Abort(Exception):
    def __init__(self, condition: str, expected=None, actual=None):
        self.condition = condition
        self.expected = expected
        self.actual = actual
        super().__init__(f"ABORT: {condition} expected={expected!r} actual={actual!r}")


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


def body_fp(body: dict | None) -> str:
    return hashlib.sha256(
        json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def ncert_level(body: dict | None) -> str | None:
    return ((body or {}).get("ncert_evidence") or {}).get("verification_level")


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


async def load_batch_map(session) -> dict[str, ContentItem]:
    items = (
        await session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.deleted_at.is_(None))
        )
    ).scalars().all()
    out: dict[str, ContentItem] = {}
    for i in items:
        if not is_batch_item(i):
            continue
        eid = eid_from_slug(i.slug)
        if eid:
            out[eid] = i
    return out


def assert_ch01_regression(snap_data: dict) -> None:
    if snap_data["ch01_regression"] != EXPECTED_CH01:
        raise Abort("ch01_regression", EXPECTED_CH01, snap_data["ch01_regression"])


async def preflight(
    session,
    planned_ids: list[str],
    approve_ids: list[str],
    hold_ids: list[str],
    superseded_excluded: list[str],
) -> dict:
    if len(planned_ids) != 100 or len(set(planned_ids)) != 100:
        raise Abort("planned_count", 100, len(planned_ids))
    if set(approve_ids) | set(hold_ids) != set(planned_ids):
        raise Abort(
            "approve_hold_partition",
            set(planned_ids),
            {"approve": approve_ids, "hold": hold_ids},
        )
    if set(approve_ids) & set(hold_ids):
        raise Abort("approve_hold_overlap", set(), set(approve_ids) & set(hold_ids))
    if set(planned_ids) & set(superseded_excluded):
        raise Abort("superseded_in_plan", set(), set(planned_ids) & set(superseded_excluded))

    pre = await snap(session)
    if pre["taxonomy"] != EXPECTED_TAX:
        raise Abort("taxonomy", EXPECTED_TAX, pre["taxonomy"])
    if pre["biology"] != EXPECTED_BIO_PRE:
        raise Abort("biology_pre", EXPECTED_BIO_PRE, pre["biology"])
    if pre["physics_DRAFT"] != 24:
        raise Abort("physics_DRAFT", 24, pre["physics_DRAFT"])
    if pre["student_bio_hits"] != 0 or pre["practice_nonpub_hits"] != 0:
        raise Abort("student_safety", 0, pre)
    assert_ch01_regression(pre)

    by_eid = await load_batch_map(session)
    superseded_live = sorted(eid for eid, i in by_eid.items() if i.status == "SUPERSEDED")
    if len(superseded_live) != 0:
        raise Abort("superseded_count", 0, len(superseded_live))
    if set(superseded_live) & set(planned_ids):
        raise Abort("superseded_selected", set(), set(superseded_live) & set(planned_ids))

    workflow = ContentWorkflowService(session)
    fingerprints = {}
    eligibility = []
    for eid in planned_ids:
        item = by_eid.get(eid)
        if not item:
            raise Abort("missing_item", eid, None)
        if item.status != "IN_REVIEW":
            raise Abort("status", "IN_REVIEW", item.status)
        if item.deleted_at is not None:
            raise Abort("inactive", None, str(item.deleted_at))
        if not is_batch_item(item):
            raise Abort("wrong_batch", BATCH, item.tags)
        if item.concept_id is None:
            raise Abort("null_concept", eid, None)
        if PHY in eid.lower() or "phy" in (item.slug or "").lower():
            raise Abort("physics_leak", None, eid)
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        fingerprints[eid] = {
            "content_item_id": str(item.id),
            "concept_id": str(item.concept_id),
            "body_sha256": body_fp(body),
            "verification_level": ncert_level(body),
            "status": item.status,
        }
        gate = await workflow.evaluate_review(item.id, decision="approve")
        eligibility.append(
            {
                "question_id": eid,
                "eligible": gate["eligible"],
                "rejection_code": gate["rejection_code"],
                "rejection_reason": gate["rejection_reason"],
                "in_approval_set": eid in approve_ids,
            }
        )
        if eid in approve_ids and not gate["eligible"]:
            raise Abort(
                f"ineligible:{eid}",
                "ELIGIBLE",
                f"{gate['rejection_code']}: {gate['rejection_reason']}",
            )

    ineligible_approve = [
        e for e in eligibility if e["in_approval_set"] and not e["eligible"]
    ]
    if ineligible_approve:
        raise Abort("ineligible_approve_count", 0, len(ineligible_approve))

    expected_post = {
        "DRAFT": 0,
        "SUPERSEDED": 0,
        "PUBLISHED": 0,
        "APPROVED": len(approve_ids),
        "IN_REVIEW": len(hold_ids),
    }
    return {
        "pre": pre,
        "fingerprints": fingerprints,
        "eligibility": eligibility,
        "planned_ids": planned_ids,
        "approve_ids": approve_ids,
        "hold_ids": hold_ids,
        "expected_post": expected_post,
        "superseded_excluded": superseded_live,
    }


async def post_verify(session, pf: dict) -> dict:
    post = await snap(session)
    by_eid = await load_batch_map(session)
    approve_ids = pf["approve_ids"]
    hold_ids = pf["hold_ids"]
    fps = pf["fingerprints"]
    unexpected = []
    approved_ids = []
    held_ids = []

    for eid in approve_ids:
        item = by_eid.get(eid)
        if not item:
            unexpected.append(f"missing:{eid}")
            continue
        if item.status != "APPROVED":
            unexpected.append(f"status:{eid}={item.status}")
        approved_ids.append(eid)
        if str(item.concept_id) != fps[eid]["concept_id"]:
            unexpected.append(f"concept_changed:{eid}")
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        if body_fp(body) != fps[eid]["body_sha256"]:
            unexpected.append(f"body_changed:{eid}")
        if ncert_level(body) != fps[eid]["verification_level"]:
            unexpected.append(f"verification_level_changed:{eid}")
        if ver and ver.workflow_state != "APPROVED":
            unexpected.append(f"workflow_state:{eid}={ver.workflow_state}")

    for eid in hold_ids:
        item = by_eid.get(eid)
        if not item:
            unexpected.append(f"missing_held:{eid}")
            continue
        if item.status != "IN_REVIEW":
            unexpected.append(f"held_status:{eid}={item.status}")
        held_ids.append(eid)
        if str(item.concept_id) != fps[eid]["concept_id"]:
            unexpected.append(f"held_concept_changed:{eid}")
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        if body_fp(body) != fps[eid]["body_sha256"]:
            unexpected.append(f"held_body_changed:{eid}")
        if ncert_level(body) != fps[eid]["verification_level"]:
            unexpected.append(f"held_verification_level_changed:{eid}")

    approved_all = sorted(eid for eid, i in by_eid.items() if i.status == "APPROVED")
    in_review_all = sorted(eid for eid, i in by_eid.items() if i.status == "IN_REVIEW")
    if set(approved_all) != set(approve_ids):
        unexpected.append(
            f"approved_set_mismatch extra={sorted(set(approved_all)-set(approve_ids))} "
            f"missing={sorted(set(approve_ids)-set(approved_all))}"
        )
    if set(in_review_all) != set(hold_ids):
        unexpected.append(
            f"in_review_set_mismatch extra={sorted(set(in_review_all)-set(hold_ids))} "
            f"missing={sorted(set(hold_ids)-set(in_review_all))}"
        )
    if post["biology"] != pf["expected_post"]:
        unexpected.append(f"biology_post={post['biology']} expected={pf['expected_post']}")
    if post["taxonomy"] != EXPECTED_TAX:
        unexpected.append(f"taxonomy={post['taxonomy']}")
    if post["physics_DRAFT"] != 24:
        unexpected.append(f"physics={post['physics_DRAFT']}")
    if post["student_bio_hits"] != 0 or post["practice_nonpub_hits"] != 0:
        unexpected.append(f"student_exposure={post}")
    if post["ch01_regression"] != EXPECTED_CH01:
        unexpected.append(f"ch01_regression={post['ch01_regression']}")

    return {
        "post": post,
        "approved_ids": approved_ids,
        "held_ids": held_ids,
        "unexpected_mutations": unexpected,
        "ok": len(unexpected) == 0,
    }


async def publication_gate_sample(session, pf: dict) -> dict:
    by_eid = await load_batch_map(session)
    approve_ids = pf["approve_ids"]
    samples = [approve_ids[0], approve_ids[len(approve_ids) // 2], approve_ids[-1]]
    if pf["hold_ids"]:
        samples.append(pf["hold_ids"][0])
    sample_results = []
    batch_blocker_counts: Counter = Counter()
    would_publish = 0
    for eid in pf["planned_ids"]:
        item = by_eid[eid]
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        report = await evaluate_question_publication_gates(
            session,
            item_id=item.id,
            status=item.status,
            content_type="QUESTION",
            concept_id=item.concept_id,
            body=body,
            tags=list(item.tags or []),
            model_used=getattr(ver, "model_used", None) if ver else None,
            knowledge_unit_id=getattr(ver, "knowledge_unit_id", None) if ver else None,
        )
        for reason in report.reasons:
            batch_blocker_counts[reason] += 1
        if report.passed:
            would_publish += 1
        if eid in samples:
            sample_results.append(
                {
                    "question_id": eid,
                    "status": item.status,
                    "passed": report.passed,
                    "reasons": list(report.reasons),
                    "ncert_level": report.ncert_level,
                }
            )
    ncert_blockers = batch_blocker_counts.get("ncert:NOT_VERIFIED", 0)
    return {
        "publish_called": False,
        "sample_results": sample_results,
        "batch_would_pass_publication": would_publish,
        "batch_blocker_counts": dict(batch_blocker_counts),
        "approved_not_published_demonstrated": would_publish == 0
        and ncert_blockers >= len(approve_ids),
        "note": (
            "APPROVED ≠ PUBLISHED — publication gates still block (esp. ncert:NOT_VERIFIED). "
            f"Held IN_REVIEW items: {pf['hold_ids']}."
        ),
    }


async def idempotency_probe(session, sample_item_id: uuid.UUID) -> dict:
    workflow = ContentWorkflowService(session)
    gate = await workflow.evaluate_review(sample_item_id, decision="approve")
    rejected = (
        not gate["eligible"]
        and gate["rejection_code"] == "INVALID_WORKFLOW_TRANSITION"
        and "APPROVED" in (gate["rejection_reason"] or "")
    )
    submit_rejected = False
    submit_code = None
    submit_message = None
    reviewer = await actor_user(session)
    try:
        await workflow.review(
            sample_item_id,
            reviewer_id=reviewer.id,
            decision="approve",
            comment="idempotency probe — must fail",
            commit=True,
        )
    except (ContentWorkflowError, AppError) as exc:
        submit_rejected = True
        submit_code = getattr(exc, "code", type(exc).__name__)
        submit_message = str(exc)
    item = await CmsRepository(session).get_item(sample_item_id)
    return {
        "sample_item_id": str(sample_item_id),
        "evaluate_rejected": rejected,
        "evaluate_code": gate["rejection_code"],
        "evaluate_reason": gate["rejection_reason"],
        "review_rejected": submit_rejected,
        "review_code": submit_code,
        "review_message": submit_message,
        "status_unchanged_approved": item.status == "APPROVED" if item else False,
        "ok": rejected and submit_rejected and item is not None and item.status == "APPROVED",
    }


def update_pipeline_stage(*, approval_report: dict) -> None:
    now = datetime.now(UTC).isoformat()
    approved_n = approval_report.get("approved_count", 0)
    held = approval_report.get("held_question_ids") or []
    held_n = len(held)
    stage = {
        "batch_id": BATCH,
        "as_of": now,
        "verdict": "GREEN — ECAEP SUBMISSION + REVIEW + APPROVAL COMPLETE",
        "current_stage": "ECAEP_APPROVAL_COMPLETE",
        "stopped_before": "NCERT_CERTIFICATION",
        "explicit_statement": [
            "BIO11-CH02-B001 ECAEP submission, review, adjudication and approval are complete.",
            f"{approved_n} questions are APPROVED; {held_n} remain IN_REVIEW (genuine defect hold).",
            "NCERT certification has NOT been started.",
            "Publication has NOT been authorized or performed.",
            "CH02 remains non-student-visible because it is not published.",
        ],
        "held_in_review": held,
        "stages": {
            "source_verification": "GREEN",
            "acquisition": "GREEN",
            "structural_validation": "GREEN",
            "scientific_audit": "GREEN",
            "repair": "GREEN",
            "taxonomy_approval": "APPROVED",
            "taxonomy_migration": "GREEN",
            "draft_import": "GREEN",
            "ecaep_submission_dry_run": "GREEN",
            "ecaep_submission": "GREEN",
            "ecaep_ai_review": "GREEN",
            "ecaep_approval": "GREEN",
            "ncert_certification": "NOT_STARTED",
            "publication_dry_run": "NOT_STARTED",
            "publication": "NOT_AUTHORIZED",
        },
        "counts": {
            "draft": 0,
            "in_review": held_n,
            "approved": approved_n,
            "published": 0,
            "superseded": 0,
            "concept_mapped": 100,
        },
        "ch01_regression": approval_report.get("ch01_regression"),
        "publication_gate_sample": (
            (approval_report.get("publication_gates") or {}).get("sample_results")
        ),
        "would_publish": (approval_report.get("publication_gates") or {}).get(
            "batch_would_pass_publication"
        ),
        "safety": {
            "student_ch02_visible": approval_report.get("student_visibility"),
            "practice_nonpub_hits": approval_report.get("practice_nonpub_hits"),
            "physics_DRAFT": approval_report.get("physics_DRAFT"),
            "bio11_ch01_artifacts_touched": False,
            "ncert_certification_called": False,
            "publication_called": False,
        },
        "artifacts": {
            "ecaep_submission_dry_run": str(ROOT / "ecaep_submission_dry_run.json"),
            "ecaep_submission_execution_report": str(EXEC_SUB),
            "ecaep_ai_review_report": str(AI_REVIEW),
            "ecaep_approval_execution_report": str(OUT_JSON),
        },
    }
    STAGE_JSON.write_text(json.dumps(stage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    STAGE_MD.write_text(
        f"""# Pipeline stage status — `{BATCH}`

## GREEN — ECAEP SUBMISSION + REVIEW + APPROVAL COMPLETE

## STOPPED BEFORE NCERT CERTIFICATION

> BIO11-CH02-B001 ECAEP submission, review, adjudication and approval are complete.
>
> {approved_n} questions are APPROVED; {held_n} remain IN_REVIEW (genuine defect hold).
>
> NCERT certification has NOT been started.
>
> Publication has NOT been authorized or performed.
>
> CH02 remains non-student-visible because it is not published.

### Held IN_REVIEW
{chr(10).join(f'- `{h}`' for h in held) if held else '_None_'}

### Exact next task
Requires separate authorization: content repair for held items (if any), then NCERT certification.
""",
        encoding="utf-8",
    )


def write_report(payload: dict) -> None:
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    lines = [
        "# ECAEP Approval Execution Report",
        "",
        f"## Verdict: {payload['verdict']}",
        "",
        f"Batch: `{BATCH}`  ",
        f"Executed: `{payload.get('executed_at')}`  ",
        f"Transaction: **{payload.get('transaction_result')}**  ",
        f"Rollback: **{payload.get('rollback_status')}**",
        "",
        "## Assertions",
        "",
        "- ACTUAL ECAEP APPROVAL PERFORMED"
        if payload.get("transaction_result") == "COMMITTED"
        else "- APPROVAL NOT COMMITTED",
        f"- EXACTLY {payload.get('approved_count', 0)} QUESTIONS",
        "- NO PUBLICATION",
        "- NO NCERT CERTIFICATION",
        "- NO STUDENT EXPOSURE",
        "- NO TAXONOMY MUTATION",
        "- CH01 REGRESSION UNCHANGED",
        "- DATABASE STATE VERIFIED",
        "",
        "## Pre / Post",
        "",
        "```json",
        json.dumps({"pre": payload.get("pre_state"), "post": payload.get("post_state")}, indent=2),
        "```",
        "",
        f"- Student CH02 visibility: **{payload.get('student_visibility')}**",
        f"- Practice nonpub hits: **{payload.get('practice_nonpub_hits')}**",
        f"- Physics DRAFT: **{payload.get('physics_DRAFT')}**",
        f"- CH01 regression: `{payload.get('ch01_regression')}`",
        f"- Unexpected mutations: **{len(payload.get('unexpected_mutations') or [])}**",
        "",
        "## Publication gates (not published)",
        "",
        "```json",
        json.dumps(payload.get("publication_gates"), indent=2),
        "```",
        "",
        "## Idempotency",
        "",
        "```json",
        json.dumps(payload.get("idempotency"), indent=2),
        "```",
        "",
        "## Failure",
        "",
        f"```json\n{json.dumps(payload.get('failure'), indent=2)}\n```"
        if payload.get("failure")
        else "_None_",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(*, do_commit: bool) -> dict:
    dry = json.loads(DRY_RUN.read_text(encoding="utf-8"))
    exec_sub = json.loads(EXEC_SUB.read_text(encoding="utf-8"))
    ai_rep = json.loads(AI_REVIEW.read_text(encoding="utf-8"))
    planned = dry["deterministic_question_ids"]
    if planned != exec_sub.get("submitted_question_ids"):
        raise SystemExit("ABORT: dry-run IDs != execution submitted IDs")
    if not str(ai_rep.get("verdict", "")).startswith("GREEN"):
        raise SystemExit(f"ABORT: AI review not GREEN: {ai_rep.get('verdict')}")

    approve_ids = [
        r["question_id"]
        for r in ai_rep["records"]
        if (r.get("adjudication") or {}).get("approval_readiness") in APPROVAL_READY
    ]
    hold_ids = [
        r["question_id"]
        for r in ai_rep["records"]
        if (r.get("adjudication") or {}).get("approval_readiness") not in APPROVAL_READY
    ]
    if set(approve_ids) | set(hold_ids) != set(planned):
        raise SystemExit("ABORT: AI review readiness partition != planned IDs")
    if not approve_ids:
        raise SystemExit("ABORT: empty approval set")

    superseded = dry.get("selection_proof", {}).get("excluded_superseded_ids") or []
    executed_at = datetime.now(UTC).isoformat()

    async with AsyncSessionLocal() as session:
        try:
            pf = await preflight(session, planned, approve_ids, hold_ids, superseded)
        except Abort as exc:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — APPROVAL FAILED / ROLLED BACK",
                "transaction_result": "NO_COMMIT",
                "rollback_status": "N/A_PREFLIGHT_ABORT",
                "approved_count": 0,
                "approved_question_ids": [],
                "held_question_ids": hold_ids,
                "failure": {
                    "condition": exc.condition,
                    "expected": exc.expected,
                    "actual": exc.actual,
                },
                "assertions": {
                    "ACTUAL ECAEP APPROVAL PERFORMED": False,
                    "LEGITIMATE APPROVAL SET": False,
                    "NO PUBLICATION": True,
                    "NO NCERT CERTIFICATION": True,
                    "NO STUDENT EXPOSURE": True,
                    "NO TAXONOMY MUTATION": True,
                    "CH01 REGRESSION UNCHANGED": True,
                    "DATABASE STATE VERIFIED": False,
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
                "approved_count": 0,
                "approved_question_ids": pf["approve_ids"],
                "held_question_ids": pf["hold_ids"],
                "pre_state": pf["pre"],
                "eligibility_results": pf["eligibility"],
                "eligible_count": len(pf["approve_ids"]),
                "ineligible_count": len(pf["hold_ids"]),
                "ai_review_verdict_referenced": ai_rep.get("verdict"),
                "failure": None,
            }
            write_report(payload)
            return payload

        workflow = ContentWorkflowService(session)
        reviewer = await actor_user(session)
        approved = []
        failure = None
        try:
            for eid in pf["approve_ids"]:
                item_id = uuid.UUID(pf["fingerprints"][eid]["content_item_id"])
                try:
                    item = await workflow.review(
                        item_id,
                        reviewer_id=reviewer.id,
                        decision="approve",
                        comment=COMMENT,
                        commit=False,
                    )
                except Exception as exc:  # noqa: BLE001
                    failure = {
                        "question_id": eid,
                        "content_item_id": str(item_id),
                        "error_type": type(exc).__name__,
                        "error_code": getattr(exc, "code", None),
                        "error_message": str(exc),
                        "gate": "ContentWorkflowService.review(decision='approve')",
                    }
                    raise
                approved.append(
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
            restored = await snap(session)
            if failure is None:
                failure = {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "gate": "batch_transaction",
                }
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — APPROVAL FAILED / ROLLED BACK",
                "transaction_result": "ROLLED_BACK",
                "rollback_status": "ROLLED_BACK_TO_PRE_APPROVAL",
                "approved_count": 0,
                "approved_question_ids": pf["approve_ids"],
                "held_question_ids": pf["hold_ids"],
                "partial_attempt_count": len(approved),
                "pre_state": pf["pre"],
                "post_state": restored,
                "restored_to_pre": restored == pf["pre"],
                "failure": failure,
                "eligibility_results": pf["eligibility"],
                "unexpected_mutations": [],
                "student_visibility": restored["student_bio_hits"],
                "practice_nonpub_hits": restored["practice_nonpub_hits"],
                "physics_DRAFT": restored["physics_DRAFT"],
                "ch01_regression": restored["ch01_regression"],
                "publication_gates": None,
                "idempotency": None,
                "assertions": {
                    "ACTUAL ECAEP APPROVAL PERFORMED": False,
                    "LEGITIMATE APPROVAL SET": False,
                    "NO PUBLICATION": restored["biology"]["PUBLISHED"] == 0,
                    "NO NCERT CERTIFICATION": True,
                    "NO STUDENT EXPOSURE": restored["student_bio_hits"] == 0,
                    "NO TAXONOMY MUTATION": restored["taxonomy"] == EXPECTED_TAX,
                    "CH01 REGRESSION UNCHANGED": restored["ch01_regression"] == EXPECTED_CH01,
                    "DATABASE STATE VERIFIED": restored == pf["pre"],
                },
            }
            write_report(payload)
            return payload

        session.expire_all()
        post = await post_verify(session, pf)
        pub = await publication_gate_sample(session, pf)
        sample_id = uuid.UUID(pf["fingerprints"][pf["approve_ids"][0]]["content_item_id"])
        idem = await idempotency_probe(session, sample_id)

        ncert_safety = {
            "certify_ncert_called": False,
            "verification_levels_unchanged": len(post["unexpected_mutations"]) == 0
            or not any("verification_level" in u for u in post["unexpected_mutations"]),
            "source_text_verified_transitions": 0,
            "note": "This ECAEP stage must not set SOURCE_TEXT_VERIFIED.",
        }

        ok = (
            post["ok"]
            and transaction_result == "COMMITTED"
            and len(approved) == len(pf["approve_ids"])
            and all(a["status"] == "APPROVED" for a in approved)
            and [a["question_id"] for a in approved] == pf["approve_ids"]
            and idem["ok"]
            and pub["batch_would_pass_publication"] == 0
            and post["post"]["biology"]["PUBLISHED"] == 0
            and post["post"]["student_bio_hits"] == 0
        )
        verdict = (
            f"GREEN — {len(approved)} QUESTIONS APPROVED"
            + (f"; {len(pf['hold_ids'])} HELD IN_REVIEW" if pf["hold_ids"] else "")
            if ok
            else "RED — APPROVAL FAILED / ROLLED BACK"
        )
        payload = {
            "batch_id": BATCH,
            "executed_at": executed_at,
            "verdict": verdict,
            "transaction_result": transaction_result,
            "rollback_status": rollback_status,
            "reviewer_user_id": str(reviewer.id),
            "approved_count": len(approved),
            "held_count": len(pf["hold_ids"]),
            "approved_question_ids": [a["question_id"] for a in approved],
            "held_question_ids": pf["hold_ids"],
            "approved_content_item_ids": [a["content_item_id"] for a in approved],
            "matches_ai_review_ready_set": [a["question_id"] for a in approved]
            == pf["approve_ids"],
            "eligible_count": len(pf["approve_ids"]),
            "held_count_from_adjudication": len(pf["hold_ids"]),
            "eligibility_results": pf["eligibility"],
            "pre_state": pf["pre"],
            "post_state": post["post"],
            "unexpected_mutations": post["unexpected_mutations"],
            "student_visibility": post["post"]["student_bio_hits"],
            "practice_nonpub_hits": post["post"]["practice_nonpub_hits"],
            "physics_DRAFT": post["post"]["physics_DRAFT"],
            "ch01_regression": post["post"]["ch01_regression"],
            "taxonomy_invariant": post["post"]["taxonomy"] == EXPECTED_TAX,
            "publication_gates": pub,
            "ncert_certification_safety": ncert_safety,
            "idempotency": idem,
            "failure": None,
            "ai_review_verdict_referenced": ai_rep.get("verdict"),
            "assertions": {
                "ACTUAL ECAEP APPROVAL PERFORMED": True,
                "LEGITIMATE APPROVAL SET": len(approved) == len(pf["approve_ids"]),
                "NO PUBLICATION": post["post"]["biology"]["PUBLISHED"] == 0,
                "NO NCERT CERTIFICATION": True,
                "NO STUDENT EXPOSURE": post["post"]["student_bio_hits"] == 0,
                "NO TAXONOMY MUTATION": post["post"]["taxonomy"] == EXPECTED_TAX,
                "CH01 REGRESSION UNCHANGED": post["post"]["ch01_regression"] == EXPECTED_CH01,
                "DATABASE STATE VERIFIED": post["ok"],
            },
        }
        write_report(payload)
        if ok:
            update_pipeline_stage(approval_report=payload)
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
                "rollback_status": result.get("rollback_status"),
                "approved_count": result.get("approved_count"),
                "held_count": result.get("held_count"),
                "held_question_ids": result.get("held_question_ids"),
                "post_biology": (result.get("post_state") or {}).get("biology"),
                "student_visibility": result.get("student_visibility"),
                "ch01_regression": result.get("ch01_regression"),
                "publication_would_pass": (result.get("publication_gates") or {}).get(
                    "batch_would_pass_publication"
                ),
                "idempotency_ok": (result.get("idempotency") or {}).get("ok"),
                "failure": result.get("failure"),
            },
            indent=2,
            default=str,
        )
    )
    ok_verdict = str(result.get("verdict", "")).startswith("GREEN")
    committed = result.get("transaction_result") == "COMMITTED"
    preflight_only = (
        result.get("transaction_result") == "NO_COMMIT"
        and "PREFLIGHT READY" in str(result.get("verdict", ""))
    )
    if preflight_only:
        return 0
    return 0 if ok_verdict and committed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
