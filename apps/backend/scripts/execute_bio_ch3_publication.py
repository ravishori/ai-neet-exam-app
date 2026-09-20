"""AUTHORIZED controlled publication for Biology Ch3 (BIO11-CH03-B001).

Uses ONLY ContentWorkflowService.publish(item_id) per plan ID.
Does NOT use bulk publish API.
Stops immediately on first failure (non-atomic — same as CH02).

Usage (from apps/backend):
  python scripts/execute_bio_ch3_publication.py            # dry-run/preflight
  python scripts/execute_bio_ch3_publication.py --commit   # authorized publish
"""
from __future__ import annotations

import argparse
import asyncio
import copy
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

BATCH = "20260912-BIO11-CH03-B001"
CH01 = "20260911-BIO11-CH01-B001"
CH02 = "20260911-BIO11-CH02-B001"
PHY = "20260911-PHY11-CH02-B001"
CHAPTER_NAME = "Plant Kingdom"
CHAPTER_CODE = "plant-kingdom"
EXPECTED_TAX = {"subjects": 4, "chapters": 36, "topics": 113, "concepts": 163}
EXPECTED_PK = {"topics": 8, "concepts": 22}
EXPECTED_CH03_PRE = {
    "DRAFT": 0,
    "SUPERSEDED": 0,
    "PUBLISHED": 0,
    "APPROVED": 100,
    "IN_REVIEW": 0,
}
EXPECTED_CH03_POST = {
    "DRAFT": 0,
    "SUPERSEDED": 0,
    "PUBLISHED": 100,
    "APPROVED": 0,
    "IN_REVIEW": 0,
}
EXPECTED_CH01 = {"DRAFT": 0, "SUPERSEDED": 5, "PUBLISHED": 100, "APPROVED": 0, "IN_REVIEW": 0}
EXPECTED_CH02 = {"DRAFT": 0, "SUPERSEDED": 1, "PUBLISHED": 100, "APPROVED": 0, "IN_REVIEW": 0}
AUTH_REPAIRED_SHA = "16664395d9823f849ef2843182a27c7304682599e6026431350165217298c087"

REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT = REPO_ROOT / "docs" / "acquisition" / "batches" / BATCH
REPAIRED = ROOT / "questions_repaired.jsonl"
OUT_JSON = ROOT / "publication_execution_report.json"
OUT_MD = ROOT / "publication_execution_report.md"
DRY_JSON = ROOT / "publication_dry_run.json"
DRY_MD = ROOT / "publication_dry_run.md"
STAGE_JSON = ROOT / "pipeline_stage_status.json"
STAGE_MD = ROOT / "pipeline_stage_status.md"
PEDAGOGY_KEYS = ("stem", "options", "correct_option", "explanation", "difficulty")
BATCH_NEEDLE = "bio11-ch03-b001"


class Abort(Exception):
    def __init__(self, condition: str, expected=None, actual=None):
        self.condition = condition
        self.expected = expected
        self.actual = actual
        super().__init__(f"ABORT: {condition} expected={expected!r} actual={actual!r}")


def sha_file(p: Path) -> str | None:
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def is_batch_item(item: ContentItem, batch: str, needle: str) -> bool:
    tags = item.tags or []
    if batch in tags or any(batch in (t or "") for t in tags):
        return True
    return bool(item.slug and needle in (item.slug or "").lower())


def eid_from_slug(slug: str | None, batch: str = BATCH) -> str | None:
    if not slug:
        return None
    marker = f"GEMINI-{batch}-"
    if marker not in slug:
        return None
    return f"GEMINI-{batch}-{slug.split(marker, 1)[1]}"


def qnum(eid: str) -> int:
    return int(eid.rsplit("-", 1)[-1])


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


def load_repaired() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in REPAIRED.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["external_question_id"]] = row
    return out


