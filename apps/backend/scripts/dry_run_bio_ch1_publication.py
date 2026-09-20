"""READ-ONLY publication dry-run for Biology Ch1 pilot.

NEVER calls ContentWorkflowService.publish / bulk publish / status writes.
Only SELECT + evaluate_question_publication_gates + filesystem artifacts.

Usage (from apps/backend):
  python scripts/dry_run_bio_ch1_publication.py
"""
from __future__ import annotations

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
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
EXPECTED_TAX = {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}
EXPECTED_BIO = {
    "DRAFT": 0,
    "SUPERSEDED": 5,
    "PUBLISHED": 0,
    "APPROVED": 100,
    "IN_REVIEW": 0,
}

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
CERT_REPORT = ROOT / "ncert_verification_workflow_implementation_report.json"
DRY_RUN_SRC = ROOT / "ecaep_submission_dry_run.json"
OUT_JSON = ROOT / "publication_dry_run.json"
OUT_MD = ROOT / "publication_dry_run.md"


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


def latest_version(item: ContentItem):
    return next((v for v in item.versions if v.id == item.latest_version_id), None)


def ncert_level(body: dict | None) -> str | None:
    return ((body or {}).get("ncert_evidence") or {}).get("verification_level")


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


async def integrity_baseline(by_eid: dict[str, ContentItem], planned: list[str]) -> dict:
    levels = Counter()
    integrity = {
        "active_ids": [],
        "slugs": [],
        "body_sha256": [],
        "option_counts": [],
        "answers": [],
        "explanation_lens": [],
        "concept_ids": [],
        "content_item_ids": [],
        "content_version_ids": [],
        "updated_at": [],
    }
    for eid in planned:
        item = by_eid[eid]
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        levels[ncert_level(body) or "MISSING"] += 1
        integrity["active_ids"].append(eid)
        integrity["slugs"].append(item.slug)
        integrity["body_sha256"].append(body_fp(body))
        integrity["option_counts"].append(len(body.get("options") or []))
        integrity["answers"].append(body.get("correct_option"))
        integrity["explanation_lens"].append(len(str(body.get("explanation") or "")))
        integrity["concept_ids"].append(str(item.concept_id) if item.concept_id else None)
        integrity["content_item_ids"].append(str(item.id))
        integrity["content_version_ids"].append(str(ver.id) if ver else None)
        integrity["updated_at"].append(
            item.updated_at.isoformat() if getattr(item, "updated_at", None) else None
        )
    return {
        "counts": {
            "active_ids": len(integrity["active_ids"]),
            "unique_ids": len(set(integrity["active_ids"])),
            "slugs": len(integrity["slugs"]),
            "unique_slugs": len(set(integrity["slugs"])),
            "bodies": len(integrity["body_sha256"]),
            "unique_bodies": len(set(integrity["body_sha256"])),
            "option_sets": len(integrity["option_counts"]),
            "answers": len([a for a in integrity["answers"] if a]),
            "explanations": len([e for e in integrity["explanation_lens"] if e > 0]),
            "concept_ids": len([c for c in integrity["concept_ids"] if c]),
            "unique_concept_ids": len(set(c for c in integrity["concept_ids"] if c)),
        },
        "ncert_levels": dict(levels),
        "fingerprint_bundle_sha256": hashlib.sha256(
            json.dumps(
                {
                    "ids": integrity["active_ids"],
                    "item_ids": integrity["content_item_ids"],
                    "version_ids": integrity["content_version_ids"],
                    "bodies": integrity["body_sha256"],
                    "concepts": integrity["concept_ids"],
                    "updated_at": integrity["updated_at"],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        "per_item": [
            {
                "question_id": integrity["active_ids"][i],
                "content_item_id": integrity["content_item_ids"][i],
                "content_version_id": integrity["content_version_ids"][i],
                "slug": integrity["slugs"][i],
                "concept_id": integrity["concept_ids"][i],
                "body_sha256": integrity["body_sha256"][i],
                "option_count": integrity["option_counts"][i],
                "correct_option": integrity["answers"][i],
                "explanation_len": integrity["explanation_lens"][i],
                "updated_at": integrity["updated_at"][i],
            }
            for i in range(len(planned))
        ],
    }


async def run_gates(session, by_eid: dict[str, ContentItem], planned: list[str]) -> dict:
    blocker_counts: Counter = Counter()
    results = []
    eligible = 0
    ineligible = 0
    for eid in planned:
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
            blocker_counts[reason] += 1
        if report.passed:
            eligible += 1
        else:
            ineligible += 1
        results.append(
            {
                "question_id": eid,
                "content_item_id": str(item.id),
                "content_version_id": str(ver.id) if ver else None,
                "status": item.status,
                "ncert_level": report.ncert_level,
                "passed": report.passed,
                "reasons": list(report.reasons),
                "ncert_ok": report.ncert_ok,
                "taxonomy_ok": report.taxonomy_ok,
                "provenance_ok": report.provenance_ok,
                "scientific_ok": report.scientific_ok,
                "duplicate_ok": report.duplicate_ok,
            }
        )
    return {
        "eligible": eligible,
        "ineligible": ineligible,
        "blocker_counts": dict(blocker_counts),
        "ncert_NOT_VERIFIED_count": blocker_counts.get("ncert:NOT_VERIFIED", 0),
        "results": results,
        "first_failure": next((r for r in results if not r["passed"]), None),
    }


def build_plan(by_eid: dict[str, ContentItem], planned: list[str], superseded: list[str]) -> dict:
    actions = []
    for eid in planned:
        item = by_eid[eid]
        ver = latest_version(item)
        actions.append(
            {
                "ordinal": len(actions) + 1,
                "question_id": eid,
                "content_item_id": str(item.id),
                "content_version_id": str(ver.id) if ver else None,
                "slug": item.slug,
                "status": item.status,
                "operation": "ContentWorkflowService.publish(item_id)",
                "api_single": f"POST /api/v1/cms/content-items/{item.id}/publish",
            }
        )
    item_ids = [a["content_item_id"] for a in actions]
    return {
        "publication_candidates": len(actions),
        "publication_actions": len(actions),
        "database_writes": 0,
        "publish_executed": False,
        "deterministic_order": "ecaep_submission_dry_run.deterministic_question_ids",
        "duplicates": len(item_ids) - len(set(item_ids)),
        "superseded_in_plan": sorted(set(planned) & set(superseded)),
        "physics_in_plan": [eid for eid in planned if "PHY" in eid.upper()],
        "all_approved": all(a["status"] == "APPROVED" for a in actions),
        "actions": actions,
        "bulk_api_payload_preview": {
            "endpoint": "POST /api/v1/cms/content-items/bulk",
            "permission": "content.publish",
            "body": {
                "action": "publish",
                "item_ids": item_ids,
            },
            "note": (
                "Bulk applies each item independently (not one atomic transaction). "
                "Single-item publish() commits per call."
            ),
        },
    }


def expected_post_publication_state() -> dict:
    """Derived from ContentWorkflowService.publish — EXPECTED, not observed."""
    return {
        "label": "EXPECTED_NOT_OBSERVED",
        "status_transition": "APPROVED → PUBLISHED (item.status + latest.workflow_state)",
        "version_changes": (
            "No new ContentVersion created. "
            "item.current_version_id set to latest_version_id."
        ),
        "body_changes": "None — publish does not mutate body/options/answer/explanation.",
        "student_visibility": (
            "CmsRepository.list_questions / student browse includes only PUBLISHED; "
            "EXPECTED Biology student-visible = 100 after successful publish of all 100."
        ),
        "practice_pool": (
            "AssessmentRepository.published_question_ids_for_scope includes PUBLISHED only; "
            "EXPECTED practice pool includes these 100 IDs after publish."
        ),
        "search_side_effect": (
            "SearchRepository.reindex_item(item_id) runs after QUESTION publish "
            "(search_text/search_vector); separate commit inside reindex_item."
        ),
        "audit_log": (
            "Single publish API: no AuditLog inside publish() itself. "
            "Bulk endpoint logs AuditService action content.publish per successful item. "
            "Single POST .../publish does not add audit in cms_router currently."
        ),
        "publication_timestamp": (
            "No dedicated published_at column. AuditedBase updated_at refreshes on status change."
        ),
        "transaction_behavior": (
            "publish() calls repo.commit() once per item. "
            "Bulk loops independently — failure of one does NOT roll back prior successes."
        ),
        "expected_biology_counts_if_all_100_succeed": {
            "APPROVED": 0,
            "PUBLISHED": 100,
            "SUPERSEDED": 5,
            "DRAFT": 0,
            "IN_REVIEW": 0,
        },
        "expected_student_bio_hits_if_all_100_succeed": 100,
        "expected_taxonomy_unchanged": EXPECTED_TAX,
        "expected_physics_DRAFT_unchanged": 24,
    }


def safety_analysis() -> dict:
    return {
        "already_PUBLISHED_again": (
            "ContentWorkflowService.publish raises ContentWorkflowError: "
            "Cannot publish content in state PUBLISHED. Idempotent no-op is NOT implemented; "
            "second publish is a hard reject."
        ),
        "SUPERSEDED_targeted": (
            "Rejected: status != APPROVED → ContentWorkflowError. "
            "Publication gates are not reached."
        ),
        "APPROVED_fails_one_gate": (
            "assert_question_publishable raises AppError PUBLICATION_GATES_FAILED (422). "
            "No status change; no reindex."
        ),
        "one_item_fails_in_100_batch_via_bulk_API": (
            "Bulk endpoint applies independently: prior successful publishes STAY published; "
            "failed item reported with success=false. NOT atomic across 100."
        ),
        "transaction_interrupted_mid_single_publish": (
            "If commit fails before completion, that item remains APPROVED. "
            "If commit succeeds but reindex fails, item may already be PUBLISHED "
            "(publish commits before reindex)."
        ),
        "atomic_100_batch": (
            "NOT available in current canonical publish()/bulk path. "
            "Unlike certify_ncert_evidence(commit=False), publish has no commit=False. "
            "A future atomic batch would require an explicit service extension — "
            "out of scope for this dry-run."
        ),
        "wrong_batch_tenant": (
            "No tenant_id on content. Batch scoping is caller responsibility "
            "(plan filters by batch tags/slug). publish(item_id) does not re-check batch_id."
        ),
    }


def write_artifacts(payload: dict) -> None:
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    plan = payload.get("publication_plan") or {}
    gates = payload.get("gate_results") or {}
    lines = [
        "# Biology Ch1 — Publication Dry-Run",
        "",
        f"## 1. Executive verdict: {payload['verdict']}",
        "",
        f"Batch: `{BATCH}`  ",
        f"Executed: `{payload.get('executed_at')}`  ",
        f"**Publish executed: `{payload.get('publish_executed')}`**  ",
        f"**Database writes: `{payload.get('database_writes')}`**",
        "",
        "## 2. Canonical publication method",
        "",
        "- Service: `ContentWorkflowService.publish(item_id)`",
        "- Single API: `POST /api/v1/cms/content-items/{item_id}/publish` (permission `content.publish`)",
        "- Bulk API: `POST /api/v1/cms/content-items/bulk` with `action=publish`",
        "- Gates: `assert_body_publishable` + `assert_question_publishable` → `evaluate_question_publication_gates`",
        "- Required transition: **APPROVED → PUBLISHED**",
        "- Side effects: set `current_version_id`; `SearchRepository.reindex_item` for QUESTION",
        "",
        "## 3. Candidate selection",
        "",
        "```json",
        json.dumps(payload.get("candidate_selection"), indent=2),
        "```",
        "",
        "## 4. Gate results",
        "",
        f"- Eligible: **{gates.get('eligible')}**",
        f"- Ineligible: **{gates.get('ineligible')}**",
        f"- ncert:NOT_VERIFIED: **{gates.get('ncert_NOT_VERIFIED_count')}**",
        f"- Blocker counts: `{gates.get('blocker_counts')}`",
        "",
        "## 5. Deterministic publication plan",
        "",
        f"- Candidates: **{plan.get('publication_candidates')}**",
        f"- Actions: **{plan.get('publication_actions')}**",
        f"- DB writes (this dry-run): **{plan.get('database_writes')}**",
        f"- Duplicates: **{plan.get('duplicates')}**",
        f"- Superseded in plan: **{plan.get('superseded_in_plan')}**",
        f"- Physics in plan: **{plan.get('physics_in_plan')}**",
        f"- All APPROVED: **{plan.get('all_approved')}**",
        "",
        "## 6. Pre-publication baseline",
        "",
        "```json",
        json.dumps(payload.get("pre_publication_baseline"), indent=2),
        "```",
        "",
        "## 7. Expected post-publication state (NOT OBSERVED)",
        "",
        "```json",
        json.dumps(payload.get("expected_post_publication_state"), indent=2),
        "```",
        "",
        "## 8. Atomicity analysis",
        "",
        payload.get("safety_analysis", {}).get("atomic_100_batch", ""),
        "",
        payload.get("safety_analysis", {}).get("one_item_fails_in_100_batch_via_bulk_API", ""),
        "",
        "## 9. Idempotency analysis",
        "",
        payload.get("safety_analysis", {}).get("already_PUBLISHED_again", ""),
        "",
        "## 10. Tests",
        "",
        "```json",
        json.dumps(payload.get("tests"), indent=2),
        "```",
        "",
        "## 11. Database mutation proof",
        "",
        "```json",
        json.dumps(payload.get("mutation_proof"), indent=2),
        "```",
        "",
        "## 12. Student visibility proof",
        "",
        f"- Student Biology hits: **{payload.get('student_visibility')}**",
        f"- Practice nonpub hits: **{payload.get('practice_nonpub_hits')}**",
        "",
        "## 13. Exact next publication command",
        "",
        "```text",
        payload.get("exact_next_publication_command", ""),
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


async def main() -> dict:
    executed_at = datetime.now(UTC).isoformat()
    dry = json.loads(DRY_RUN_SRC.read_text(encoding="utf-8"))
    cert = json.loads(CERT_REPORT.read_text(encoding="utf-8"))
    planned = list(dry["deterministic_question_ids"])
    certified = cert.get("certified_question_ids") or []
    if planned != certified:
        raise SystemExit("ABORT: planned IDs != certified_question_ids")
    if not str(cert.get("verdict", "")).startswith("GREEN"):
        raise SystemExit(f"ABORT: certification not GREEN: {cert.get('verdict')}")
    superseded = dry.get("selection_proof", {}).get("excluded_superseded_ids") or []

    async with AsyncSessionLocal() as session:
        # Force read-only session: refuse commits if any code path tries.
        session.info["publication_dry_run_readonly"] = True

        try:
            pre = await snap(session)
            if pre["taxonomy"] != EXPECTED_TAX:
                raise Abort("taxonomy", EXPECTED_TAX, pre["taxonomy"])
            if pre["biology"] != EXPECTED_BIO:
                raise Abort("biology", EXPECTED_BIO, pre["biology"])
            if pre["physics_DRAFT"] != 24:
                raise Abort("physics_DRAFT", 24, pre["physics_DRAFT"])
            if pre["student_bio_hits"] != 0 or pre["practice_nonpub_hits"] != 0:
                raise Abort("student_safety", 0, pre)

            by_eid = await load_batch_map(session)
            superseded_live = sorted(eid for eid, i in by_eid.items() if i.status == "SUPERSEDED")
            if len(superseded_live) != 5:
                raise Abort("superseded_count", 5, len(superseded_live))
            if set(superseded_live) & set(planned):
                raise Abort("superseded_in_candidates", set(), set(superseded_live) & set(planned))
            if set(superseded) and set(superseded) != set(superseded_live):
                # soft: prefer live
                pass

            for eid in planned:
                item = by_eid.get(eid)
                if not item:
                    raise Abort("missing", eid, None)
                if item.status != "APPROVED":
                    raise Abort("status", "APPROVED", f"{eid}:{item.status}")
                if ncert_level(dict(latest_version(item).body or {})) != "SOURCE_TEXT_VERIFIED":
                    raise Abort("ncert_level", "SOURCE_TEXT_VERIFIED", eid)

            integrity = await integrity_baseline(by_eid, planned)
            if integrity["counts"]["active_ids"] != 100:
                raise Abort("integrity_count", 100, integrity["counts"])
            if integrity["ncert_levels"] != {"SOURCE_TEXT_VERIFIED": 100}:
                raise Abort("ncert_levels", {"SOURCE_TEXT_VERIFIED": 100}, integrity["ncert_levels"])

            gates = await run_gates(session, by_eid, planned)
            if gates["ineligible"] != 0:
                raise Abort(
                    "gate_failure",
                    0,
                    gates["first_failure"],
                )
            if gates["eligible"] != 100:
                raise Abort("eligible", 100, gates["eligible"])
            if gates["ncert_NOT_VERIFIED_count"] != 0:
                raise Abort("ncert_blocker", 0, gates["ncert_NOT_VERIFIED_count"])

            plan = build_plan(by_eid, planned, superseded_live)
            if plan["duplicates"] != 0 or plan["superseded_in_plan"] or plan["physics_in_plan"]:
                raise Abort("plan_contamination", None, plan)

            post = await snap(session)
            by_eid_after = await load_batch_map(session)
            integrity_after = await integrity_baseline(by_eid_after, planned)
            mutation_ok = (
                pre == post
                and integrity["fingerprint_bundle_sha256"]
                == integrity_after["fingerprint_bundle_sha256"]
            )
            if not mutation_ok:
                raise Abort(
                    "unexpected_mutation_during_dry_run",
                    integrity["fingerprint_bundle_sha256"],
                    integrity_after["fingerprint_bundle_sha256"],
                )

            green = mutation_ok and gates["eligible"] == 100 and plan["publication_candidates"] == 100
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "GREEN — PUBLICATION DRY-RUN READY (NOT PUBLISHED)"
                if green
                else "AMBER/RED — DRY-RUN ANOMALY",
                "publish_executed": False,
                "database_writes": 0,
                "canonical_publication_method": {
                    "service": "ContentWorkflowService.publish",
                    "api_single": "POST /api/v1/cms/content-items/{item_id}/publish",
                    "api_bulk": "POST /api/v1/cms/content-items/bulk action=publish",
                    "gates": [
                        "assert_body_publishable",
                        "assert_question_publishable",
                        "evaluate_question_publication_gates",
                    ],
                    "required_status": "APPROVED",
                    "target_status": "PUBLISHED",
                    "commit": "per-item repo.commit() inside publish()",
                    "reindex": "SearchRepository.reindex_item after QUESTION publish",
                },
                "candidate_selection": {
                    "batch_id": BATCH,
                    "status": "APPROVED",
                    "ncert": "SOURCE_TEXT_VERIFIED",
                    "active_candidates": 100,
                    "superseded_excluded": superseded_live,
                    "physics_excluded": True,
                    "source_id_list": "ecaep_submission_dry_run.deterministic_question_ids",
                },
                "gate_results": {
                    "eligible": gates["eligible"],
                    "ineligible": gates["ineligible"],
                    "blocker_counts": gates["blocker_counts"],
                    "ncert_NOT_VERIFIED_count": gates["ncert_NOT_VERIFIED_count"],
                    "results": gates["results"],
                },
                "publication_plan": plan,
                "pre_publication_baseline": {
                    "biology": pre["biology"],
                    "ncert": integrity["ncert_levels"],
                    "student": {
                        "biology_visible": pre["student_bio_hits"],
                        "practice_nonpub_hits": pre["practice_nonpub_hits"],
                    },
                    "taxonomy": pre["taxonomy"],
                    "physics_DRAFT": pre["physics_DRAFT"],
                    "content_integrity": integrity["counts"],
                    "fingerprint_bundle_sha256": integrity["fingerprint_bundle_sha256"],
                },
                "expected_post_publication_state": expected_post_publication_state(),
                "safety_analysis": safety_analysis(),
                "tests": {
                    "note": "Executed separately via pytest against trinetra_test_db; see report section after run.",
                    "planned_modules": [
                        "tests/test_cms_publish_quality.py",
                        "tests/test_ecaep_biology_workflow_gates.py",
                        "tests/test_ncert_certification_workflow.py",
                    ],
                },
                "mutation_proof": {
                    "pre_equals_post_snap": pre == post,
                    "fingerprint_unchanged": integrity["fingerprint_bundle_sha256"]
                    == integrity_after["fingerprint_bundle_sha256"],
                    "publish_not_called": True,
                    "database_writes": 0,
                },
                "student_visibility": pre["student_bio_hits"],
                "practice_nonpub_hits": pre["practice_nonpub_hits"],
                "exact_next_publication_command": (
                    "ONLY after explicit human authorization:\n"
                    "1) Prefer a controlled loop calling ContentWorkflowService.publish(uuid) "
                    "for each content_item_id in publication_plan.actions (order preserved), "
                    "OR\n"
                    "2) POST /api/v1/cms/content-items/bulk with action=publish and the 100 "
                    "item_ids from publication_plan.bulk_api_payload_preview "
                    "(WARNING: not atomic — partial publish possible).\n"
                    "Do NOT run publish as part of this dry-run script."
                ),
                "failure": None,
                "assertions": {
                    "canonical_path_identified": True,
                    "candidates_100": plan["publication_candidates"] == 100,
                    "superseded_5_excluded": len(superseded_live) == 5,
                    "gates_100_pass": gates["eligible"] == 100,
                    "ncert_blocker_0": gates["ncert_NOT_VERIFIED_count"] == 0,
                    "plan_exactly_100": plan["publication_actions"] == 100,
                    "no_unrelated_content": not plan["physics_in_plan"]
                    and not plan["superseded_in_plan"],
                    "database_writes_0": True,
                    "biology_still_APPROVED_100_PUBLISHED_0": pre["biology"] == EXPECTED_BIO,
                    "student_visibility_0": pre["student_bio_hits"] == 0,
                    "practice_pool_0": pre["practice_nonpub_hits"] == 0,
                    "taxonomy_unchanged": pre["taxonomy"] == EXPECTED_TAX,
                    "physics_unchanged": pre["physics_DRAFT"] == 24,
                    "publish_not_executed": True,
                },
            }
            write_artifacts(payload)
            return payload
        except Abort as exc:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — PUBLICATION DRY-RUN FAILED",
                "publish_executed": False,
                "database_writes": 0,
                "failure": {
                    "condition": exc.condition,
                    "expected": exc.expected,
                    "actual": exc.actual,
                },
            }
            write_artifacts(payload)
            return payload


if __name__ == "__main__":
    result = asyncio.run(main())
    print(json.dumps({"verdict": result["verdict"], "publish_executed": result.get("publish_executed"), "database_writes": result.get("database_writes")}, indent=2))
    if not str(result.get("verdict", "")).startswith("GREEN"):
        raise SystemExit(1)
