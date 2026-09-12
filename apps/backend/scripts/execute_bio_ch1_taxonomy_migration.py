"""Execute Biology Ch1 taxonomy expansion + concept mapping (atomic).

Usage:
  python execute_bio_ch1_taxonomy_migration.py --dry-run-only
  python execute_bio_ch1_taxonomy_migration.py --commit
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import uuid
from collections import Counter
from copy import deepcopy
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
MAYR = f"GEMINI-{BATCH}-000098"
ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
PLAN_PATH = ROOT / "taxonomy_migration_plan.json"
OUT_MD = ROOT / "taxonomy_migration_execution_report.md"
OUT_JSON = ROOT / "taxonomy_migration_execution_report.json"

EXPECTED_CODES = {
    "lw-diversity-what-is-living",
    "lw-nomenclature-identification-codes",
    "lw-binomial-nomenclature",
    "lw-taxonomy-systematics",
    "lw-taxonomic-hierarchy-relations",
    "lw-taxonomic-categories-ranks",
}


class StopMigration(Exception):
    def __init__(self, condition: str, expected, actual, affected: str | None = None):
        self.condition = condition
        self.expected = expected
        self.actual = actual
        self.affected = affected
        super().__init__(f"STOP: {condition} expected={expected!r} actual={actual!r} affected={affected}")


def fail(condition: str, expected, actual, affected: str | None = None) -> None:
    raise StopMigration(condition, expected, actual, affected)


def body_fingerprint(body: dict | None) -> str:
    raw = json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


async def live_parent(session) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT sub.id::text AS subject_id, sub.name AS subject_name, sub.code AS subject_code,
                       ch.id::text AS chapter_id, ch.name AS chapter_name, ch.code AS chapter_code,
                       t.id::text AS topic_id, t.name AS topic_name, t.code AS topic_code
                FROM academic.subjects sub
                JOIN academic.chapters ch ON ch.subject_id = sub.id AND ch.deleted_at IS NULL
                JOIN academic.topics t ON t.chapter_id = ch.id AND t.deleted_at IS NULL
                WHERE sub.deleted_at IS NULL
                  AND sub.code = 'BOTANY'
                  AND ch.code = 'the-living-world'
                  AND t.code = 'sv2t-botany-01'
                """
            )
        )
    ).mappings().one()
    return dict(row)


async def content_status_snapshot(session) -> dict:
    items = (
        await session.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))
    ).scalars().all()
    bio = [
        i
        for i in items
        if BATCH in (i.tags or []) or (i.slug and "bio11-ch01-b001" in (i.slug or "").lower())
    ]
    phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
    bs, ps = Counter(i.status for i in bio), Counter(i.status for i in phy)
    return {
        "biology": {
            "DRAFT": bs.get("DRAFT", 0),
            "SUPERSEDED": bs.get("SUPERSEDED", 0),
            "PUBLISHED": bs.get("PUBLISHED", 0),
            "APPROVED": bs.get("APPROVED", 0),
            "IN_REVIEW": bs.get("IN_REVIEW", 0),
        },
        "physics_DRAFT": ps.get("DRAFT", 0),
        "bio_items": bio,
        "phy_items": phy,
    }


def external_id_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    marker = "GEMINI-20260911-BIO11-CH01-B001-"
    if marker not in slug:
        return None
    return f"GEMINI-20260911-BIO11-CH01-B001-{slug.split(marker, 1)[1]}"


def load_plan() -> dict:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    concepts = plan["proposed_concepts"]
    if len(concepts) != 6:
        fail("plan.proposed_concepts.count", 6, len(concepts))
    codes = {c["code"] for c in concepts}
    if codes != EXPECTED_CODES:
        fail("plan.proposed_concepts.codes", sorted(EXPECTED_CODES), sorted(codes))
    mappings = plan["question_mappings"]
    if len(mappings) != 100:
        fail("plan.question_mappings.count", 100, len(mappings))
    to_map = [m for m in mappings if m.get("touch_in_migration")]
    unmapped = [m for m in mappings if not m.get("touch_in_migration")]
    if len(to_map) != 99:
        fail("plan.mapped.count", 99, len(to_map))
    if len(unmapped) != 1 or unmapped[0]["question_id"] != MAYR:
        fail("plan.unmapped", MAYR, [u["question_id"] for u in unmapped])
    return plan


