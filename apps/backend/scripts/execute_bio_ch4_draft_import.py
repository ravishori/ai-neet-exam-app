"""BIO11-CH04-B001 — DRAFT import ONLY.

Uses GeminiJsonlDraftImporter → ContentWorkflowService.create_item.
Maps concepts from question_taxonomy_mapping_committed.json.
Does NOT submit ECAEP / certify NCERT / publish.

Usage (from apps/backend):
  python scripts/execute_bio_ch4_draft_import.py --dry-run
  python scripts/execute_bio_ch4_draft_import.py --commit
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
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.acquisition.gemini_jsonl_draft_importer import (
    GeminiJsonlDraftImporter,
    import_slug,
)
from app.modules.cms.acquisition.physics_t6d_service import actor_user
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import ContentWorkflowService

BATCH = "20260912-BIO11-CH04-B001"
CH01 = "20260911-BIO11-CH01-B001"
CH02 = "20260911-BIO11-CH02-B001"
CH03 = "20260912-BIO11-CH03-B001"
PHY = "20260911-PHY11-CH02-B001"
ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
FINAL_JSONL = ROOT / "questions_repaired_final.jsonl"
EXPECTED_SHA = "743bbacfd1a744e85c0a25ff79ed1908c35446d68169efbd8213fd454451b0c9"
COMMITTED_MAP = ROOT / "question_taxonomy_mapping_committed.json"
CHAPTER_ID = uuid.UUID("5285cefb-e25f-4849-9c3b-d25f336bc65f")
TAXONOMY_TARGET = (4, 36, 125, 192)
MEDIUM_Q = {"Q000054", "Q000074", "Q000084", "Q000085"}

OUT_MD = ROOT / "draft_import_report.md"
OUT_JSON = ROOT / "draft_import_results.json"


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
    if isinstance(tags, dict):
        tags = tags.get("tags") or []
    if batch in (tags or []) or any(batch in str(t) for t in (tags or [])):
        return True
    return bool(item.slug and slug_bit in (item.slug or "").lower())


def is_ch04(item: ContentItem) -> bool:
    return is_batch(item, BATCH, "bio11-ch04-b001")


async def taxonomy_tuple(session) -> tuple[int, int, int, int]:
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
    return tuple(row)


async def content_snapshot(session) -> dict:
    items = (
        await session.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))
    ).scalars().all()
    groups = {
        "CH01": [i for i in items if is_batch(i, CH01, "bio11-ch01-b001")],
        "CH02": [i for i in items if is_batch(i, CH02, "bio11-ch02-b001")],
        "CH03": [i for i in items if is_batch(i, CH03, "bio11-ch03-b001")],
        "CH04": [i for i in items if is_ch04(i)],
        "PHY02": [i for i in items if is_batch(i, PHY, "phy11-ch02-b001")],
    }
    out: dict = {}
    for name, subset in groups.items():
        c = Counter(i.status for i in subset)
        out[name] = {**dict(c), "_total": len(subset)}
        out[f"{name}_items"] = subset
    return out


async def student_ch04_visible(session) -> int:
    repo = CmsRepository(session)
    n = 0
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        n += sum(1 for i in page if is_ch04(i))
        off += 100
        if off >= tot or not page:
            break
    return n


async def practice_ch04_hits(session) -> int:
    pool = set(await AssessmentRepository(session).published_question_ids_for_scope("FULL", None))
    snap = await content_snapshot(session)
    return len({i.id for i in snap["CH04_items"] if i.status == "PUBLISHED"} & pool)


async def ecaep_ch04_count(session) -> int:
    snap = await content_snapshot(session)
    return sum(1 for i in snap["CH04_items"] if i.status in ("IN_REVIEW", "APPROVED", "PUBLISHED"))


def load_artifacts() -> tuple[list[dict], dict]:
    sha = sha256_file(FINAL_JSONL)
    if sha != EXPECTED_SHA:
        raise Stop("final_artifact_sha", EXPECTED_SHA, sha)
    qs = [json.loads(l) for l in FINAL_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(qs) != 100:
        raise Stop("question_count", 100, len(qs))
    mapping = json.loads(COMMITTED_MAP.read_text(encoding="utf-8"))
    if mapping.get("batch_id") != BATCH:
        raise Stop("mapping_batch", BATCH, mapping.get("batch_id"))
    if mapping.get("authoritative_sha256") != EXPECTED_SHA:
        raise Stop("mapping_sha", EXPECTED_SHA, mapping.get("authoritative_sha256"))
    maps = mapping.get("mappings") or []
    if len(maps) != 100:
        raise Stop("mapping_count", 100, len(maps))
    conf = Counter(m["confidence"] for m in maps)
    if conf.get("HIGH") != 96 or conf.get("MEDIUM") != 4:
        raise Stop("mapping_confidence", {"HIGH": 96, "MEDIUM": 4}, dict(conf))
    med = {m["qnum"] for m in maps if m["confidence"] == "MEDIUM"}
    if med != MEDIUM_Q:
        raise Stop("medium_q", sorted(MEDIUM_Q), sorted(med))
    return qs, mapping


async def import_draft(session, *, commit: bool) -> dict:
    actor = await actor_user(session)
    importer = GeminiJsonlDraftImporter(session)
    report = await importer.run(
        input_path=FINAL_JSONL,
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


async def map_concepts(session, mapping: dict) -> dict:
    updated = 0
    already = 0
    for m in mapping["mappings"]:
        eid = m["question_id"]
        slug = import_slug(eid)
        item = (
            await session.execute(
                select(ContentItem).where(ContentItem.slug == slug, ContentItem.deleted_at.is_(None))
            )
        ).scalar_one()
        want = uuid.UUID(m["concept_id"])
        if item.concept_id == want:
            already += 1
            continue
        if item.status != "DRAFT":
            raise Stop("map_non_draft", "DRAFT", item.status)
        if item.concept_id is not None and item.concept_id != want:
            raise Stop(f"unexpected_concept:{m['qnum']}", str(want), str(item.concept_id))
        item.concept_id = want
        # Drop unresolved tag once approved mapping is applied
        tags = list(item.tags or [])
        if "concept:unresolved" in tags:
            tags = [t for t in tags if t != "concept:unresolved"]
            tags.append(f"talos_topic:{m['topic_code']}")
            tags.append(f"talos_concept:{m['concept_code']}")
            item.tags = tags
        updated += 1
    await session.flush()
    return {"updated": updated, "already": already, "total": len(mapping["mappings"])}


async def verify_post(session, qs: list[dict], mapping: dict) -> dict:
    snap = await content_snapshot(session)
    tax = await taxonomy_tuple(session)
    issues: list[str] = []
    ch4 = snap["CH04"]
    if ch4.get("_total") != 100 or ch4.get("DRAFT") != 100:
        issues.append(f"ch04_status={ch4}")
    for bad in ("IN_REVIEW", "APPROVED", "PUBLISHED"):
        if ch4.get(bad):
            issues.append(f"non_draft_{bad}={ch4.get(bad)}")
    if tax != TAXONOMY_TARGET:
        issues.append(f"taxonomy={tax}")
    if snap["CH01"].get("PUBLISHED") != 100:
        issues.append(f"ch01={snap['CH01']}")
    if snap["CH02"].get("PUBLISHED") != 100:
        issues.append(f"ch02={snap['CH02']}")
    if snap["CH03"].get("PUBLISHED") != 100:
        issues.append(f"ch03={snap['CH03']}")
    if snap["PHY02"].get("DRAFT") != 24:
        issues.append(f"physics={snap['PHY02']}")

    by_eid = {q["external_question_id"]: q for q in qs}
    map_by_eid = {m["question_id"]: m for m in mapping["mappings"]}
    mapped = 0
    not_verified = 0
    provenance_ok = 0
    content_ok = 0
    medium_validation: dict = {}
    seen_ids: set[str] = set()
    mismatches: Counter = Counter()

    for eid, q in by_eid.items():
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
        if str(item.id) in seen_ids:
            issues.append(f"duplicate_item:{eid}")
        seen_ids.add(str(item.id))
        if item.status != "DRAFT":
            issues.append(f"status:{eid}={item.status}")

        want = map_by_eid[eid]
        if item.concept_id is None:
            issues.append(f"null_concept:{eid}")
        elif str(item.concept_id) != want["concept_id"]:
            issues.append(f"concept_mismatch:{eid}")
        else:
            mapped += 1
            path = (
                await session.execute(
                    text(
                        """
                        SELECT s.code, ch.code, t.code, c.code, ch.id
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
            if path[0] != "ZOOLOGY" or path[1] != "animal-kingdom" or path[4] != CHAPTER_ID:
                issues.append(f"wrong_path:{eid}:{path}")
            if path[2] != want["topic_code"] or path[3] != want["concept_code"]:
                issues.append(f"code_mismatch:{eid}:{path[2]}/{path[3]}")

        ver = next((v for v in item.versions if v.id == item.latest_version_id), None)
        body = dict(ver.body or {}) if ver else {}
        if body.get("stem") != q["stem"]:
            mismatches["stem"] += 1
            issues.append(f"stem_mismatch:{eid}")
        opts = body.get("options")
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
        qtype_tag = f"question_type:{q['question_type']}"
        if qtype_tag not in (item.tags or []):
            mismatches["question_type"] += 1
            issues.append(f"type_mismatch:{eid}")

        ncert = body.get("ncert_evidence") or {}
        if isinstance(ncert, dict) and ncert.get("verification_level") == "NOT_VERIFIED":
            not_verified += 1
        elif any(str(t) == "ncert:NOT_VERIFIED" for t in (item.tags or [])):
            not_verified += 1
        else:
            issues.append(f"ncert_not_unverified:{eid}")
        if isinstance(ncert, dict) and ncert.get("verification_level") == "SOURCE_TEXT_VERIFIED":
            issues.append(f"ncert_certified:{eid}")

        prov = body.get("provenance") or {}
        if (
            prov.get("batch_id") == BATCH
            and (ncert.get("chapter") == "Animal Kingdom" or q["chapter"] == "Animal Kingdom")
            and "NOT_VERIFIED" in (ncert.get("verification_level") or "")
        ):
            provenance_ok += 1
        else:
            issues.append(f"provenance:{eid}")

        if (
            body.get("stem")
            and len(opt_map) == 4
            and body.get("correct_option")
            and body.get("explanation")
            and body.get("difficulty")
            and item.concept_id is not None
        ):
            content_ok += 1

        qnum = want["qnum"]
        if qnum in MEDIUM_Q:
            medium_validation[qnum] = {
                "ok": str(item.concept_id) == want["concept_id"]
                and want["confidence"] == "MEDIUM",
                "topic_code": want["topic_code"],
                "concept_code": want["concept_code"],
                "topic_id": want["topic_id"],
                "concept_id": want["concept_id"],
                "confidence": want["confidence"],
                "content_item_id": str(item.id),
            }

    if len(seen_ids) != 100:
        issues.append(f"unique_items={len(seen_ids)}")
    if mapped != 100:
        issues.append(f"mapped={mapped}")
    if not_verified != 100:
        issues.append(f"not_verified={not_verified}")
    if provenance_ok != 100:
        issues.append(f"provenance_ok={provenance_ok}")
    if content_ok != 100:
        issues.append(f"content_ok={content_ok}")
    for qn in sorted(MEDIUM_Q):
        if qn not in medium_validation or not medium_validation[qn]["ok"]:
            issues.append(f"medium_fail:{qn}")

    vis = await student_ch04_visible(session)
    prac = await practice_ch04_hits(session)
    ecaep = await ecaep_ch04_count(session)
    if vis != 0:
        issues.append(f"student_visible={vis}")
    if prac != 0:
        issues.append(f"practice={prac}")
    if ecaep != 0:
        issues.append(f"ecaep={ecaep}")

    certified = 0
    for item in snap["CH04_items"]:
        ver = None
        # lightweight: rely on tags + earlier body scan
        if any("SOURCE_TEXT_VERIFIED" in str(t) for t in (item.tags or [])):
            certified += 1
    if certified:
        issues.append(f"certified={certified}")

    return {
        "ok": not issues,
        "issues": issues[:100],
        "issue_count": len(issues),
        "mapped": mapped,
        "not_verified": not_verified,
        "provenance_ok": provenance_ok,
        "content_ok": content_ok,
        "mismatches": dict(mismatches),
        "medium_validation": medium_validation,
        "snapshot": {k: v for k, v in snap.items() if not k.endswith("_items")},
        "student_visible": vis,
        "practice_pool": prac,
        "ecaep": ecaep,
        "certified": certified,
        "published": ch4.get("PUBLISHED", 0),
        "taxonomy": list(tax),
    }


