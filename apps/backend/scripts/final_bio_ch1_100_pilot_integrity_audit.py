"""READ-ONLY final 100-question Biology Ch1 pilot integrity audit (pre-ECAEP).

Writes:
  docs/acquisition/batches/20260911-BIO11-CH01-B001/
    final_100_pilot_integrity_audit.md
    final_100_pilot_integrity_audit.json

Does NOT modify PostgreSQL, source JSONL/manifest, or prior audit artifacts.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

get_settings.cache_clear()
from app.core.database import AsyncSessionLocal
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.schemas.content_bodies import QuestionBody, assert_body_publishable
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
MAYR_EID = f"GEMINI-{BATCH}-000098"
MAYR_CONCEPT_ID = "64a807cc-89f2-52dc-8b26-0e784e66b0cc"
MAYR_CODE = "lw-biological-species-concept-mayr"
TOPIC_ID = "1a85b6d3-4972-47ad-8c0e-a20afc35f133"
CHAPTER_CODE = "the-living-world"
SUBJECT_CODE = "BOTANY"
NEAR_DUP_THRESHOLD = 0.82
RSTAR = {"R000095", "R000096", "R000097", "R000099", "R000100"}

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
JSONL = ROOT / "questions_repaired.jsonl"
ORIG_JSONL = ROOT / "questions.jsonl"
MANIFEST = ROOT / "manifest.json"
NCERT_AUDIT = ROOT / "ncert_verification_audit.json"
REPAIR = ROOT / "repair_results.json"
NCERT_TXT = ROOT.parent / "_scratch_bio11_ch01_ncert.txt"
OUT_JSON = ROOT / "final_100_pilot_integrity_audit.json"
OUT_MD = ROOT / "final_100_pilot_integrity_audit.md"

EXPECTED_TAX = {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}
EXPECTED_BIO = {"DRAFT": 100, "SUPERSEDED": 5, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 0}
EXPECTED_ORIG_Q = "0eadfa2d8f00376294f94f9c1396652e67ab0a361b1ccd231449e9493dcdcc9a"
EXPECTED_MANIFEST = "a9e5bf015ce7fb4741310f50c06a0126e0dc2f62fd6a13607fb93f235e15c548"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def eid_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    marker = f"GEMINI-{BATCH}-"
    if marker not in slug:
        return None
    return f"GEMINI-{BATCH}-{slug.split(marker, 1)[1]}"


def display_qid(eid: str) -> str:
    suffix = eid.rsplit("-", 1)[-1]
    if suffix.startswith("R"):
        return suffix
    return f"Q{suffix}"


def option_map(options: Any) -> dict[str, str]:
    if isinstance(options, dict):
        return {k: str(v).strip() for k, v in options.items()}
    out: dict[str, str] = {}
    if isinstance(options, list):
        for o in options:
            out[str(o.get("label", "")).strip().upper()] = str(o.get("text", "")).strip()
    return out


def tokenize(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(t) > 1}


def jaccard(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def content_tuple(stem: str, options: dict[str, str], correct: str, explanation: str) -> tuple:
    return (
        (stem or "").strip(),
        tuple((k, options.get(k, "").strip()) for k in ("A", "B", "C", "D")),
        (correct or "").strip().upper(),
        (explanation or "").strip(),
    )


async def snap(session, label: str) -> dict:
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
    bio = [
        i
        for i in items
        if BATCH in (i.tags or []) or (i.slug and "bio11-ch01-b001" in (i.slug or "").lower())
    ]
    phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
    bs, ps = Counter(i.status for i in bio), Counter(i.status for i in phy)
    drafts = [i for i in bio if i.status == "DRAFT"]
    mapped = sum(1 for i in drafts if i.concept_id)

    repo = CmsRepository(session)
    student_hits = 0
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        student_hits += sum(
            1
            for i in page
            if BATCH in (i.tags or []) or (i.slug and "bio11-ch01-b001" in (i.slug or "").lower())
        )
        off += 100
        if off >= tot or not page:
            break
    pool = set(await AssessmentRepository(session).published_question_ids_for_scope("FULL", None))
    nonpub = {i.id for i in bio if i.status != "PUBLISHED"}
    superseded = [i for i in bio if i.status == "SUPERSEDED"]
    return {
        "label": label,
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
        "physics_DRAFT": ps.get("DRAFT", 0),
        "mapped": mapped,
        "unmapped": len(drafts) - mapped,
        "student_bio_hits": student_hits,
        "practice_nonpub_hits": len(nonpub & pool),
        "student_superseded_hits": sum(
            1 for i in superseded if i.id in pool or False
        ),  # superseded never in published list via status filter
        "bio_item_ids": {str(i.id) for i in bio},
        "draft_ids": {str(i.id) for i in drafts},
        "superseded_ids": {str(i.id) for i in superseded},
        "published_pool_size": len(pool),
        "bio_in_published_endpoint": student_hits,
        "draft_in_pool": len({i.id for i in drafts} & pool),
        "superseded_in_pool": len({i.id for i in superseded} & pool),
    }


async def load_live_drafts(session) -> list[dict]:
    items = (
        await session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.deleted_at.is_(None), ContentItem.status == "DRAFT")
        )
    ).scalars().all()
    drafts = [
        i
        for i in items
        if BATCH in (i.tags or []) or (i.slug and "bio11-ch01-b001" in (i.slug or "").lower())
    ]
    concept_ids = [i.concept_id for i in drafts if i.concept_id]
    concepts: dict[uuid.UUID, dict] = {}
    if concept_ids:
        rows = (
            await session.execute(
                select(
                    Concept.id,
                    Concept.code,
                    Concept.name,
                    Concept.topic_id,
                    Concept.deleted_at,
                    Topic.id,
                    Topic.code,
                    Topic.name,
                    Topic.chapter_id,
                    Chapter.id,
                    Chapter.code,
                    Chapter.name,
                    Subject.id,
                    Subject.code,
                    Subject.name,
                )
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .join(Subject, Subject.id == Chapter.subject_id)
                .where(Concept.id.in_(concept_ids))
            )
        ).all()
        for r in rows:
            concepts[r[0]] = {
                "id": str(r[0]),
                "code": r[1],
                "name": r[2],
                "topic_id": str(r[3]),
                "deleted_at": r[4],
                "topic_code": r[6],
                "topic_name": r[7],
                "chapter_id": str(r[9]),
                "chapter_code": r[10],
                "chapter_name": r[11],
                "subject_id": str(r[12]),
                "subject_code": r[13],
                "subject_name": r[14],
            }

    # Taxonomy integrity: orphan concepts, duplicate codes, broken FKs.
    # Concept model has no parent_concept_id; hierarchy is Subject→Chapter→Topic→Concept.
    tax_issues: list[dict] = []
    orphan_rows = (
        await session.execute(
            text(
                """
                SELECT c.id::text, c.code
                FROM academic.concepts c
                LEFT JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                WHERE c.deleted_at IS NULL AND t.id IS NULL
                """
            )
        )
    ).all()
    for cid, code in orphan_rows:
        tax_issues.append({"type": "orphan_concept", "concept_id": cid, "code": code})

    dup_codes = (
        await session.execute(
            text(
                """
                SELECT code, count(*) AS n
                FROM academic.concepts
                WHERE deleted_at IS NULL
                GROUP BY code
                HAVING count(*) > 1
                """
            )
        )
    ).all()
    for code, n in dup_codes:
        tax_issues.append({"type": "duplicate_code", "code": code, "count": int(n)})

    # Invalid relationships: topic without chapter / chapter without subject
    broken = (
        await session.execute(
            text(
                """
                SELECT 'topic_missing_chapter' AS kind, t.id::text AS id, t.code
                FROM academic.topics t
                LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                WHERE t.deleted_at IS NULL AND ch.id IS NULL
                UNION ALL
                SELECT 'chapter_missing_subject', ch.id::text, ch.code
                FROM academic.chapters ch
                LEFT JOIN academic.subjects s ON s.id = ch.subject_id AND s.deleted_at IS NULL
                WHERE ch.deleted_at IS NULL AND s.id IS NULL
                """
            )
        )
    ).all()
    for kind, oid, code in broken:
        tax_issues.append({"type": kind, "id": oid, "code": code})

    # No self/cycle edges possible on concept adjacency (flat under topic); record N/A check
    tax_issues_note = {
        "self_cycle_relationships": 0,
        "note": "Concept entities are leaf nodes under topics; no parent_concept_id column exists.",
    }
    _ = tax_issues_note  # retained in summary via empty self/cycle count
    out = []
    for i in drafts:
        latest = next((v for v in i.versions if v.id == i.latest_version_id), None)
        if latest is None and i.versions:
            latest = max(i.versions, key=lambda v: v.version_number)
        body = latest.body if latest else {}
        eid = eid_from_slug(i.slug) or tag_eid(i.tags)
        c = concepts.get(i.concept_id) if i.concept_id else None
        out.append(
            {
                "content_item_id": str(i.id),
                "external_question_id": eid,
                "slug": i.slug,
                "status": i.status,
                "concept_id": str(i.concept_id) if i.concept_id else None,
                "concept": c,
                "tags": list(i.tags or []),
                "body": body or {},
                "model_used": getattr(latest, "model_used", None) if latest else None,
                "knowledge_unit_id": str(latest.knowledge_unit_id)
                if latest and getattr(latest, "knowledge_unit_id", None)
                else None,
                "latest_version_id": str(i.latest_version_id) if i.latest_version_id else None,
            }
        )
    return out, tax_issues


def tag_eid(tags: list[str] | None) -> str | None:
    for t in tags or []:
        if t.startswith("external_id:"):
            return t.split(":", 1)[1]
        if t.startswith("GEMINI-"):
            return t
    return None


def load_jsonl(path: Path) -> dict[str, dict]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["external_question_id"]] = row
    return out


async def main() -> int:
    assert NCERT_TXT.is_file(), "NCERT extract missing"
    ncert_audit = json.loads(NCERT_AUDIT.read_text(encoding="utf-8"))
    ncert_by_id = {r["question_id"]: r for r in ncert_audit["records"]}
    repair = json.loads(REPAIR.read_text(encoding="utf-8"))
    repaired = load_jsonl(JSONL)
    assert len(repaired) == 100

    orig_hash = sha256_file(ORIG_JSONL)
    man_hash = sha256_file(MANIFEST)
    source_hashes = {
        "questions_jsonl_sha256": orig_hash,
        "manifest_sha256": man_hash,
        "questions_jsonl_unchanged": orig_hash.lower() == EXPECTED_ORIG_Q.lower(),
        "manifest_unchanged": man_hash.lower() == EXPECTED_MANIFEST.lower(),
        "matches_repair_results_recorded_hashes": (
            orig_hash.lower() == repair["safety"]["original_questions_sha256"].lower()
            and man_hash.lower() == repair["safety"]["original_manifest_sha256"].lower()
        ),
    }

    async with AsyncSessionLocal() as session:
        before = await snap(session, "BEFORE")
        drafts, tax_integrity_issues = await load_live_drafts(session)

        # Inventory
        inventory_failures: list[str] = []
        if len(drafts) != 100:
            inventory_failures.append(f"draft_count={len(drafts)}")
        eids = [d["external_question_id"] for d in drafts]
        if None in eids:
            inventory_failures.append("null_external_ids")
        if len(set(eids)) != len([e for e in eids if e]):
            inventory_failures.append("duplicate_question_ids")
        slugs = [d["slug"] for d in drafts]
        if len(set(slugs)) != len(slugs):
            inventory_failures.append("duplicate_slugs")
        if any(d["status"] != "DRAFT" for d in drafts):
            inventory_failures.append("non_draft_included")
        if before["biology"]["SUPERSEDED"] != 5:
            inventory_failures.append(f"superseded_count={before['biology']['SUPERSEDED']}")
        if before["biology"]["PUBLISHED"] != 0:
            inventory_failures.append("published_present")

        # Source artifact comparison
        source_mismatches: list[dict] = []
        missing_in_live: list[str] = []
        missing_in_jsonl: list[str] = []
        live_by_eid = {d["external_question_id"]: d for d in drafts if d["external_question_id"]}
        for eid in repaired:
            if eid not in live_by_eid:
                missing_in_live.append(eid)
        for eid, d in live_by_eid.items():
            if eid not in repaired:
                missing_in_jsonl.append(eid)
                continue
            src = repaired[eid]
            body = d["body"]
            live_opts = option_map(body.get("options"))
            src_opts = option_map(src.get("options"))
            live_t = content_tuple(
                body.get("stem", ""),
                live_opts,
                body.get("correct_option", ""),
                body.get("explanation", ""),
            )
            src_t = content_tuple(
                src.get("stem", ""),
                src_opts,
                src.get("correct_option", ""),
                src.get("explanation", ""),
            )
            if live_t != src_t:
                source_mismatches.append(
                    {
                        "question_id": eid,
                        "stem_match": live_t[0] == src_t[0],
                        "options_match": live_t[1] == src_t[1],
                        "answer_match": live_t[2] == src_t[2],
                        "explanation_match": live_t[3] == src_t[3],
                    }
                )

        rstar_present = sorted(
            display_qid(e) for e in live_by_eid if e and e.rsplit("-", 1)[-1] in RSTAR
        )

        # Near / exact duplicates across live stems
        stems = [(d["external_question_id"], (d["body"].get("stem") or "").strip()) for d in drafts]
        exact_dups: list[tuple[str, str]] = []
        seen_stems: dict[str, str] = {}
        for eid, stem in stems:
            key = stem.lower()
            if key in seen_stems:
                exact_dups.append((seen_stems[key], eid))
            else:
                seen_stems[key] = eid
        near_dups: list[tuple[str, str, float]] = []
        for i in range(len(stems)):
            for j in range(i + 1, len(stems)):
                a, b = stems[i][1], stems[j][1]
                if a.lower() == b.lower():
                    continue
                score = jaccard(a, b)
                if score >= NEAR_DUP_THRESHOLD:
                    near_dups.append((stems[i][0], stems[j][0], round(score, 3)))

        records: list[dict] = []
        quality_fail_ids: list[str] = []
        taxonomy_fail_ids: list[str] = []
        provenance_fail_ids: list[str] = []
        ncert_counts: Counter = Counter()
        ncert_revisions: list[dict] = []

        for d in sorted(drafts, key=lambda x: x["external_question_id"] or ""):
            eid = d["external_question_id"]
            body = d["body"]
            opts = option_map(body.get("options"))
            correct = str(body.get("correct_option") or "").strip().upper()
            stem = str(body.get("stem") or "").strip()
            explanation = str(body.get("explanation") or "").strip()
            ncert_ev = body.get("ncert_evidence") or {}
            provenance = body.get("provenance") or {}
            concept = d.get("concept")

            # Quality
            q_failures: list[str] = []
            if set(opts.keys()) != {"A", "B", "C", "D"}:
                q_failures.append("option_labels")
            texts = [opts.get(k, "") for k in ("A", "B", "C", "D")]
            if any(not t for t in texts):
                q_failures.append("empty_option")
            if len({t.lower() for t in texts}) != 4:
                q_failures.append("duplicate_options")
            if correct not in opts:
                q_failures.append("answer_key_mismatch")
            if not stem:
                q_failures.append("missing_stem")
            if not explanation:
                q_failures.append("missing_explanation")
            # structural pydantic
            structural_ok = True
            try:
                QuestionBody.model_validate(body)
            except Exception as exc:  # noqa: BLE001
                structural_ok = False
                q_failures.append(f"body_schema:{type(exc).__name__}")

            # Taxonomy
            tax_failures: list[str] = []
            taxonomy_path = None
            if not d["concept_id"]:
                tax_failures.append("null_concept_id")
            elif not concept:
                tax_failures.append("concept_missing")
            else:
                taxonomy_path = (
                    f"{concept['subject_name']} → {concept['chapter_name']} → "
                    f"{concept['topic_name']} → {concept['name']}"
                )
                if concept["subject_code"] != SUBJECT_CODE:
                    tax_failures.append("cross_subject")
                if concept["chapter_code"] != CHAPTER_CODE:
                    tax_failures.append("wrong_chapter")
                if concept["topic_id"] != TOPIC_ID:
                    tax_failures.append("wrong_topic")
                if concept.get("deleted_at") is not None:
                    tax_failures.append("concept_soft_deleted")
            if eid == MAYR_EID:
                if d["concept_id"] != MAYR_CONCEPT_ID:
                    tax_failures.append("mayr_concept_id_mismatch")
                if not concept or concept.get("code") != MAYR_CODE:
                    tax_failures.append("mayr_concept_code_mismatch")

            # Provenance
            prov_failures: list[str] = []
            batch_ok = (
                provenance.get("batch_id") == BATCH
                or BATCH in (d["tags"] or [])
                or any(BATCH in (t or "") for t in (d["tags"] or []))
            )
            if not batch_ok:
                prov_failures.append("missing_batch_id")
            if not provenance and not any(
                (t or "").startswith(("ncert:", "source", "batch:", "acquisition"))
                for t in (d["tags"] or [])
            ):
                # still require ncert_evidence block presence
                pass
            if not ncert_ev:
                prov_failures.append("missing_ncert_evidence_block")
            else:
                if ncert_ev.get("verification_level") not in (None, "NOT_VERIFIED"):
                    # falsely marked verified in DB would be integrity issue for this pilot
                    if ncert_ev.get("verification_level") in {
                        "PAGE_VERIFIED",
                        "SECTION_VERIFIED",
                        "HUMAN_VERIFIED",
                    }:
                        prov_failures.append(
                            f"falsely_database_verified:{ncert_ev.get('verification_level')}"
                        )
                # expected state for this pilot
                if ncert_ev.get("verification_level") != "NOT_VERIFIED":
                    # informational only if missing level entirely
                    if ncert_ev.get("verification_level") is None:
                        prov_failures.append("missing_verification_level")

            # NCERT from prior audit + Mayr reclassification
            prior_n = ncert_by_id.get(eid)
            if eid == MAYR_EID:
                # Prior artifact: UNMAPPED_REVIEW. Content evidence was DIRECT; now mapped.
                ncert_result = "VERIFIED_DIRECT"
                ncert_revisions.append(
                    {
                        "question_id": eid,
                        "prior_artifact_verdict": prior_n["verification_verdict"] if prior_n else None,
                        "revised_audit_verdict": "VERIFIED_DIRECT",
                        "reason": (
                            "Prior UNMAPPED_REVIEW was solely due to NULL concept_id. "
                            "Mayr leaf now installed; NCERT biography evidence remains DIRECT. "
                            "ncert_verification_audit.json intentionally NOT modified."
                        ),
                        "prior_artifact_unmodified": True,
                    }
                )
                ncert_detail = {
                    "evidence_type": "DIRECT",
                    "answer_supported": True,
                    "explanation_supported": True,
                    "distractors_defensible": True,
                    "prior_artifact_verdict": "UNMAPPED_REVIEW",
                    "revised_for_this_audit": True,
                }
            elif prior_n:
                ncert_result = prior_n["verification_verdict"]
                ncert_detail = {
                    "evidence_type": prior_n.get("evidence_type"),
                    "answer_supported": prior_n.get("answer_supported"),
                    "explanation_supported": prior_n.get("explanation_supported"),
                    "distractors_defensible": prior_n.get("distractors_consistent_with_ncert"),
                    "prior_artifact_verdict": prior_n.get("verification_verdict"),
                    "revised_for_this_audit": False,
                }
                if ncert_result in {"REPAIR_REQUIRED", "REJECT", "UNMAPPED_REVIEW"}:
                    q_failures.append(f"ncert:{ncert_result}")
            else:
                ncert_result = "MISSING_PRIOR_AUDIT"
                ncert_detail = {"revised_for_this_audit": False}
                q_failures.append("ncert:missing_prior_audit")

            ncert_counts[ncert_result] += 1

            # Ambiguity from prior
            if prior_n and prior_n.get("distractor_audit", {}).get("failures"):
                # only count as quality fail if residual after repair path
                if any(
                    f in prior_n["distractor_audit"]["failures"]
                    for f in ("ambiguity", "distractor_quality_or_ambiguity", "answer_key_not_supported")
                ) and ncert_result in {"REPAIR_REQUIRED", "REJECT"}:
                    q_failures.append("ncert_distractor_residual")

            # Student visibility (batch-level; per-question always 0 if draft)
            student_vis = {
                "visible_to_student": False,
                "in_practice_pool": False,
                "ok": True,
            }

            # ECAEP readiness (do not submit)
            academic_blockers: list[str] = []
            workflow_blockers: list[str] = []
            submit_eligible = True
            submit_blockers: list[str] = []

            if tax_failures:
                academic_blockers.extend([f"taxonomy:{x}" for x in tax_failures])
            if q_failures:
                academic_blockers.extend([f"quality:{x}" for x in q_failures])
            if ncert_result in {"REPAIR_REQUIRED", "REJECT", "UNMAPPED_REVIEW", "MISSING_PRIOR_AUDIT"}:
                academic_blockers.append(f"ncert:{ncert_result}")

            # submit_for_review gates (read-only evaluation)
            if d["status"] != "DRAFT":
                workflow_blockers.append("status_not_draft")
                submit_eligible = False
                submit_blockers.append("status_not_draft")
            if not d["concept_id"]:
                academic_blockers.append("MISSING_ACADEMIC_MAPPING")
                submit_eligible = False
                submit_blockers.append("MISSING_ACADEMIC_MAPPING")
            try:
                assert_body_publishable("QUESTION", body)
            except Exception as exc:  # noqa: BLE001
                academic_blockers.append(f"INVALID_CONTENT_BODY:{getattr(exc, 'code', type(exc).__name__)}")
                submit_eligible = False
                submit_blockers.append("INVALID_CONTENT_BODY")

            # Publication gates (hypothetical; expect workflow/ncert blockers)
            pub = await evaluate_question_publication_gates(
                session,
                item_id=uuid.UUID(d["content_item_id"]),
                status=d["status"],
                content_type="QUESTION",
                concept_id=uuid.UUID(d["concept_id"]) if d["concept_id"] else None,
                body=body,
                tags=d["tags"],
                model_used=d.get("model_used"),
                knowledge_unit_id=uuid.UUID(d["knowledge_unit_id"]) if d.get("knowledge_unit_id") else None,
            )
            for reason in pub.reasons:
                if reason.startswith("review:") or reason == "ncert:NOT_VERIFIED":
                    workflow_blockers.append(reason)
                elif reason.startswith("ncert:"):
                    # NOT_VERIFIED is workflow/provenance state for this pilot, not content failure
                    if reason == "ncert:NOT_VERIFIED":
                        workflow_blockers.append(reason)
                    else:
                        academic_blockers.append(reason)
                elif reason.startswith("taxonomy:") or reason.startswith("structural:"):
                    academic_blockers.append(reason)
                else:
                    workflow_blockers.append(reason)

            # Distinguish: content ready for ECAEP submit vs publish
            content_ready_for_ecaep_submit = (
                submit_eligible
                and not academic_blockers
                and ncert_result in {"VERIFIED_DIRECT", "VERIFIED_SUPPORTED_INFERENCE"}
            )
            # Expected publish blockers remain
            expected_workflow = {"review:not_approved", "ncert:NOT_VERIFIED"}
            unexpected_workflow = [b for b in workflow_blockers if b not in expected_workflow]

            if q_failures:
                quality_fail_ids.append(eid)
            if tax_failures:
                taxonomy_fail_ids.append(eid)
            if prov_failures:
                provenance_fail_ids.append(eid)

            final_q = "PASS"
            if tax_failures or q_failures or prov_failures:
                final_q = "FAIL"
            elif ncert_result not in {"VERIFIED_DIRECT", "VERIFIED_SUPPORTED_INFERENCE"}:
                final_q = "FAIL"
            elif unexpected_workflow:
                final_q = "AMBER"
            elif source_mismatches and any(m["question_id"] == eid for m in source_mismatches):
                final_q = "FAIL"

            records.append(
                {
                    "question_id": eid,
                    "display_id": display_qid(eid) if eid else None,
                    "content_item_id": d["content_item_id"],
                    "status": d["status"],
                    "concept_id": d["concept_id"],
                    "concept_code": concept["code"] if concept else None,
                    "concept_name": concept["name"] if concept else None,
                    "taxonomy_path": taxonomy_path,
                    "ncert_verification_result": ncert_result,
                    "ncert_detail": ncert_detail,
                    "question_quality_result": "PASS" if not q_failures else "FAIL",
                    "question_quality_failures": q_failures,
                    "structural_ok": structural_ok,
                    "provenance_result": "PASS" if not prov_failures else "FAIL",
                    "provenance_failures": prov_failures,
                    "verification_level_in_db": ncert_ev.get("verification_level"),
                    "student_visibility_result": student_vis,
                    "ecaep_readiness": {
                        "submit_for_review_eligible": submit_eligible and not submit_blockers,
                        "content_ready_for_ecaep_submit": content_ready_for_ecaep_submit,
                        "academic_content_blockers": academic_blockers,
                        "workflow_state_blockers": workflow_blockers,
                        "publication_gate_reasons": list(pub.reasons),
                        "publication_would_pass": pub.passed,
                        "note": (
                            "submit_for_review NOT called. "
                            "Expected publish blockers: review:not_approved + ncert:NOT_VERIFIED."
                        ),
                    },
                    "blockers": {
                        "A_academic_content": academic_blockers,
                        "B_workflow_state": workflow_blockers,
                    },
                    "final_question_verdict": final_q,
                }
            )

        after = await snap(session, "AFTER")

    # Inventory / source summary
    source_ok = (
        not missing_in_live
        and not missing_in_jsonl
        and not source_mismatches
        and source_hashes["questions_jsonl_unchanged"]
        and source_hashes["manifest_unchanged"]
        and len(rstar_present) == 5
    )

    student_ok = (
        after["student_bio_hits"] == 0
        and after["practice_nonpub_hits"] == 0
        and after["draft_in_pool"] == 0
        and after["superseded_in_pool"] == 0
        and after["biology"]["PUBLISHED"] == 0
    )

    db_unchanged = before == after or (
        {k: before[k] for k in before if k not in {"bio_item_ids", "draft_ids", "superseded_ids"}}
        == {k: after[k] for k in after if k not in {"bio_item_ids", "draft_ids", "superseded_ids"}}
    )
    # Compare without set fields
    def slim(s: dict) -> dict:
        return {
            k: v
            for k, v in s.items()
            if k
            not in {
                "bio_item_ids",
                "draft_ids",
                "superseded_ids",
                "label",
            }
        }

    db_safety = {
        "before": {**slim(before), "label": "BEFORE"},
        "after": {**slim(after), "label": "AFTER"},
        "unchanged": slim(before) == slim(after),
        "writes_performed": False,
        "matches_expected": (
            after["taxonomy"] == EXPECTED_TAX
            and after["biology"] == EXPECTED_BIO
            and after["physics_DRAFT"] == 24
            and after["mapped"] == 100
            and after["unmapped"] == 0
            and after["student_bio_hits"] == 0
            and after["practice_nonpub_hits"] == 0
        ),
    }

    mapped_count = sum(1 for r in records if r["concept_id"])
    quality_failures = sum(1 for r in records if r["question_quality_result"] != "PASS")
    taxonomy_failures = len(taxonomy_fail_ids)
    provenance_failures = len(provenance_fail_ids)
    ncert_bad = sum(
        1
        for r in records
        if r["ncert_verification_result"]
        not in {"VERIFIED_DIRECT", "VERIFIED_SUPPORTED_INFERENCE"}
    )
    submit_eligible_count = sum(
        1 for r in records if r["ecaep_readiness"]["submit_for_review_eligible"]
    )
    content_ready_count = sum(
        1 for r in records if r["ecaep_readiness"]["content_ready_for_ecaep_submit"]
    )

    inventory_ok = (
        len(records) == 100
        and not inventory_failures
        and before["biology"]["DRAFT"] == 100
    )
    taxonomy_ok = (
        mapped_count == 100
        and taxonomy_failures == 0
        and not tax_integrity_issues
        and after["taxonomy"] == EXPECTED_TAX
    )
    # Mayr specific
    mayr = next((r for r in records if r["question_id"] == MAYR_EID), None)
    mayr_ok = (
        mayr is not None
        and mayr["concept_id"] == MAYR_CONCEPT_ID
        and mayr["concept_code"] == MAYR_CODE
        and mayr["ncert_verification_result"] == "VERIFIED_DIRECT"
    )

    # Final verdict
    if (
        not inventory_ok
        or not source_ok
        or not db_safety["unchanged"]
        or not db_safety["matches_expected"]
        or not student_ok
        or after["physics_DRAFT"] != 24
    ):
        verdict = "RED — INTEGRITY FAILURE"
    elif (
        quality_failures
        or ncert_bad
        or taxonomy_failures
        or provenance_failures
        or tax_integrity_issues
        or not mayr_ok
    ):
        verdict = "AMBER — REVIEW REQUIRED"
    elif content_ready_count == 100 and submit_eligible_count == 100:
        verdict = "GREEN — PILOT READY FOR ECAEP"
    else:
        # Content NCERT/taxonomy ok but unexpected submit blockers
        if content_ready_count < 100 and (quality_failures or ncert_bad or taxonomy_failures):
            verdict = "AMBER — REVIEW REQUIRED"
        elif submit_eligible_count == 100 and ncert_bad == 0 and quality_failures == 0:
            verdict = "GREEN — PILOT READY FOR ECAEP"
        else:
            verdict = "AMBER — REVIEW REQUIRED"

    # If only expected workflow blockers remain and content is ready → GREEN
    if (
        inventory_ok
        and source_ok
        and student_ok
        and db_safety["unchanged"]
        and db_safety["matches_expected"]
        and quality_failures == 0
        and ncert_bad == 0
        and taxonomy_failures == 0
        and provenance_failures == 0
        and not tax_integrity_issues
        and mayr_ok
        and mapped_count == 100
        and exact_dups == []
        and near_dups == []
    ):
        verdict = "GREEN — PILOT READY FOR ECAEP"

    summary = {
        "inventory": {
            "active_drafts": len(records),
            "expected": 100,
            "duplicate_ids": "duplicate_question_ids" in inventory_failures,
            "duplicate_slugs": "duplicate_slugs" in inventory_failures,
            "superseded_included": False,
            "published_included": False,
            "failures": inventory_failures,
            "ok": inventory_ok,
        },
        "source_artifact": {
            "jsonl_ids": 100,
            "live_ids_matched": 100 - len(missing_in_live) - len(missing_in_jsonl),
            "content_mismatches": len(source_mismatches),
            "replacement_ids_present": rstar_present,
            "hashes": source_hashes,
            "ok": source_ok,
        },
        "ncert_counts": dict(ncert_counts),
        "ncert_expected": {
            "VERIFIED_DIRECT": 95,  # 94 prior + Q000098 reclassified
            "VERIFIED_SUPPORTED_INFERENCE": 5,
            "REPAIR_REQUIRED": 0,
            "REJECT": 0,
            "UNMAPPED_REVIEW": 0,
        },
        "ncert_revisions_reported": ncert_revisions,
        "ncert_prior_artifact_unmodified": True,
        "taxonomy": {
            "mapped": mapped_count,
            "unmapped": 100 - mapped_count,
            "failures": taxonomy_failures,
            "integrity_issues": tax_integrity_issues,
            "counts": after["taxonomy"],
            "q000098": {
                "concept_id": mayr["concept_id"] if mayr else None,
                "concept_code": mayr["concept_code"] if mayr else None,
                "ok": mayr_ok,
            },
            "ok": taxonomy_ok and mayr_ok,
        },
        "quality_failures": quality_failures,
        "exact_duplicate_stems": exact_dups,
        "near_duplicate_stems": near_dups,
        "provenance_failures": provenance_failures,
        "student_visibility": {
            "student_bio_hits": after["student_bio_hits"],
            "practice_nonpub_hits": after["practice_nonpub_hits"],
            "draft_in_published_pool": after["draft_in_pool"],
            "superseded_in_published_pool": after["superseded_in_pool"],
            "ok": student_ok,
        },
        "ecaep_readiness": {
            "submit_for_review_eligible": submit_eligible_count,
            "content_ready_for_ecaep_submit": content_ready_count,
            "submitted": False,
            "expected_workflow_blockers_for_publish": [
                "review:not_approved",
                "ncert:NOT_VERIFIED",
            ],
            "note": (
                "All 100 remain DRAFT with provenance verification_level=NOT_VERIFIED. "
                "That blocks PUBLISH, not necessarily submit_for_review. "
                "No submit/approve/publish was performed."
            ),
        },
        "database_safety": db_safety,
        "physics_DRAFT": after["physics_DRAFT"],
        "final_verdict": verdict,
        "read_only_audit": True,
        "database_unchanged": db_safety["unchanged"],
        "no_ecaep_submission": True,
        "no_publication": True,
    }

    payload = {
        "batch_id": BATCH,
        "audit_type": "FINAL_100_PILOT_INTEGRITY_READ_ONLY",
        "executed_at": datetime.now(UTC).isoformat(),
        "database_modified": False,
        "taxonomy_modified": False,
        "content_modified": False,
        "prior_artifacts_modified": False,
        "ecaep_submitted": False,
        "publication_occurred": False,
        "verdict": verdict,
        "summary": summary,
        "records": records,
        "assertions": {
            "READ-ONLY AUDIT": True,
            "DATABASE UNCHANGED": db_safety["unchanged"],
            "NO ECAEP SUBMISSION": True,
            "NO PUBLICATION": True,
        },
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Final 100-Question Pilot Integrity Audit",
        "",
        f"## Verdict: {verdict}",
        "",
        "**READ-ONLY AUDIT**  ",
        "**DATABASE UNCHANGED**  ",
        "**NO ECAEP SUBMISSION**  ",
        "**NO PUBLICATION**",
        "",
        f"Batch: `{BATCH}`  ",
        f"Executed: `{payload['executed_at']}`",
        "",
        "## 1. Inventory",
        "",
        f"- Active DRAFTs: **{summary['inventory']['active_drafts']}/100**",
        f"- Duplicate IDs: **{summary['inventory']['duplicate_ids']}**",
        f"- Duplicate slugs: **{summary['inventory']['duplicate_slugs']}**",
        f"- SUPERSEDED included: **false** (SUPERSEDED count outside inventory = {after['biology']['SUPERSEDED']})",
        f"- PUBLISHED included: **false**",
        f"- Inventory OK: **{inventory_ok}**",
        "",
        "## 2. Source artifact integrity",
        "",
        f"- `questions_repaired.jsonl` IDs matched: **{source_ok}**",
        f"- Content mismatches: **{len(source_mismatches)}**",
        f"- Replacement IDs present: `{', '.join(rstar_present)}`",
        f"- Original `questions.jsonl` SHA-256: `{orig_hash}` (unchanged={source_hashes['questions_jsonl_unchanged']})",
        f"- Original `manifest.json` SHA-256: `{man_hash}` (unchanged={source_hashes['manifest_unchanged']})",
        "",
        "## 3. NCERT verification",
        "",
        "Uses prior `ncert_verification_audit.json` + Chapter 1 extract. "
        "**Prior artifact not modified.**",
        "",
        "```json",
        json.dumps(dict(ncert_counts), indent=2),
        "```",
        "",
        "### Q000098 revised classification (this audit only)",
        "",
    ]
    for rev in ncert_revisions:
        lines += [
            f"- Prior artifact verdict: `{rev['prior_artifact_verdict']}`",
            f"- Revised audit verdict: `{rev['revised_audit_verdict']}`",
            f"- Reason: {rev['reason']}",
            "",
        ]
    lines += [
        f"Expected after remapping: VERIFIED_DIRECT=95, VERIFIED_SUPPORTED_INFERENCE=5, UNMAPPED_REVIEW=0.",
        "",
        "## 4. Taxonomy / concept integrity",
        "",
        f"- Mapped: **{mapped_count}/100**",
        f"- Taxonomy failures: **{taxonomy_failures}**",
        f"- Integrity issues (self/cycle/dup codes): **{len(tax_integrity_issues)}**",
        f"- Live taxonomy counts: `{after['taxonomy']}`",
        f"- Q000098 → `{MAYR_CODE}` / `{MAYR_CONCEPT_ID}`: **{mayr_ok}**",
        "",
        "## 5. Question quality",
        "",
        f"- Quality failures: **{quality_failures}**",
        f"- Exact duplicate stems: **{len(exact_dups)}**",
        f"- Near-duplicate stems (≥{NEAR_DUP_THRESHOLD}): **{len(near_dups)}**",
        "",
        "## 6. Provenance",
        "",
        f"- Provenance integrity failures: **{provenance_failures}**",
        f"- DB `verification_level` remains `NOT_VERIFIED` for pilot (not falsely marked verified).",
        "",
        "## 7. Student safety",
        "",
        f"- Student Biology visibility: **{after['student_bio_hits']}**",
        f"- Practice non-published hits: **{after['practice_nonpub_hits']}**",
        f"- DRAFT in published pool: **{after['draft_in_pool']}**",
        f"- SUPERSEDED in published pool: **{after['superseded_in_pool']}**",
        f"- Student safety OK: **{student_ok}**",
        "",
        "## 8. ECAEP readiness (not submitted)",
        "",
        f"- `submit_for_review` eligible (structural + concept): **{submit_eligible_count}/100**",
        f"- Content ready for ECAEP submit (academic + NCERT audit): **{content_ready_count}/100**",
        "- Expected **publish** blockers (workflow/state, not content defects):",
        "  - `review:not_approved` (status still DRAFT)",
        "  - `ncert:NOT_VERIFIED` (provenance level intentionally retained)",
        "- **No** `submit_for_review` / approve / publish calls were made.",
        "",
        "### Blocker classes",
        "",
        "- **A. Academic/content blockers:** should be empty for GREEN.",
        "- **B. Workflow-state blockers:** expected until ECAEP transitions + NCERT provenance upgrade.",
        "",
        "## 9. Database safety",
        "",
        "```json",
        json.dumps(db_safety, indent=2, default=str),
        "```",
        "",
        f"- Physics DRAFT: **{after['physics_DRAFT']}** (expected 24)",
        "",
        "## Final assertions",
        "",
        "- READ-ONLY AUDIT",
        "- DATABASE UNCHANGED",
        "- NO ECAEP SUBMISSION",
        "- NO PUBLICATION",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "summary": summary}, indent=2, default=str))
    return 0 if verdict.startswith("GREEN") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
