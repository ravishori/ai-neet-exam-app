"""BIO11-CH03 authorized taxonomy migration + DRAFT import.

Usage (from apps/backend):
  python scripts/execute_bio_ch3_taxonomy_and_draft_import.py --dry-run-only
  python scripts/execute_bio_ch3_taxonomy_and_draft_import.py --commit

STOPS after taxonomy + DRAFT import. Does NOT run ECAEP / certify / publish.

Does NOT overwrite taxonomy_migration_plan.json or other protected artifacts.
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
from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.acquisition.gemini_jsonl_draft_importer import (
    GeminiJsonlDraftImporter,
    import_slug,
)
from app.modules.cms.acquisition.physics_t6d_service import actor_user
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import ContentWorkflowService

BATCH = "20260912-BIO11-CH03-B001"
CH01 = "20260911-BIO11-CH01-B001"
CH02 = "20260911-BIO11-CH02-B001"
PHY = "20260911-PHY11-CH02-B001"
ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
REPAIRED = ROOT / "questions_repaired.jsonl"
PLAN_PATH = ROOT / "taxonomy_migration_plan.json"
REVIEW_PATH = ROOT / "taxonomy_expansion_review.json"
EXPECTED_SHA = "16664395d9823f849ef2843182a27c7304682599e6026431350165217298c087"

CHAPTER_CODE = "plant-kingdom"
CHAPTER_ID = uuid.UUID("9cc2b730-e778-460a-aacd-57147f0f502f")
BOTANY_ID = uuid.UUID("92283579-413a-45d7-8d77-0c407fe7d277")
SEED_TOPIC_CODES = {"sv2t-botany-03", "sv2t-botany-04"}
SEED_CONCEPT_CODES = {"sv2c-botany-03", "sv2c-botany-04"}

TAX_MD = ROOT / "taxonomy_migration_execution_report.md"
TAX_JSON = ROOT / "taxonomy_migration_execution_report.json"


class Stop(Exception):
    def __init__(self, condition: str, expected=None, actual=None):
        self.condition = condition
        self.expected = expected
        self.actual = actual
        super().__init__(f"STOP: {condition} expected={expected!r} actual={actual!r}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_batch(item: ContentItem, batch: str, slug_bit: str) -> bool:
    tags = item.tags or []
    if batch in tags or any(batch in (t or "") for t in tags):
        return True
    return bool(item.slug and slug_bit in (item.slug or "").lower())


def is_ch03(item: ContentItem) -> bool:
    return is_batch(item, BATCH, "bio11-ch03-b001")


def is_ch01(item: ContentItem) -> bool:
    return is_batch(item, CH01, "bio11-ch01-b001")


def is_ch02(item: ContentItem) -> bool:
    return is_batch(item, CH02, "bio11-ch02-b001")


def is_phy(item: ContentItem) -> bool:
    return any(PHY in (t or "") for t in (item.tags or []))


async def taxonomy_counts(session) -> dict:
    row = (
        await session.execute(
            text(
                "SELECT (SELECT count(*) FROM academic.subjects WHERE deleted_at IS NULL),"
                "(SELECT count(*) FROM academic.chapters WHERE deleted_at IS NULL),"
                "(SELECT count(*) FROM academic.topics WHERE deleted_at IS NULL),"
                "(SELECT count(*) FROM academic.concepts WHERE deleted_at IS NULL)"
            )
        )
    ).one()
    return {"subjects": row[0], "chapters": row[1], "topics": row[2], "concepts": row[3]}


async def plant_kingdom_counts(session) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT count(DISTINCT t.id), count(DISTINCT n.id)
                FROM academic.chapters c
                LEFT JOIN academic.topics t ON t.chapter_id = c.id AND t.deleted_at IS NULL
                LEFT JOIN academic.concepts n ON n.topic_id = t.id AND n.deleted_at IS NULL
                WHERE c.code = :code AND c.deleted_at IS NULL
                """
            ),
            {"code": CHAPTER_CODE},
        )
    ).one()
    return {"topics": row[0], "concepts": row[1]}


async def content_snapshot(session) -> dict:
    items = (
        await session.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))
    ).scalars().all()
    ch03 = [i for i in items if is_ch03(i)]
    ch01 = [i for i in items if is_ch01(i)]
    ch02 = [i for i in items if is_ch02(i)]
    phy = [i for i in items if is_phy(i)]
    return {
        "ch03": {
            **Counter(i.status for i in ch03),
            "total": len(ch03),
            "DRAFT": Counter(i.status for i in ch03).get("DRAFT", 0),
            "IN_REVIEW": Counter(i.status for i in ch03).get("IN_REVIEW", 0),
            "APPROVED": Counter(i.status for i in ch03).get("APPROVED", 0),
            "PUBLISHED": Counter(i.status for i in ch03).get("PUBLISHED", 0),
            "SUPERSEDED": Counter(i.status for i in ch03).get("SUPERSEDED", 0),
        },
        "ch01_PUBLISHED": Counter(i.status for i in ch01).get("PUBLISHED", 0),
        "ch02_PUBLISHED": Counter(i.status for i in ch02).get("PUBLISHED", 0),
        "physics_DRAFT": Counter(i.status for i in phy).get("DRAFT", 0),
        "ch03_items": ch03,
    }


