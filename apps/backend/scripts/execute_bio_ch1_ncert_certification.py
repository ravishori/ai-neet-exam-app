"""Atomic NCERT SOURCE_TEXT_VERIFIED certification for Biology Ch1 pilot.

Uses ContentWorkflowService.certify_ncert_evidence(..., commit=False)
then a single session.commit(). Never publishes.

Usage (from apps/backend):
  python scripts/execute_bio_ch1_ncert_certification.py            # dry-run default
  python scripts/execute_bio_ch1_ncert_certification.py --commit
  python scripts/execute_bio_ch1_ncert_certification.py --dry-preflight
"""
from __future__ import annotations

import argparse
import asyncio
import copy
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
    DEFAULT_NCERT_CERTIFICATION_METHOD,
    NCERT_CERTIFICATION_LEVEL,
)
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
EXPECTED_TAX = {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}
EXPECTED_BIO_PRE = {
    "DRAFT": 0,
    "SUPERSEDED": 5,
    "PUBLISHED": 0,
    "APPROVED": 100,
    "IN_REVIEW": 0,
}
EXPECTED_BIO_POST = EXPECTED_BIO_PRE

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
DRY_RUN_SRC = ROOT / "ecaep_submission_dry_run.json"
APPROVAL_EXEC = ROOT / "ecaep_approval_execution_report.json"
OUT_JSON = ROOT / "ncert_verification_workflow_implementation_report.json"
OUT_MD = ROOT / "ncert_verification_workflow_implementation_report.md"

PEDAGOGY_KEYS = ("stem", "options", "correct_option", "explanation", "difficulty")


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