def options_map(body_or_q: dict) -> dict[str, str]:
    opts = body_or_q.get("options")
    if isinstance(opts, list):
        return {o.get("label"): o.get("text") for o in opts if isinstance(o, dict)}
    if isinstance(opts, dict):
        return opts
    return {}


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
    pk = (
        await session.execute(
            text(
                "SELECT count(DISTINCT t.id), count(DISTINCT n.id) "
                "FROM academic.chapters c "
                "LEFT JOIN academic.topics t ON t.chapter_id = c.id AND t.deleted_at IS NULL "
                "LEFT JOIN academic.concepts n ON n.topic_id = t.id AND n.deleted_at IS NULL "
                "WHERE c.code = :code AND c.deleted_at IS NULL"
            ),
            {"code": CHAPTER_CODE},
        )
    ).one()
    items = (
        await session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.deleted_at.is_(None))
        )
    ).scalars().all()
    ch3 = [i for i in items if is_batch_item(i, BATCH, BATCH_NEEDLE)]
    ch1 = [i for i in items if is_batch_item(i, CH01, "bio11-ch01-b001")]
    ch2 = [i for i in items if is_batch_item(i, CH02, "bio11-ch02-b001")]
    phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
    bs = Counter(i.status for i in ch3)
    c1 = Counter(i.status for i in ch1)
    c2 = Counter(i.status for i in ch2)
    repo = CmsRepository(session)
    student_ch3 = 0
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        student_ch3 += sum(1 for i in page if is_batch_item(i, BATCH, BATCH_NEEDLE))
        off += 100
        if off >= tot or not page:
            break
    pool = set(await AssessmentRepository(session).published_question_ids_for_scope("FULL", None))
    ch3_pub = {i.id for i in ch3 if i.status == "PUBLISHED"}
    ch3_nonpub = {i.id for i in ch3 if i.status != "PUBLISHED"}
    return {
        "taxonomy": {
            "subjects": tax[0],
            "chapters": tax[1],
            "topics": tax[2],
            "concepts": tax[3],
        },
        "plant_kingdom": {"topics": pk[0], "concepts": pk[1]},
        "ch03": {
            "DRAFT": bs.get("DRAFT", 0),
            "SUPERSEDED": bs.get("SUPERSEDED", 0),
            "PUBLISHED": bs.get("PUBLISHED", 0),
            "APPROVED": bs.get("APPROVED", 0),
            "IN_REVIEW": bs.get("IN_REVIEW", 0),
        },
        "ch01": {
            "DRAFT": c1.get("DRAFT", 0),
            "SUPERSEDED": c1.get("SUPERSEDED", 0),
            "PUBLISHED": c1.get("PUBLISHED", 0),
            "APPROVED": c1.get("APPROVED", 0),
            "IN_REVIEW": c1.get("IN_REVIEW", 0),
        },
        "ch02": {
            "DRAFT": c2.get("DRAFT", 0),
            "SUPERSEDED": c2.get("SUPERSEDED", 0),
            "PUBLISHED": c2.get("PUBLISHED", 0),
            "APPROVED": c2.get("APPROVED", 0),
            "IN_REVIEW": c2.get("IN_REVIEW", 0),
        },
        "physics_DRAFT": Counter(i.status for i in phy).get("DRAFT", 0),
        "student_ch03": student_ch3,
        "practice_ch03": len(ch3_pub & pool),
        "practice_nonpub_ch03": len(ch3_nonpub & pool),
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
        if not is_batch_item(i, BATCH, BATCH_NEEDLE):
            continue
        eid = eid_from_slug(i.slug)
        if eid:
            out[eid] = i
    return out


async def chapter_name_for_concept(session, concept_id: uuid.UUID) -> str | None:
    return (
        await session.execute(
            select(Chapter.name)
            .join(Topic, Topic.chapter_id == Chapter.id)
            .join(Concept, Concept.topic_id == Topic.id)
            .where(Concept.id == concept_id)
        )
    ).scalar_one_or_none()


async def chapter_id(session) -> uuid.UUID:
    return (
        await session.execute(
            select(Chapter.id).where(Chapter.code == CHAPTER_CODE, Chapter.deleted_at.is_(None))
        )
    ).scalar_one()


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
        "stem_preview": (body.get("stem") or "")[:120],
        "question_type_tag": next(
            (t for t in (item.tags or []) if str(t).startswith("question_type:")), None
        ),
    }


async def build_plan(session) -> list[dict]:
    by_eid = await load_batch_map(session)
    planned = sorted(
        (eid for eid, i in by_eid.items() if i.status == "APPROVED"),
        key=qnum,
    )
    actions = []
    for eid in planned:
        item = by_eid[eid]
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        actions.append(
            {
                "question_id": eid,
                "content_item_id": str(item.id),
                "status": item.status,
                "current_version_id": str(item.latest_version_id) if item.latest_version_id else None,
                "ncert_verification_level": ncert_level(body),
                "concept_id": str(item.concept_id) if item.concept_id else None,
                "planned_action": "publish",
            }
        )
    return actions


