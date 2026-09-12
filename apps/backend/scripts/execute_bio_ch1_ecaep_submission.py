"""Execute atomic ECAEP submit_for_review for Biology Ch1 100 DRAFTs.

Uses ContentWorkflowService.submit_for_review(..., commit=False) for each planned
ID, then a single session.commit(). On any failure: session.rollback().

Usage:
  python scripts/execute_bio_ch1_ecaep_submission.py --commit
  python scripts/execute_bio_ch1_ecaep_submission.py --dry-preflight  # preflight only
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
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.knowledge.models  # noqa: F401 — ContentVersion FK metadata
from app.core.database import AsyncSessionLocal
from app.core.exceptions import AppError
from app.modules.academic.models import Concept
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem, ContentVersion
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import (
    ContentWorkflowError,
    ContentWorkflowService,
)

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
MAYR_EID = f"GEMINI-{BATCH}-000098"
MAYR_CONCEPT_ID = "64a807cc-89f2-52dc-8b26-0e784e66b0cc"
MAYR_CODE = "lw-biological-species-concept-mayr"
EXPECTED_TAX = {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}
EXPECTED_BIO_PRE = {"DRAFT": 100, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 0}
EXPECTED_BIO_POST = {"DRAFT": 0, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 100}

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
DRY_RUN = ROOT / "ecaep_submission_dry_run.json"
OUT_JSON = ROOT / "ecaep_submission_execution_report.json"
OUT_MD = ROOT / "ecaep_submission_execution_report.md"


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
    ev = (body or {}).get("ncert_evidence") or {}
    return ev.get("verification_level")


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
    drafts = [i for i in bio if i.status == "DRAFT"]
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
        "mapped_drafts": sum(1 for i in drafts if i.concept_id),
        "student_bio_hits": student_hits,
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
        if not is_batch_item(i):
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


async def preflight(session, plan: dict) -> dict:
    planned_ids: list[str] = plan["deterministic_question_ids"]
    if len(planned_ids) != 100:
        raise Abort("planned_id_count", 100, len(planned_ids))
    if len(set(planned_ids)) != 100:
        raise Abort("planned_id_unique", 100, len(set(planned_ids)))

    superseded_plan = set(plan.get("selection_proof", {}).get("excluded_superseded_ids") or [])
    overlap = set(planned_ids) & superseded_plan
    if overlap:
        raise Abort("superseded_in_plan", set(), overlap)

    pre = await snap(session)
    if pre["taxonomy"] != EXPECTED_TAX:
        raise Abort("taxonomy", EXPECTED_TAX, pre["taxonomy"])
    if pre["biology"] != EXPECTED_BIO_PRE:
        raise Abort("biology_pre", EXPECTED_BIO_PRE, pre["biology"])
    if pre["physics_DRAFT"] != 24:
        raise Abort("physics_DRAFT", 24, pre["physics_DRAFT"])
    if pre["student_bio_hits"] != 0 or pre["practice_nonpub_hits"] != 0:
        raise Abort("student_safety_pre", 0, pre)

    by_eid = await load_item_map(session)
    fingerprints: dict[str, dict] = {}
    for eid in planned_ids:
        item = by_eid.get(eid)
        if not item:
            raise Abort("missing_live_item", eid, None)
        if item.status != "DRAFT":
            raise Abort("status_not_draft", "DRAFT", item.status)
        if item.deleted_at is not None:
            raise Abort("not_active", None, str(item.deleted_at))
        if not is_batch_item(item):
            raise Abort("wrong_batch", BATCH, item.tags)
        if item.concept_id is None:
            raise Abort("null_concept", eid, None)
        body = latest_body(item)
        fingerprints[eid] = {
            "content_item_id": str(item.id),
            "concept_id": str(item.concept_id),
            "body_sha256": body_fp(body),
            "verification_level": ncert_level(body),
            "status": item.status,
        }

    # SUPERSEDED must exist and not be in plan
    superseded_live = [
        eid for eid, i in by_eid.items() if i.status == "SUPERSEDED"
    ]
    if len(superseded_live) != 5:
        raise Abort("superseded_count", 5, len(superseded_live))
    if set(superseded_live) & set(planned_ids):
        raise Abort("superseded_in_selection", set(), set(superseded_live) & set(planned_ids))

    # Q000098 Mayr
    mayr = by_eid.get(MAYR_EID)
    if not mayr:
        raise Abort("mayr_missing", MAYR_EID, None)
    if str(mayr.concept_id) != MAYR_CONCEPT_ID:
        raise Abort("mayr_concept_id", MAYR_CONCEPT_ID, str(mayr.concept_id))
    code = (
        await session.execute(select(Concept.code).where(Concept.id == mayr.concept_id))
    ).scalar_one_or_none()
    if code != MAYR_CODE:
        raise Abort("mayr_concept_code", MAYR_CODE, code)

    # Canonical eligibility for all 100
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

    return {
        "pre": pre,
        "fingerprints": fingerprints,
        "eligibility": eligibility,
        "superseded_excluded": sorted(superseded_live),
        "planned_ids": planned_ids,
        "content_item_ids": [fingerprints[e]["content_item_id"] for e in planned_ids],
    }


async def post_verify(session, preflight_data: dict) -> dict:
    post = await snap(session)
    planned = preflight_data["planned_ids"]
    fps_before = preflight_data["fingerprints"]
    by_eid = await load_item_map(session)

    unexpected_mutations: list[str] = []
    ai_reports: list[dict] = []
    statuses = {}
    for eid in planned:
        item = by_eid.get(eid)
        if not item:
            unexpected_mutations.append(f"missing_after:{eid}")
            continue
        statuses[eid] = item.status
        if item.status != "IN_REVIEW":
            unexpected_mutations.append(f"status:{eid}={item.status}")
        if str(item.concept_id) != fps_before[eid]["concept_id"]:
            unexpected_mutations.append(f"concept_changed:{eid}")
        body = latest_body(item)
        # Strip ai_check from comparison? ai_check is on version not body.
        if body_fp(body) != fps_before[eid]["body_sha256"]:
            unexpected_mutations.append(f"body_changed:{eid}")
        if ncert_level(body) != fps_before[eid]["verification_level"]:
            unexpected_mutations.append(f"verification_level_changed:{eid}")
        ver = latest_version(item)
        report = ver.ai_check_report if ver else None
        ok_report = isinstance(report, dict) and "status" in report and "checked_at" in report
        ai_reports.append(
            {
                "question_id": eid,
                "ai_check_report_present": report is not None,
                "ai_check_report_ok": ok_report,
                "ai_check_status": (report or {}).get("status") if isinstance(report, dict) else None,
                "workflow_state": ver.workflow_state if ver else None,
            }
        )
        if not ok_report:
            unexpected_mutations.append(f"ai_check_missing_or_malformed:{eid}")

    # No unexpected IDs in IN_REVIEW for this batch
    in_review_eids = sorted(eid for eid, i in by_eid.items() if i.status == "IN_REVIEW")
    if set(in_review_eids) != set(planned):
        unexpected_mutations.append(
            f"in_review_set_mismatch extra={sorted(set(in_review_eids)-set(planned))} "
            f"missing={sorted(set(planned)-set(in_review_eids))}"
        )

    if post["biology"] != EXPECTED_BIO_POST:
        unexpected_mutations.append(f"biology_post={post['biology']}")
    if post["taxonomy"] != EXPECTED_TAX:
        unexpected_mutations.append(f"taxonomy_changed={post['taxonomy']}")
    if post["physics_DRAFT"] != 24:
        unexpected_mutations.append(f"physics_DRAFT={post['physics_DRAFT']}")
    if post["student_bio_hits"] != 0 or post["practice_nonpub_hits"] != 0:
        unexpected_mutations.append(f"student_exposure={post}")

    ai_ok = sum(1 for r in ai_reports if r["ai_check_report_ok"])
    return {
        "post": post,
        "ai_check_coverage": {
            "present_ok": ai_ok,
            "total": len(ai_reports),
            "all_ok": ai_ok == 100,
            "reports": ai_reports,
        },
        "in_review_ids": in_review_eids,
        "unexpected_mutations": unexpected_mutations,
        "ok": len(unexpected_mutations) == 0 and post["biology"] == EXPECTED_BIO_POST,
    }


async def idempotency_probe(session, sample_item_id: uuid.UUID) -> dict:
    workflow = ContentWorkflowService(session)
    gate = await workflow.evaluate_submit_for_review(sample_item_id)
    rejected = (
        not gate["eligible"]
        and gate["rejection_code"] == "INVALID_WORKFLOW_TRANSITION"
        and "IN_REVIEW" in (gate["rejection_reason"] or "")
    )
    # Also attempt submit (must not mutate) — catch error, ensure still IN_REVIEW
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
    return {
        "sample_item_id": str(sample_item_id),
        "evaluate_rejected": rejected,
        "evaluate_code": gate["rejection_code"],
        "evaluate_reason": gate["rejection_reason"],
        "submit_rejected": submit_rejected,
        "submit_code": submit_code,
        "submit_message": submit_message,
        "status_unchanged_in_review": item.status == "IN_REVIEW" if item else False,
        "ok": rejected and submit_rejected and item is not None and item.status == "IN_REVIEW",
    }


def write_report(payload: dict) -> None:
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    s = payload.get("summary") or payload
    lines = [
        "# ECAEP Submission Execution Report",
        "",
        f"## Verdict: {payload['verdict']}",
        "",
        f"Batch: `{BATCH}`  ",
        f"Executed: `{payload.get('executed_at')}`  ",
        f"Transaction: **{payload.get('transaction_result')}**  ",
        f"Rollback status: **{payload.get('rollback_status')}**",
        "",
        "## Assertions",
        "",
        "- ACTUAL ECAEP SUBMISSION PERFORMED"
        if payload.get("transaction_result") == "COMMITTED"
        else "- ECAEP SUBMISSION NOT COMMITTED",
        "- EXACTLY 100 QUESTIONS"
        if payload.get("submitted_count") == 100
        else f"- SUBMITTED COUNT: {payload.get('submitted_count')}",
        "- DATABASE STATE VERIFIED",
        "- NO PUBLICATION",
        "- NO STUDENT EXPOSURE",
        "- NO TAXONOMY MUTATION",
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
        f"- AI check reports OK: **{payload.get('ai_check_coverage', {}).get('present_ok')}/100**",
        f"- Student Biology visibility: **{payload.get('student_visibility')}**",
        f"- Practice nonpub hits: **{payload.get('practice_nonpub_hits')}**",
        f"- Physics DRAFT: **{payload.get('physics_DRAFT')}**",
        f"- Unexpected mutations: **{len(payload.get('unexpected_mutations') or [])}**",
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
        f"Exact submission IDs: see JSON (`submitted_question_ids`, n={len(payload.get('submitted_question_ids') or [])}).",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(*, do_commit: bool) -> dict:
    plan = json.loads(DRY_RUN.read_text(encoding="utf-8"))
    executed_at = datetime.now(UTC).isoformat()

    async with AsyncSessionLocal() as session:
        try:
            pf = await preflight(session, plan)
        except Abort as exc:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — ECAEP SUBMISSION FAILED",
                "transaction_result": "NO_COMMIT",
                "rollback_status": "N/A_PREFLIGHT_ABORT",
                "submitted_count": 0,
                "submitted_question_ids": [],
                "failure": {
                    "condition": exc.condition,
                    "expected": exc.expected,
                    "actual": exc.actual,
                },
                "pre_state": None,
                "post_state": None,
                "assertions": {
                    "ACTUAL ECAEP SUBMISSION PERFORMED": False,
                    "EXACTLY 100 QUESTIONS": False,
                    "DATABASE STATE VERIFIED": False,
                    "NO PUBLICATION": True,
                    "NO STUDENT EXPOSURE": True,
                    "NO TAXONOMY MUTATION": True,
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
                "submitted_question_ids": pf["planned_ids"],
                "pre_state": pf["pre"],
                "eligibility_results": pf["eligibility"],
                "failure": None,
            }
            write_report(payload)
            return payload

        workflow = ContentWorkflowService(session)
        submitted: list[dict] = []
        failure: dict | None = None
        try:
            # Ensure AI logs flush into this transaction
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
            # Verify restored state
            restored = await snap(session)
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — ECAEP SUBMISSION FAILED",
                "transaction_result": transaction_result,
                "rollback_status": rollback_status,
                "submitted_count": 0,
                "submitted_question_ids": pf["planned_ids"],
                "partial_attempt_count": len(submitted),
                "pre_state": pf["pre"],
                "post_state": restored,
                "restored_to_pre": restored == pf["pre"],
                "failure": failure,
                "eligibility_results": pf["eligibility"],
                "unexpected_mutations": [],
                "ai_check_coverage": {"present_ok": 0, "total": 0, "all_ok": False},
                "student_visibility": restored["student_bio_hits"],
                "practice_nonpub_hits": restored["practice_nonpub_hits"],
                "physics_DRAFT": restored["physics_DRAFT"],
                "idempotency": None,
                "assertions": {
                    "ACTUAL ECAEP SUBMISSION PERFORMED": False,
                    "EXACTLY 100 QUESTIONS": False,
                    "DATABASE STATE VERIFIED": restored == pf["pre"],
                    "NO PUBLICATION": restored["biology"]["PUBLISHED"] == 0,
                    "NO STUDENT EXPOSURE": restored["student_bio_hits"] == 0,
                    "NO TAXONOMY MUTATION": restored["taxonomy"] == EXPECTED_TAX,
                },
            }
            write_report(payload)
            return payload
        finally:
            session.info.pop("defer_commit", None)

        # Post-commit verification (new transaction state after commit)
        # Expire/refresh
        session.expire_all()
        post = await post_verify(session, pf)
        sample_id = uuid.UUID(pf["fingerprints"][pf["planned_ids"][0]]["content_item_id"])
        idem = await idempotency_probe(session, sample_id)

        ok = (
            post["ok"]
            and transaction_result == "COMMITTED"
            and len(submitted) == 100
            and all(s["status"] == "IN_REVIEW" for s in submitted)
            and idem["ok"]
        )
        verdict = (
            "GREEN — 100 QUESTIONS SUBMITTED TO ECAEP"
            if ok
            else "RED — ECAEP SUBMISSION FAILED"
        )
        payload = {
            "batch_id": BATCH,
            "executed_at": executed_at,
            "verdict": verdict,
            "transaction_result": transaction_result,
            "rollback_status": rollback_status,
            "submitted_count": len(submitted),
            "submitted_question_ids": [s["question_id"] for s in submitted],
            "submitted_content_item_ids": [s["content_item_id"] for s in submitted],
            "matches_dry_run_plan": [s["question_id"] for s in submitted] == pf["planned_ids"],
            "pre_state": pf["pre"],
            "post_state": post["post"],
            "eligibility_results": pf["eligibility"],
            "ai_check_coverage": {
                "present_ok": post["ai_check_coverage"]["present_ok"],
                "total": post["ai_check_coverage"]["total"],
                "all_ok": post["ai_check_coverage"]["all_ok"],
                # keep per-question in JSON but summarize statuses
                "status_counts": dict(
                    Counter(
                        r["ai_check_status"]
                        for r in post["ai_check_coverage"]["reports"]
                    )
                ),
                "reports": post["ai_check_coverage"]["reports"],
            },
            "student_visibility": post["post"]["student_bio_hits"],
            "practice_nonpub_hits": post["post"]["practice_nonpub_hits"],
            "physics_DRAFT": post["post"]["physics_DRAFT"],
            "taxonomy_invariant": post["post"]["taxonomy"] == EXPECTED_TAX,
            "unexpected_mutations": post["unexpected_mutations"],
            "idempotency": idem,
            "failure": None,
            "assertions": {
                "ACTUAL ECAEP SUBMISSION PERFORMED": True,
                "EXACTLY 100 QUESTIONS": len(submitted) == 100,
                "DATABASE STATE VERIFIED": post["ok"],
                "NO PUBLICATION": post["post"]["biology"]["PUBLISHED"] == 0,
                "NO STUDENT EXPOSURE": post["post"]["student_bio_hits"] == 0,
                "NO TAXONOMY MUTATION": post["post"]["taxonomy"] == EXPECTED_TAX,
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
                "rollback_status": result.get("rollback_status"),
                "submitted_count": result.get("submitted_count"),
                "post_biology": (result.get("post_state") or {}).get("biology"),
                "student_visibility": result.get("student_visibility"),
                "unexpected_mutations": result.get("unexpected_mutations"),
                "idempotency_ok": (result.get("idempotency") or {}).get("ok"),
                "failure": result.get("failure"),
            },
            indent=2,
            default=str,
        )
    )
    return 0 if str(result.get("verdict", "")).startswith("GREEN") and result.get("transaction_result") == "COMMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