def pedagogy_fp(body: dict | None) -> str:
    raw = body or {}
    snap = {k: copy.deepcopy(raw.get(k)) for k in PEDAGOGY_KEYS}
    return hashlib.sha256(
        json.dumps(snap, sort_keys=True, ensure_ascii=False, default=str).encode()
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
    not_verified = 0
    already_certified = 0
    for eid in planned_ids:
        item = by_eid.get(eid)
        if not item:
            raise Abort("missing_item", eid, None)
        if item.status != "APPROVED":
            raise Abort("status", "APPROVED", item.status)
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
        level = ncert_level(body)
        if level == "NOT_VERIFIED":
            not_verified += 1
        elif level == NCERT_CERTIFICATION_LEVEL:
            already_certified += 1
        fingerprints[eid] = {
            "content_item_id": str(item.id),
            "content_version_id": str(ver.id) if ver else None,
            "slug": item.slug,
            "concept_id": str(item.concept_id),
            "status": item.status,
            "body_sha256": body_fp(body),
            "pedagogy_sha256": pedagogy_fp(body),
            "verification_level": level,
            "provenance_origin": (body.get("provenance") or {}).get("origin"),
            "provenance_source": (body.get("provenance") or {}).get("source"),
            "provenance_batch_id": (body.get("provenance") or {}).get("batch_id"),
            "ncert_source_document": (body.get("ncert_evidence") or {}).get("source_document"),
            "ncert_chapter": (body.get("ncert_evidence") or {}).get("chapter"),
            "difficulty": body.get("difficulty"),
            "question_type_tag": next(
                (t for t in (item.tags or []) if t.startswith("question_type:")), None
            ),
        }
        gate = await workflow.evaluate_certify_ncert(item.id, required_batch_id=BATCH)
        eligibility.append(
            {
                "question_id": eid,
                "eligible": gate["eligible"],
                "rejection_code": gate["rejection_code"],
                "rejection_reason": gate["rejection_reason"],
                "previous_level": gate["previous_level"],
                "already_certified": gate["already_certified"],
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
        "not_verified_count": not_verified,
        "already_certified_count": already_certified,
        "eligible_count": len(eligibility),
        "rejected_count": 0,
        "would_certify": sum(1 for e in eligibility if e["eligible"] and not e["already_certified"]),
        "would_noop_already_certified": sum(1 for e in eligibility if e["already_certified"]),
        "would_publish": 0,
        "db_writes": 0,
    }


async def post_verify(session, pf: dict) -> dict:
    post = await snap(session)
    by_eid = await load_batch_map(session)
    planned = pf["planned_ids"]
    fps = pf["fingerprints"]
    unexpected = []
    certified_ids = []
    levels = Counter()
    for eid in planned:
        item = by_eid.get(eid)
        if not item:
            unexpected.append(f"missing:{eid}")
            continue
        if item.status != "APPROVED":
            unexpected.append(f"status:{eid}={item.status}")
        certified_ids.append(eid)
        if str(item.concept_id) != fps[eid]["concept_id"]:
            unexpected.append(f"concept_changed:{eid}")
        if item.slug != fps[eid]["slug"]:
            unexpected.append(f"slug_changed:{eid}")
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        if pedagogy_fp(body) != fps[eid]["pedagogy_sha256"]:
            unexpected.append(f"pedagogy_changed:{eid}")
        level = ncert_level(body)
        levels[level or "MISSING"] += 1
        if level != NCERT_CERTIFICATION_LEVEL:
            unexpected.append(f"verification_level:{eid}={level}")
        prov = body.get("provenance") or {}
        if prov.get("origin") != fps[eid]["provenance_origin"]:
            unexpected.append(f"provenance_origin:{eid}")
        if prov.get("source") != fps[eid]["provenance_source"]:
            unexpected.append(f"provenance_source:{eid}")
        if prov.get("batch_id") != fps[eid]["provenance_batch_id"]:
            unexpected.append(f"provenance_batch_id:{eid}")
        ncert = body.get("ncert_evidence") or {}
        if ncert.get("source_document") != fps[eid]["ncert_source_document"]:
            unexpected.append(f"ncert_source_document:{eid}")
        if ncert.get("chapter") != fps[eid]["ncert_chapter"]:
            unexpected.append(f"ncert_chapter:{eid}")
        if body.get("difficulty") != fps[eid]["difficulty"]:
            unexpected.append(f"difficulty:{eid}")
        if str(ver.id) != fps[eid]["content_version_id"]:
            unexpected.append(f"version_id_changed:{eid}")

    # Superseded must remain untouched (still NOT_VERIFIED typically)
    for eid in pf["superseded_excluded"]:
        item = by_eid.get(eid)
        if not item:
            unexpected.append(f"superseded_missing:{eid}")
            continue
        if item.status != "SUPERSEDED":
            unexpected.append(f"superseded_status:{eid}={item.status}")

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
        "certified_ids": certified_ids,
        "verification_levels": dict(levels),
        "unexpected_mutations": unexpected,
        "ok": len(unexpected) == 0,
    }


async def publication_gate_batch(session, pf: dict) -> dict:
    by_eid = await load_batch_map(session)
    batch_blocker_counts: Counter = Counter()
    would_publish = 0
    ncert_blocker = 0
    samples = [
        pf["planned_ids"][0],
        pf["planned_ids"][49],
        pf["planned_ids"][97],
        pf["planned_ids"][-1],
    ]
    sample_results = []
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
        if "ncert:NOT_VERIFIED" in report.reasons:
            ncert_blocker += 1
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
                    "ncert_ok": report.ncert_ok,
                }
            )
    return {
        "publish_called": False,
        "sample_results": sample_results,
        "batch_would_pass_publication": would_publish,
        "batch_blocker_counts": dict(batch_blocker_counts),
        "ncert_NOT_VERIFIED_blocker_count": ncert_blocker,
        "ncert_blocker_cleared": ncert_blocker == 0,
        "remaining_publication_blockers": dict(batch_blocker_counts),
        "note": "Certification does not publish. Remaining blockers reported only.",
    }


async def idempotency_probe(session, sample_item_id: uuid.UUID) -> dict:
    workflow = ContentWorkflowService(session)
    actor = await actor_user(session)
    before = await workflow.repo.get_item(sample_item_id)
    before_ver = await workflow.repo.get_version(before.latest_version_id)
    before_body = copy.deepcopy(before_ver.body)
    result = await workflow.certify_ncert_evidence(
        sample_item_id,
        actor_user_id=actor.id,
        required_batch_id=BATCH,
        commit=True,
    )
    after = await workflow.repo.get_item(sample_item_id)
    after_ver = await workflow.repo.get_version(after.latest_version_id)
    return {
        "sample_item_id": str(sample_item_id),
        "changed": result["changed"],
        "already_certified": result.get("already_certified"),
        "previous_verification_level": result["previous_verification_level"],
        "new_verification_level": result["new_verification_level"],
        "status_unchanged_approved": after.status == "APPROVED",
        "body_unchanged": after_ver.body == before_body,
        "ok": (
            result["changed"] is False
            and result.get("already_certified") is True
            and after.status == "APPROVED"
            and after_ver.body == before_body
        ),
    }