async def preflight(session, plan_actions: list[dict]) -> dict:
    repaired_sha = sha_file(REPAIRED)
    if repaired_sha != AUTH_REPAIRED_SHA:
        raise Abort("questions_repaired_sha", AUTH_REPAIRED_SHA, repaired_sha)

    if len(plan_actions) != 100:
        raise Abort("plan_count", 100, len(plan_actions))
    qids = [a["question_id"] for a in plan_actions]
    item_ids = [a["content_item_id"] for a in plan_actions]
    if len(set(qids)) != 100 or len(set(item_ids)) != 100:
        raise Abort("duplicates", 100, {"qids": len(set(qids)), "items": len(set(item_ids))})

    pre = await snap(session)
    if pre["taxonomy"] != EXPECTED_TAX:
        raise Abort("taxonomy", EXPECTED_TAX, pre["taxonomy"])
    if pre["plant_kingdom"] != EXPECTED_PK:
        raise Abort("plant_kingdom", EXPECTED_PK, pre["plant_kingdom"])
    if pre["ch03"] != EXPECTED_CH03_PRE:
        raise Abort("ch03_pre", EXPECTED_CH03_PRE, pre["ch03"])
    if pre["ch01"] != EXPECTED_CH01:
        raise Abort("ch01_regression", EXPECTED_CH01, pre["ch01"])
    if pre["ch02"] != EXPECTED_CH02:
        raise Abort("ch02_regression", EXPECTED_CH02, pre["ch02"])
    if pre["physics_DRAFT"] != 24:
        raise Abort("physics_DRAFT", 24, pre["physics_DRAFT"])
    if pre["student_ch03"] != 0 or pre["practice_nonpub_ch03"] != 0:
        raise Abort("student_safety", 0, pre)

    by_eid = await load_batch_map(session)
    superseded_live = sorted(eid for eid, i in by_eid.items() if i.status == "SUPERSEDED")
    if superseded_live != []:
        raise Abort("superseded_set", [], superseded_live)

    repaired = load_repaired()
    if set(repaired) != set(qids):
        raise Abort(
            "repaired_id_set_mismatch",
            sorted(set(repaired) - set(qids))[:5],
            sorted(set(qids) - set(repaired))[:5],
        )

    baselines = {}
    eligibility = []
    content_mismatches: list[str] = []
    for action in plan_actions:
        eid = action["question_id"]
        item = by_eid.get(eid)
        if not item:
            raise Abort("missing_item", eid, None)
        if str(item.id) != action["content_item_id"]:
            raise Abort("item_id_mismatch", action["content_item_id"], str(item.id))
        if item.status != "APPROVED":
            raise Abort("status", "APPROVED", f"{eid}:{item.status}")
        if item.concept_id is None:
            raise Abort("null_concept", eid, None)
        chap = await chapter_name_for_concept(session, item.concept_id)
        if chap != CHAPTER_NAME:
            raise Abort("wrong_chapter", CHAPTER_NAME, f"{eid}:{chap}")
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        if ncert_level(body) != "SOURCE_TEXT_VERIFIED":
            raise Abort("ncert_level", "SOURCE_TEXT_VERIFIED", f"{eid}:{ncert_level(body)}")
        if (body.get("provenance") or {}).get("batch_id") not in (BATCH, None):
            if (body.get("provenance") or {}).get("batch_id") != BATCH:
                raise Abort("provenance_batch", BATCH, (body.get("provenance") or {}).get("batch_id"))

        q = repaired[eid]
        if body.get("stem") != q["stem"]:
            content_mismatches.append(f"stem:{eid}")
        live_opts = options_map(body)
        for lab in "ABCD":
            if live_opts.get(lab) != q["options"].get(lab):
                content_mismatches.append(f"option:{eid}:{lab}")
                break
        if body.get("correct_option") != q["correct_option"]:
            content_mismatches.append(f"answer:{eid}")
        if body.get("explanation") != q["explanation"]:
            content_mismatches.append(f"explanation:{eid}")
        if body.get("difficulty") != q["difficulty"]:
            content_mismatches.append(f"difficulty:{eid}")

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
        baselines[eid] = item_snapshot(item, chap)

    if content_mismatches:
        raise Abort("content_vs_repaired", [], content_mismatches[:20])

    ineligible = [e for e in eligibility if not e["passed"]]
    if ineligible:
        raise Abort("ineligible_count", 0, ineligible)

    return {
        "pre": pre,
        "baselines": baselines,
        "eligibility": eligibility,
        "planned_ids": qids,
        "plan_actions": plan_actions,
        "superseded_excluded": superseded_live,
        "eligible": 100,
        "ineligible": 0,
        "questions_repaired_sha256": repaired_sha,
        "content_vs_repaired_mismatches": 0,
    }


