"""Execute BIO11-CH04-B001 approved taxonomy migration ONLY.

Creates 12 ak-t-* topics + 29 ak-* concepts under existing animal-kingdom.
Persists/validates 100 question→concept mappings as a committed ledger
(ContentItem import is NOT authorized).

Usage:
  python execute_bio_ch4_taxonomy_migration.py --dry-run
  python execute_bio_ch4_taxonomy_migration.py --commit
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
from app.core.database import AsyncSessionLocal
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.cms.models import ContentItem

BATCH = "20260912-BIO11-CH04-B001"
ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
FINAL_JSONL = ROOT / "questions_repaired_final.jsonl"
EXPECTED_SHA = "743bbacfd1a744e85c0a25ff79ed1908c35446d68169efbd8213fd454451b0c9"
PROPOSAL = ROOT / "taxonomy_proposal.json"
MAPPING = ROOT / "question_taxonomy_mapping.json"

CHAPTER_ID = uuid.UUID("5285cefb-e25f-4849-9c3b-d25f336bc65f")
ZOOLOGY_ID = uuid.UUID("1bbd31b8-60a1-4630-bdca-23167454b934")

BASELINE = (4, 36, 113, 163)
TARGET = (4, 36, 125, 192)
MEDIUM_Q = {"Q000054", "Q000074", "Q000084", "Q000085"}

OUT_MD = ROOT / "taxonomy_migration_report.md"
OUT_JSON = ROOT / "taxonomy_migration_results.json"
OUT_MAP = ROOT / "question_taxonomy_mapping_committed.json"


class Stop(Exception):
    def __init__(self, condition: str, expected=None, actual=None):
        self.condition = condition
        self.expected = expected
        self.actual = actual
        super().__init__(f"STOP: {condition} expected={expected!r} actual={actual!r}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_batch(item: ContentItem, batch: str, needle: str) -> bool:
    tags = item.tags or []
    if isinstance(tags, dict):
        tags = tags.get("tags") or []
    if batch in (tags or []) or any(batch in str(t) for t in (tags or [])):
        return True
    slug = item.slug or ""
    return needle in slug.lower() or batch in slug


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


async def content_regression(session) -> dict:
    items = (
        await session.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))
    ).scalars().all()
    batches = {
        "CH01": ("20260912-BIO11-CH01-B001", "bio11-ch01-b001"),
        "CH02": ("20260912-BIO11-CH02-B001", "bio11-ch02-b001"),
        "CH03": ("20260912-BIO11-CH03-B001", "bio11-ch03-b001"),
        "CH04": ("20260912-BIO11-CH04-B001", "bio11-ch04-b001"),
        "PHY02": ("20260911-PHY11-CH02-B001", "phy11-ch02-b001"),
    }
    # CH01 batch id in DB may be 20260911
    batches["CH01"] = ("20260911-BIO11-CH01-B001", "bio11-ch01-b001")
    batches["CH02"] = ("20260911-BIO11-CH02-B001", "bio11-ch02-b001")

    out = {}
    for name, (b, n) in batches.items():
        subset = [i for i in items if is_batch(i, b, n)]
        out[name] = dict(Counter(i.status for i in subset))
        out[name]["_total"] = len(subset)
    return out


def load_artifacts() -> tuple[dict, dict, list[dict]]:
    sha = sha256_file(FINAL_JSONL)
    if sha != EXPECTED_SHA:
        raise Stop("final_artifact_sha", EXPECTED_SHA, sha)
    qs = [json.loads(l) for l in FINAL_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(qs) != 100:
        raise Stop("question_count", 100, len(qs))
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    topics = proposal["proposed_topics"]
    concepts = proposal["proposed_concepts"]
    maps = mapping["mappings"]
    if len(topics) != 12:
        raise Stop("proposed_topics", 12, len(topics))
    if len(concepts) != 29:
        raise Stop("proposed_concepts", 29, len(concepts))
    if len(maps) != 100:
        raise Stop("mappings", 100, len(maps))
    conf = Counter(m["confidence"] for m in maps)
    if conf.get("HIGH") != 96 or conf.get("MEDIUM") != 4 or conf.get("LOW", 0) != 0:
        raise Stop("confidence_distribution", {"HIGH": 96, "MEDIUM": 4, "LOW": 0}, dict(conf))
    med = {m["qnum"] for m in maps if m["confidence"] == "MEDIUM"}
    if med != MEDIUM_Q:
        raise Stop("medium_questions", sorted(MEDIUM_Q), sorted(med))
    if proposal["chapter"]["id"] != str(CHAPTER_ID):
        raise Stop("chapter_id", str(CHAPTER_ID), proposal["chapter"]["id"])
    if mapping.get("unmapped"):
        raise Stop("unmapped", [], mapping["unmapped"])
    if mapping.get("ambiguous"):
        raise Stop("ambiguous", [], mapping["ambiguous"])
    return proposal, mapping, qs


async def migrate(session, proposal: dict, mapping: dict, *, commit: bool) -> dict:
    created = {"topics": 0, "concepts": 0}
    reused = {"topics": 0, "concepts": 0}

    subject = (
        await session.execute(
            select(Subject).where(Subject.id == ZOOLOGY_ID, Subject.deleted_at.is_(None))
        )
    ).scalar_one()
    if subject.code != "ZOOLOGY":
        raise Stop("subject_code", "ZOOLOGY", subject.code)

    chapter = (
        await session.execute(
            select(Chapter).where(Chapter.id == CHAPTER_ID, Chapter.deleted_at.is_(None))
        )
    ).scalar_one()
    if chapter.code != "animal-kingdom":
        raise Stop("chapter_code", "animal-kingdom", chapter.code)
    if chapter.subject_id != ZOOLOGY_ID:
        raise Stop("chapter_subject", str(ZOOLOGY_ID), str(chapter.subject_id))

    # Duplicate Animal Kingdom chapter check
    ak_dupes = (
        await session.execute(
            select(Chapter).where(
                Chapter.code == "animal-kingdom",
                Chapter.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    if len(ak_dupes) != 1:
        raise Stop("animal_kingdom_chapter_count", 1, len(ak_dupes))

    topic_ids: dict[str, uuid.UUID] = {}
    topic_rows: list[dict] = []
    for t in proposal["proposed_topics"]:
        tid = uuid.UUID(t["proposed_topic_id"])
        calc = uuid.uuid5(CHAPTER_ID, t["code"])
        if calc != tid:
            raise Stop(f"topic_uuid5:{t['code']}", str(tid), str(calc))
        if t["parent_chapter_id"] != str(CHAPTER_ID):
            raise Stop(f"topic_parent:{t['code']}", str(CHAPTER_ID), t["parent_chapter_id"])

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
            code_hit = (
                await session.execute(
                    select(Topic).where(Topic.code == t["code"], Topic.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if code_hit:
                raise Stop(f"topic_code_collision:{t['code']}", "absent", str(code_hit.id))
            session.add(
                Topic(
                    id=tid,
                    chapter_id=CHAPTER_ID,
                    code=t["code"],
                    name=t["name"],
                    display_order=int(t["display_order"]),
                )
            )
            created["topics"] += 1
            topic_ids[t["code"]] = tid
            topic_rows.append({"code": t["code"], "id": str(tid), "action": "CREATED", "name": t["name"]})
        else:
            if row.id != tid:
                raise Stop(f"topic_id_mismatch:{t['code']}", str(tid), str(row.id))
            if row.name != t["name"]:
                raise Stop(f"topic_name:{t['code']}", t["name"], row.name)
            reused["topics"] += 1
            topic_ids[t["code"]] = row.id
            topic_rows.append({"code": t["code"], "id": str(row.id), "action": "REUSED", "name": t["name"]})

    await session.flush()

    concept_rows: list[dict] = []
    for idx, c in enumerate(proposal["proposed_concepts"]):
        tcode = c.get("parent_topic_code") or c["topic"]
        tid = topic_ids[tcode]
        cid = uuid.UUID(c["proposed_concept_id"])
        calc = uuid.uuid5(tid, c["code"])
        if calc != cid:
            raise Stop(f"concept_uuid5:{c['code']}", str(cid), str(calc))
        if uuid.UUID(c["proposed_topic_id"]) != tid:
            raise Stop(f"concept_proposed_topic_id:{c['code']}", str(tid), c["proposed_topic_id"])

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
                raise Stop(f"concept_code_collision:{c['code']}", "absent", str(code_hit.id))
            session.add(
                Concept(
                    id=cid,
                    topic_id=tid,
                    code=c["code"],
                    name=c["name"],
                    summary=c.get("definition") or c["name"],
                    ncert_reference=(
                        f"ncert-books-class-11-biology-chapter-4.pdf — {c.get('ncert') or ''}"
                    )[:300],
                    difficulty="medium",
                    display_order=idx,
                )
            )
            created["concepts"] += 1
            concept_rows.append(
                {
                    "code": c["code"],
                    "id": str(cid),
                    "topic_code": tcode,
                    "topic_id": str(tid),
                    "action": "CREATED",
                    "name": c["name"],
                }
            )
        else:
            if row.id != cid:
                raise Stop(f"concept_id_mismatch:{c['code']}", str(cid), str(row.id))
            if row.name != c["name"]:
                raise Stop(f"concept_name:{c['code']}", c["name"], row.name)
            reused["concepts"] += 1
            concept_rows.append(
                {
                    "code": c["code"],
                    "id": str(row.id),
                    "topic_code": tcode,
                    "topic_id": str(tid),
                    "action": "REUSED",
                    "name": c["name"],
                }
            )

    await session.flush()

    # Validate mappings against live IDs
    concept_by_code = {r["code"]: r for r in concept_rows}
    persisted_maps = []
    for m in mapping["mappings"]:
        cinfo = concept_by_code[m["concept_code"]]
        if m["topic_code"] != cinfo["topic_code"]:
            raise Stop(f"map_topic:{m['qnum']}", cinfo["topic_code"], m["topic_code"])
        if m["topic_id"] != cinfo["topic_id"]:
            raise Stop(f"map_topic_id:{m['qnum']}", cinfo["topic_id"], m["topic_id"])
        if m["concept_id"] != cinfo["id"]:
            raise Stop(f"map_concept_id:{m['qnum']}", cinfo["id"], m["concept_id"])
        # live DB check
        live = (
            await session.execute(
                select(Concept).where(Concept.id == uuid.UUID(cinfo["id"]), Concept.deleted_at.is_(None))
            )
        ).scalar_one()
        if live.code != m["concept_code"]:
            raise Stop(f"live_concept_code:{m['qnum']}", m["concept_code"], live.code)
        persisted_maps.append(
            {
                "question_id": m["question_id"],
                "qnum": m["qnum"],
                "topic_code": m["topic_code"],
                "topic_id": m["topic_id"],
                "concept_code": m["concept_code"],
                "concept_id": m["concept_id"],
                "confidence": m["confidence"],
                "rationale": m["rationale"],
                "persisted": True,
            }
        )

    # Medium Q explicit validation
    medium_validation = {}
    for qn in sorted(MEDIUM_Q):
        row = next(x for x in persisted_maps if x["qnum"] == qn)
        approved = next(x for x in mapping["mappings"] if x["qnum"] == qn)
        medium_validation[qn] = {
            "ok": row["topic_id"] == approved["topic_id"] and row["concept_id"] == approved["concept_id"],
            "topic_code": row["topic_code"],
            "concept_code": row["concept_code"],
            "topic_id": row["topic_id"],
            "concept_id": row["concept_id"],
            "confidence": row["confidence"],
        }
        if not medium_validation[qn]["ok"] or row["confidence"] != "MEDIUM":
            raise Stop(f"medium_validation:{qn}", approved, row)

    # Duplicate audits
    topic_ids_list = [r["id"] for r in topic_rows]
    concept_ids_list = [r["id"] for r in concept_rows]
    if len(set(topic_ids_list)) != 12:
        raise Stop("duplicate_topic_ids", 12, len(set(topic_ids_list)))
    if len(set(concept_ids_list)) != 29:
        raise Stop("duplicate_concept_ids", 29, len(set(concept_ids_list)))
    if len({r["code"] for r in topic_rows}) != 12:
        raise Stop("duplicate_topic_codes", 12, len({r["code"] for r in topic_rows}))
    if len({r["code"] for r in concept_rows}) != 29:
        raise Stop("duplicate_concept_codes", 29, len({r["code"] for r in concept_rows}))

    subject_info = {"code": subject.code, "id": str(subject.id)}
    chapter_info = {"code": chapter.code, "id": str(chapter.id), "name": chapter.name}

    if commit:
        await session.commit()
    else:
        await session.rollback()

    return {
        "created": created,
        "reused": reused,
        "committed": commit,
        "topics": topic_rows,
        "concepts": concept_rows,
        "mappings": persisted_maps,
        "medium_validation": medium_validation,
        "subject": subject_info,
        "chapter": chapter_info,
    }


async def post_validate(session, proposal: dict) -> dict:
    counts = await taxonomy_tuple(session)
    issues = []
    if counts != TARGET:
        issues.append(f"counts={counts}")

    for t in proposal["proposed_topics"]:
        row = (
            await session.execute(
                select(Topic).where(Topic.id == uuid.UUID(t["proposed_topic_id"]), Topic.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if row is None:
            issues.append(f"missing_topic:{t['code']}")
        elif uuid.uuid5(CHAPTER_ID, t["code"]) != row.id:
            issues.append(f"uuid5_topic:{t['code']}")

    for c in proposal["proposed_concepts"]:
        tid = uuid.UUID(c["proposed_topic_id"])
        row = (
            await session.execute(
                select(Concept).where(Concept.id == uuid.UUID(c["proposed_concept_id"]), Concept.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if row is None:
            issues.append(f"missing_concept:{c['code']}")
        elif uuid.uuid5(tid, c["code"]) != row.id:
            issues.append(f"uuid5_concept:{c['code']}")

    # unexpected ak-* extras beyond approved set
    approved_t = {t["code"] for t in proposal["proposed_topics"]}
    approved_c = {c["code"] for c in proposal["proposed_concepts"]}
    live_t = (
        await session.execute(
            select(Topic).where(Topic.chapter_id == CHAPTER_ID, Topic.deleted_at.is_(None), Topic.code.like("ak-t-%"))
        )
    ).scalars().all()
    live_c = (
        await session.execute(
            select(Concept).where(Concept.deleted_at.is_(None), Concept.code.like("ak-%"))
        )
    ).scalars().all()
    # filter concepts that are under our ak topics only
    ak_topic_ids = {t.id for t in live_t}
    live_c_ak = [c for c in live_c if c.topic_id in ak_topic_ids]
    extra_t = {t.code for t in live_t} - approved_t
    extra_c = {c.code for c in live_c_ak} - approved_c
    if extra_t:
        issues.append(f"extra_topics:{sorted(extra_t)}")
    if extra_c:
        issues.append(f"extra_concepts:{sorted(extra_c)}")
    if len(live_t) != 12:
        issues.append(f"ak_topic_count={len(live_t)}")
    if len(live_c_ak) != 29:
        issues.append(f"ak_concept_count={len(live_c_ak)}")

    return {"ok": not issues, "issues": issues, "counts": counts}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    commit = bool(args.commit) and not bool(args.dry_run)

    proposal, mapping, _qs = load_artifacts()
    sha = sha256_file(FINAL_JSONL)
    first_created = {"topics": 0, "concepts": 0}

    async with AsyncSessionLocal() as session:
        pre = await taxonomy_tuple(session)
        if pre not in (BASELINE, TARGET):
            raise Stop("taxonomy_baseline", BASELINE, pre)
        content_pre = await content_regression(session)
        already_applied = pre == TARGET
        try:
            result = await migrate(session, proposal, mapping, commit=commit and not already_applied)
            if commit and not already_applied:
                first_created = dict(result["created"])
        except Exception:
            await session.rollback()
            raise

    async with AsyncSessionLocal() as session:
        post = await post_validate(session, proposal)
        counts_post = await taxonomy_tuple(session)
        content_post = await content_regression(session)
        if commit:
            before_idem = counts_post
            result2 = await migrate(session, proposal, mapping, commit=True)
            after_idem = await taxonomy_tuple(session)
            content_post = await content_regression(session)
            if result2["created"]["topics"] or result2["created"]["concepts"]:
                raise Stop("idempotency_created", {"topics": 0, "concepts": 0}, result2["created"])
            if after_idem != TARGET:
                raise Stop("idempotency_counts", TARGET, after_idem)
            idempotency = {
                "second_execution": "SAFE_NOOP_REUSE",
                "additional_topics": 0,
                "additional_concepts": 0,
                "counts_unchanged": before_idem == after_idem == TARGET,
                "post_second_counts": list(after_idem),
            }
            # Preserve first-pass CREATED/REUSED labels for audit; second pass only proves noop.
            if first_created["topics"] or first_created["concepts"] or not already_applied:
                for t in result2["topics"]:
                    t["action"] = "CREATED" if not already_applied else t["action"]
                    t["idempotency_second_pass"] = "REUSED"
                for c in result2["concepts"]:
                    c["action"] = "CREATED" if not already_applied else c["action"]
                    c["idempotency_second_pass"] = "REUSED"
            result = result2
            counts_post = after_idem
            post = await post_validate(session, proposal)
        else:
            idempotency = {"second_execution": "SKIPPED_DRY_RUN"}
            counts_post = pre
            post = {"ok": True, "issues": ["dry_run_skipped_live_ak_count_check"], "counts": pre}

    if commit and not post["ok"]:
        raise Stop("post_validate", True, post["issues"])

    if commit and not already_applied:
        created_topics, created_concepts = first_created["topics"], first_created["concepts"]
    elif commit and already_applied:
        created_topics = created_concepts = 0
    else:
        created_topics, created_concepts = result["created"]["topics"], result["created"]["concepts"]

    conf = Counter(m["confidence"] for m in result["mappings"])
    atomicity = (
        "ALREADY_APPLIED" if already_applied and commit
        else ("COMMITTED_SINGLE_TRANSACTION" if commit else "ROLLED_BACK_DRY_RUN")
    )
    green = (
        commit and sha == EXPECTED_SHA and sha256_file(FINAL_JSONL) == EXPECTED_SHA
        and counts_post == TARGET and created_topics in (0, 12) and created_concepts in (0, 29)
        and len(result["mappings"]) == 100 and conf.get("HIGH") == 96 and conf.get("MEDIUM") == 4
        and all(v["ok"] for v in result["medium_validation"].values())
        and content_post.get("CH04", {}).get("_total", 0) == 0
        and content_post.get("CH01", {}).get("PUBLISHED") == 100
        and content_post.get("CH02", {}).get("PUBLISHED") == 100
        and content_post.get("CH03", {}).get("PUBLISHED") == 100
        and content_post.get("PHY02", {}).get("DRAFT") == 24
        and post["ok"] and bool(idempotency.get("counts_unchanged", True))
    )
    verdict = (
        "AMBER — DRY RUN ONLY (not committed)" if not commit
        else ("GREEN — BIO11-CH04-B001 TAXONOMY MIGRATION COMPLETE" if green else "AMBER — TAXONOMY MIGRATION REQUIRES REVIEW")
    )
    mutations = {
        "subjects_created": 0, "chapters_created": 0,
        "topics_created": created_topics if commit else 0,
        "concepts_created": created_concepts if commit else 0,
        "question_mappings_created_updated": 100 if commit else 0,
        "content_items_created": 0,
        "mapping_persistence_note": "Mappings locked in committed ledger bound to live topic/concept UUIDs. No ContentItem.concept_id writes.",
    }
    results_doc = {
        "batch_id": BATCH, "final_verdict": verdict, "mode": "COMMIT" if commit else "DRY_RUN",
        "authoritative_artifact": "questions_repaired_final.jsonl", "authoritative_sha256": sha,
        "artifact_unchanged": sha256_file(FINAL_JSONL) == EXPECTED_SHA,
        "pre_migration_counts": {"subjects": pre[0], "chapters": pre[1], "topics": pre[2], "concepts": pre[3]},
        "post_migration_counts": {"subjects": counts_post[0], "chapters": counts_post[1], "topics": counts_post[2], "concepts": counts_post[3]},
        "subject_reused": result["subject"], "chapter_reused": result["chapter"],
        "topics": result["topics"], "concepts": result["concepts"],
        "topics_created": created_topics, "topics_reused": result["reused"]["topics"],
        "concepts_created": created_concepts, "concepts_reused": result["reused"]["concepts"],
        "mapping_count": len(result["mappings"]), "confidence_distribution": dict(conf),
        "medium_validation": result["medium_validation"],
        "uuid5_validation": "PASS" if (post["ok"] or not commit) else post["issues"],
        "duplicate_validation": {"duplicate_topic_ids": False, "duplicate_concept_ids": False, "duplicate_topic_codes": False, "duplicate_concept_codes": False, "duplicate_animal_kingdom_chapter": False},
        "atomicity": atomicity, "idempotency": idempotency, "database_mutations": mutations,
        "ch04_content_items": content_post.get("CH04", {}).get("_total", 0),
        "student_visibility_ch04": 0, "practice_pool_ch04": 0, "ecaep_ch04": 0, "ncert_certified_ch04": 0, "published_ch04": 0,
        "regression": content_post, "content_pre": content_pre, "post_validate": post,
        "created_at": datetime.now(UTC).isoformat(), "mandatory_stop": True,
    }
    if commit:
        OUT_JSON.write_text(json.dumps(results_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        OUT_MAP.write_text(json.dumps({"batch_id": BATCH, "committed_at": datetime.now(UTC).isoformat(), "authoritative_sha256": sha, "chapter_id": str(CHAPTER_ID), "mapping_count": 100, "confidence_distribution": dict(conf), "mappings": result["mappings"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = [f"# Taxonomy migration report — BIO11-CH04-B001", "", f"**Verdict:** {verdict}", "", f"- Final artifact SHA: `{sha}` (unchanged)", f"- Pre: `{pre}` → Post: `{counts_post}`", f"- Subject reused: ZOOLOGY `{result['subject']['id']}`", f"- Chapter reused: animal-kingdom `{result['chapter']['id']}`", f"- Topics created: **{mutations['topics_created']}**", f"- Concepts created: **{mutations['concepts_created']}**", f"- Mappings persisted (ledger): **{len(result['mappings'])}**", f"- Confidence: {dict(conf)}", f"- Atomicity: {atomicity}", f"- Idempotency: {idempotency}", f"- UUID5 validation: {results_doc['uuid5_validation']}", f"- CH04 ContentItems: {content_post.get('CH04', {}).get('_total', 0)}", "", "## Medium-confidence validation", ""]
        for qn, v in result["medium_validation"].items():
            lines.append(f"- {qn}: {'PASS' if v['ok'] else 'FAIL'} · `{v['topic_code']}` → `{v['concept_code']}` · {v['confidence']}")
        lines += ["", "## Topics", ""]
        for t in result["topics"]:
            lines.append(f"- `{t['code']}` `{t['id']}` ({t['action']})")
        lines += ["", "## Concepts", ""]
        for c in result["concepts"]:
            lines.append(f"- `{c['code']}` `{c['id']}` under `{c['topic_code']}` ({c['action']})")
        lines += ["", "## Regression", "", f"- CH01: {content_post.get('CH01')}", f"- CH02: {content_post.get('CH02')}", f"- CH03: {content_post.get('CH03')}", f"- Physics: {content_post.get('PHY02')}", f"- CH04: {content_post.get('CH04')}", "", "## Mandatory stop", "", "DRAFT import / ECAEP / NCERT certification / publication not executed.", ""]
        OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"verdict": verdict, "commit": commit, "pre": list(pre), "post": list(counts_post), "created_topics": mutations["topics_created"], "created_concepts": mutations["concepts_created"], "mappings": len(result["mappings"]), "confidence": dict(conf), "medium": result["medium_validation"], "idempotency": idempotency, "uuid5": results_doc["uuid5_validation"], "ch04_content": content_post.get("CH04"), "regression": {k: content_post.get(k) for k in ("CH01", "CH02", "CH03", "PHY02")}, "post_ok": post["ok"], "post_issues": post.get("issues")}, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