async def preflight(session, plan: dict) -> dict:
    counts = await taxonomy_counts(session)
    if counts != {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 127}:
        # Allow already-applied? Preflight for first run expects 127.
        # Idempotent path handled separately.
        pass
    parent = await live_parent(session)
    planned_parent = plan["parent_hierarchy"]
    for k in (
        "subject_id",
        "subject_code",
        "chapter_id",
        "chapter_code",
        "topic_id",
        "topic_code",
    ):
        if parent[k] != planned_parent[k]:
            fail(f"parent.{k}", planned_parent[k], parent[k], "live hierarchy")

    snap = await content_status_snapshot(session)
    expected_bio = {"DRAFT": 100, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 0}
    if snap["biology"] != expected_bio:
        fail("biology.status", expected_bio, snap["biology"])
    if snap["physics_DRAFT"] != 24:
        fail("physics.DRAFT", 24, snap["physics_DRAFT"])

    return {"counts": counts, "parent": parent, "content": snap}


async def dry_run(session, plan: dict, pre: dict) -> dict:
    parent = pre["parent"]
    topic_id = uuid.UUID(parent["topic_id"])
    failures: list[dict] = []

    # 1-4 concepts
    planned_inserts = []
    for c in plan["proposed_concepts"]:
        code = c["code"]
        expected_id = uuid.UUID(c["proposed_concept_id"])
        computed = uuid.uuid5(topic_id, code)
        if computed != expected_id:
            fail("uuid5(topic_id,code)", str(expected_id), str(computed), code)
        if uuid.UUID(c["parent_topic_id"]) != topic_id:
            fail("concept.parent_topic_id", str(topic_id), c["parent_topic_id"], code)

        existing_by_code = (
            await session.execute(
                select(Concept).where(
                    Concept.topic_id == topic_id,
                    Concept.code == code,
                    Concept.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        exact_name = (
            await session.execute(
                select(Concept).where(
                    Concept.name == c["name"],
                    Concept.deleted_at.is_(None),
                )
            )
        ).scalars().all()

        if existing_by_code is None and exact_name:
            # name exists elsewhere — blocking for create
            fail(
                "exact_name_duplicate_elsewhere",
                "absent",
                [str(x.id) for x in exact_name],
                c["name"],
            )

        if existing_by_code is None:
            planned_inserts.append(c)
        else:
            # already applied concept — verify match for idempotency dry-run
            if existing_by_code.id != expected_id:
                fail("existing_concept.id", str(expected_id), str(existing_by_code.id), code)
            if existing_by_code.name != c["name"]:
                fail("existing_concept.name", c["name"], existing_by_code.name, code)

    # 5-10 questions
    bio_by_ext: dict[str, ContentItem] = {}
    for item in pre["content"]["bio_items"]:
        eid = external_id_from_slug(item.slug)
        if eid:
            bio_by_ext[eid] = item

    phy_ids = {i.id for i in pre["content"]["phy_items"]}
    planned_updates = []
    fingerprints_before: dict[str, str] = {}

    for m in plan["question_mappings"]:
        eid = m["question_id"]
        item = bio_by_ext.get(eid)
        if item is None:
            fail("question.exists_active_bio", "present", "missing", eid)
        if str(item.id) != m["content_item_id"]:
            fail("question.content_item_id", m["content_item_id"], str(item.id), eid)
        if item.id in phy_ids:
            fail("physics_not_in_mapping", "not physics", "physics", eid)

        # load version body fingerprint
        latest = (
            await session.execute(select(ContentVersion).where(ContentVersion.id == item.latest_version_id))
        ).scalar_one()
        fingerprints_before[eid] = body_fingerprint(latest.body)

        if m.get("touch_in_migration"):
            if item.status != "DRAFT":
                fail("mapped.status", "DRAFT", item.status, eid)
            if item.status == "SUPERSEDED":
                fail("mapped.not_superseded", "DRAFT", item.status, eid)
            if m["proposed_concept_id"] is None:
                fail("mapped.has_concept", "uuid", None, eid)
            # verify assignment matches plan concept
            code = m["proposed_concept_code"]
            concept = next(c for c in plan["proposed_concepts"] if c["code"] == code)
            if m["proposed_concept_id"] != concept["proposed_concept_id"]:
                fail("mapping.concept_id_matches_plan", concept["proposed_concept_id"], m["proposed_concept_id"], eid)
            if item.concept_id is None:
                planned_updates.append(m)
            elif str(item.concept_id) == m["proposed_concept_id"]:
                pass  # already mapped correctly
            else:
                fail(
                    "mapped.unexpected_existing_concept",
                    m["proposed_concept_id"],
                    str(item.concept_id),
                    eid,
                )
        else:
            if eid != MAYR:
                fail("unmapped.only_mayr", MAYR, eid)
            if item.status != "DRAFT":
                fail("mayr.status", "DRAFT", item.status, eid)
            if item.concept_id is not None:
                fail("mayr.concept_id", None, str(item.concept_id), eid)

    if len([m for m in plan["question_mappings"] if m.get("touch_in_migration")]) != 99:
        fail("planned_assignments", 99, "mismatch")

    # First-run expectation when concepts still at 127
    counts = pre["counts"]
    already_applied = counts["concepts"] == 133 and len(planned_inserts) == 0 and len(planned_updates) == 0
    first_run_ready = counts["concepts"] == 127 and len(planned_inserts) == 6 and len(planned_updates) == 99

    if not already_applied and not first_run_ready:
        fail(
            "dry_run.mode",
            "first_run(6 inserts,99 updates) or already_applied(0,0)",
            {
                "concepts": counts["concepts"],
                "planned_inserts": len(planned_inserts),
                "planned_updates": len(planned_updates),
            },
        )

    if first_run_ready:
        # codes must be absent from topic
        for c in plan["proposed_concepts"]:
            exists = (
                await session.execute(
                    select(Concept.id).where(
                        Concept.topic_id == topic_id,
                        Concept.code == c["code"],
                        Concept.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if exists is not None:
                fail("code.absent_before_create", None, str(exists), c["code"])

    return {
        "ok": True,
        "mode": "already_applied" if already_applied else "first_run",
        "planned_concept_inserts": len(planned_inserts),
        "planned_question_updates": len(planned_updates),
        "planned_insert_codes": [c["code"] for c in planned_inserts],
        "planned_update_ids": [m["content_item_id"] for m in planned_updates],
        "fingerprints_before": fingerprints_before,
        "expected_post": {
            "taxonomy": {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 133},
            "biology": {
                "DRAFT": 100,
                "SUPERSEDED": 5,
                "PUBLISHED": 0,
                "APPROVED": 0,
                "IN_REVIEW": 0,
            },
            "physics_DRAFT": 24,
            "mapped": 99,
            "unmapped": 1,
        },
        "failures": failures,
    }


async def atomic_commit(session, plan: dict, pre: dict, dry: dict) -> dict:
    if dry["mode"] != "first_run":
        fail("commit.requires_first_run", "first_run", dry["mode"])

    parent = pre["parent"]
    topic_id = uuid.UUID(parent["topic_id"])
    inserted = []

    try:
        # Re-verify parent inside transaction
        live = await live_parent(session)
        if live["topic_id"] != parent["topic_id"]:
            fail("txn.parent_topic", parent["topic_id"], live["topic_id"])

        for c in plan["proposed_concepts"]:
            cid = uuid.UUID(c["proposed_concept_id"])
            concept = Concept(
                id=cid,
                topic_id=topic_id,
                code=c["code"],
                name=c["name"],
                summary=c["summary"],
                ncert_reference=c["ncert_reference"],
                difficulty=c["difficulty"],
                display_order=c["display_order"],
            )
            session.add(concept)
            inserted.append({"id": str(cid), "code": c["code"], "name": c["name"]})

        await session.flush()

        # Verify inserts
        for c in plan["proposed_concepts"]:
            row = (
                await session.execute(
                    select(Concept).where(Concept.id == uuid.UUID(c["proposed_concept_id"]))
                )
            ).scalar_one()
            if row.topic_id != topic_id or row.code != c["code"] or row.name != c["name"]:
                fail("inserted_concept_verify", c["code"], f"{row.code}/{row.name}/{row.topic_id}")

        # Assign 99 questions — only concept_id, only listed DRAFT NULL
        assignments = []
        for m in plan["question_mappings"]:
            if not m.get("touch_in_migration"):
                continue
            item_id = uuid.UUID(m["content_item_id"])
            concept_id = uuid.UUID(m["proposed_concept_id"])
            result = await session.execute(
                update(ContentItem)
                .where(
                    ContentItem.id == item_id,
                    ContentItem.deleted_at.is_(None),
                    ContentItem.status == "DRAFT",
                    ContentItem.concept_id.is_(None),
                )
                .values(concept_id=concept_id)
            )
            if result.rowcount != 1:
                fail("question_update_rowcount", 1, result.rowcount, m["question_id"])
            assignments.append(
                {
                    "question_id": m["question_id"],
                    "content_item_id": m["content_item_id"],
                    "concept_id": m["proposed_concept_id"],
                    "concept_code": m["proposed_concept_code"],
                }
            )

        if len(assignments) != 99:
            fail("assignments.count", 99, len(assignments))

        # Mayr still NULL
        mayr_item = (
            await session.execute(
                select(ContentItem).where(ContentItem.id == uuid.UUID(
                    next(m["content_item_id"] for m in plan["question_mappings"] if m["question_id"] == MAYR)
                ))
            )
        ).scalar_one()
        if mayr_item.concept_id is not None:
            fail("mayr.still_null", None, str(mayr_item.concept_id), MAYR)

        # No SUPERSEDED modified: all SUPERSEDED still null concept or unchanged
        superseded = [
            i for i in pre["content"]["bio_items"] if i.status == "SUPERSEDED"
        ]
        for s in superseded:
            refreshed = (
                await session.execute(select(ContentItem).where(ContentItem.id == s.id))
            ).scalar_one()
            if refreshed.concept_id != s.concept_id:
                fail("superseded.untouched", str(s.concept_id), str(refreshed.concept_id), str(s.id))

        # Physics untouched
        for p in pre["content"]["phy_items"]:
            refreshed = (
                await session.execute(select(ContentItem).where(ContentItem.id == p.id))
            ).scalar_one()
            if refreshed.concept_id != p.concept_id or refreshed.status != p.status:
                fail("physics.untouched", p.status, refreshed.status, str(p.id))

        counts = await taxonomy_counts(session)
        if counts != {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 133}:
            fail("post_flush.taxonomy", {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 133}, counts)

        await session.commit()
        return {
            "committed": True,
            "rolled_back": False,
            "inserted_concepts": inserted,
            "assignments": assignments,
            "assignment_count": len(assignments),
        }
    except Exception:
        await session.rollback()
        raise


async def post_verify(session, plan: dict, fingerprints_before: dict) -> dict:
    counts = await taxonomy_counts(session)
    if counts != {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 133}:
        fail("post.taxonomy", {"concepts": 133}, counts)

    parent = await live_parent(session)
    topic_id = uuid.UUID(parent["topic_id"])
    inserted = []
    for c in plan["proposed_concepts"]:
        row = (
            await session.execute(
                select(Concept).where(Concept.id == uuid.UUID(c["proposed_concept_id"]))
            )
        ).scalar_one()
        if row.topic_id != topic_id or row.code != c["code"] or row.name != c["name"]:
            fail("post.concept", c, {"code": row.code, "name": row.name, "topic": str(row.topic_id)})
        # hierarchy via join
        hier = (
            await session.execute(
                text(
                    """
                    SELECT sub.code AS subject_code, ch.code AS chapter_code, t.code AS topic_code
                    FROM academic.concepts c
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects sub ON sub.id = ch.subject_id
                    WHERE c.id = :cid
                    """
                ),
                {"cid": row.id},
            )
        ).mappings().one()
        if hier["subject_code"] != "BOTANY" or hier["chapter_code"] != "the-living-world" or hier["topic_code"] != "sv2t-botany-01":
            fail("post.hierarchy", "BOTANY/the-living-world/sv2t-botany-01", dict(hier), c["code"])
        inserted.append({"id": str(row.id), "code": row.code, "name": row.name, "topic_id": str(row.topic_id)})

    snap = await content_status_snapshot(session)
    expected_bio = {"DRAFT": 100, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 0}
    if snap["biology"] != expected_bio:
        fail("post.biology", expected_bio, snap["biology"])
    if snap["physics_DRAFT"] != 24:
        fail("post.physics", 24, snap["physics_DRAFT"])

    mapped = 0
    unmapped = []
    assignment_check = []
    by_ext = {}
    for item in snap["bio_items"]:
        eid = external_id_from_slug(item.slug)
        if eid and item.status == "DRAFT":
            by_ext[eid] = item

    for m in plan["question_mappings"]:
        item = by_ext[m["question_id"]]
        latest = (
            await session.execute(select(ContentVersion).where(ContentVersion.id == item.latest_version_id))
        ).scalar_one()
        fp = body_fingerprint(latest.body)
        if fp != fingerprints_before[m["question_id"]]:
            fail("body_unchanged", fingerprints_before[m["question_id"]], fp, m["question_id"])

        if m.get("touch_in_migration"):
            if str(item.concept_id) != m["proposed_concept_id"]:
                fail("post.mapping", m["proposed_concept_id"], str(item.concept_id), m["question_id"])
            mapped += 1
            assignment_check.append(
                {
                    "question_id": m["question_id"],
                    "content_item_id": str(item.id),
                    "concept_id": str(item.concept_id),
                    "concept_code": m["proposed_concept_code"],
                }
            )
        else:
            if item.concept_id is not None:
                fail("post.mayr_null", None, str(item.concept_id), MAYR)
            unmapped.append(m["question_id"])

    if mapped != 99 or unmapped != [MAYR]:
        fail("post.map_counts", {"mapped": 99, "unmapped": [MAYR]}, {"mapped": mapped, "unmapped": unmapped})

    # SUPERSEDED still unmapped / untouched concept_ids from pre — all null typically
    for item in snap["bio_items"]:
        if item.status == "SUPERSEDED" and item.concept_id is not None:
            # plan never assigned them; if somehow set, fail
            fail("post.superseded_null_or_untouched", None, str(item.concept_id), str(item.id))

    return {
        "counts": counts,
        "biology": snap["biology"],
        "physics_DRAFT": snap["physics_DRAFT"],
        "mapped": mapped,
        "unmapped": unmapped,
        "inserted_concepts": inserted,
        "assignments": assignment_check,
    }


async def student_safety(session) -> dict:
    repo = CmsRepository(session)
    bio_hits = 0
    off = 0
    while True:
        items, total = await repo.list_questions(class_level="11", limit=100, offset=off)
        for i in items:
            if i.status != "PUBLISHED":
                fail("student.list_not_published_only", "PUBLISHED", i.status, str(i.id))
            tags = i.tags or []
            if BATCH in tags or (i.slug and "bio11-ch01-b001" in i.slug.lower()):
                bio_hits += 1
        off += 100
        if off >= total or not items:
            break

    pool = await AssessmentRepository(session).published_question_ids_for_scope("FULL", None)
    bio_draft_ids = set()
    items = (
        await session.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))
    ).scalars().all()
    for i in items:
        if BATCH in (i.tags or []) or (i.slug and "bio11-ch01-b001" in (i.slug or "").lower()):
            if i.status in {"DRAFT", "IN_REVIEW", "SUPERSEDED", "APPROVED"}:
                bio_draft_ids.add(i.id)
    practice_hits = len(bio_draft_ids & set(pool))
    return {
        "student_bio_published_hits": bio_hits,
        "practice_bio_nonpublished_hits": practice_hits,
        "ok": bio_hits == 0 and practice_hits == 0,
    }


def write_report(report: dict) -> None:
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    r = report
    md = f"""# Taxonomy Migration Execution Report — `{BATCH}`

## Verdict: {r['verdict']}

Executed: `{r['executed_at']}`
Transaction: **{r.get('transaction_result')}**
Rollback: **{r.get('rollback_status')}**

## Pre-flight counts

```json
{json.dumps(r['preflight'], indent=2)}
```

## Dry-run

```json
{json.dumps({k: r['dry_run'][k] for k in r['dry_run'] if k != 'fingerprints_before' and k != 'planned_update_ids'}, indent=2)}
```

- planned concept creates: **{r['dry_run'].get('planned_concept_inserts')}**
- planned question updates: **{r['dry_run'].get('planned_question_updates')}**

## Inserted concepts

| code | id |
|---|---|
"""
    for c in r.get("inserted_concepts") or []:
        md += f"| `{c['code']}` | `{c['id']}` |\n"
    md += f"""
## Question mapping

- Mapped: **{r.get('mapped', 'n/a')}**
- Unmapped: **{r.get('unmapped', 'n/a')}** (must be Q000098 only)

## Post-migration counts

```json
{json.dumps(r.get('post_verify_counts'), indent=2)}
```

## Idempotency (second dry-run)

```json
{json.dumps(r.get('idempotency'), indent=2)}
```

## Student visibility

```json
{json.dumps(r.get('student_safety'), indent=2)}
```

## Regression

```json
{json.dumps(r.get('regression'), indent=2)}
```

## Stop / error

{r.get('stop_error') or '_none_'}
"""
    OUT_MD.write_text(md, encoding="utf-8")


async def run(*, commit: bool) -> dict:
    plan = load_plan()
    report: dict = {
        "batch_id": BATCH,
        "executed_at": datetime.now(UTC).isoformat(),
        "commit_requested": commit,
        "plan_path": str(PLAN_PATH),
    }
    try:
        async with AsyncSessionLocal() as session:
            pre = await preflight(session, plan)
            # For first execution concepts must be 127
            if pre["counts"]["concepts"] not in (127, 133):
                fail("preflight.concepts", "127 or 133", pre["counts"]["concepts"])
            if commit and pre["counts"]["concepts"] != 127:
                fail("commit.requires_concepts_127", 127, pre["counts"]["concepts"])

            report["preflight"] = {
                "counts": pre["counts"],
                "parent": pre["parent"],
                "biology": pre["content"]["biology"],
                "physics_DRAFT": pre["content"]["physics_DRAFT"],
            }

            dry = await dry_run(session, plan, pre)
            report["dry_run"] = {
                "ok": dry["ok"],
                "mode": dry["mode"],
                "planned_concept_inserts": dry["planned_concept_inserts"],
                "planned_question_updates": dry["planned_question_updates"],
                "planned_insert_codes": dry["planned_insert_codes"],
                "expected_post": dry["expected_post"],
            }

            if not commit:
                report["transaction_result"] = "NO_COMMIT_DRY_RUN_ONLY"
                report["rollback_status"] = "n/a"
                report["verdict"] = (
                    "GREEN — DRY RUN READY" if dry["mode"] == "first_run" else "GREEN — ALREADY APPLIED"
                )
                # Do not overwrite a prior COMMITTED execution report with a dry-run-only run.
                if dry["mode"] == "already_applied" and OUT_JSON.exists():
                    try:
                        prior = json.loads(OUT_JSON.read_text(encoding="utf-8"))
                        if prior.get("transaction_result") == "COMMITTED":
                            report["note"] = (
                                "Dry-run-only after successful commit; prior COMMITTED execution report preserved."
                            )
                            print(json.dumps({k: report.get(k) for k in ("verdict", "dry_run", "note")}, indent=2))
                            return report
                    except Exception:
                        pass
                write_report(report)
                return report

            # PHASE 4 commit
            commit_result = await atomic_commit(session, plan, pre, dry)
            report["transaction_result"] = "COMMITTED"
            report["rollback_status"] = "not_needed"
            report["inserted_concepts"] = commit_result["inserted_concepts"]
            report["assignments"] = commit_result["assignments"]
            report["mapped"] = 99
            report["unmapped"] = [MAYR]

        # New session for post-verify (committed data)
        async with AsyncSessionLocal() as session:
            post = await post_verify(session, plan, dry["fingerprints_before"])
            report["post_verify_counts"] = {
                "taxonomy": post["counts"],
                "biology": post["biology"],
                "physics_DRAFT": post["physics_DRAFT"],
                "mapped": post["mapped"],
                "unmapped": post["unmapped"],
            }
            report["inserted_concepts"] = post["inserted_concepts"]
            report["assignments"] = post["assignments"]

            # Idempotency dry-run
            pre2 = await preflight(session, plan)
            # preflight biology still ok; concepts now 133 — adjust dry_run expectations
            dry2 = await dry_run(session, plan, {**pre2, "counts": await taxonomy_counts(session)})
            report["idempotency"] = {
                "mode": dry2["mode"],
                "planned_concept_inserts": dry2["planned_concept_inserts"],
                "planned_question_updates": dry2["planned_question_updates"],
                "ok": dry2["planned_concept_inserts"] == 0 and dry2["planned_question_updates"] == 0,
            }
            if not report["idempotency"]["ok"]:
                fail(
                    "idempotency.zero_writes",
                    {"creates": 0, "updates": 0},
                    {
                        "creates": dry2["planned_concept_inserts"],
                        "updates": dry2["planned_question_updates"],
                    },
                )

            safety = await student_safety(session)
            report["student_safety"] = safety
            if not safety["ok"]:
                fail("student_safety", 0, safety)

            report["regression"] = {
                "subjects_chapters_topics_unchanged": post["counts"]["subjects"] == 4
                and post["counts"]["chapters"] == 35
                and post["counts"]["topics"] == 101,
                "concepts_127_to_133": post["counts"]["concepts"] == 133,
                "physics_DRAFT_24": post["physics_DRAFT"] == 24,
                "biology_status_unchanged": post["biology"] == {
                    "DRAFT": 100,
                    "SUPERSEDED": 5,
                    "PUBLISHED": 0,
                    "APPROVED": 0,
                    "IN_REVIEW": 0,
                },
            }
            report["verdict"] = "GREEN — TAXONOMY MIGRATION VERIFIED"
            report["stop_error"] = None

        write_report(report)
        return report

    except StopMigration as e:
        report["verdict"] = "RED — ATOMICITY / DATA INTEGRITY / STUDENT SAFETY FAILURE"
        report["transaction_result"] = report.get("transaction_result", "ABORTED")
        report["rollback_status"] = "rolled_back_or_never_committed"
        report["stop_error"] = {
            "condition": e.condition,
            "expected": e.expected,
            "actual": e.actual,
            "affected": e.affected,
        }
        write_report(report)
        return report
    except Exception as e:
        report["verdict"] = "RED — ATOMICITY / DATA INTEGRITY / STUDENT SAFETY FAILURE"
        report["transaction_result"] = report.get("transaction_result", "ABORTED")
        report["rollback_status"] = "rolled_back_or_never_committed"
        report["stop_error"] = {"condition": "unhandled_exception", "expected": "success", "actual": str(e), "affected": None}
        write_report(report)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true", help="Perform atomic commit after successful dry-run")
    parser.add_argument("--dry-run-only", action="store_true", help="Preflight + dry-run only")
    args = parser.parse_args()
    commit = bool(args.commit) and not args.dry_run_only
    if not args.commit and not args.dry_run_only:
        # default: commit path when authorized by this task
        commit = True
    result = asyncio.run(run(commit=commit))
    print(json.dumps({k: result.get(k) for k in ("verdict", "transaction_result", "rollback_status", "stop_error", "dry_run", "post_verify_counts", "idempotency", "student_safety")}, indent=2, default=str))
    if str(result.get("verdict", "")).startswith("RED"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
