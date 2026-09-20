"""AUTHORIZED production publication for Biology Ch1 100-question pilot.

Uses ONLY ContentWorkflowService.publish(item_id) per plan ID.
Does NOT use bulk publish API.
Stops immediately on first failure (non-atomic — no ad-hoc rollback).

Usage (from apps/backend):
  python scripts/execute_bio_ch1_publication.py            # preflight-only
  python scripts/execute_bio_ch1_publication.py --commit   # authorized publish
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
from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.assessment.services.assessment_service import AssessmentService
from app.modules.cms.acquisition.physics_t6d_service import actor_user
from app.modules.cms.api.cms_router import _question_summary
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import (
    ContentWorkflowError,
    ContentWorkflowService,
)
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
CHAPTER_NAME = "The Living World"
EXPECTED_TAX = {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}
EXPECTED_BIO_PRE = {
    "DRAFT": 0,
    "SUPERSEDED": 5,
    "PUBLISHED": 0,
    "APPROVED": 100,
    "IN_REVIEW": 0,
}
EXPECTED_BIO_POST = {
    "DRAFT": 0,
    "SUPERSEDED": 5,
    "PUBLISHED": 100,
    "APPROVED": 0,
    "IN_REVIEW": 0,
}

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
DRY_RUN = ROOT / "publication_dry_run.json"
OUT_JSON = ROOT / "publication_execution_report.json"
OUT_MD = ROOT / "publication_execution_report.md"

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
    bio_ids = {i.id for i in bio}
    bio_published = {i.id for i in bio if i.status == "PUBLISHED"}
    bio_nonpub = bio_ids - bio_published
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
        "practice_bio_hits": len(bio_published & pool),
        "practice_nonpub_hits": len(bio_nonpub & pool),
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


async def chapter_name_for_concept(session, concept_id: uuid.UUID) -> str | None:
    row = (
        await session.execute(
            select(Chapter.name)
            .join(Topic, Topic.chapter_id == Chapter.id)
            .join(Concept, Concept.topic_id == Topic.id)
            .where(Concept.id == concept_id)
        )
    ).scalar_one_or_none()
    return row


async def living_world_chapter_id(session) -> uuid.UUID:
    row = (
        await session.execute(
            select(Chapter.id).where(Chapter.name == CHAPTER_NAME, Chapter.deleted_at.is_(None))
        )
    ).scalar_one()
    return row


def item_snapshot(item: ContentItem, chapter: str | None) -> dict:
    ver = latest_version(item)
    body = dict(ver.body or {}) if ver else {}
    prov = body.get("provenance") or {}
    ncert = body.get("ncert_evidence") or {}
    return {
        "question_id": eid_from_slug(item.slug),
        "content_item_id": str(item.id),
        "slug": item.slug,
        "status": item.status,
        "current_version_id": str(item.current_version_id) if item.current_version_id else None,
        "latest_version_id": str(item.latest_version_id) if item.latest_version_id else None,
        "content_version_id": str(ver.id) if ver else None,
        "body_sha256": body_fp(body),
        "pedagogy_sha256": pedagogy_fp(body),
        "concept_id": str(item.concept_id) if item.concept_id else None,
        "chapter_name": chapter,
        "provenance_origin": prov.get("origin"),
        "provenance_source": prov.get("source"),
        "provenance_batch_id": prov.get("batch_id"),
        "ncert_verification_level": ncert.get("verification_level"),
        "ncert_evidence_sha256": body_fp(ncert),
        "difficulty": body.get("difficulty"),
        "question_type_tag": next(
            (t for t in (item.tags or []) if str(t).startswith("question_type:")), None
        ),
        "tenant_id": None,  # content model has no tenant_id; batch_id is the scope key
        "updated_at": item.updated_at.isoformat() if getattr(item, "updated_at", None) else None,
    }


async def preflight(session, plan_actions: list[dict], dry_run: dict) -> dict:
    if len(plan_actions) != 100:
        raise Abort("plan_count", 100, len(plan_actions))
    qids = [a["question_id"] for a in plan_actions]
    item_ids = [a["content_item_id"] for a in plan_actions]
    if len(set(qids)) != 100 or len(set(item_ids)) != 100:
        raise Abort("duplicates", 100, {"qids": len(set(qids)), "items": len(set(item_ids))})

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
    if set(superseded_live) & set(qids):
        raise Abort("superseded_in_plan", set(), set(superseded_live) & set(qids))

    dry_actions = (dry_run.get("publication_plan") or {}).get("actions") or []
    dry_map = {a["question_id"]: a["content_item_id"] for a in dry_actions}
    if [a["question_id"] for a in dry_actions] != qids:
        raise Abort("plan_order_mismatch", qids[:3], [a["question_id"] for a in dry_actions][:3])

    baselines = {}
    eligibility = []
    unexpected = []
    for action in plan_actions:
        eid = action["question_id"]
        expected_item_id = action["content_item_id"]
        item = by_eid.get(eid)
        if not item:
            raise Abort("missing_item", eid, None)
        if str(item.id) != expected_item_id:
            raise Abort("item_id_mismatch", expected_item_id, str(item.id))
        if dry_map.get(eid) != expected_item_id:
            raise Abort("dry_run_id_mismatch", dry_map.get(eid), expected_item_id)
        if item.deleted_at is not None:
            raise Abort("inactive", eid, str(item.deleted_at))
        if item.status == "SUPERSEDED":
            raise Abort("superseded", eid, item.status)
        if item.status != "APPROVED":
            raise Abort("status", "APPROVED", f"{eid}:{item.status}")
        if not is_batch_item(item):
            raise Abort("wrong_batch", BATCH, item.tags)
        if item.concept_id is None:
            raise Abort("null_concept", eid, None)
        if PHY in eid.upper() or "phy" in (item.slug or "").lower():
            raise Abort("physics_leak", None, eid)
        chap = await chapter_name_for_concept(session, item.concept_id)
        if chap != CHAPTER_NAME:
            raise Abort("wrong_chapter", CHAPTER_NAME, f"{eid}:{chap}")
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        if ncert_level(body) != "SOURCE_TEXT_VERIFIED":
            raise Abort("ncert_level", "SOURCE_TEXT_VERIFIED", f"{eid}:{ncert_level(body)}")
        if (body.get("provenance") or {}).get("batch_id") not in (BATCH, None):
            # allow None only if tags carry batch; prefer explicit match
            if (body.get("provenance") or {}).get("batch_id") != BATCH:
                raise Abort("provenance_batch", BATCH, (body.get("provenance") or {}).get("batch_id"))

        gate = await evaluate_question_publication_gates(
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
        eligibility.append(
            {
                "question_id": eid,
                "content_item_id": str(item.id),
                "passed": gate.passed,
                "reasons": list(gate.reasons),
                "ncert_level": gate.ncert_level,
            }
        )
        if not gate.passed:
            raise Abort("gate_failed", eid, gate.reasons)

        snap_row = item_snapshot(item, chap)
        baselines[eid] = snap_row

    ineligible = [e for e in eligibility if not e["passed"]]
    if ineligible:
        raise Abort("ineligible_count", 0, ineligible)
    if unexpected:
        raise Abort("unexpected", 0, unexpected)

    return {
        "pre": pre,
        "baselines": baselines,
        "eligibility": eligibility,
        "planned_ids": qids,
        "plan_actions": plan_actions,
        "superseded_excluded": superseded_live,
        "eligible": 100,
        "ineligible": 0,
        "unexpected": 0,
    }


async def publish_one(session, action: dict, baseline: dict) -> dict:
    workflow = ContentWorkflowService(session)
    item_id = uuid.UUID(action["content_item_id"])
    eid = action["question_id"]

    # Fresh load
    item = await CmsRepository(session).get_item(item_id)
    if not item:
        raise Abort("missing_at_publish", eid, None)
    if item.status != "APPROVED":
        raise Abort("status_at_publish", "APPROVED", f"{eid}:{item.status}")

    ver = await workflow.repo.get_version(item.latest_version_id)
    body = dict(ver.body or {}) if ver else {}
    gate = await evaluate_question_publication_gates(
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
    if not gate.passed:
        raise Abort("gate_at_publish", eid, gate.reasons)

    before_body = body_fp(body)
    before_ped = pedagogy_fp(body)
    before_concept = str(item.concept_id)
    before_prov = {
        "origin": (body.get("provenance") or {}).get("origin"),
        "source": (body.get("provenance") or {}).get("source"),
        "batch_id": (body.get("provenance") or {}).get("batch_id"),
    }
    before_ncert = body_fp(body.get("ncert_evidence") or {})
    before_version_id = str(ver.id)

    published = await workflow.publish(item_id)

    if published.status != "PUBLISHED":
        raise Abort("post_status", "PUBLISHED", published.status)
    if str(published.current_version_id) != before_version_id:
        raise Abort("current_version_id", before_version_id, str(published.current_version_id))

    # Re-load body
    latest = await workflow.repo.get_version(published.latest_version_id)
    after_body = dict(latest.body or {})
    if body_fp(after_body) != before_body:
        raise Abort("body_mutated", eid, None)
    if pedagogy_fp(after_body) != before_ped:
        raise Abort("pedagogy_mutated", eid, None)
    if str(published.concept_id) != before_concept:
        raise Abort("concept_mutated", eid, None)
    after_prov = after_body.get("provenance") or {}
    for k, v in before_prov.items():
        if after_prov.get(k) != v:
            raise Abort(f"provenance_{k}_mutated", eid, after_prov.get(k))
    if body_fp(after_body.get("ncert_evidence") or {}) != before_ncert:
        raise Abort("ncert_mutated", eid, None)
    if baseline["body_sha256"] != before_body:
        raise Abort("baseline_drift", eid, None)

    return {
        "question_id": eid,
        "content_item_id": str(published.id),
        "status": published.status,
        "current_version_id": str(published.current_version_id),
        "content_version_id": before_version_id,
        "body_unchanged": True,
        "success": True,
    }


async def post_audit(session, pf: dict) -> dict:
    post = await snap(session)
    by_eid = await load_batch_map(session)
    unexpected = []
    after_snaps = {}
    levels = Counter()
    for eid in pf["planned_ids"]:
        item = by_eid.get(eid)
        base = pf["baselines"][eid]
        if not item:
            unexpected.append(f"missing:{eid}")
            continue
        if item.status != "PUBLISHED":
            unexpected.append(f"status:{eid}={item.status}")
        chap = await chapter_name_for_concept(session, item.concept_id) if item.concept_id else None
        snap_row = item_snapshot(item, chap)
        after_snaps[eid] = snap_row
        levels[snap_row["ncert_verification_level"] or "MISSING"] += 1
        for key in (
            "content_item_id",
            "slug",
            "body_sha256",
            "pedagogy_sha256",
            "concept_id",
            "provenance_origin",
            "provenance_source",
            "provenance_batch_id",
            "ncert_verification_level",
            "ncert_evidence_sha256",
            "difficulty",
            "question_type_tag",
            "content_version_id",
        ):
            if snap_row.get(key) != base.get(key):
                unexpected.append(f"{key}:{eid}")
        if snap_row["status"] != "PUBLISHED":
            unexpected.append(f"not_published:{eid}")
        if snap_row["current_version_id"] != base["content_version_id"]:
            unexpected.append(f"current_version:{eid}")

    for eid in pf["superseded_excluded"]:
        item = by_eid.get(eid)
        if not item or item.status != "SUPERSEDED":
            unexpected.append(f"superseded_changed:{eid}")

    published_all = sorted(eid for eid, i in by_eid.items() if i.status == "PUBLISHED")
    if set(published_all) != set(pf["planned_ids"]):
        unexpected.append(
            f"published_set_mismatch extra={sorted(set(published_all)-set(pf['planned_ids']))} "
            f"missing={sorted(set(pf['planned_ids'])-set(published_all))}"
        )
    if post["biology"] != EXPECTED_BIO_POST:
        unexpected.append(f"biology_post={post['biology']}")
    if post["taxonomy"] != EXPECTED_TAX:
        unexpected.append(f"taxonomy={post['taxonomy']}")
    if post["physics_DRAFT"] != 24:
        unexpected.append(f"physics={post['physics_DRAFT']}")

    return {
        "post": post,
        "after_snaps": after_snaps,
        "verification_levels": dict(levels),
        "unexpected_mutations": unexpected,
        "ok": len(unexpected) == 0,
    }


async def verify_student_and_practice(session, pf: dict) -> dict:
    repo = CmsRepository(session)
    plan_ids = {uuid.UUID(pf["baselines"][eid]["content_item_id"]) for eid in pf["planned_ids"]}
    superseded_ids = set()
    by_eid = await load_batch_map(session)
    for eid in pf["superseded_excluded"]:
        if eid in by_eid:
            superseded_ids.add(by_eid[eid].id)

    # Student browse (same path as GET /cms/questions)
    visible = []
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        visible.extend(page)
        off += 100
        if off >= tot or not page:
            break
    visible_ids = {i.id for i in visible}
    bio_visible = visible_ids & plan_ids
    superseded_visible = visible_ids & superseded_ids

    # Sample student projection — no answer leak
    sample_id = next(iter(plan_ids))
    sample_item = await repo.get_item(sample_id)
    names = await repo.academic_names_for_concepts(
        [sample_item.concept_id] if sample_item and sample_item.concept_id else []
    )
    summary = _question_summary(sample_item, names)
    answer_leaked = ("correct_option" in summary) or ("explanation" in summary)

    # Practice pool
    arepo = AssessmentRepository(session)
    chapter_id = await living_world_chapter_id(session)
    chapter_pool = set(await arepo.published_question_ids_for_scope("CHAPTER", chapter_id))
    full_pool = set(await arepo.published_question_ids_for_scope("FULL", None))
    practice_bio = plan_ids & full_pool
    practice_chapter = plan_ids & chapter_pool

    # Practice Now E2E via AssessmentService (canonical path)
    actor = await actor_user(session)
    asvc = AssessmentService(session)
    assessment = await asvc.generate_practice(
        scope_type="CHAPTER",
        scope_id=chapter_id,
        question_count=5,
        user_id=actor.id,
    )
    attempt = await asvc.start_attempt(assessment.id, actor.id)

    from app.modules.assessment.api.assessment_router import _public_question

    assessment_full = await asvc.repo.get_assessment(assessment.id)
    aq_ids = [q.content_item_id for q in (assessment_full.questions if assessment_full else [])]

    q1_item = await repo.get_item(aq_ids[0]) if aq_ids else None
    q1_public = None
    q1_leaked = True
    q1_renders = False
    if q1_item:
        q1_names = await repo.academic_names_for_concepts(
            [q1_item.concept_id] if q1_item.concept_id else []
        )
        q1_public = _public_question(q1_item, None, q1_names, {}, set())
        q1_leaked = ("correct_option" in q1_public) or ("explanation" in q1_public)
        q1_renders = bool(q1_public.get("stem")) and bool(q1_public.get("options"))

    # search reindex sample
    reindex_row = (
        await session.execute(
            text(
                "SELECT search_text IS NOT NULL AS has_text, "
                "search_vector IS NOT NULL AS has_vector "
                "FROM cms.content_items WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(sample_id)},
        )
    ).one()

    audit_n = (
        await session.execute(
            text(
                "SELECT count(*) FROM system.audit_logs "
                "WHERE action = 'content.publish' "
                "AND entity_id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": [str(i) for i in plan_ids]},
        )
    ).scalar_one()

    return {
        "student_api": {
            "biology_visible_count": len(bio_visible),
            "expected": 100,
            "superseded_visible_count": len(superseded_visible),
            "sample_question_id": str(sample_id),
            "sample_renders": bool(summary.get("stem")) and bool(summary.get("options")),
            "answer_leaked_before_submit": answer_leaked,
            "chapter_name_sample": (summary.get("chapter") or {}).get("name")
            if isinstance(summary.get("chapter"), dict)
            else summary.get("chapter"),
        },
        "practice_pool": {
            "full_scope_bio_hits": len(practice_bio),
            "chapter_scope_bio_hits": len(practice_chapter),
            "chapter_id": str(chapter_id),
            "superseded_in_pool": len(superseded_ids & full_pool),
        },
        "practice_now_e2e": {
            "assessment_id": str(assessment.id),
            "attempt_id": str(attempt.id),
            "assessment_type": assessment.assessment_type,
            "scope_type": assessment.scope_type,
            "question_count": assessment.question_count,
            "question_ids": [str(i) for i in aq_ids],
            "all_from_plan": all(uuid.UUID(str(i)) in plan_ids for i in aq_ids) if aq_ids else False,
            "q1_content_item_id": str(aq_ids[0]) if aq_ids else None,
            "q1_renders": q1_renders,
            "q1_answer_leaked": q1_leaked,
            "no_mock_fallback": assessment.question_count > 0 and bool(aq_ids),
        },
        "reindex": {
            "sample_has_search_text": bool(reindex_row[0]),
            "sample_has_search_vector": bool(reindex_row[1]),
        },
        "audit": {
            "content_publish_audit_rows_for_plan": int(audit_n),
            "note": (
                "ContentWorkflowService.publish does not write AuditLog; "
                "AuditLog content.publish is only emitted by bulk API (not used)."
            ),
        },
    }


async def idempotency_probe(session, sample_item_id: uuid.UUID) -> dict:
    workflow = ContentWorkflowService(session)
    rejected = False
    code = None
    message = None
    try:
        await workflow.publish(sample_item_id)
    except (ContentWorkflowError, AppError) as exc:
        rejected = True
        code = getattr(exc, "code", type(exc).__name__)
        message = str(exc)
    item = await CmsRepository(session).get_item(sample_item_id)
    version_count = (
        await session.execute(
            text(
                "SELECT count(*) FROM cms.content_versions "
                "WHERE content_item_id = CAST(:id AS uuid)"
            ),
            {"id": str(sample_item_id)},
        )
    ).scalar_one()
    return {
        "sample_item_id": str(sample_item_id),
        "second_publish_rejected": rejected,
        "error_code": code,
        "error_message": message,
        "status_still_published": item.status == "PUBLISHED" if item else False,
        "version_count": int(version_count),
        "ok": rejected and item is not None and item.status == "PUBLISHED",
    }


def write_report(payload: dict) -> None:
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    lines = [
        "# Biology Ch1 — Publication Execution Report",
        "",
        f"## 1. Executive verdict: {payload['verdict']}",
        "",
        f"Batch: `{BATCH}`  ",
        f"Executed: `{payload.get('executed_at')}`  ",
        f"Authorization: **{payload.get('authorization_basis')}**  ",
        f"Published count: **{payload.get('published_count', 0)}**  ",
        f"Bulk API used: **{payload.get('bulk_api_used', False)}**",
        "",
        "## 2–4. Plan / Preflight / Baseline",
        "",
        "```json",
        json.dumps(
            {
                "planned_count": len(payload.get("published_question_ids") or payload.get("planned_ids") or []),
                "preflight": payload.get("preflight"),
                "before": payload.get("before_snapshot"),
            },
            indent=2,
            default=str,
        ),
        "```",
        "",
        "## 5–8. Results",
        "",
        "```json",
        json.dumps(
            {
                "published_count": payload.get("published_count"),
                "post_counts": payload.get("after_snapshot"),
                "content_integrity": payload.get("content_integrity"),
                "taxonomy": payload.get("taxonomy_comparison"),
                "provenance": payload.get("provenance_comparison"),
            },
            indent=2,
            default=str,
        ),
        "```",
        "",
        "## 9–14. Student / Practice / Audit",
        "",
        "```json",
        json.dumps(payload.get("student_practice_verification"), indent=2, default=str),
        "```",
        "",
        "## 15. Failure / rollback",
        "",
        f"```json\n{json.dumps(payload.get('failure'), indent=2, default=str)}\n```"
        if payload.get("failure")
        else "_None — full batch published; no rollback attempted (non-atomic path)._",
        "",
        "## 16. Idempotency",
        "",
        "```json",
        json.dumps(payload.get("idempotency"), indent=2, default=str),
        "```",
        "",
        "## 17–19. Counts / anomalies / next",
        "",
        f"- Exact published count: **{payload.get('published_count')}**",
        f"- Anomalies: **{payload.get('anomalies') or []}**",
        f"- Next task: {payload.get('exact_next_task')}",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(*, do_commit: bool) -> dict:
    executed_at = datetime.now(UTC).isoformat()
    dry = json.loads(DRY_RUN.read_text(encoding="utf-8"))
    if not str(dry.get("verdict", "")).startswith("GREEN"):
        raise SystemExit(f"ABORT: dry-run not GREEN: {dry.get('verdict')}")
    plan_actions = list((dry.get("publication_plan") or {}).get("actions") or [])
    if len(plan_actions) != 100:
        raise SystemExit(f"ABORT: dry-run plan actions != 100 ({len(plan_actions)})")

    auth = (
        "Explicit user authorization after GREEN publication dry-run for "
        f"{BATCH}; publish only the 100 plan IDs via ContentWorkflowService.publish"
    )

    async with AsyncSessionLocal() as session:
        try:
            pf = await preflight(session, plan_actions, dry)
        except Abort as exc:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — PUBLICATION PREFLIGHT FAILED (NOTHING PUBLISHED)",
                "authorization_basis": auth,
                "bulk_api_used": False,
                "published_count": 0,
                "planned_ids": [a["question_id"] for a in plan_actions],
                "failure": {
                    "condition": exc.condition,
                    "expected": exc.expected,
                    "actual": exc.actual,
                },
                "exact_next_task": "Fix preflight failure; do not publish.",
            }
            write_report(payload)
            return payload

        if not do_commit:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "GREEN — PREFLIGHT READY (NO PUBLICATION)",
                "authorization_basis": auth,
                "bulk_api_used": False,
                "published_count": 0,
                "preflight": {
                    "eligible": pf["eligible"],
                    "ineligible": pf["ineligible"],
                    "unexpected": pf["unexpected"],
                },
                "before_snapshot": pf["pre"],
                "planned_ids": pf["planned_ids"],
                "exact_next_task": "Re-run with --commit to publish.",
            }
            write_report(payload)
            return payload

        published_results = []
        failure = None
        try:
            for action in pf["plan_actions"]:
                eid = action["question_id"]
                try:
                    result = await publish_one(session, action, pf["baselines"][eid])
                except Exception as exc:  # noqa: BLE001
                    failure = {
                        "question_id": eid,
                        "content_item_id": action["content_item_id"],
                        "error_type": type(exc).__name__,
                        "error_code": getattr(exc, "code", None),
                        "error_message": str(exc),
                        "already_published": [r["question_id"] for r in published_results],
                        "remaining_approved_planned": [
                            a["question_id"]
                            for a in pf["plan_actions"]
                            if a["question_id"]
                            not in {r["question_id"] for r in published_results}
                            and a["question_id"] != eid
                        ],
                    }
                    raise
                published_results.append(result)
        except Exception as exc:  # noqa: BLE001
            # Non-atomic: leave already-published items as-is; report AMBER/RED
            state = await snap(session)
            if failure is None:
                failure = {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "already_published": [r["question_id"] for r in published_results],
                }
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — PARTIAL PUBLICATION (STOPPED ON FAILURE)",
                "authorization_basis": auth,
                "bulk_api_used": False,
                "published_count": len(published_results),
                "published_question_ids": [r["question_id"] for r in published_results],
                "per_item_results": published_results,
                "before_snapshot": pf["pre"],
                "after_snapshot": state,
                "failure": failure,
                "rollback": "NOT_ATTEMPTED — publish is non-atomic; no ad-hoc rollback",
                "exact_next_task": "Investigate failure; decide remediation for partial publish.",
            }
            write_report(payload)
            return payload

        post = await post_audit(session, pf)
        student = await verify_student_and_practice(session, pf)
        sample_id = uuid.UUID(pf["baselines"][pf["planned_ids"][0]]["content_item_id"])
        idem = await idempotency_probe(session, sample_id)

        content_integrity = {
            "unexpected_mutations": post["unexpected_mutations"],
            "bodies_unchanged": not any(u.startswith("body_") for u in post["unexpected_mutations"]),
            "options_answers_explanations_in_pedagogy_hash": not any(
                u.startswith("pedagogy_") for u in post["unexpected_mutations"]
            ),
            "concept_ids_unchanged": not any(u.startswith("concept_id") for u in post["unexpected_mutations"]),
            "ncert_unchanged": not any(u.startswith("ncert_") for u in post["unexpected_mutations"]),
            "ok": post["ok"],
        }
        taxonomy_comparison = {
            "before": pf["pre"]["taxonomy"],
            "after": post["post"]["taxonomy"],
            "unchanged": pf["pre"]["taxonomy"] == post["post"]["taxonomy"],
        }
        provenance_comparison = {
            "source_batch_unchanged": not any(
                u.startswith("provenance_") for u in post["unexpected_mutations"]
            ),
            "ok": not any(u.startswith("provenance_") for u in post["unexpected_mutations"]),
        }

        green = (
            len(published_results) == 100
            and post["ok"]
            and post["post"]["biology"] == EXPECTED_BIO_POST
            and student["student_api"]["biology_visible_count"] == 100
            and student["student_api"]["superseded_visible_count"] == 0
            and student["practice_pool"]["full_scope_bio_hits"] == 100
            and student["practice_now_e2e"]["no_mock_fallback"]
            and not student["student_api"]["answer_leaked_before_submit"]
            and not student["practice_now_e2e"]["q1_answer_leaked"]
            and idem["ok"]
            and student["reindex"]["sample_has_search_vector"]
        )

        payload = {
            "batch_id": BATCH,
            "executed_at": executed_at,
            "verdict": (
                "GREEN — BIOLOGY CH1 PILOT FULLY PUBLISHED"
                if green
                else "AMBER/RED — PUBLICATION COMPLETED WITH ANOMALIES"
            ),
            "authorization_basis": auth,
            "bulk_api_used": False,
            "canonical_method": "ContentWorkflowService.publish",
            "published_count": 100,
            "published_question_ids": pf["planned_ids"],
            "published_content_item_ids": [
                pf["baselines"][eid]["content_item_id"] for eid in pf["planned_ids"]
            ],
            "superseded_excluded": pf["superseded_excluded"],
            "preflight": {
                "eligible": 100,
                "ineligible": 0,
                "unexpected": 0,
                "eligibility_sample": pf["eligibility"][:3],
            },
            "before_snapshot": pf["pre"],
            "after_snapshot": post["post"],
            "per_item_results": published_results,
            "content_integrity": content_integrity,
            "taxonomy_comparison": taxonomy_comparison,
            "provenance_comparison": provenance_comparison,
            "verification_levels": post["verification_levels"],
            "student_practice_verification": student,
            "idempotency": idem,
            "failure": None,
            "rollback": "N/A — full success",
            "anomalies": post["unexpected_mutations"],
            "assertions": {
                "exact_100_published": True,
                "APPROVED_0": post["post"]["biology"]["APPROVED"] == 0,
                "PUBLISHED_100": post["post"]["biology"]["PUBLISHED"] == 100,
                "SUPERSEDED_5": post["post"]["biology"]["SUPERSEDED"] == 5,
                "SOURCE_TEXT_VERIFIED_100": post["verification_levels"].get("SOURCE_TEXT_VERIFIED")
                == 100,
                "taxonomy_unchanged": taxonomy_comparison["unchanged"],
                "bodies_unchanged": content_integrity["ok"],
                "student_visible_100": student["student_api"]["biology_visible_count"] == 100,
                "superseded_not_visible": student["student_api"]["superseded_visible_count"] == 0,
                "practice_pool_100": student["practice_pool"]["full_scope_bio_hits"] == 100,
                "practice_e2e_ok": student["practice_now_e2e"]["no_mock_fallback"],
                "idempotency_ok": idem["ok"],
                "bulk_api_not_used": True,
            },
            "exact_next_task": (
                "Pilot publication complete. Next: monitor student practice quality; "
                "do not start another MCQ batch unless explicitly authorized."
            ),
        }
        write_report(payload)
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorized Biology Ch1 publication")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Execute publication (default: preflight only)",
    )
    args = parser.parse_args()
    payload = asyncio.run(run(do_commit=bool(args.commit)))
    print(
        json.dumps(
            {
                "verdict": payload["verdict"],
                "published_count": payload.get("published_count", 0),
                "bulk_api_used": payload.get("bulk_api_used", False),
            },
            indent=2,
        )
    )
    if not str(payload.get("verdict", "")).startswith("GREEN"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
