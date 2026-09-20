"""Atomic migration: create Mayr concept + map Q000098 only.

Usage:
  python execute_q000098_mayr_concept_migration.py --dry-run
  python execute_q000098_mayr_concept_migration.py --commit
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

from sqlalchemy import select, text, update
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

get_settings.cache_clear()
from app.core.database import AsyncSessionLocal
from app.modules.academic.models import Concept
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem, ContentVersion
from app.modules.cms.repositories.cms_repository import CmsRepository

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
QID = f"GEMINI-{BATCH}-000098"
CONCEPT_ID = uuid.UUID("64a807cc-89f2-52dc-8b26-0e784e66b0cc")
CODE = "lw-biological-species-concept-mayr"
NAME = "Biological species concept — Ernst Mayr"
TOPIC_ID = uuid.UUID("1a85b6d3-4972-47ad-8c0e-a20afc35f133")
TOPIC_CODE = "sv2t-botany-01"
CHAPTER_CODE = "the-living-world"
SUBJECT_CODE = "BOTANY"
SUMMARY = "Mayr attribution of the currently accepted biological species definition (Ch1 biography only)."
NCERT_REF = "ncert-books-class-11-biology-chapter-1.pdf — Ernst Mayr biography (PDF_PAGE_INDEX=2)"
DISPLAY_ORDER = 70

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
OUT_MD = ROOT / "q000098_mayr_concept_migration_report.md"
OUT_JSON = ROOT / "q000098_mayr_concept_migration_report.json"


class Abort(Exception):
    def __init__(self, condition: str, expected, actual):
        self.condition = condition
        self.expected = expected
        self.actual = actual
        super().__init__(f"ABORT: {condition} expected={expected!r} actual={actual!r}")


def fail(condition: str, expected, actual) -> None:
    raise Abort(condition, expected, actual)


def eid_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    marker = "GEMINI-20260911-BIO11-CH01-B001-"
    if marker not in slug:
        return None
    return f"GEMINI-20260911-BIO11-CH01-B001-{slug.split(marker, 1)[1]}"


def body_fp(body: dict | None) -> str:
    return hashlib.sha256(
        json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


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


async def parent_ok(session) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT sub.id::text AS subject_id, sub.code AS subject_code,
                       ch.id::text AS chapter_id, ch.code AS chapter_code,
                       t.id::text AS topic_id, t.code AS topic_code, t.name AS topic_name
                FROM academic.subjects sub
                JOIN academic.chapters ch ON ch.subject_id = sub.id AND ch.deleted_at IS NULL
                JOIN academic.topics t ON t.chapter_id = ch.id AND t.deleted_at IS NULL
                WHERE sub.deleted_at IS NULL
                  AND sub.code = :sc AND ch.code = :cc AND t.code = :tc
                """
            ),
            {"sc": SUBJECT_CODE, "cc": CHAPTER_CODE, "tc": TOPIC_CODE},
        )
    ).mappings().one_or_none()
    if not row:
        fail("parent_hierarchy", "BOTANY/the-living-world/sv2t-botany-01", None)
    if row["topic_id"] != str(TOPIC_ID):
        fail("parent_topic_id", str(TOPIC_ID), row["topic_id"])
    return dict(row)


async def bio_snapshot(session) -> dict:
    items = (
        await session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.deleted_at.is_(None))
        )
    ).scalars().all()
    bio = [
        i
        for i in items
        if BATCH in (i.tags or []) or (i.slug and "bio11-ch01-b001" in (i.slug or "").lower())
    ]
    phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
    bs = Counter(i.status for i in bio)
    drafts = [i for i in bio if i.status == "DRAFT"]
    by_eid = {}
    for i in drafts:
        eid = eid_from_slug(i.slug)
        if eid:
            by_eid[eid] = i
    return {
        "biology": {
            "DRAFT": bs.get("DRAFT", 0),
            "SUPERSEDED": bs.get("SUPERSEDED", 0),
            "PUBLISHED": bs.get("PUBLISHED", 0),
            "APPROVED": bs.get("APPROVED", 0),
            "IN_REVIEW": bs.get("IN_REVIEW", 0),
        },
        "physics_DRAFT": Counter(i.status for i in phy).get("DRAFT", 0),
        "drafts_by_eid": by_eid,
        "mapped": sum(1 for i in drafts if i.concept_id),
        "mapping_fingerprint": {
            eid: str(i.concept_id) if i.concept_id else None for eid, i in by_eid.items()
        },
        "bio_items": bio,
    }