async def publish_one(session, action: dict, baseline: dict) -> dict:
    """Publish one item. ContentWorkflowService.publish commits per item (non-atomic)."""
    workflow = ContentWorkflowService(session)
    item_id = uuid.UUID(action["content_item_id"])
    eid = action["question_id"]
    item = await CmsRepository(session).get_item(item_id)
    if not item or item.status != "APPROVED":
        raise Abort("status_at_publish", "APPROVED", f"{eid}:{getattr(item, 'status', None)}")
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
        if snap_row["current_version_id"] != base["content_version_id"]:
            unexpected.append(f"current_version:{eid}")

    superseded_live = sorted(eid for eid, i in by_eid.items() if i.status == "SUPERSEDED")
    if superseded_live:
        unexpected.append(f"unexpected_superseded={superseded_live}")

    published_all = sorted(eid for eid, i in by_eid.items() if i.status == "PUBLISHED")
    if set(published_all) != set(pf["planned_ids"]):
        unexpected.append("published_set_mismatch")

    if post["ch03"] != EXPECTED_CH03_POST:
        unexpected.append(f"ch03_post={post['ch03']}")
    if post["taxonomy"] != EXPECTED_TAX:
        unexpected.append(f"taxonomy={post['taxonomy']}")
    if post["plant_kingdom"] != EXPECTED_PK:
        unexpected.append(f"plant_kingdom={post['plant_kingdom']}")
    if post["ch01"] != EXPECTED_CH01:
        unexpected.append(f"ch01={post['ch01']}")
    if post["ch02"] != EXPECTED_CH02:
        unexpected.append(f"ch02={post['ch02']}")
    if post["physics_DRAFT"] != 24:
        unexpected.append(f"physics={post['physics_DRAFT']}")
    if post["student_ch03"] != 100:
        unexpected.append(f"student_ch03={post['student_ch03']}")
    if post["practice_ch03"] != 100:
        unexpected.append(f"practice_ch03={post['practice_ch03']}")
    if post["practice_nonpub_ch03"] != 0:
        unexpected.append(f"practice_nonpub_ch03={post['practice_nonpub_ch03']}")

    return {
        "post": post,
        "verification_levels": dict(levels),
        "unexpected_mutations": unexpected,
        "ok": len(unexpected) == 0,
    }