async def student_ch03_visible(session) -> int:
    repo = CmsRepository(session)
    n = 0
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        n += sum(1 for i in page if is_ch03(i))
        off += 100
        if off >= tot or not page:
            break
    return n


async def practice_ch03_hits(session) -> int:
    pool = set(await AssessmentRepository(session).published_question_ids_for_scope("FULL", None))
    snap = await content_snapshot(session)
    return len({i.id for i in snap["ch03_items"] if i.status == "PUBLISHED"} & pool)


def load_plan() -> dict:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if plan.get("batch_id") != BATCH:
        raise Stop("plan_batch", BATCH, plan.get("batch_id"))
    if len(plan.get("proposed_topics", [])) != 6:
        raise Stop("plan_topics", 6, len(plan.get("proposed_topics", [])))
    if len(plan.get("proposed_concepts", [])) != 20:
        raise Stop("plan_concepts", 20, len(plan.get("proposed_concepts", [])))
    assignments = plan.get("question_concept_assignments") or []
    if len(assignments) != 100:
        raise Stop("plan_assignments", 100, len(assignments))
    # normalize mappings list used by mapper
    plan["question_mappings"] = [
        {
            "external_question_id": a["external_question_id"],
            "proposed_concept_code": a["proposed_concept_code"],
            "proposed_concept_id": a["proposed_concept_id"],
        }
        for a in assignments
    ]
    return plan