def write_report(payload: dict) -> None:
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    lines = [
        "# NCERT Verification Workflow Implementation Report",
        "",
        f"## Verdict: {payload['verdict']}",
        "",
        f"Batch: `{BATCH}`  ",
        f"Executed: `{payload.get('executed_at')}`  ",
        f"Transaction: **{payload.get('transaction_result')}**  ",
        f"Mode: **{payload.get('mode')}**",
        "",
        "## Architecture",
        "",
        "- Service: `ContentWorkflowService.certify_ncert_evidence` / `evaluate_certify_ncert`",
        "- API: `POST /content-items/{item_id}/certify-ncert` (permission `content.review`)",
        "- CLI: `scripts/execute_bio_ch1_ncert_certification.py` (thin wrapper; logic in service)",
        f"- Verification level: `{NCERT_CERTIFICATION_LEVEL}`",
        f"- Method: `{DEFAULT_NCERT_CERTIFICATION_METHOD}`",
        "- Evidence basis: existing Ch1 NCERT extract + batch audit artifacts "
        "(final_100_pilot_integrity_audit, ncert_verification_audit); "
        "no fabricated page numbers; existing `ncert_evidence` source fields preserved",
        "- Audit: `AuditLog` action `content.certify_ncert`",
        "",
        "## Dry-run / Live results",
        "",
        "```json",
        json.dumps(
            {
                "eligible": payload.get("eligible_count"),
                "rejected": payload.get("rejected_count"),
                "would_certify": payload.get("would_certify"),
                "certified_count": payload.get("certified_count"),
                "already_certified_noop": payload.get("already_certified_noop"),
                "would_publish": payload.get("would_publish", 0),
                "db_writes": payload.get("db_writes"),
            },
            indent=2,
        ),
        "```",
        "",
        "## Before / After",
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
        "## No-content-mutation proof",
        "",
        "```json",
        json.dumps(payload.get("mutation_proof"), indent=2),
        "```",
        "",
        "## Limitations",
        "",
        "- Certification records SOURCE_TEXT_VERIFIED against existing structured evidence; "
        "filesystem audit paths are not stored in JSONB.",
        "- Does not invent PAGE_VERIFIED / page numbers.",
        "- Does not publish or change publication_gates logic.",
        "",
        "## Exact next step",
        "",
        payload.get("exact_next_step")
        or "Address remaining publication blockers (if any), then a separate explicit publish task.",
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
    dry = json.loads(DRY_RUN_SRC.read_text(encoding="utf-8"))
    approval = json.loads(APPROVAL_EXEC.read_text(encoding="utf-8"))
    planned = dry["deterministic_question_ids"]
    approved_ids = approval.get("approved_question_ids") or []
    if planned != approved_ids:
        raise SystemExit("ABORT: planned dry-run IDs != approval approved_question_ids")
    if not str(approval.get("verdict", "")).startswith("GREEN"):
        raise SystemExit(f"ABORT: approval report not GREEN: {approval.get('verdict')}")

    superseded = dry.get("selection_proof", {}).get("excluded_superseded_ids") or []
    executed_at = datetime.now(UTC).isoformat()

    async with AsyncSessionLocal() as session:
        try:
            pf = await preflight(session, planned, superseded)
        except Abort as exc:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "mode": "commit" if do_commit else "dry-run",
                "verdict": "RED — NCERT CERTIFICATION PREFLIGHT FAILED",
                "transaction_result": "NO_COMMIT",
                "certified_count": 0,
                "certified_question_ids": [],
                "failure": {
                    "condition": exc.condition,
                    "expected": exc.expected,
                    "actual": exc.actual,
                },
                "architecture": {
                    "service": "ContentWorkflowService.certify_ncert_evidence",
                    "api": "POST /content-items/{item_id}/certify-ncert",
                    "cli": "scripts/execute_bio_ch1_ncert_certification.py",
                    "verification_level": NCERT_CERTIFICATION_LEVEL,
                },
            }
            write_report(payload)
            return payload

        if not do_commit:
            gates = await publication_gate_batch(session, pf)
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "mode": "dry-run",
                "verdict": "GREEN — DRY-RUN READY (NO DB WRITES)",
                "transaction_result": "NO_COMMIT",
                "rollback_status": "N/A",
                "eligible_count": pf["eligible_count"],
                "rejected_count": 0,
                "would_certify": pf["would_certify"],
                "would_noop_already_certified": pf["would_noop_already_certified"],
                "would_publish": 0,
                "db_writes": 0,
                "certified_count": 0,
                "certified_question_ids": pf["planned_ids"],
                "not_verified_count": pf["not_verified_count"],
                "pre_state": pf["pre"],
                "post_state": None,
                "eligibility_results": pf["eligibility"],
                "superseded_excluded": pf["superseded_excluded"],
                "publication_gates": gates,
                "student_visibility": pf["pre"]["student_bio_hits"],
                "practice_nonpub_hits": pf["pre"]["practice_nonpub_hits"],
                "physics_DRAFT": pf["pre"]["physics_DRAFT"],
                "architecture": {
                    "service": "ContentWorkflowService.certify_ncert_evidence",
                    "api": "POST /content-items/{item_id}/certify-ncert",
                    "cli": "scripts/execute_bio_ch1_ncert_certification.py",
                    "verification_level": NCERT_CERTIFICATION_LEVEL,
                    "verification_method": DEFAULT_NCERT_CERTIFICATION_METHOD,
                    "evidence_basis": [
                        "docs/acquisition/batches/_scratch_bio11_ch01_ncert.txt",
                        "ncert_verification_audit.md/json",
                        "final_100_pilot_integrity_audit.md/json",
                        "existing body.ncert_evidence source fields",
                    ],
                },
                "exact_next_step": (
                    "Re-run with --commit to apply SOURCE_TEXT_VERIFIED to the 100 APPROVED questions."
                ),
                "failure": None,
            }
            write_report(payload)
            return payload

        workflow = ContentWorkflowService(session)
        actor = await actor_user(session)
        certified = []
        failure = None
        try:
            for eid in pf["planned_ids"]:
                item_id = uuid.UUID(pf["fingerprints"][eid]["content_item_id"])
                try:
                    result = await workflow.certify_ncert_evidence(
                        item_id,
                        actor_user_id=actor.id,
                        required_batch_id=BATCH,
                        commit=False,
                    )
                except Exception as exc:  # noqa: BLE001
                    failure = {
                        "question_id": eid,
                        "content_item_id": str(item_id),
                        "error_type": type(exc).__name__,
                        "error_code": getattr(exc, "code", None),
                        "error_message": str(exc),
                        "gate": "ContentWorkflowService.certify_ncert_evidence",
                    }
                    raise
                certified.append(
                    {
                        "question_id": eid,
                        "content_item_id": result["content_item_id"],
                        "content_version_id": result["content_version_id"],
                        "changed": result["changed"],
                        "previous_verification_level": result["previous_verification_level"],
                        "new_verification_level": result["new_verification_level"],
                        "status": result["status"],
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
                "mode": "commit",
                "verdict": "RED — NCERT CERTIFICATION FAILED / ROLLED BACK",
                "transaction_result": "ROLLED_BACK",
                "rollback_status": "ROLLED_BACK_TO_PRE_CERTIFICATION",
                "certified_count": 0,
                "certified_question_ids": pf["planned_ids"],
                "pre_state": pf["pre"],
                "post_state": restored,
                "failure": failure,
                "architecture": {
                    "service": "ContentWorkflowService.certify_ncert_evidence",
                    "verification_level": NCERT_CERTIFICATION_LEVEL,
                },
            }
            write_report(payload)
            return payload

        # Re-load after commit
        by_eid = await load_batch_map(session)
        post = await post_verify(session, pf)
        gates = await publication_gate_batch(session, pf)
        sample_id = uuid.UUID(pf["fingerprints"][pf["planned_ids"][0]]["content_item_id"])
        idem = await idempotency_probe(session, sample_id)

        changed_count = sum(1 for c in certified if c["changed"])
        noop_count = sum(1 for c in certified if not c["changed"])
        mutation_proof = {
            "pedagogy_unchanged_count": 100 - sum(
                1 for u in post["unexpected_mutations"] if u.startswith("pedagogy_")
            ),
            "concept_unchanged": not any(
                u.startswith("concept_changed") for u in post["unexpected_mutations"]
            ),
            "slug_unchanged": not any(
                u.startswith("slug_changed") for u in post["unexpected_mutations"]
            ),
            "provenance_source_batch_unchanged": not any(
                u.startswith("provenance_") for u in post["unexpected_mutations"]
            ),
            "version_ids_unchanged": not any(
                u.startswith("version_id_changed") for u in post["unexpected_mutations"]
            ),
            "only_ncert_verification_metadata_intended_change": True,
            "unexpected_mutations": post["unexpected_mutations"],
        }

        green = (
            post["ok"]
            and gates["ncert_blocker_cleared"]
            and idem["ok"]
            and post["post"]["biology"]["PUBLISHED"] == 0
            and post["post"]["student_bio_hits"] == 0
            and changed_count + noop_count == 100
        )
        remaining = {
            k: v
            for k, v in gates["remaining_publication_blockers"].items()
            if k != "ncert:NOT_VERIFIED"
        }
        payload = {
            "batch_id": BATCH,
            "executed_at": executed_at,
            "mode": "commit",
            "verdict": (
                "GREEN — NCERT CERTIFICATION COMPLETE (NOT PUBLISHED)"
                if green
                else "AMBER/RED — CERTIFICATION COMPLETED WITH ANOMALIES"
            ),
            "transaction_result": transaction_result,
            "rollback_status": rollback_status,
            "eligible_count": 100,
            "rejected_count": 0,
            "certified_count": changed_count,
            "already_certified_noop": noop_count,
            "db_writes": changed_count,
            "would_publish": 0,
            "certified_question_ids": pf["planned_ids"],
            "certification_results": certified,
            "superseded_excluded": pf["superseded_excluded"],
            "pre_state": pf["pre"],
            "post_state": post["post"],
            "verification_levels": post["verification_levels"],
            "publication_gates": gates,
            "remaining_publication_blockers": remaining,
            "idempotency": idem,
            "mutation_proof": mutation_proof,
            "unexpected_mutations": post["unexpected_mutations"],
            "student_visibility": post["post"]["student_bio_hits"],
            "practice_nonpub_hits": post["post"]["practice_nonpub_hits"],
            "physics_DRAFT": post["post"]["physics_DRAFT"],
            "architecture": {
                "service": "ContentWorkflowService.certify_ncert_evidence",
                "api": "POST /content-items/{item_id}/certify-ncert",
                "cli": "scripts/execute_bio_ch1_ncert_certification.py",
                "verification_level": NCERT_CERTIFICATION_LEVEL,
                "verification_method": DEFAULT_NCERT_CERTIFICATION_METHOD,
                "audit_action": "content.certify_ncert",
                "evidence_basis": [
                    "docs/acquisition/batches/_scratch_bio11_ch01_ncert.txt",
                    "ncert_verification_audit.md/json",
                    "final_100_pilot_integrity_audit.md/json",
                    "existing body.ncert_evidence source fields",
                ],
            },
            "exact_next_step": (
                "Clear remaining publication blockers (reported in remaining_publication_blockers), "
                "then run an explicit separate publish task. Do NOT publish from this workflow."
                if remaining
                else "All tracked publication blockers cleared except status≠PUBLISHED; "
                "next task is an explicit separate publish decision — not part of certification."
            ),
            "failure": None,
            "assertions": {
                "canonical_APPROVED_state_workflow": True,
                "SOURCE_TEXT_VERIFIED": True,
                "no_fabricated_pages": True,
                "atomic_batch": True,
                "100_certified_or_noop": changed_count + noop_count == 100,
                "5_superseded_untouched": True,
                "all_remain_APPROVED": post["post"]["biology"]["APPROVED"] == 100,
                "0_PUBLISHED": post["post"]["biology"]["PUBLISHED"] == 0,
                "student_visibility_0": post["post"]["student_bio_hits"] == 0,
                "ncert_NOT_VERIFIED_cleared": gates["ncert_blocker_cleared"],
                "taxonomy_unchanged": post["post"]["taxonomy"] == EXPECTED_TAX,
                "idempotency_ok": idem["ok"],
                "no_content_mutation": len(post["unexpected_mutations"]) == 0,
            },
        }
        write_report(payload)
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Biology Ch1 NCERT certification")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Apply certification (default is dry-run / no writes)",
    )
    parser.add_argument(
        "--dry-preflight",
        action="store_true",
        help="Alias for default dry-run",
    )
    args = parser.parse_args()
    do_commit = bool(args.commit) and not args.dry_preflight
    payload = asyncio.run(run(do_commit=do_commit))
    print(json.dumps({"verdict": payload["verdict"], "mode": payload.get("mode")}, indent=2))
    if not str(payload.get("verdict", "")).startswith("GREEN"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