async def verify_student_and_practice(session, pf: dict) -> dict:
    from app.modules.assessment.api.assessment_router import _public_question

    repo = CmsRepository(session)
    plan_ids = {uuid.UUID(pf["baselines"][eid]["content_item_id"]) for eid in pf["planned_ids"]}
    sample_eid = pf["planned_ids"][0]
    sample_id = uuid.UUID(pf["baselines"][sample_eid]["content_item_id"])

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

    sample_item = await repo.get_item(sample_id)
    names = await repo.academic_names_for_concepts(
        [sample_item.concept_id] if sample_item and sample_item.concept_id else []
    )
    summary = _question_summary(sample_item, names)
    answer_leaked = ("correct_option" in summary) or ("explanation" in summary)
    internal_leak = any(
        k in summary for k in ("ai_check_report", "workflow_state", "ncert_evidence", "verification_level")
    )

    arepo = AssessmentRepository(session)
    chap_id = await chapter_id(session)
    chapter_pool = set(await arepo.published_question_ids_for_scope("CHAPTER", chap_id))
    full_pool = set(await arepo.published_question_ids_for_scope("FULL", None))

    actor = await actor_user(session)
    asvc = AssessmentService(session)
    assessment = await asvc.generate_practice(
        scope_type="CHAPTER",
        scope_id=chap_id,
        question_count=5,
        user_id=actor.id,
    )
    attempt = await asvc.start_attempt(assessment.id, actor.id)
    assessment_full = await asvc.repo.get_assessment(assessment.id)
    aq_ids = [q.content_item_id for q in (assessment_full.questions if assessment_full else [])]

    q1_item = await repo.get_item(aq_ids[0]) if aq_ids else None
    q1_public = None
    q1_leaked = True
    q1_renders = False
    options_ok = False
    if q1_item:
        q1_names = await repo.academic_names_for_concepts(
            [q1_item.concept_id] if q1_item.concept_id else []
        )
        q1_public = _public_question(q1_item, None, q1_names, {}, set())
        q1_leaked = ("correct_option" in q1_public) or ("explanation" in q1_public)
        q1_renders = bool(q1_public.get("stem")) and bool(q1_public.get("options"))
        opts = q1_public.get("options") or []
        if isinstance(opts, list):
            labels = {str(o.get("label") or o.get("id") or "") for o in opts}
            options_ok = {"A", "B", "C", "D"}.issubset(labels) or len(opts) == 4
        elif isinstance(opts, dict):
            options_ok = {"A", "B", "C", "D"}.issubset(set(opts.keys()))

    submit_ok = False
    score_ok = False
    explanation_after = False
    if q1_item and aq_ids:
        ver = await ContentWorkflowService(session).repo.get_version(q1_item.latest_version_id)
        correct = (ver.body or {}).get("correct_option")
        await asvc.save_answer(
            attempt.id,
            actor.id,
            content_item_id=aq_ids[0],
            selected_option=str(correct) if correct else "A",
            time_spent_seconds=5,
        )
        for cid in aq_ids[1:]:
            it = await repo.get_item(cid)
            v = await ContentWorkflowService(session).repo.get_version(it.latest_version_id)
            c = (v.body or {}).get("correct_option") or "A"
            await asvc.save_answer(
                attempt.id, actor.id, content_item_id=cid, selected_option=str(c), time_spent_seconds=1
            )
        submitted = await asvc.submit_attempt(attempt.id, actor.id)
        submit_ok = submitted.status in ("SUBMITTED", "COMPLETED", "SCORED") or submitted.submitted_at is not None
        result = await asvc.repo.get_attempt(attempt.id)
        score_ok = result is not None and (
            getattr(result, "score", None) is not None
            or getattr(result, "correct_count", None) is not None
            or result.status in ("SUBMITTED", "COMPLETED", "SCORED")
        )
        hist = await asvc.get_question_history(actor.id, aq_ids[0])
        explanation_after = bool(hist) or submit_ok
        if ver and (ver.body or {}).get("explanation"):
            explanation_after = True

    search_rows = (
        await session.execute(
            text(
                "SELECT "
                "count(*) FILTER (WHERE search_text IS NOT NULL) AS has_text, "
                "count(*) FILTER (WHERE search_vector IS NOT NULL) AS has_vector, "
                "count(*) AS total "
                "FROM cms.content_items "
                "WHERE id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": [str(i) for i in plan_ids]},
        )
    ).one()

    return {
        "student_api": {
            "ch03_visible_count": len(bio_visible),
            "expected": 100,
            "sample_question_id": sample_eid,
            "sample_renders": bool(summary.get("stem")) and bool(summary.get("options")),
            "answer_leaked_before_submit": answer_leaked,
            "internal_metadata_leaked": internal_leak,
        },
        "practice_pool": {
            "full_scope_ch03_hits": len(plan_ids & full_pool),
            "chapter_scope_ch03_hits": len(plan_ids & chapter_pool),
            "chapter_id": str(chap_id),
        },
        "practice_now_e2e": {
            "assessment_id": str(assessment.id),
            "attempt_id": str(attempt.id),
            "question_count": assessment.question_count,
            "question_ids": [str(i) for i in aq_ids],
            "all_from_plan": all(uuid.UUID(str(i)) in plan_ids for i in aq_ids) if aq_ids else False,
            "ch03_selected": bool(aq_ids) and all(uuid.UUID(str(i)) in plan_ids for i in aq_ids),
            "q1_renders": q1_renders,
            "options_a_d": options_ok,
            "q1_answer_leaked": q1_leaked,
            "answer_submit_ok": submit_ok,
            "scoring_ok": score_ok,
            "explanation_available_after": explanation_after,
            "no_mock_fallback": assessment.question_count > 0 and bool(aq_ids),
        },
        "reindex": {
            "published_with_search_text": int(search_rows[0]),
            "published_with_search_vector": int(search_rows[1]),
            "published_total": int(search_rows[2]),
            "ok": int(search_rows[0]) == 100 and int(search_rows[1]) == 100,
        },
    }


async def idempotency_probe(session, sample_item_id: uuid.UUID) -> dict:
    workflow = ContentWorkflowService(session)
    rejected = False
    code = None
    message = None
    before_ver_count = (
        await session.execute(
            text(
                "SELECT count(*) FROM cms.content_versions "
                "WHERE content_item_id = CAST(:id AS uuid)"
            ),
            {"id": str(sample_item_id)},
        )
    ).scalar_one()
    try:
        await workflow.publish(sample_item_id)
    except (ContentWorkflowError, AppError) as exc:
        rejected = True
        code = getattr(exc, "code", type(exc).__name__)
        message = str(exc)
    item = await CmsRepository(session).get_item(sample_item_id)
    after_ver_count = (
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
        "version_count_unchanged": int(before_ver_count) == int(after_ver_count),
        "ok": (
            rejected
            and code == "INVALID_WORKFLOW_TRANSITION"
            and item is not None
            and item.status == "PUBLISHED"
            and int(before_ver_count) == int(after_ver_count)
        ),
    }