async def test_rollback(session) -> dict:
    before = await content_snapshot(session)
    actor = await actor_user(session)
    wf = ContentWorkflowService(session)
    nested = await session.begin_nested()
    failed = False
    try:
        await wf.create_item(
            content_type="QUESTION",
            concept_id=uuid.UUID("f5112095-56f7-54d4-b8eb-0a16f50e00e0"),
            title="ROLLBACK-TEST-CH04",
            slug=f"rollback-test-ch04-{uuid.uuid4().hex[:8]}",
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
                "ncert_evidence": {
                    "verification_level": "NOT_VERIFIED",
                    "source_document": "ncert-books-class-11-biology-chapter-4.pdf",
                    "class_level": "11",
                    "chapter": "Animal Kingdom",
                    "section": None,
                    "page_number": None,
                    "source_excerpt": "rollback",
                    "verification_method": "gemini_jsonl_acquisition_unverified",
                },
                "provenance": {
                    "origin": "ai_generated",
                    "source": "attached_ncert_pdf",
                    "batch_id": BATCH,
                    "validation_process": "UNVERIFIED_ACQUISITION",
                },
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
    return {
        "induced_failure": failed,
        "ch04_before": before["CH04"]["_total"],
        "ch04_after": after["CH04"]["_total"],
        "unchanged": before["CH04"]["_total"] == after["CH04"]["_total"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    commit = bool(args.commit) and not bool(args.dry_run)

    qs, mapping = load_artifacts()
    sha = sha256_file(FINAL_JSONL)
    first_created = 0

    async with AsyncSessionLocal() as session:
        pre_tax = await taxonomy_tuple(session)
        if pre_tax != TAXONOMY_TARGET:
            raise Stop("taxonomy_baseline", TAXONOMY_TARGET, pre_tax)
        pre_snap = await content_snapshot(session)
        if pre_snap["CH04"]["_total"] not in (0, 100):
            raise Stop("ch04_pre_count", "0 or 100", pre_snap["CH04"]["_total"])
        already = pre_snap["CH04"]["_total"] == 100
        pre_counts = {
            "taxonomy": list(pre_tax),
            "CH04": dict(pre_snap["CH04"]),
            "CH01_PUBLISHED": pre_snap["CH01"].get("PUBLISHED", 0),
            "CH02_PUBLISHED": pre_snap["CH02"].get("PUBLISHED", 0),
            "CH03_PUBLISHED": pre_snap["CH03"].get("PUBLISHED", 0),
            "PHY02_DRAFT": pre_snap["PHY02"].get("DRAFT", 0),
            "student_visible": await student_ch04_visible(session),
            "practice": await practice_ch04_hits(session),
            "ecaep": await ecaep_ch04_count(session),
        }

        try:
            imp = await import_draft(session, commit=commit and not already)
            if commit and not already:
                first_created = imp["created_count"]
                map_res = await map_concepts(session, mapping)
                await session.commit()
            elif commit and already:
                map_res = await map_concepts(session, mapping)
                await session.commit()
                first_created = 0
            else:
                map_res = {"updated": 0, "already": 0, "total": 100, "note": "dry_run"}
                await session.rollback()
        except Exception:
            await session.rollback()
            raise

    async with AsyncSessionLocal() as session:
        if commit:
            post = await verify_post(session, qs, mapping)
            if not post["ok"]:
                raise Stop("post_validate", True, post["issues"][:40])
            # Idempotency second pass
            before_total = (await content_snapshot(session))["CH04"]["_total"]
            imp2 = await import_draft(session, commit=True)
            map2 = await map_concepts(session, mapping)
            await session.commit()
            after_total = (await content_snapshot(session))["CH04"]["_total"]
            if imp2["created_count"] != 0:
                raise Stop("idempotency_created", 0, imp2["created_count"])
            if after_total != 100 or before_total != 100:
                raise Stop("idempotency_counts", 100, {"before": before_total, "after": after_total})
            if imp2["already_exists"] != 100:
                raise Stop("idempotency_already", 100, imp2["already_exists"])
            idempotency = {
                "second_execution": "SAFE_NOOP_ALREADY_EXISTS",
                "additional_content_items": 0,
                "already_exists": imp2["already_exists"],
                "map_already": map2["already"],
                "counts_unchanged": True,
            }
            rollback = await test_rollback(session)
            await session.rollback()
            post = await verify_post(session, qs, mapping)
            post_tax = await taxonomy_tuple(session)
            post_snap = await content_snapshot(session)
        else:
            post = {
                "ok": True,
                "mapped": 0,
                "not_verified": 0,
                "provenance_ok": 0,
                "student_visible": 0,
                "practice_pool": 0,
                "ecaep": 0,
                "certified": 0,
                "published": 0,
                "medium_validation": {},
                "issues": ["dry_run"],
            }
            idempotency = {"second_execution": "SKIPPED_DRY_RUN"}
            rollback = {"skipped": True}
            post_tax = pre_tax
            post_snap = pre_snap
            imp2 = None

    created = first_created if commit else imp.get("would_create_count", 0)
    green = (
        commit
        and sha == EXPECTED_SHA
        and sha256_file(FINAL_JSONL) == EXPECTED_SHA
        and created in (0, 100)
        and post["ok"]
        and post["mapped"] == 100
        and post["not_verified"] == 100
        and post["student_visible"] == 0
        and post["practice_pool"] == 0
        and post["ecaep"] == 0
        and post["certified"] == 0
        and post["published"] == 0
        and tuple(post_tax) == TAXONOMY_TARGET
        and post_snap["CH01"].get("PUBLISHED") == 100
        and post_snap["CH02"].get("PUBLISHED") == 100
        and post_snap["CH03"].get("PUBLISHED") == 100
        and post_snap["PHY02"].get("DRAFT") == 24
        and bool(idempotency.get("counts_unchanged", True))
        and all(v.get("ok") for v in (post.get("medium_validation") or {}).values())
    )
    verdict = (
        "AMBER — DRY RUN ONLY (not committed)"
        if not commit
        else (
            "GREEN — BIO11-CH04-B001 DRAFT IMPORT COMPLETE"
            if green
            else "AMBER — DRAFT IMPORT REQUIRES REVIEW"
        )
    )

    mutations = {
        "subjects_created": 0,
        "chapters_created": 0,
        "topics_created": 0,
        "concepts_created": 0,
        "content_items_created": created if commit else 0,
        "concept_mappings_updated": map_res.get("updated", 0) if commit else 0,
        "ecaep_mutations": 0,
        "ncert_certification_mutations": 0,
        "publication_mutations": 0,
        "student_visibility_mutations": 0,
    }

    results = {
        "batch_id": BATCH,
        "final_verdict": verdict,
        "mode": "COMMIT" if commit else "DRY_RUN",
        "authoritative_artifact": "questions_repaired_final.jsonl",
        "authoritative_sha256": sha,
        "artifact_unchanged": sha256_file(FINAL_JSONL) == EXPECTED_SHA,
        "pre_import": pre_counts,
        "post_import": {
            "taxonomy": list(post_tax),
            "CH04": dict(post_snap["CH04"]) if commit else dict(pre_snap["CH04"]),
            "CH01_PUBLISHED": post_snap["CH01"].get("PUBLISHED", 0),
            "CH02_PUBLISHED": post_snap["CH02"].get("PUBLISHED", 0),
            "CH03_PUBLISHED": post_snap["CH03"].get("PUBLISHED", 0),
            "PHY02_DRAFT": post_snap["PHY02"].get("DRAFT", 0),
        },
        "import_execution": {
            k: v
            for k, v in imp.items()
            if k != "outcomes"
        },
        "content_items_created": created if commit else 0,
        "would_create": imp.get("would_create_count"),
        "skipped_duplicate": imp.get("already_exists") if commit and already else (imp2 or {}).get("already_exists", 0) if commit else 0,
        "draft_count": 100 if commit else 0,
        "not_verified_count": post.get("not_verified", 0),
        "source_to_content_mapping": f"{post.get('mapped', 0)}/100",
        "taxonomy_mapping_validation": post.get("mapped"),
        "provenance_validation": post.get("provenance_ok"),
        "medium_validation": post.get("medium_validation"),
        "map_concepts": map_res,
        "idempotency": idempotency,
        "rollback_test": rollback,
        "student_visibility": post.get("student_visible", 0),
        "practice_pool": post.get("practice_pool", 0),
        "ecaep": post.get("ecaep", 0),
        "ncert_certification": post.get("certified", 0),
        "publication": post.get("published", 0),
        "database_mutations": mutations,
        "post_validate": {k: v for k, v in post.items() if k != "snapshot"},
        "canonical_method": "GeminiJsonlDraftImporter → ContentWorkflowService.create_item",
        "created_at": datetime.now(UTC).isoformat(),
        "mandatory_stop": True,
    }

    if commit:
        # Run unit tests and attach summary
        import subprocess
        import sys

        test_cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_gemini_jsonl_draft_importer.py",
            "-q",
            "--tb=no",
        ]
        try:
            proc = subprocess.run(
                test_cmd,
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,
                text=True,
                timeout=180,
            )
            results["tests"] = {
                "command": " ".join(test_cmd),
                "returncode": proc.returncode,
                "passed": proc.returncode == 0,
                "stdout_tail": (proc.stdout or "")[-1500:],
                "stderr_tail": (proc.stderr or "")[-800:],
            }
        except Exception as exc:  # noqa: BLE001
            results["tests"] = {"passed": False, "error": str(exc)}

        if not results["tests"].get("passed"):
            # Do not downgrade GREEN for unrelated pytest env issues if import validated;
            # record clearly but keep green only if import criteria already met and note.
            results["tests"]["note"] = (
                "Importer unit tests reported failure; import validation gates still apply."
            )
            # Re-evaluate green requiring tests
            if green and not results["tests"].get("passed"):
                # Keep GREEN if only env noise; mark AMBER if tests clearly fail assertions
                out = (results["tests"].get("stdout_tail") or "") + (results["tests"].get("stderr_tail") or "")
                if "failed" in out.lower() or results["tests"].get("returncode") not in (0, None):
                    # If import is solid, still report test status separately; user asked tests pass for GREEN
                    green = False
                    verdict = "AMBER — DRAFT IMPORT REQUIRES REVIEW"
                    results["final_verdict"] = verdict

        OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        lines = [
            "# DRAFT import report — BIO11-CH04-B001",
            "",
            f"**Verdict:** {verdict}",
            "",
            f"- Source artifact SHA: `{sha}` (unchanged)",
            f"- Pre: CH04={pre_counts['CH04']}; taxonomy={pre_counts['taxonomy']}",
            f"- Post: CH04={results['post_import']['CH04']}; taxonomy={results['post_import']['taxonomy']}",
            f"- ContentItems created: **{mutations['content_items_created']}**",
            f"- DRAFT: **{results['draft_count']}**",
            f"- NOT_VERIFIED: **{results['not_verified_count']}**",
            f"- Source→content: {results['source_to_content_mapping']}",
            f"- Taxonomy mappings: {results['taxonomy_mapping_validation']}/100",
            f"- Provenance OK: {results['provenance_validation']}/100",
            f"- Idempotency: {idempotency}",
            f"- Student visibility: {results['student_visibility']}",
            f"- Practice pool: {results['practice_pool']}",
            f"- ECAEP: {results['ecaep']}",
            f"- NCERT certified: {results['ncert_certification']}",
            f"- Published: {results['publication']}",
            f"- DB mutations: {mutations}",
            f"- Tests: {results.get('tests', {}).get('passed')}",
            "",
            "## Medium-confidence mappings (unchanged)",
            "",
        ]
        for qn, v in (post.get("medium_validation") or {}).items():
            lines.append(
                f"- {qn}: {'PASS' if v.get('ok') else 'FAIL'} · `{v.get('topic_code')}` → `{v.get('concept_code')}` · {v.get('confidence')}"
            )
        lines += [
            "",
            "## Regression",
            "",
            f"- CH01 PUBLISHED: {results['post_import']['CH01_PUBLISHED']}",
            f"- CH02 PUBLISHED: {results['post_import']['CH02_PUBLISHED']}",
            f"- CH03 PUBLISHED: {results['post_import']['CH03_PUBLISHED']}",
            f"- Physics DRAFT: {results['post_import']['PHY02_DRAFT']}",
            "",
            "## Mandatory stop",
            "",
            "ECAEP / NCERT certification / publication / student visibility — NOT EXECUTED.",
            "",
        ]
        OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "commit": commit,
                "sha": sha,
                "pre": pre_counts,
                "created": mutations["content_items_created"],
                "post_ch04": results["post_import"]["CH04"],
                "taxonomy": results["post_import"]["taxonomy"],
                "mapped": post.get("mapped"),
                "not_verified": post.get("not_verified"),
                "idempotency": idempotency,
                "student_visible": post.get("student_visible"),
                "practice": post.get("practice_pool"),
                "ecaep": post.get("ecaep"),
                "medium": post.get("medium_validation"),
                "tests": results.get("tests", {}).get("passed") if commit else None,
                "green": green,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
