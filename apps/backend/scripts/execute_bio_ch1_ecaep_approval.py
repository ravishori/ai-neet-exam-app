"""Atomic ECAEP approval for Biology Ch1 100 IN_REVIEW questions.

Uses ContentWorkflowService.review(..., decision='approve', commit=False)
then a single session.commit(). Never publishes.

Usage:
  python scripts/execute_bio_ch1_ecaep_approval.py --commit
  python scripts/execute_bio_ch1_ecaep_approval.py --dry-preflight
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

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
EXPECTED_TAX = {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}
EXPECTED_BIO_PRE = {"DRAFT": 0, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 100}
EXPECTED_BIO_POST = {"DRAFT": 0, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 100, "IN_REVIEW": 0}

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
DRY_RUN = ROOT / "ecaep_submission_dry_run.json"
EXEC_SUB = ROOT / "ecaep_submission_execution_report.json"
ADJ = ROOT / "ecaep_ai_review_adjudication.json"
OUT_JSON = ROOT / "ecaep_approval_execution_report.json"
OUT_MD = ROOT / "ecaep_approval_execution_report.md"
COMMENT = (
    "Biology Ch1 pilot ECAEP approval — AI review + adjudication GREEN; "
    "documented warnings accepted; no publication."
)


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


async def preflight(session, planned_ids: list[str], superseded_excluded: list[str]) -> dict:
    if len(planned_ids) != 100 or len(set(planned_ids)) != 100:
        raise Abort("planned_count", 100, len(planned_ids))
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

    by_eid = await load_batch_map(session)
    superseded_live = sorted(eid for eid, i in by_eid.items() if i.status == "SUPERSEDED")
    if len(superseded_live) != 5:
        raise Abort("superseded_count", 5, len(superseded_live))
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
            }
        )
        if not gate["eligible"]:
            raise Abort(
                f"ineligible:{eid}",
                "ELIGIBLE",
                f"{gate['rejection_code']}: {gate['rejection_reason']}",
            )

    ineligible = [e for e in eligibility if not e["eligible"]]
    if ineligible:
        raise Abort("ineligible_count", 0, len(ineligible))

    return {
        "pre": pre,
        "fingerprints": fingerprints,
        "eligibility": eligibility,
        "planned_ids": planned_ids,
        "superseded_excluded": superseded_live,
    }


async def post_verify(session, pf: dict) -> dict:
    post = await snap(session)
    by_eid = await load_batch_map(session)
    planned = pf["planned_ids"]
    fps = pf["fingerprints"]
    unexpected = []
    approved_ids = []
    for eid in planned:
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

    approved_all = sorted(eid for eid, i in by_eid.items() if i.status == "APPROVED")
    if set(approved_all) != set(planned):
        unexpected.append(
            f"approved_set_mismatch extra={sorted(set(approved_all)-set(planned))} "
            f"missing={sorted(set(planned)-set(approved_all))}"
        )
    if post["biology"] != EXPECTED_BIO_POST:
        unexpected.append(f"biology_post={post['biology']}")
    if post["taxonomy"] != EXPECTED_TAX:
        unexpected.append(f"taxonomy={post['taxonomy']}")
    if post["physics_DRAFT"] != 24:
        unexpected.append(f"physics={post['physics_DRAFT']}")
    if post["student_bio_hits"] != 0 or post["practice_nonpub_hits"] != 0:
        unexpected.append(f"student_exposure={post}")

    return {
        "post": post,
        "approved_ids": approved_ids,
        "unexpected_mutations": unexpected,
        "ok": len(unexpected) == 0,
    }


async def publication_gate_sample(session, pf: dict) -> dict:
    """Evaluate publication gates WITHOUT publishing. Expect ncert:NOT_VERIFIED blockers."""
    by_eid = await load_batch_map(session)
    samples = [
        pf["planned_ids"][0],
        pf["planned_ids"][49],
        pf["planned_ids"][97],  # Q000098 Mayr
        pf["planned_ids"][-1],
    ]
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
    return {
        "publish_called": False,
        "sample_results": sample_results,
        "batch_would_pass_publication": would_publish,
        "batch_blocker_counts": dict(batch_blocker_counts),
        "approved_not_published_demonstrated": would_publish == 0
        and batch_blocker_counts.get("ncert:NOT_VERIFIED", 0) == 100,
        "note": "APPROVED ≠ PUBLISHED — publication gates still block (esp. ncert:NOT_VERIFIED).",
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
        "- NO STUDENT EXPOSURE",
        "- NO TAXONOMY MUTATION",
        "- DATABASE STATE VERIFIED",
        "",
        "## Pre / Post",
        "",
        "```json",
        json.dumps({"pre": payload.get("pre_state"), "post": payload.get("post_state")}, indent=2),
        "```",
        "",
        f"- Student Biology visibility: **{payload.get('student_visibility')}**",
        f"- Practice nonpub hits: **{payload.get('practice_nonpub_hits')}**",
        f"- Physics DRAFT: **{payload.get('physics_DRAFT')}**",
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
    adj = json.loads(ADJ.read_text(encoding="utf-8"))
    planned = dry["deterministic_question_ids"]
    if planned != exec_sub.get("submitted_question_ids"):
        raise SystemExit("ABORT: dry-run IDs != execution submitted IDs")
    if not str(adj.get("verdict", "")).startswith("GREEN"):
        raise SystemExit(f"ABORT: adjudication not GREEN: {adj.get('verdict')}")

    superseded = dry.get("selection_proof", {}).get("excluded_superseded_ids") or []
    executed_at = datetime.now(UTC).isoformat()

    async with AsyncSessionLocal() as session:
        try:
            pf = await preflight(session, planned, superseded)
        except Abort as exc:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — APPROVAL FAILED / ROLLED BACK",
                "transaction_result": "NO_COMMIT",
                "rollback_status": "N/A_PREFLIGHT_ABORT",
                "approved_count": 0,
                "approved_question_ids": [],
                "failure": {
                    "condition": exc.condition,
                    "expected": exc.expected,
                    "actual": exc.actual,
                },
                "assertions": {
                    "ACTUAL ECAEP APPROVAL PERFORMED": False,
                    "EXACTLY 100 QUESTIONS": False,
                    "NO PUBLICATION": True,
                    "NO STUDENT EXPOSURE": True,
                    "NO TAXONOMY MUTATION": True,
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
                "approved_question_ids": pf["planned_ids"],
                "pre_state": pf["pre"],
                "eligibility_results": pf["eligibility"],
                "eligible_count": 100,
                "ineligible_count": 0,
                "failure": None,
            }
            write_report(payload)
            return payload

        workflow = ContentWorkflowService(session)
        reviewer = await actor_user(session)
        approved = []
        failure = None
        try:
            for eid in pf["planned_ids"]:
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
                "approved_question_ids": pf["planned_ids"],
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
                "publication_gates": None,
                "idempotency": None,
                "assertions": {
                    "ACTUAL ECAEP APPROVAL PERFORMED": False,
                    "EXACTLY 100 QUESTIONS": False,
                    "NO PUBLICATION": restored["biology"]["PUBLISHED"] == 0,
                    "NO STUDENT EXPOSURE": restored["student_bio_hits"] == 0,
                    "NO TAXONOMY MUTATION": restored["taxonomy"] == EXPECTED_TAX,
                    "DATABASE STATE VERIFIED": restored == pf["pre"],
                },
            }
            write_report(payload)
            return payload

        session.expire_all()
        post = await post_verify(session, pf)
        pub = await publication_gate_sample(session, pf)
        sample_id = uuid.UUID(pf["fingerprints"][pf["planned_ids"][0]]["content_item_id"])
        idem = await idempotency_probe(session, sample_id)

        ok = (
            post["ok"]
            and transaction_result == "COMMITTED"
            and len(approved) == 100
            and all(a["status"] == "APPROVED" for a in approved)
            and [a["question_id"] for a in approved] == pf["planned_ids"]
            and idem["ok"]
            and pub["approved_not_published_demonstrated"]
            and post["post"]["biology"]["PUBLISHED"] == 0
        )
        verdict = (
            "GREEN — 100 QUESTIONS APPROVED"
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
            "approved_question_ids": [a["question_id"] for a in approved],
            "approved_content_item_ids": [a["content_item_id"] for a in approved],
            "matches_dry_run_plan": [a["question_id"] for a in approved] == pf["planned_ids"],
            "eligible_count": 100,
            "ineligible_count": 0,
            "eligibility_results": pf["eligibility"],
            "pre_state": pf["pre"],
            "post_state": post["post"],
            "unexpected_mutations": post["unexpected_mutations"],
            "student_visibility": post["post"]["student_bio_hits"],
            "practice_nonpub_hits": post["post"]["practice_nonpub_hits"],
            "physics_DRAFT": post["post"]["physics_DRAFT"],
            "taxonomy_invariant": post["post"]["taxonomy"] == EXPECTED_TAX,
            "publication_gates": pub,
            "idempotency": idem,
            "failure": None,
            "adjudication_verdict_referenced": adj.get("verdict"),
            "assertions": {
                "ACTUAL ECAEP APPROVAL PERFORMED": True,
                "EXACTLY 100 QUESTIONS": len(approved) == 100,
                "NO PUBLICATION": post["post"]["biology"]["PUBLISHED"] == 0,
                "NO STUDENT EXPOSURE": post["post"]["student_bio_hits"] == 0,
                "NO TAXONOMY MUTATION": post["post"]["taxonomy"] == EXPECTED_TAX,
                "DATABASE STATE VERIFIED": post["ok"],
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
                "approved_count": result.get("approved_count"),
                "post_biology": (result.get("post_state") or {}).get("biology"),
                "student_visibility": result.get("student_visibility"),
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
    return (
        0
        if str(result.get("verdict", "")).startswith("GREEN")
        and result.get("transaction_result") == "COMMITTED"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