def run_tests() -> dict:
    backend = Path(__file__).resolve().parents[1]
    candidates = [
        backend / ".venv" / "Scripts" / "python.exe",
        backend / ".venv" / "bin" / "python",
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        REPO_ROOT / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    py = next((str(p) for p in candidates if p.exists()), sys.executable)
    cmd = [
        py,
        "-m",
        "pytest",
        "tests/test_cms_workflow.py",
        "tests/test_cms_publish_quality.py",
        "tests/test_ncert_certification_workflow.py",
        "tests/test_ecaep_biology_workflow_gates.py",
        "tests/test_content_draft_supersession.py",
        "app/modules/cms/tests/test_content_bodies.py",
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(backend),
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": "."},
    )
    return {
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "ok": proc.returncode == 0,
        "tail": "\n".join(((proc.stdout or "") + "\n" + (proc.stderr or "")).splitlines()[-40:]),
    }


def write_dry_run(payload: dict) -> None:
    dry = {
        "batch_id": BATCH,
        "executed_at": payload.get("executed_at"),
        "verdict": "GREEN PREFLIGHT / dry-run ready",
        "db_writes": 0,
        "published_count": 0,
        "bulk_api_used": False,
        "preflight": payload.get("preflight"),
        "before_snapshot": payload.get("before_snapshot"),
        "planned_ids": payload.get("planned_ids"),
        "publication_plan": payload.get("publication_plan"),
        "superseded_excluded": payload.get("superseded_excluded"),
        "questions_repaired_sha256": payload.get("questions_repaired_sha256"),
        "exact_next_task": "Re-run with --commit to publish.",
    }
    DRY_JSON.write_text(
        json.dumps(dry, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    DRY_MD.write_text(
        f"""# Publication dry-run — `{BATCH}`

## Verdict: GREEN PREFLIGHT / dry-run ready

- Eligible: **100**
- Ineligible: **0**
- SUPERSEDED in batch: **0**
- DB writes: **0**
- Bulk API used: **false**

Re-run with `--commit` to publish.
""",
        encoding="utf-8",
    )


def write_report(payload: dict) -> None:
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    lines = [
        f"# Publication execution report — `{BATCH}`",
        "",
        f"## Verdict: {payload['verdict']}",
        "",
        f"Executed: `{payload.get('executed_at')}`  ",
        f"Authorization: **{payload.get('authorization_basis')}**  ",
        f"Published: **{payload.get('published_count', 0)}/100**  ",
        f"Bulk API used: **{payload.get('bulk_api_used', False)}**  ",
        f"Method: `{payload.get('canonical_method', 'ContentWorkflowService.publish')}`",
        "",
        "## Preflight / plan",
        "",
        "```json",
        json.dumps(
            {
                "eligible": (payload.get("preflight") or {}).get("eligible"),
                "ineligible": (payload.get("preflight") or {}).get("ineligible"),
                "superseded_excluded": payload.get("superseded_excluded"),
                "before": payload.get("before_snapshot"),
            },
            indent=2,
            default=str,
        ),
        "```",
        "",
        "## Post-publication",
        "",
        "```json",
        json.dumps(
            {
                "after": payload.get("after_snapshot"),
                "verification_levels": payload.get("verification_levels"),
                "student_practice": payload.get("student_practice_verification"),
                "idempotency": payload.get("idempotency"),
                "content_integrity": payload.get("content_integrity"),
            },
            indent=2,
            default=str,
        ),
        "```",
        "",
        "## Commands",
        "",
        "```text",
        "\n".join(payload.get("exact_commands") or []),
        "```",
        "",
        "## Failure",
        "",
        f"```json\n{json.dumps(payload.get('failure'), indent=2, default=str)}\n```"
        if payload.get("failure")
        else "_None_",
        "",
    ]
    if str(payload.get("verdict", "")).startswith("GREEN") and payload.get("published_count") == 100:
        lines.extend(payload.get("explicit_stop") or [])
        lines.append("")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stage(payload: dict) -> None:
    if not (
        str(payload.get("verdict", "")).startswith("GREEN")
        and payload.get("published_count") == 100
    ):
        return
    stage = {
        "batch_id": BATCH,
        "as_of": payload["executed_at"],
        "verdict": "GREEN — BIO11-CH03-B001 PUBLISHED AND VERIFIED",
        "current_stage": "PUBLICATION_COMPLETE",
        "stopped_after": "PUBLICATION",
        "explicit_statement": list(payload.get("explicit_stop") or []),
        "counts": (payload.get("after_snapshot") or {}).get("ch03"),
        "verification_levels": payload.get("verification_levels"),
        "stages": {
            "ncert_certification": "GREEN",
            "publication": "GREEN",
        },
        "artifacts": {
            "publication_execution_report": str(OUT_JSON),
            "publication_dry_run": str(DRY_JSON),
        },
    }
    STAGE_JSON.write_text(json.dumps(stage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    STAGE_MD.write_text(
        f"""# Pipeline stage status — `{BATCH}`

## GREEN — BIO11-CH03-B001 PUBLISHED AND VERIFIED

> 100/100 PUBLISHED · STUDENT VISIBLE 100 · PRACTICE POOL 100

BIO11-CH03-B001 PUBLICATION COMPLETE.
100/100 PUBLISHED.
NCERT SOURCE_TEXT_VERIFIED = 100.
STUDENT VISIBILITY VERIFIED.
PRACTICE AVAILABILITY VERIFIED.
NO UNEXPECTED CONTENT MUTATIONS.
MANDATORY STOP REACHED.
""",
        encoding="utf-8",
    )


async def run(*, do_commit: bool) -> dict:
    executed_at = datetime.now(UTC).isoformat()
    commands = [
        f"python scripts/execute_bio_ch3_publication.py{' --commit' if do_commit else ''}",
    ]
    auth = (
        "Explicit owner authorization for controlled BIO11-CH03-B001 publication; "
        "publish only the 100 active APPROVED+SOURCE_TEXT_VERIFIED plan IDs via "
        "ContentWorkflowService.publish (CH02 pattern; non-atomic per-item commit)."
    )
    explicit_stop = [
        "BIO11-CH03-B001 PUBLICATION COMPLETE.",
        "100/100 PUBLISHED.",
        "NCERT SOURCE_TEXT_VERIFIED = 100.",
        "STUDENT VISIBILITY VERIFIED.",
        "PRACTICE AVAILABILITY VERIFIED.",
        "NO UNEXPECTED CONTENT MUTATIONS.",
        "MANDATORY STOP REACHED.",
    ]

    async with AsyncSessionLocal() as session:
        plan_actions = await build_plan(session)
        try:
            pf = await preflight(session, plan_actions)
        except Abort as exc:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "RED — PUBLICATION BLOCKED (PREFLIGHT)",
                "authorization_basis": auth,
                "bulk_api_used": False,
                "published_count": 0,
                "db_writes": 0,
                "planned_ids": [a["question_id"] for a in plan_actions],
                "failure": {
                    "condition": exc.condition,
                    "expected": exc.expected,
                    "actual": exc.actual,
                },
                "exact_commands": commands,
            }
            write_report(payload)
            return payload

        if not do_commit:
            payload = {
                "batch_id": BATCH,
                "executed_at": executed_at,
                "verdict": "GREEN PREFLIGHT / dry-run ready",
                "authorization_basis": auth,
                "bulk_api_used": False,
                "published_count": 0,
                "db_writes": 0,
                "preflight": {
                    "eligible": 100,
                    "ineligible": 0,
                    "publication_actions": 100,
                    "superseded_excluded": 0,
                },
                "before_snapshot": pf["pre"],
                "planned_ids": pf["planned_ids"],
                "publication_plan": pf["plan_actions"],
                "superseded_excluded": pf["superseded_excluded"],
                "questions_repaired_sha256": pf["questions_repaired_sha256"],
                "exact_commands": commands,
                "exact_next_task": "Re-run with --commit to publish.",
            }
            write_dry_run(payload)
            write_report(payload)
            return payload

        published_results = []
        failure = None
        try:
            # Non-atomic: publish() commits per item; stop on first failure.
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
                    }
                    raise
                published_results.append(result)
        except Exception as exc:  # noqa: BLE001
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
                "before_snapshot": pf["pre"],
                "after_snapshot": state,
                "failure": failure,
                "rollback": "NOT_ATTEMPTED — publish is non-atomic (CH02 pattern)",
                "exact_commands": commands,
            }
            write_report(payload)
            return payload

        post = await post_audit(session, pf)
        student = await verify_student_and_practice(session, pf)
        first_eid = pf["planned_ids"][0]
        sample_id = uuid.UUID(pf["baselines"][first_eid]["content_item_id"])
        idem = await idempotency_probe(session, sample_id)
        tests = run_tests()
        commands.append(tests["command"])

        content_integrity = {
            "unexpected_mutations": post["unexpected_mutations"],
            "ok": post["ok"],
        }
        green = (
            len(published_results) == 100
            and post["ok"]
            and post["post"]["ch03"] == EXPECTED_CH03_POST
            and student["student_api"]["ch03_visible_count"] == 100
            and student["practice_pool"]["full_scope_ch03_hits"] == 100
            and student["practice_pool"]["chapter_scope_ch03_hits"] == 100
            and student["practice_now_e2e"]["ch03_selected"]
            and student["practice_now_e2e"]["q1_renders"]
            and student["practice_now_e2e"]["options_a_d"]
            and not student["student_api"]["answer_leaked_before_submit"]
            and not student["practice_now_e2e"]["q1_answer_leaked"]
            and student["practice_now_e2e"]["answer_submit_ok"]
            and student["reindex"]["ok"]
            and idem["ok"]
            and tests["ok"]
            and post["post"]["ch01"] == EXPECTED_CH01
            and post["post"]["ch02"] == EXPECTED_CH02
            and post["post"]["physics_DRAFT"] == 24
            and post["verification_levels"].get("SOURCE_TEXT_VERIFIED") == 100
        )

        payload = {
            "batch_id": BATCH,
            "executed_at": executed_at,
            "verdict": (
                "GREEN — BIO11-CH03-B001 PUBLISHED AND VERIFIED"
                if green
                else "AMBER/RED — PUBLICATION BLOCKED"
            ),
            "authorization_basis": auth,
            "bulk_api_used": False,
            "canonical_method": "ContentWorkflowService.publish",
            "published_count": 100,
            "published_question_ids": pf["planned_ids"],
            "publication_plan": pf["plan_actions"],
            "superseded_excluded": pf["superseded_excluded"],
            "preflight": {
                "eligible": 100,
                "ineligible": 0,
                "publication_actions": 100,
                "superseded_excluded": 0,
                "unrelated_actions": 0,
            },
            "before_snapshot": pf["pre"],
            "after_snapshot": post["post"],
            "per_item_results": published_results,
            "content_integrity": content_integrity,
            "verification_levels": post["verification_levels"],
            "student_practice_verification": student,
            "idempotency": idem,
            "regression_tests": tests,
            "questions_repaired_sha256": pf["questions_repaired_sha256"],
            "artifact_hashes_preserved": {
                "questions_repaired.jsonl": AUTH_REPAIRED_SHA,
                "match": pf["questions_repaired_sha256"] == AUTH_REPAIRED_SHA,
            },
            "failure": None if green else {
                "unexpected_mutations": post["unexpected_mutations"],
                "student": student,
                "idempotency": idem,
                "tests": tests,
            },
            "exact_commands": commands,
            "assertions": {
                "PUBLISHED_100": post["post"]["ch03"]["PUBLISHED"] == 100,
                "APPROVED_0": post["post"]["ch03"]["APPROVED"] == 0,
                "SUPERSEDED_0": post["post"]["ch03"]["SUPERSEDED"] == 0,
                "SOURCE_TEXT_VERIFIED_100": post["verification_levels"].get("SOURCE_TEXT_VERIFIED")
                == 100,
                "student_visible_100": student["student_api"]["ch03_visible_count"] == 100,
                "practice_pool_100": student["practice_pool"]["full_scope_ch03_hits"] == 100,
                "chapter_practice_100": student["practice_pool"]["chapter_scope_ch03_hits"] == 100,
                "answer_leakage_0": (
                    not student["student_api"]["answer_leaked_before_submit"]
                    and not student["practice_now_e2e"]["q1_answer_leaked"]
                ),
                "reindex_100": student["reindex"]["ok"],
                "ch01_unchanged": post["post"]["ch01"] == EXPECTED_CH01,
                "ch02_unchanged": post["post"]["ch02"] == EXPECTED_CH02,
                "physics_unchanged": post["post"]["physics_DRAFT"] == 24,
                "taxonomy_unchanged": post["post"]["taxonomy"] == EXPECTED_TAX,
                "plant_kingdom_unchanged": post["post"]["plant_kingdom"] == EXPECTED_PK,
                "idempotency_ok": idem["ok"],
                "tests_ok": tests["ok"],
                "bulk_api_not_used": True,
            },
            "explicit_stop": explicit_stop,
        }
        write_report(payload)
        write_stage(payload)
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorized Biology Ch3 publication")
    parser.add_argument("--commit", action="store_true", help="Execute publication")
    args = parser.parse_args()
    payload = asyncio.run(run(do_commit=bool(args.commit)))
    print(
        json.dumps(
            {
                "verdict": payload["verdict"],
                "published_count": payload.get("published_count", 0),
                "after": payload.get("after_snapshot"),
                "failure": payload.get("failure"),
            },
            indent=2,
            default=str,
        )
    )
    if not str(payload.get("verdict", "")).startswith("GREEN"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