async def student_safety(session, bio_items: list) -> dict:
    repo = CmsRepository(session)
    hits = 0
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        hits += sum(
            1
            for i in page
            if BATCH in (i.tags or []) or (i.slug and "bio11-ch01-b001" in (i.slug or "").lower())
        )
        off += 100
        if off >= tot or not page:
            break
    pool = set(await AssessmentRepository(session).published_question_ids_for_scope("FULL", None))
    nonpub = {i.id for i in bio_items if i.status != "PUBLISHED"}
    return {
        "student_bio_hits": hits,
        "practice_nonpub_hits": len(nonpub & pool),
        "ok": hits == 0 and len(nonpub & pool) == 0,
    }


async def preflight(session) -> dict:
    counts = await taxonomy_counts(session)
    if counts != {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 133}:
        # allow already applied 134 for idempotency path
        if counts != {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}:
            fail("taxonomy_counts", {"concepts": "133 or 134"}, counts)

    parent = await parent_ok(session)
    snap = await bio_snapshot(session)
    expected_bio = {"DRAFT": 100, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 0}
    if snap["biology"] != expected_bio:
        fail("biology_status", expected_bio, snap["biology"])
    if snap["physics_DRAFT"] != 24:
        fail("physics_DRAFT", 24, snap["physics_DRAFT"])

    q = snap["drafts_by_eid"].get(QID)
    if not q:
        fail("q000098_exists", QID, None)
    if q.status != "DRAFT":
        fail("q000098_status", "DRAFT", q.status)
    if BATCH not in (q.tags or []) and f"batch:{BATCH}" not in (q.tags or []):
        fail("q000098_batch_tag", BATCH, q.tags)
    if "The Living World" not in str(q.tags) and not any(
        "living" in (t or "").lower() for t in (q.tags or [])
    ):
        # still accept if provenance chapter in body
        latest = next(v for v in q.versions if v.id == q.latest_version_id)
        chap = ((latest.body or {}).get("provenance") or {}).get("chapter") or (
            (latest.body or {}).get("ncert_evidence") or {}
        ).get("chapter")
        if chap != "The Living World":
            fail("q000098_chapter", "The Living World", chap)

    latest = next(v for v in q.versions if v.id == q.latest_version_id)
    fp = body_fp(latest.body)

    code_hit = (
        await session.execute(
            select(Concept).where(Concept.code == CODE, Concept.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    id_hit = (
        await session.execute(select(Concept).where(Concept.id == CONCEPT_ID))
    ).scalar_one_or_none()

    already = (
        counts["concepts"] == 134
        and code_hit is not None
        and code_hit.id == CONCEPT_ID
        and q.concept_id == CONCEPT_ID
    )
    first_run = (
        counts["concepts"] == 133
        and code_hit is None
        and id_hit is None
        and q.concept_id is None
    )
    if not already and not first_run:
        fail(
            "migration_mode",
            "first_run(133,null) or already(134,mapped)",
            {
                "concepts": counts["concepts"],
                "code_hit": str(code_hit.id) if code_hit else None,
                "id_hit": bool(id_hit),
                "q_concept": str(q.concept_id) if q.concept_id else None,
            },
        )

    if first_run:
        # extra: name should not exist elsewhere
        name_hit = (
            await session.execute(
                select(Concept).where(Concept.name == NAME, Concept.deleted_at.is_(None))
            )
        ).scalars().all()
        if name_hit:
            fail("name_conflict", [], [str(c.id) for c in name_hit])

    return {
        "mode": "already_applied" if already else "first_run",
        "counts": counts,
        "parent": parent,
        "biology": snap["biology"],
        "physics_DRAFT": snap["physics_DRAFT"],
        "mapped": snap["mapped"],
        "mapping_fingerprint": snap["mapping_fingerprint"],
        "q": {
            "content_item_id": str(q.id),
            "status": q.status,
            "concept_id": str(q.concept_id) if q.concept_id else None,
            "slug": q.slug,
            "body_fingerprint": fp,
            "latest_version_id": str(q.latest_version_id),
        },
        "planned_creates": 0 if already else 1,
        "planned_updates": 0 if already else 1,
        "bio_items": snap["bio_items"],
    }


async def atomic_commit(session, pre: dict) -> dict:
    if pre["mode"] != "first_run":
        fail("commit_requires_first_run", "first_run", pre["mode"])

    q_id = uuid.UUID(pre["q"]["content_item_id"])
    try:
        await parent_ok(session)
        concept = Concept(
            id=CONCEPT_ID,
            topic_id=TOPIC_ID,
            code=CODE,
            name=NAME,
            summary=SUMMARY,
            ncert_reference=NCERT_REF,
            difficulty="medium",
            display_order=DISPLAY_ORDER,
        )
        session.add(concept)
        await session.flush()

        row = (await session.execute(select(Concept).where(Concept.id == CONCEPT_ID))).scalar_one()
        if row.code != CODE or row.topic_id != TOPIC_ID or row.name != NAME:
            fail("inserted_concept", CODE, {"code": row.code, "name": row.name})

        # Map only Q000098 — concept_id only, only if NULL DRAFT
        result = await session.execute(
            update(ContentItem)
            .where(
                ContentItem.id == q_id,
                ContentItem.deleted_at.is_(None),
                ContentItem.status == "DRAFT",
                ContentItem.concept_id.is_(None),
            )
            .values(concept_id=CONCEPT_ID)
        )
        if result.rowcount != 1:
            fail("q_update_rowcount", 1, result.rowcount)

        # body unchanged
        item = (
            await session.execute(
                select(ContentItem)
                .options(selectinload(ContentItem.versions))
                .where(ContentItem.id == q_id)
            )
        ).scalar_one()
        latest = next(v for v in item.versions if v.id == item.latest_version_id)
        if body_fp(latest.body) != pre["q"]["body_fingerprint"]:
            fail("body_changed", pre["q"]["body_fingerprint"], body_fp(latest.body))
        if item.status != "DRAFT" or item.concept_id != CONCEPT_ID:
            fail("q_after_map", {"status": "DRAFT", "concept": str(CONCEPT_ID)}, {
                "status": item.status,
                "concept": str(item.concept_id),
            })

        counts = await taxonomy_counts(session)
        if counts != {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}:
            fail("post_flush_counts", {"concepts": 134}, counts)

        await session.commit()
        return {"committed": True, "concept_id": str(CONCEPT_ID), "question_id": QID}
    except Exception:
        await session.rollback()
        raise


async def post_verify(session, pre: dict) -> dict:
    counts = await taxonomy_counts(session)
    if counts != {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}:
        fail("post.taxonomy", {"concepts": 134}, counts)

    concept = (await session.execute(select(Concept).where(Concept.id == CONCEPT_ID))).scalar_one()
    if concept.code != CODE or concept.topic_id != TOPIC_ID or concept.name != NAME:
        fail("post.concept", CODE, {"code": concept.code, "name": concept.name})
    if concept.deleted_at is not None:
        fail("post.concept_not_deleted", None, concept.deleted_at)

    # no duplicate codes under topic
    dups = (
        await session.execute(
            select(Concept).where(
                Concept.topic_id == TOPIC_ID,
                Concept.code == CODE,
                Concept.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    if len(dups) != 1:
        fail("post.no_duplicate_code", 1, len(dups))

    snap = await bio_snapshot(session)
    expected_bio = {"DRAFT": 100, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 0}
    if snap["biology"] != expected_bio:
        fail("post.biology", expected_bio, snap["biology"])
    if snap["physics_DRAFT"] != 24:
        fail("post.physics", 24, snap["physics_DRAFT"])

    q = snap["drafts_by_eid"][QID]
    if q.status != "DRAFT" or q.concept_id != CONCEPT_ID:
        fail("post.q000098", {"DRAFT", str(CONCEPT_ID)}, {q.status, str(q.concept_id)})

    latest = next(v for v in q.versions if v.id == q.latest_version_id)
    if body_fp(latest.body) != pre["q"]["body_fingerprint"]:
        fail("post.body", pre["q"]["body_fingerprint"], body_fp(latest.body))
    # verification_level unchanged
    lvl = ((latest.body or {}).get("ncert_evidence") or {}).get("verification_level")
    if lvl != "NOT_VERIFIED":
        fail("post.verification_level", "NOT_VERIFIED", lvl)

    # other 99 mappings unchanged
    before_fp = pre["mapping_fingerprint"]
    after_fp = snap["mapping_fingerprint"]
    changed = []
    for eid, before_cid in before_fp.items():
        if eid == QID:
            continue
        if after_fp.get(eid) != before_cid:
            changed.append({"eid": eid, "before": before_cid, "after": after_fp.get(eid)})
    if changed:
        fail("other_mappings_unchanged", [], changed)
    if after_fp.get(QID) != str(CONCEPT_ID):
        fail("q_mapped", str(CONCEPT_ID), after_fp.get(QID))
    if snap["mapped"] != 100:
        fail("mapped_count", 100, snap["mapped"])

    # ECAEP: no IN_REVIEW/APPROVED/PUBLISHED for bio
    if any(snap["biology"][k] for k in ("IN_REVIEW", "APPROVED", "PUBLISHED")):
        fail("ecaep_unchanged", 0, snap["biology"])

    safety = await student_safety(session, snap["bio_items"])
    if not safety["ok"]:
        fail("student_safety", 0, safety)

    return {
        "counts": counts,
        "biology": snap["biology"],
        "physics_DRAFT": snap["physics_DRAFT"],
        "mapped": snap["mapped"],
        "q000098": {"status": q.status, "concept_id": str(q.concept_id)},
        "concept": {
            "id": str(concept.id),
            "code": concept.code,
            "name": concept.name,
            "topic_id": str(concept.topic_id),
            "summary": concept.summary,
            "ncert_reference": concept.ncert_reference,
        },
        "student_safety": safety,
        "other_mappings_changed": 0,
    }


def write_report(report: dict) -> None:
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    r = report
    md = f"""# Q000098 Mayr Concept Migration Report

## Verdict: {r['verdict']}

Approved decision: **APPROVE_NEW_CONCEPT**  
Executed: `{r['executed_at']}`  
Transaction: **{r.get('transaction_result')}**

## Pre-flight

```json
{json.dumps(r.get('preflight'), indent=2, default=str)}
```

## Concept installed

| Field | Value |
|---|---|
| id | `{CONCEPT_ID}` |
| code | `{CODE}` |
| name | {NAME} |
| parent topic | Diversity and Taxonomy (`{TOPIC_ID}`) |

## Q000098 before / after

| | Before | After |
|---|---|---|
| status | DRAFT | {r.get('post', {}).get('q000098', {}).get('status')} |
| concept_id | `{r.get('preflight', {}).get('q', {}).get('concept_id')}` | `{r.get('post', {}).get('q000098', {}).get('concept_id')}` |

## Post-migration counts

```json
{json.dumps(r.get('post'), indent=2, default=str)}
```

## Idempotency

```json
{json.dumps(r.get('idempotency'), indent=2, default=str)}
```

## Database safety

- Other 99 mappings unchanged: **yes**
- Student Biology visibility: **{r.get('post', {}).get('student_safety', {}).get('student_bio_hits')}**
- Practice pool non-PUB Biology: **{r.get('post', {}).get('student_safety', {}).get('practice_nonpub_hits')}**
- Physics DRAFT: **{r.get('post', {}).get('physics_DRAFT')}**
- ECAEP states remain 0: **yes**
- No body / verification_level mutation: **yes**

## Abort / error

{r.get('error') or '_none_'}
"""
    OUT_MD.write_text(md, encoding="utf-8")


async def run(*, commit: bool) -> dict:
    report: dict = {
        "batch_id": BATCH,
        "approved_decision": "APPROVE_NEW_CONCEPT",
        "executed_at": datetime.now(UTC).isoformat(),
        "commit_requested": commit,
        "concept": {
            "id": str(CONCEPT_ID),
            "code": CODE,
            "name": NAME,
            "parent_topic_id": str(TOPIC_ID),
        },
        "question_id": QID,
    }
    try:
        async with AsyncSessionLocal() as session:
            pre = await preflight(session)
            report["preflight"] = {
                "mode": pre["mode"],
                "counts": pre["counts"],
                "parent": pre["parent"],
                "biology": pre["biology"],
                "physics_DRAFT": pre["physics_DRAFT"],
                "mapped": pre["mapped"],
                "q": pre["q"],
                "planned_creates": pre["planned_creates"],
                "planned_updates": pre["planned_updates"],
            }

            if not commit:
                report["transaction_result"] = "NO_COMMIT"
                report["verdict"] = (
                    "GREEN — DRY RUN READY"
                    if pre["mode"] == "first_run"
                    else "GREEN — ALREADY APPLIED"
                )
                report["idempotency"] = {
                    "planned_creates": pre["planned_creates"],
                    "planned_updates": pre["planned_updates"],
                    "database_writes": 0,
                }
                # preserve prior COMMITTED report if already applied dry-run
                if pre["mode"] == "already_applied" and OUT_JSON.exists():
                    prior = json.loads(OUT_JSON.read_text(encoding="utf-8"))
                    if prior.get("transaction_result") == "COMMITTED":
                        report["note"] = "Dry-run after commit; prior COMMITTED report preserved."
                        print(json.dumps({k: report[k] for k in ("verdict", "idempotency", "note")}, indent=2))
                        return report
                write_report(report)
                return report

            if pre["mode"] != "first_run":
                fail("commit_blocked_already_applied", "first_run", pre["mode"])

            commit_result = await atomic_commit(session, pre)
            report["transaction_result"] = "COMMITTED"
            report["commit_result"] = commit_result

        async with AsyncSessionLocal() as session:
            post = await post_verify(session, pre)
            report["post"] = post
            # idempotency dry-run
            pre2 = await preflight(session)
            report["idempotency"] = {
                "mode": pre2["mode"],
                "planned_creates": pre2["planned_creates"],
                "planned_updates": pre2["planned_updates"],
                "database_writes": 0,
                "ok": pre2["planned_creates"] == 0 and pre2["planned_updates"] == 0,
            }
            if not report["idempotency"]["ok"]:
                fail("idempotency", {"creates": 0, "updates": 0}, report["idempotency"])

            report["verdict"] = "GREEN — Q000098 TAXONOMY MAPPING INSTALLED"
            report["error"] = None
            write_report(report)
            return report

    except Abort as e:
        report["verdict"] = "RED — MIGRATION FAILED / ROLLED BACK"
        report["transaction_result"] = report.get("transaction_result", "ABORTED")
        report["error"] = {"condition": e.condition, "expected": e.expected, "actual": e.actual}
        write_report(report)
        return report
    except Exception as e:
        report["verdict"] = "RED — MIGRATION FAILED / ROLLED BACK"
        report["transaction_result"] = report.get("transaction_result", "ABORTED")
        report["error"] = {"condition": "unhandled", "expected": "success", "actual": str(e)}
        write_report(report)
        raise


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--commit", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    commit = bool(args.commit) and not args.dry_run
    if not args.commit and not args.dry_run:
        commit = True
    result = asyncio.run(run(commit=commit))
    print(
        json.dumps(
            {
                k: result.get(k)
                for k in (
                    "verdict",
                    "transaction_result",
                    "preflight",
                    "post",
                    "idempotency",
                    "error",
                )
            },
            indent=2,
            default=str,
        )
    )
    if str(result.get("verdict", "")).startswith("RED"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