async def preflight(session) -> dict:
    if not REPAIRED.exists():
        raise Stop("repaired_missing", True, False)
    sha = sha256_file(REPAIRED)
    if sha != EXPECTED_SHA:
        raise Stop("repaired_sha256", EXPECTED_SHA, sha)

    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    if "PASSED" not in str(review.get("overall_verdict", "")):
        raise Stop("review_not_passed", "PASSED", review.get("overall_verdict"))

    qs = [json.loads(l) for l in REPAIRED.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(qs) != 100:
        raise Stop("repaired_count", 100, len(qs))
    q1 = next(q for q in qs if q["external_question_id"].endswith("000001"))
    stem_l = q1["stem"].lower()
    opt_a = (q1.get("options") or {}).get("A", "")
    if "seventy species used as food" not in stem_l or "Porphyra" not in opt_a:
        raise Stop("q000001_not_repaired_food_algae", "food-algae", q1["stem"][:80])

    tax = await taxonomy_counts(session)
    pk = await plant_kingdom_counts(session)
    snap = await content_snapshot(session)

    if snap["ch01_PUBLISHED"] != 100:
        raise Stop("ch01_published", 100, snap["ch01_PUBLISHED"])
    if snap["ch02_PUBLISHED"] != 100:
        raise Stop("ch02_published", 100, snap["ch02_PUBLISHED"])
    if snap["physics_DRAFT"] != 24:
        raise Stop("physics_draft", 24, snap["physics_DRAFT"])

    ch03_ok_clean = snap["ch03"]["total"] == 0
    ch03_ok_resume = (
        snap["ch03"]["total"] == 100
        and snap["ch03"]["DRAFT"] == 100
        and snap["ch03"]["IN_REVIEW"] == 0
        and snap["ch03"]["APPROVED"] == 0
        and snap["ch03"]["PUBLISHED"] == 0
    )
    if not (ch03_ok_clean or ch03_ok_resume):
        raise Stop("unexpected_ch03_content", "0 or 100 DRAFT", snap["ch03"])

    pk_ok_clean = pk == {"topics": 2, "concepts": 2}
    pk_ok_resume = pk == {"topics": 8, "concepts": 22}
    if not (pk_ok_clean or pk_ok_resume):
        raise Stop("unexpected_plant_kingdom_pre", "2/2 or 8/22", pk)

    # Partial pk-* only allowed when full approved set is present (resume)
    existing_pk_t = (
        await session.execute(
            text(
                "SELECT code FROM academic.topics WHERE deleted_at IS NULL AND code LIKE 'pk-t-%' ORDER BY code"
            )
        )
    ).scalars().all()
    existing_pk_c = (
        await session.execute(
            text(
                """
                SELECT code FROM academic.concepts
                WHERE deleted_at IS NULL AND code LIKE 'pk-%' AND code NOT LIKE 'pk-t-%'
                ORDER BY code
                """
            )
        )
    ).scalars().all()
    plan_preview = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    expected_t = sorted(t["code"] for t in plan_preview["proposed_topics"])
    expected_c = sorted(c["code"] for c in plan_preview["proposed_concepts"])
    if existing_pk_t or existing_pk_c:
        if sorted(existing_pk_t) != expected_t or sorted(existing_pk_c) != expected_c:
            raise Stop(
                "partial_or_unexpected_pk_taxonomy",
                {"topics": expected_t, "concepts": expected_c},
                {"topics": list(existing_pk_t), "concepts": list(existing_pk_c)},
            )

    chapter = (
        await session.execute(
            select(Chapter).where(Chapter.code == CHAPTER_CODE, Chapter.deleted_at.is_(None))
        )
    ).scalar_one()
    if chapter.id != CHAPTER_ID:
        raise Stop("chapter_id", str(CHAPTER_ID), str(chapter.id))
    if chapter.subject_id != BOTANY_ID:
        raise Stop("chapter_subject", str(BOTANY_ID), str(chapter.subject_id))

    # slug conflicts: only our own DRAFT batch items are allowed
    existing_slugs = []
    for q in qs:
        slug = import_slug(q["external_question_id"])
        row = (
            await session.execute(
                select(ContentItem).where(ContentItem.slug == slug, ContentItem.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if row and not (is_ch03(row) and row.status == "DRAFT"):
            existing_slugs.append({"id": str(row.id), "status": row.status, "slug": row.slug})
    if existing_slugs:
        raise Stop("slug_conflicts", [], existing_slugs)

    return {
        "batch_id": BATCH,
        "repaired_sha256": sha,
        "review_verdict": review.get("overall_verdict"),
        "resume_mode": bool(ch03_ok_resume or pk_ok_resume),
        "taxonomy_counts": tax,
        "plant_kingdom": pk,
        "content": {k: v for k, v in snap.items() if k != "ch03_items"},
        "student_ch03_visible": await student_ch03_visible(session),
        "practice_ch03_hits": await practice_ch03_hits(session),
        "chapter_id": str(chapter.id),
        "q000001_stem": q1["stem"],
    }


async def migrate_taxonomy(session, plan: dict, *, commit: bool) -> dict:
    created = {"topics": 0, "concepts": 0}
    existing = {"topics": 0, "concepts": 0}

    chapter = (
        await session.execute(
            select(Chapter).where(Chapter.id == CHAPTER_ID, Chapter.deleted_at.is_(None))
        )
    ).scalar_one()

    topic_ids: dict[str, uuid.UUID] = {}
    for t in plan["proposed_topics"]:
        tid = uuid.UUID(t["proposed_topic_id"])
        if uuid.uuid5(CHAPTER_ID, t["code"]) != tid:
            raise Stop("topic_uuid5", str(uuid.uuid5(CHAPTER_ID, t["code"])), str(tid))
        if t["parent_chapter_id"] != str(CHAPTER_ID):
            raise Stop("topic_parent", str(CHAPTER_ID), t["parent_chapter_id"])
        row = (
            await session.execute(
                select(Topic).where(
                    Topic.chapter_id == CHAPTER_ID,
                    Topic.code == t["code"],
                    Topic.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            # global code collision
            hit = (
                await session.execute(
                    select(Topic).where(Topic.code == t["code"], Topic.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if hit:
                raise Stop("topic_code_collision", "absent", str(hit.id))
            session.add(
                Topic(
                    id=tid,
                    chapter_id=CHAPTER_ID,
                    code=t["code"],
                    name=t["name"],
                    display_order=t["display_order"],
                )
            )
            created["topics"] += 1
            topic_ids[t["code"]] = tid
        else:
            existing["topics"] += 1
            if row.id != tid:
                raise Stop("topic_id_mismatch", str(tid), str(row.id))
            if row.name != t["name"]:
                raise Stop("topic_name", t["name"], row.name)
            topic_ids[t["code"]] = row.id
    await session.flush()

    for c in plan["proposed_concepts"]:
        tid = topic_ids[c["topic_code"]]
        cid = uuid.UUID(c["proposed_concept_id"])
        if uuid.uuid5(tid, c["code"]) != cid:
            raise Stop("concept_uuid5", str(cid), str(uuid.uuid5(tid, c["code"])))
        if c["parent_topic_id"] != str(tid):
            # plan stores proposed parent; must match resolved topic id
            if uuid.UUID(c["parent_topic_id"]) != tid:
                raise Stop("concept_parent", str(tid), c["parent_topic_id"])
        row = (
            await session.execute(
                select(Concept).where(
                    Concept.topic_id == tid,
                    Concept.code == c["code"],
                    Concept.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            code_hit = (
                await session.execute(
                    select(Concept).where(Concept.code == c["code"], Concept.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if code_hit:
                raise Stop("concept_code_collision", "absent", str(code_hit.id))
            name_hit = (
                await session.execute(
                    select(Concept).where(Concept.name == c["name"], Concept.deleted_at.is_(None))
                )
            ).scalars().all()
            if name_hit:
                raise Stop("concept_name_duplicate", "absent", [str(x.id) for x in name_hit])
            session.add(
                Concept(
                    id=cid,
                    topic_id=tid,
                    code=c["code"],
                    name=c["name"],
                    summary=c.get("definition") or c["name"],
                    ncert_reference=(
                        f"ncert-books-class-11-biology-chapter-3.pdf — "
                        f"{c.get('ncert_reference') or ''}"
                    )[:300],
                    difficulty="medium",
                    display_order=c.get("display_order", 0),
                )
            )
            created["concepts"] += 1
        else:
            existing["concepts"] += 1
            if row.id != cid:
                raise Stop("concept_id_mismatch", str(cid), str(row.id))
            if row.name != c["name"]:
                raise Stop("concept_name", c["name"], row.name)

    await session.flush()
    verify = await verify_taxonomy(session, plan)
    if not verify["ok"]:
        await session.rollback()
        raise Stop("taxonomy_verify_failed", True, verify)

    chapter_id_str = str(CHAPTER_ID)
    if commit:
        await session.commit()
    else:
        await session.rollback()

    return {
        "created": created,
        "existing": existing,
        "committed": commit,
        "verify": verify,
        "chapter_id": chapter_id_str,
    }


async def verify_taxonomy(session, plan: dict) -> dict:
    issues = []
    pk = await plant_kingdom_counts(session)
    if pk["topics"] != 8:
        issues.append(f"topic_count={pk['topics']}")
    if pk["concepts"] != 22:
        issues.append(f"concept_count={pk['concepts']}")

    topics = (
        await session.execute(
            select(Topic).where(Topic.chapter_id == CHAPTER_ID, Topic.deleted_at.is_(None))
        )
    ).scalars().all()
    codes_t = {t.code for t in topics}
    expected_new = {t["code"] for t in plan["proposed_topics"]}
    if not expected_new.issubset(codes_t):
        issues.append(f"missing_topics={sorted(expected_new - codes_t)}")
    if not SEED_TOPIC_CODES.issubset(codes_t):
        issues.append(f"seed_topics_missing={sorted(SEED_TOPIC_CODES - codes_t)}")

    concepts = (
        await session.execute(
            select(Concept)
            .join(Topic, Topic.id == Concept.topic_id)
            .where(Topic.chapter_id == CHAPTER_ID, Concept.deleted_at.is_(None))
        )
    ).scalars().all()
    codes_c = {c.code for c in concepts}
    expected_c = {c["code"] for c in plan["proposed_concepts"]}
    if not expected_c.issubset(codes_c):
        issues.append(f"missing_concepts={sorted(expected_c - codes_c)}")
    if not SEED_CONCEPT_CODES.issubset(codes_c):
        issues.append(f"seed_concepts_missing={sorted(SEED_CONCEPT_CODES - codes_c)}")

    topic_by_code = {t.code: t for t in topics}
    for cspec in plan["proposed_concepts"]:
        t = topic_by_code.get(cspec["topic_code"])
        if not t:
            issues.append(f"parent_missing:{cspec['code']}")
            continue
        cid = uuid.UUID(cspec["proposed_concept_id"])
        row = next((x for x in concepts if x.code == cspec["code"]), None)
        if row is None:
            issues.append(f"concept_absent:{cspec['code']}")
            continue
        if row.id != cid:
            issues.append(f"id_mismatch:{cspec['code']}")
        if row.topic_id != t.id:
            issues.append(f"wrong_parent:{cspec['code']}")
        if uuid.uuid5(t.id, cspec["code"]) != cid:
            issues.append(f"uuid5_fail:{cspec['code']}")

    return {
        "ok": not issues,
        "issues": issues,
        "plant_kingdom": pk,
        "topic_codes": sorted(codes_t),
        "concept_codes_new": sorted(expected_c & codes_c),
    }


async def import_draft(session, *, commit: bool) -> dict:
    actor = await actor_user(session)
    importer = GeminiJsonlDraftImporter(session)
    report = await importer.run(
        input_path=REPAIRED,
        author_id=actor.id,
        dry_run=not commit,
        batch_id=BATCH,
        atomic=True,
    )
    data = report.to_dict()
    data["created_count"] = report.created
    data["would_create_count"] = report.would_create
    data["already_exists"] = report.already_exists
    data["rejected"] = report.rejected
    data["failed"] = report.failed
    if commit and report.rejected:
        raise Stop("import_rejected", 0, report.rejected)
    if commit and report.failed:
        raise Stop("import_failed", 0, report.failed)
    if commit and (report.created + report.already_exists) != 100:
        raise Stop(
            "import_count",
            100,
            {"created": report.created, "already_exists": report.already_exists},
        )
    return data


async def map_concepts(session, plan: dict) -> dict:
    code_to_id = {c["code"]: uuid.UUID(c["proposed_concept_id"]) for c in plan["proposed_concepts"]}
    eid_to_code = {
        m["external_question_id"]: m["proposed_concept_code"] for m in plan["question_mappings"]
    }
    updated = 0
    already = 0
    for eid, code in eid_to_code.items():
        slug = import_slug(eid)
        item = (
            await session.execute(
                select(ContentItem).where(ContentItem.slug == slug, ContentItem.deleted_at.is_(None))
            )
        ).scalar_one()
        want = code_to_id[code]
        if item.concept_id == want:
            already += 1
            continue
        if item.status != "DRAFT":
            raise Stop("map_non_draft", "DRAFT", item.status)
        if item.concept_id is not None and item.concept_id != want:
            raise Stop("unexpected_concept", str(want), str(item.concept_id))
        item.concept_id = want
        updated += 1
    await session.flush()
    return {"updated": updated, "already": already, "total": len(eid_to_code)}


async def verify_post(session, plan: dict) -> dict:
    snap = await content_snapshot(session)
    pk = await plant_kingdom_counts(session)
    issues = []
    if snap["ch03"]["DRAFT"] != 100 or snap["ch03"]["total"] != 100:
        issues.append(f"ch03={snap['ch03']}")
    if snap["ch03"]["IN_REVIEW"] or snap["ch03"]["APPROVED"] or snap["ch03"]["PUBLISHED"]:
        issues.append(f"non_draft={snap['ch03']}")
    if pk != {"topics": 8, "concepts": 22}:
        issues.append(f"plant_kingdom={pk}")
    if snap["ch01_PUBLISHED"] != 100:
        issues.append(f"ch01={snap['ch01_PUBLISHED']}")
    if snap["ch02_PUBLISHED"] != 100:
        issues.append(f"ch02={snap['ch02_PUBLISHED']}")
    if snap["physics_DRAFT"] != 24:
        issues.append(f"physics={snap['physics_DRAFT']}")

    repaired = {
        q["external_question_id"]: q
        for q in (json.loads(l) for l in REPAIRED.read_text(encoding="utf-8").splitlines() if l.strip())
    }
    mapped = 0
    not_verified = 0
    mismatches = Counter()
    for eid, q in repaired.items():
        slug = import_slug(eid)
        item = (
            await session.execute(
                select(ContentItem)
                .options(selectinload(ContentItem.versions))
                .where(ContentItem.slug == slug, ContentItem.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if item is None:
            issues.append(f"missing:{eid}")
            continue
        if item.status != "DRAFT":
            issues.append(f"status:{eid}={item.status}")
        want = next(m for m in plan["question_mappings"] if m["external_question_id"] == eid)
        if item.concept_id is None:
            issues.append(f"null_concept:{eid}")
        elif str(item.concept_id) != want["proposed_concept_id"]:
            issues.append(f"concept_mismatch:{eid}")
        else:
            mapped += 1
            # verify concept under plant-kingdom
            path = (
                await session.execute(
                    text(
                        """
                        SELECT s.code, ch.code, t.code, c.code
                        FROM academic.concepts c
                        JOIN academic.topics t ON t.id = c.topic_id
                        JOIN academic.chapters ch ON ch.id = t.chapter_id
                        JOIN academic.subjects s ON s.id = ch.subject_id
                        WHERE c.id = :cid AND c.deleted_at IS NULL
                        """
                    ),
                    {"cid": item.concept_id},
                )
            ).one()
            if path[0] != "BOTANY" or path[1] != CHAPTER_CODE:
                issues.append(f"wrong_path:{eid}:{path}")

        ver = next((v for v in item.versions if v.id == item.latest_version_id), None)
        body = dict(ver.body or {}) if ver else {}
        if body.get("stem") != q["stem"]:
            mismatches["stem"] += 1
            issues.append(f"stem_mismatch:{eid}")
        opts = body.get("options")
        # options may be list[{label,text}] or dict
        if isinstance(opts, list):
            opt_map = {o.get("label"): o.get("text") for o in opts if isinstance(o, dict)}
        elif isinstance(opts, dict):
            opt_map = opts
        else:
            opt_map = {}
        for lab in "ABCD":
            if opt_map.get(lab) != q["options"].get(lab):
                mismatches["options"] += 1
                issues.append(f"option_mismatch:{eid}:{lab}")
                break
        if body.get("correct_option") != q["correct_option"]:
            mismatches["answer"] += 1
            issues.append(f"answer_mismatch:{eid}")
        if body.get("explanation") != q["explanation"]:
            mismatches["explanation"] += 1
            issues.append(f"explanation_mismatch:{eid}")
        if body.get("difficulty") != q["difficulty"]:
            mismatches["difficulty"] += 1
            issues.append(f"difficulty_mismatch:{eid}")
        # question_type may live in body or tags
        qt = body.get("question_type")
        if qt and qt != q["question_type"]:
            mismatches["question_type"] += 1
            issues.append(f"type_mismatch:{eid}")
        ncert = body.get("ncert_evidence") or {}
        if isinstance(ncert, dict) and ncert.get("verification_level") == "NOT_VERIFIED":
            not_verified += 1
        elif NCERT_NOT_VERIFIED_IN_TAGS(item):
            not_verified += 1
        else:
            # importer should set NOT_VERIFIED
            blob = json.dumps(body, ensure_ascii=False)
            if "NOT_VERIFIED" in blob or "ncert:NOT_VERIFIED" in (item.tags or []):
                not_verified += 1
            else:
                issues.append(f"ncert_not_unverified:{eid}")

        if eid.endswith("000001"):
            # Repaired Q000001: food-algae stem; Porphyra/Laminaria/Sargassum in options
            stem_ok = "seventy species used as food" in (body.get("stem") or "").lower()
            opt_blob = " ".join(str(v) for v in opt_map.values())
            opts_ok = "Porphyra" in opt_blob and "Laminaria" in opt_blob
            nav_reverted = "which of the following is correct regarding" in (body.get("stem") or "").lower()
            if not (stem_ok and opts_ok) or nav_reverted:
                issues.append("q000001_reverted")

    vis = await student_ch03_visible(session)
    prac = await practice_ch03_hits(session)
    if vis != 0:
        issues.append(f"student_visible={vis}")
    if prac != 0:
        issues.append(f"practice_hits={prac}")

    return {
        "ok": not issues,
        "issues": issues[:80],
        "issue_count": len(issues),
        "mapped": mapped,
        "not_verified": not_verified,
        "mismatches": dict(mismatches),
        "snapshot": {k: v for k, v in snap.items() if k != "ch03_items"},
        "plant_kingdom": pk,
        "student_ch03_visible": vis,
        "practice_ch03_hits": prac,
        "taxonomy_counts": await taxonomy_counts(session),
    }


def NCERT_NOT_VERIFIED_IN_TAGS(item: ContentItem) -> bool:
    return any((t or "").startswith("ncert:NOT_VERIFIED") or t == "ncert:NOT_VERIFIED" for t in (item.tags or []))


async def test_rollback(session, plan: dict) -> dict:
    before_pk = await plant_kingdom_counts(session)
    before = await content_snapshot(session)
    actor = await actor_user(session)
    wf = ContentWorkflowService(session)
    nested = await session.begin_nested()
    failed = False
    try:
        await wf.create_item(
            content_type="QUESTION",
            concept_id=uuid.UUID(plan["proposed_concepts"][0]["proposed_concept_id"]),
            title="ROLLBACK-TEST-CH03",
            slug=f"rollback-test-ch03-{uuid.uuid4().hex[:8]}",
            tags=["rollback-test", BATCH],
            language="en",
            body={
                "stem": "rollback test stem — discard",
                "options": [
                    {"label": "A", "text": "option a"},
                    {"label": "B", "text": "option b"},
                    {"label": "C", "text": "option c"},
                    {"label": "D", "text": "option d"},
                ],
                "correct_option": "A",
                "explanation": "rollback",
                "difficulty": "easy",
            },
            author_id=actor.id,
            model_used="test",
            prompt_version="rollback",
            commit=False,
        )
        raise RuntimeError("induced_import_failure")
    except RuntimeError:
        failed = True
        await nested.rollback()
    after = await content_snapshot(session)
    after_pk = await plant_kingdom_counts(session)
    return {
        "induced_failure": failed,
        "ch03_before": before["ch03"]["total"],
        "ch03_after": after["ch03"]["total"],
        "plant_kingdom_before": before_pk,
        "plant_kingdom_after": after_pk,
        "ok": failed
        and after["ch03"]["total"] == before["ch03"]["total"]
        and after_pk == before_pk,
    }


def write_report(*, plan, pre, tax, imp, mapped, post, rollback, idem) -> None:
    ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    topics_present = tax["created"]["topics"] + tax["existing"]["topics"]
    concepts_present = tax["created"]["concepts"] + tax["existing"]["concepts"]
    questions_present = int(imp.get("created_count") or 0) + int(imp.get("already_exists") or 0)
    # True baseline before any CH03 mutation (from dry-run / authorization package)
    true_pre = {
        "plant_kingdom": {"topics": 2, "concepts": 2},
        "ch03_imported": 0,
        "ch01_PUBLISHED": 100,
        "ch02_PUBLISHED": 100,
        "physics_DRAFT": 24,
        "subjects": 4,
        "chapters": 36,
        "topics_global": 107,
        "concepts_global": 143,
    }
    mutation = {
        "topics_created_approved": 6,
        "concepts_created_approved": 20,
        "questions_imported_DRAFT": 100,
        "concept_mappings_applied": 100,
        "this_run_taxonomy_creates": tax["created"],
        "this_run_question_creates": imp.get("created_count"),
        "this_run_map_updates": mapped.get("updated"),
        "resume_or_idempotent_run": bool(pre.get("resume_mode")),
        "note": (
            "First authorized commit created 6 topics + 20 concepts + 100 DRAFT items and "
            "applied 100 concept mappings. Subsequent verification/idempotency runs create 0."
            if pre.get("resume_mode")
            else "This run performed the initial creates."
        ),
    }
    payload = {
        "batch_id": BATCH,
        "timestamp": ts,
        "authorization_scope": (
            "Explicit user authorization for BIO11-CH03-B001 taxonomy migration + DRAFT import; "
            "taxonomy_expansion_review PASSED"
        ),
        "source_artifact": {
            "path": str(REPAIRED),
            "sha256": pre["repaired_sha256"],
            "expected_sha256": EXPECTED_SHA,
        },
        "true_pre_migration_baseline": true_pre,
        "verification_run_snapshot": pre,
        "taxonomy_plan": {
            "reuse_subject": "BOTANY",
            "reuse_chapter": CHAPTER_CODE,
            "topics_delta": 6,
            "concepts_delta": 20,
            "id_strategy": "uuid5(parent_id, code)",
        },
        "taxonomy_execution": tax,
        "approved_topics_present": topics_present,
        "approved_concepts_present": concepts_present,
        "import_execution": {k: v for k, v in imp.items() if k != "outcomes"},
        "questions_present": questions_present,
        "concept_mapping": mapped,
        "post_verification": post,
        "rollback_test": rollback,
        "idempotency": idem,
        "database_mutation_summary": mutation,
        "final_state": {
            "ch03_DRAFT": post["snapshot"]["ch03"]["DRAFT"],
            "ch03_IN_REVIEW": post["snapshot"]["ch03"]["IN_REVIEW"],
            "ch03_APPROVED": post["snapshot"]["ch03"]["APPROVED"],
            "ch03_PUBLISHED": post["snapshot"]["ch03"]["PUBLISHED"],
            "plant_kingdom_topics": post["plant_kingdom"]["topics"],
            "plant_kingdom_concepts": post["plant_kingdom"]["concepts"],
            "concept_mapped": post["mapped"],
            "ncert_NOT_VERIFIED": post["not_verified"],
            "student_visible": post["student_ch03_visible"],
            "practice_pool": post["practice_ch03_hits"],
            "ch01_PUBLISHED": post["snapshot"]["ch01_PUBLISHED"],
            "ch02_PUBLISHED": post["snapshot"]["ch02_PUBLISHED"],
            "physics_DRAFT": post["snapshot"]["physics_DRAFT"],
        },
        "commands": [
            "python scripts/execute_bio_ch3_taxonomy_and_draft_import.py --dry-run-only",
            "python scripts/execute_bio_ch3_taxonomy_and_draft_import.py --commit",
        ],
        "verdict": "GREEN — BIO11-CH03-B001 TAXONOMY MIGRATION + DRAFT IMPORT COMPLETE",
        "stopped_before": ["ECAEP", "NCERT certification", "publication"],
    }
    TAX_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    TAX_MD.write_text(
        f"""# Taxonomy Migration + DRAFT Import Execution — `{BATCH}`

## Verdict

**{payload['verdict']}**

Timestamp: `{ts}`

## Authorization

{payload['authorization_scope']}

## Source artifact

- Path: `questions_repaired.jsonl`
- SHA-256: `{EXPECTED_SHA}`
- Verified match: **yes**

## True pre-migration baseline

- CH01 PUBLISHED: **100**
- CH02 PUBLISHED: **100**
- Physics DRAFT: **24**
- CH03 imported: **0**
- Plant Kingdom topics/concepts: **2 / 2**

## Database mutation summary

- Approved topics created: **6** (`pk-t-*`)
- Approved concepts created: **20** (`pk-*`)
- Questions imported as DRAFT: **100**
- Concept mappings: **100 / 100**
- This verification run creates: taxonomy `{tax['created']}`, questions `{imp.get('created_count')}`
- Note: {mutation['note']}

## Taxonomy execution

Reuse subject **BOTANY**, chapter **plant-kingdom** (no new subject/chapter).

After migration: Plant Kingdom **8 topics / 22 concepts** (2 Seed-V2 + 6/20 approved).

```json
{json.dumps(tax, indent=2, default=str)}
```

## Import + mapping

```json
{json.dumps({k: v for k, v in imp.items() if k != 'outcomes'}, indent=2, default=str)}
```

```json
{json.dumps(mapped, indent=2, default=str)}
```

## Post verification

- CH03 DRAFT: **{post['snapshot']['ch03']['DRAFT']}**
- IN_REVIEW / APPROVED / PUBLISHED: **0 / 0 / 0**
- Concept mapped: **{post['mapped']}/100**
- NCERT NOT_VERIFIED: **{post['not_verified']}**
- Student visibility: **{post['student_ch03_visible']}**
- Practice pool: **{post['practice_ch03_hits']}**
- Content fingerprint mismatches: `{post['mismatches']}`
- Plant Kingdom: **{post['plant_kingdom']}**
- Regression CH01 / CH02 / Physics: **{post['snapshot']['ch01_PUBLISHED']} / {post['snapshot']['ch02_PUBLISHED']} / {post['snapshot']['physics_DRAFT']}**
- Q000001: retained repaired food-algae stem (Porphyra / Laminaria / Sargassum)

## Rollback test

```json
{json.dumps(rollback, indent=2, default=str)}
```

## Idempotency

```json
{json.dumps(idem, indent=2, default=str)}
```

Second run: taxonomy creates **0**, question creates **0**.

## Mandatory stop

TAXONOMY MIGRATION COMPLETE.  
DRAFT IMPORT COMPLETE.  
ECAEP NOT EXECUTED.  
NCERT CERTIFICATION NOT EXECUTED.  
PUBLICATION NOT EXECUTED.  
MANDATORY STOP REACHED.
""",
        encoding="utf-8",
        newline="\n",
    )


async def main(commit: bool, dry_run_only: bool) -> dict:
    plan = load_plan()
    async with AsyncSessionLocal() as session:
        pre = await preflight(session)

        if dry_run_only and not commit:
            tax = await migrate_taxonomy(session, plan, commit=False)
            # after rollback, import dry-run on clean session state
            async with AsyncSessionLocal() as s2:
                imp = await import_draft(s2, commit=False)
            return {
                "mode": "dry_run_only",
                "preflight": {k: v for k, v in pre.items()},
                "taxonomy": tax,
                "import": {k: v for k, v in imp.items() if k != "outcomes"},
            }

        # COMMIT PATH
        tax = await migrate_taxonomy(session, plan, commit=True)

    async with AsyncSessionLocal() as s2:
        rb = await test_rollback(s2, plan)
        await s2.rollback()
        if not rb["ok"]:
            raise Stop("rollback_test", True, rb)

    async with AsyncSessionLocal() as s3:
        imp = await import_draft(s3, commit=True)

    async with AsyncSessionLocal() as s4:
        mapped = await map_concepts(s4, plan)
        await s4.commit()
        post = await verify_post(s4, plan)
        if not post["ok"]:
            raise Stop("post_verify", [], post["issues"])

    # idempotency second run
    async with AsyncSessionLocal() as s5:
        tax2 = await migrate_taxonomy(s5, plan, commit=True)
        imp2 = await import_draft(s5, commit=True)
        map2 = await map_concepts(s5, plan)
        await s5.commit()
        post2 = await verify_post(s5, plan)

    idem = {
        "taxonomy": {
            "second_created": tax2["created"],
            "ok": tax2["created"] == {"topics": 0, "concepts": 0},
        },
        "import": {
            "second_created": imp2.get("created_count"),
            "second_already_exists": imp2.get("already_exists"),
            "second_map_updated": map2["updated"],
            "ok": imp2.get("created_count", 0) == 0
            and map2["updated"] == 0
            and post2["ok"],
        },
    }
    if not idem["taxonomy"]["ok"] or not idem["import"]["ok"]:
        raise Stop("idempotency", True, idem)

    write_report(
        plan=plan,
        pre=pre,
        tax=tax,
        imp=imp,
        mapped=mapped,
        post=post,
        rollback=rb,
        idem=idem,
    )
    return {
        "verdict": "GREEN — BIO11-CH03-B001 TAXONOMY MIGRATION + DRAFT IMPORT COMPLETE",
        "taxonomy_created": tax["created"],
        "import_created": imp.get("created_count"),
        "mapped": mapped,
        "final": {
            "plant_kingdom": post["plant_kingdom"],
            "ch03_DRAFT": post["snapshot"]["ch03"]["DRAFT"],
            "mapped": post["mapped"],
            "student_visible": post["student_ch03_visible"],
            "ncert_NOT_VERIFIED": post["not_verified"],
            "ch01_PUBLISHED": post["snapshot"]["ch01_PUBLISHED"],
            "ch02_PUBLISHED": post["snapshot"]["ch02_PUBLISHED"],
            "physics_DRAFT": post["snapshot"]["physics_DRAFT"],
        },
        "rollback": rb,
        "idempotency": idem,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run-only", action="store_true")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    if not args.commit and not args.dry_run_only:
        args.dry_run_only = True
    try:
        result = asyncio.run(main(commit=args.commit, dry_run_only=args.dry_run_only))
        print(json.dumps(result, indent=2, default=str))
    except Stop as exc:
        print(json.dumps({"verdict": "RED — CH03 MIGRATION/IMPORT BLOCKED", "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
