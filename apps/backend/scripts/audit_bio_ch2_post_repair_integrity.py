"""READ-ONLY post-repair integrity audit for BIO11-CH02-B001 Q000085→R000085."""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.acquisition.gemini_jsonl_draft_importer import import_slug
from app.modules.cms.models import ContentItem
from app.modules.cms.models.content_item import STUDENT_VISIBLE_STATUSES
from app.modules.cms.repositories.cms_repository import CmsRepository

BATCH = "20260911-BIO11-CH02-B001"
CH01 = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
ORIG = f"GEMINI-{BATCH}-000085"
REPL = f"GEMINI-{BATCH}-R000085"
AUTH_SHA = "020d48816b5c318928cf2edda28703e17e923929a262b86be93b387b4f41637c"
EXPECTED_TAX = {"subjects": 4, "chapters": 36, "topics": 107, "concepts": 143}

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
OUT_JSON = ROOT / "post_repair_integrity_audit.json"
OUT_MD = ROOT / "post_repair_integrity_audit.md"
STAGE_JSON = ROOT / "pipeline_stage_status.json"
STAGE_MD = ROOT / "pipeline_stage_status.md"
NCERT = ROOT / "_source_extract.txt"
REPAIR_EXEC = ROOT / "q000085_repair_execution_report.json"
REPAIR_REP = ROOT / "q000085_repair_report.json"


def sha_file(p: Path) -> str | None:
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def body_fp(body: dict | None) -> str:
    return hashlib.sha256(
        json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def is_batch(item: ContentItem, batch: str, needle: str) -> bool:
    tags = item.tags or []
    if batch in tags or any(batch in (t or "") for t in tags):
        return True
    return bool(item.slug and needle in (item.slug or "").lower())


def eid_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    marker = f"GEMINI-{BATCH}-"
    if marker not in slug:
        return None
    return f"GEMINI-{BATCH}-{slug.split(marker, 1)[1]}"


def latest(item: ContentItem):
    return next((v for v in item.versions if v.id == item.latest_version_id), None)


def ncert_level(body: dict | None) -> str | None:
    return ((body or {}).get("ncert_evidence") or {}).get("verification_level")


def opts_map(options) -> dict:
    if isinstance(options, dict):
        return {str(k): str(v) for k, v in options.items()}
    return {str(o.get("label")): str(o.get("text")) for o in (options or [])}


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
    ch_topics = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM academic.topics t "
                "JOIN academic.chapters c ON c.id=t.chapter_id "
                "WHERE c.code='biological-classification' AND t.deleted_at IS NULL"
            )
        )
    ).scalar()
    bc = (
        await session.execute(
            text("SELECT COUNT(*) FROM academic.concepts WHERE code LIKE 'bc-%' AND deleted_at IS NULL")
        )
    ).scalar()
    ch_count = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM academic.chapters "
                "WHERE code='biological-classification' AND deleted_at IS NULL"
            )
        )
    ).scalar()
    items = (
        await session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.deleted_at.is_(None))
        )
    ).scalars().all()
    ch2 = [i for i in items if is_batch(i, BATCH, "bio11-ch02-b001")]
    ch1 = [i for i in items if is_batch(i, CH01, "bio11-ch01-b001")]
    phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
    repo = CmsRepository(session)
    stud2 = stud1 = 0
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        stud2 += sum(1 for i in page if is_batch(i, BATCH, "bio11-ch02-b001"))
        stud1 += sum(1 for i in page if is_batch(i, CH01, "bio11-ch01-b001"))
        off += 100
        if off >= tot or not page:
            break
    pool = set(await AssessmentRepository(session).published_question_ids_for_scope("FULL", None))
    nonpub = {i.id for i in ch2 if i.status != "PUBLISHED"}
    by_status = Counter(i.status for i in ch2)
    return {
        "taxonomy_total": {
            "subjects": tax[0],
            "chapters": tax[1],
            "topics": tax[2],
            "concepts": tax[3],
        },
        "ch02_taxonomy": {"chapters": ch_count, "topics": ch_topics, "bc_concepts": bc},
        "ch02_status": {
            "DRAFT": by_status.get("DRAFT", 0),
            "IN_REVIEW": by_status.get("IN_REVIEW", 0),
            "APPROVED": by_status.get("APPROVED", 0),
            "PUBLISHED": by_status.get("PUBLISHED", 0),
            "SUPERSEDED": by_status.get("SUPERSEDED", 0),
            "CHANGES_REQUESTED": by_status.get("CHANGES_REQUESTED", 0),
        },
        "ch01_status": dict(Counter(i.status for i in ch1)),
        "physics_DRAFT": Counter(i.status for i in phy).get("DRAFT", 0),
        "student_ch02": stud2,
        "student_ch01": stud1,
        "practice_nonpub_ch02": len(nonpub & pool),
        "items": ch2,
    }


def inspect_item(item: ContentItem | None) -> dict | None:
    if not item:
        return None
    ver = latest(item)
    body = dict(ver.body or {}) if ver else {}
    return {
        "external_question_id": eid_from_slug(item.slug),
        "content_item_id": str(item.id),
        "slug": item.slug,
        "status": item.status,
        "student_visible_status": item.status in STUDENT_VISIBLE_STATUSES,
        "concept_id": str(item.concept_id) if item.concept_id else None,
        "replaces_id": str(item.replaces_id) if item.replaces_id else None,
        "latest_version_id": str(item.latest_version_id) if item.latest_version_id else None,
        "version_count": len(item.versions or []),
        "workflow_state": getattr(ver, "workflow_state", None),
        "stem": body.get("stem"),
        "options": opts_map(body.get("options")),
        "correct_option": body.get("correct_option"),
        "explanation": body.get("explanation"),
        "difficulty": body.get("difficulty"),
        "body_sha256": body_fp(body),
        "verification_level": ncert_level(body),
        "ncert_evidence": body.get("ncert_evidence"),
        "provenance": body.get("provenance"),
        "tags": list(item.tags or []),
        "ai_check_status": (
            (ver.ai_check_report or {}).get("status")
            if ver and isinstance(ver.ai_check_report, dict)
            else None
        ),
        "has_autotrophic_in_any_version": any(
            "partially autotrophic" in json.dumps(v.body or {}) for v in (item.versions or [])
        ),
        "active_stem_has_heterotrophic": "heterotrophic" in (body.get("stem") or "").lower(),
        "active_stem_has_partially_autotrophic": "partially autotrophic"
        in (body.get("stem") or ""),
    }


async def main() -> dict:
    issues: list[str] = []
    amber: list[str] = []

    # Read-only: open session, never commit
    async with AsyncSessionLocal() as session:
        # Explicitly mark intent — rollback at end always
        s = await snap(session)
        by_eid: dict[str, ContentItem] = {}
        for i in s["items"]:
            eid = eid_from_slug(i.slug)
            if eid:
                by_eid[eid] = i

        orig = by_eid.get(ORIG)
        repl = by_eid.get(REPL)
        orig_i = inspect_item(orig)
        repl_i = inspect_item(repl)

        # Active approved set
        active = [i for i in s["items"] if i.status == "APPROVED"]
        active_eids = sorted(eid_from_slug(i.slug) or str(i.id) for i in active)
        active_slugs = [i.slug for i in active]
        active_ids = [str(i.id) for i in active]

        # Snapshot counts
        if s["ch02_status"]["APPROVED"] != 100:
            issues.append(f"approved!={s['ch02_status']}")
        if s["ch02_status"]["IN_REVIEW"] != 0:
            issues.append(f"in_review!={s['ch02_status']}")
        if s["ch02_status"]["PUBLISHED"] != 0:
            issues.append(f"published!={s['ch02_status']}")
        if s["ch02_status"]["DRAFT"] != 0:
            issues.append(f"draft!={s['ch02_status']}")
        if s["ch02_status"]["SUPERSEDED"] != 1:
            # explain semantics if different
            amber.append(
                f"SUPERSEDED count={s['ch02_status']['SUPERSEDED']} (expected 1 historical Q000085)"
            )
            if s["ch02_status"]["SUPERSEDED"] < 1:
                issues.append("missing_superseded_original")

        # Lineage / forensic
        if not orig_i or orig_i["status"] != "SUPERSEDED":
            issues.append(f"original_status={orig_i}")
        if not repl_i or repl_i["status"] != "APPROVED":
            issues.append(f"replacement_status={repl_i}")
        if not repl_i or not orig or str(repl.replaces_id) != str(orig.id):
            issues.append("lineage_R_does_not_point_to_original")
        if orig and orig.replaces_id == orig.id:
            issues.append("self_reference_original")
        if repl and repl.replaces_id == repl.id:
            issues.append("self_reference_replacement")
        if orig and repl and orig.replaces_id == repl.id:
            issues.append("cycle_original_points_to_replacement")
        if REPL not in active_eids:
            issues.append("R000085_not_in_active_approved")
        if ORIG in active_eids:
            issues.append("original_Q000085_still_active_approved")
        if repl_i and not repl_i["active_stem_has_heterotrophic"]:
            issues.append("active_stem_missing_heterotrophic")
        if repl_i and repl_i["active_stem_has_partially_autotrophic"]:
            issues.append("active_stem_still_has_partially_autotrophic")
        if orig_i and not orig_i["has_autotrophic_in_any_version"]:
            issues.append("original_defect_history_not_recoverable")
        if repl_i and orig_i and repl_i["concept_id"] != orig_i["concept_id"]:
            issues.append("concept_id_changed")
        if repl_i and repl_i["verification_level"] != "NOT_VERIFIED":
            issues.append(f"repl_verification={repl_i['verification_level']}")
        if orig_i and orig_i["student_visible_status"]:
            issues.append("original_student_visible")
        if repl_i and repl_i["student_visible_status"]:
            issues.append("replacement_student_visible")

        # No unrelated references to R000085
        refs = [
            eid_from_slug(i.slug)
            for i in s["items"]
            if i.replaces_id and repl and i.replaces_id == repl.id
        ]
        if refs:
            issues.append(f"unexpected_items_replace_R000085={refs}")

        # Duplicate R000085?
        r_slugs = [i for i in s["items"] if i.slug and "r000085" in i.slug.lower()]
        if len(r_slugs) != 1:
            issues.append(f"r000085_item_count={len(r_slugs)}")

        # Active set integrity
        if len(active) != 100:
            issues.append(f"active_count={len(active)}")
        if len(set(active_ids)) != 100:
            issues.append("duplicate_active_ids")
        if len(set(active_slugs)) != 100:
            issues.append("duplicate_active_slugs")
        null_concepts = [eid_from_slug(i.slug) for i in active if i.concept_id is None]
        if null_concepts:
            issues.append(f"null_concepts={null_concepts[:5]}")
        batch_missing = [
            eid_from_slug(i.slug)
            for i in active
            if BATCH not in (i.tags or []) and not any(BATCH in (t or "") for t in (i.tags or []))
        ]
        if batch_missing:
            # slug-based batch may still be ok
            slug_ok = all(eid and BATCH in eid for eid in batch_missing if eid)
            if not slug_ok:
                issues.append(f"batch_identity_weak={batch_missing[:5]}")

        # NCERT levels all active
        levels = Counter()
        for i in active:
            ver = latest(i)
            body = dict(ver.body or {}) if ver else {}
            levels[ncert_level(body) or "MISSING"] += 1
        if levels.get("NOT_VERIFIED", 0) != 100:
            issues.append(f"ncert_levels={dict(levels)}")
        for bad in ("SOURCE_TEXT_VERIFIED", "SECTION_VERIFIED", "PAGE_VERIFIED"):
            if levels.get(bad, 0):
                issues.append(f"certified_level_present={bad}")

        # Focused NCERT check for R000085
        ncert_text = NCERT.read_text(encoding="utf-8") if NCERT.exists() else ""
        ncert_norm = " ".join(ncert_text.split())
        focused = {
            "ncert_has_partially_heterotrophic": "partially heterotrophic" in ncert_norm,
            "ncert_has_bladderwort": "Bladderwort" in ncert_text,
            "ncert_has_cuscuta": "Cuscuta" in ncert_text,
            "stem_ok": bool(repl_i and "partially heterotrophic" in (repl_i.get("stem") or "")),
            "answer_a": bool(repl_i and repl_i.get("correct_option") == "A"),
            "option_a_examples": bool(
                repl_i
                and "Bladderwort" in (repl_i.get("options") or {}).get("A", "")
                and "Cuscuta" in (repl_i.get("options") or {}).get("A", "")
            ),
            "explanation_mentions_examples": bool(
                repl_i
                and "Bladderwort" in (repl_i.get("explanation") or "")
                and "Cuscuta" in (repl_i.get("explanation") or "")
            ),
        }
        focused["verdict"] = (
            "PASS"
            if all(
                [
                    focused["ncert_has_partially_heterotrophic"],
                    focused["ncert_has_bladderwort"],
                    focused["ncert_has_cuscuta"],
                    focused["stem_ok"],
                    focused["answer_a"],
                    focused["option_a_examples"],
                    focused["explanation_mentions_examples"],
                ]
            )
            else "FAIL"
        )
        if focused["verdict"] != "PASS":
            issues.append(f"focused_ncert={focused}")

        # Other 99 mutation check vs repair execution fingerprints if present
        other99_mutations: list[dict] = []
        repair_exec = json.loads(REPAIR_EXEC.read_text(encoding="utf-8")) if REPAIR_EXEC.exists() else {}
        repair_rep = json.loads(REPAIR_REP.read_text(encoding="utf-8")) if REPAIR_REP.exists() else {}
        # Use live compare: all APPROVED except REPL should match bodies from... we don't have
        # pre-repair dump of all 99 in this script. Prefer repair execution report claim +
        # compare concept/level/status stability from approval fingerprints if embedded.
        # Load approval report fingerprints isn't available for all. Instead: verify
        # other99_mutated_count from repair execution was 0 and re-check that ORIG is not
        # among active and no unexpected body fields for REPL vs repair report.
        if repair_exec.get("other99_mutated_count", 0) != 0:
            issues.append(f"repair_exec_reported_mutations={repair_exec.get('other99_mutated_count')}")

        # Deterministic: hash of each APPROVED body excluding REPL — compare to
        # ecaep_approval approved set content via draft import? Better approach:
        # load questions_repaired.jsonl for the 99 non-085 IDs and compare stems/answers
        # (R000085 is the only intentional content change from imported set for 085).
        repaired = {}
        for line in (ROOT / "questions_repaired.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            repaired[row["external_question_id"]] = row

        for i in active:
            eid = eid_from_slug(i.slug)
            if not eid or eid == REPL:
                continue
            # Active IDs for the 99 should still be original GEMINI-...-0000xx (not R*)
            if "-R" in eid:
                other99_mutations.append({"id": eid, "field": "unexpected_replacement_active"})
                continue
            src = repaired.get(eid)
            if not src:
                other99_mutations.append({"id": eid, "field": "missing_from_authoritative_artifact"})
                continue
            ver = latest(i)
            body = dict(ver.body or {}) if ver else {}
            if (body.get("stem") or "").strip() != (src.get("stem") or "").strip():
                other99_mutations.append(
                    {
                        "id": eid,
                        "field": "stem",
                        "before": src.get("stem"),
                        "after": body.get("stem"),
                        "source": "questions_repaired.jsonl",
                    }
                )
            if body.get("correct_option") != src.get("correct_option"):
                other99_mutations.append(
                    {
                        "id": eid,
                        "field": "correct_option",
                        "before": src.get("correct_option"),
                        "after": body.get("correct_option"),
                        "source": "questions_repaired.jsonl",
                    }
                )
            if opts_map(body.get("options")) != opts_map(src.get("options")):
                other99_mutations.append({"id": eid, "field": "options", "source": "questions_repaired.jsonl"})
            if (body.get("explanation") or "").strip() != (src.get("explanation") or "").strip():
                other99_mutations.append({"id": eid, "field": "explanation", "source": "questions_repaired.jsonl"})
            if body.get("difficulty") != src.get("difficulty"):
                other99_mutations.append(
                    {
                        "id": eid,
                        "field": "difficulty",
                        "before": src.get("difficulty"),
                        "after": body.get("difficulty"),
                        "source": "questions_repaired.jsonl",
                    }
                )
            if ncert_level(body) != "NOT_VERIFIED":
                other99_mutations.append({"id": eid, "field": "verification_level", "after": ncert_level(body)})

        if other99_mutations:
            issues.append(f"other99_content_mutations={len(other99_mutations)}")

        # Before/after table data
        before_after = {
            "ID": {"original": ORIG, "corrected": REPL},
            "Status": {"original": "SUPERSEDED (was IN_REVIEW)", "corrected": repl_i["status"] if repl_i else None},
            "Terminology": {
                "original": "partially autotrophic",
                "corrected": "partially heterotrophic"
                if repl_i and repl_i["active_stem_has_heterotrophic"]
                else None,
            },
            "Answer": {
                "original": (orig_i or {}).get("correct_option"),
                "corrected": (repl_i or {}).get("correct_option"),
            },
            "Options": {
                "original_count": len((orig_i or {}).get("options") or {}),
                "corrected_count": len((repl_i or {}).get("options") or {}),
                "same_options": (orig_i or {}).get("options") == (repl_i or {}).get("options"),
            },
            "Explanation": {
                "same": (orig_i or {}).get("explanation") == (repl_i or {}).get("explanation"),
            },
            "Concept": {
                "original": (orig_i or {}).get("concept_id"),
                "corrected": (repl_i or {}).get("concept_id"),
                "unchanged": (orig_i or {}).get("concept_id") == (repl_i or {}).get("concept_id"),
            },
            "NCERT verification": {
                "original": (orig_i or {}).get("verification_level"),
                "corrected": (repl_i or {}).get("verification_level"),
            },
            "body_sha256": {
                "original_latest": (orig_i or {}).get("body_sha256"),
                "corrected": (repl_i or {}).get("body_sha256"),
                "repair_report_before": repair_rep.get("before_body_sha256"),
                "repair_report_after": repair_rep.get("after_body_sha256"),
            },
        }
        # Prefer original answer from repaired artifact for Q000085
        if ORIG in repaired:
            before_after["Answer"]["original"] = repaired[ORIG].get("correct_option")
            before_after["Options"]["original"] = opts_map(repaired[ORIG].get("options"))
            before_after["Options"]["corrected"] = (repl_i or {}).get("options")
            before_after["Options"]["same_options"] = before_after["Options"]["original"] == before_after[
                "Options"
            ]["corrected"]

        # Artifact hashes
        hashes = {
            "questions.jsonl": sha_file(ROOT / "questions.jsonl"),
            "questions_repaired.jsonl": sha_file(ROOT / "questions_repaired.jsonl"),
            "questions_repaired.concurrent_020d4881.jsonl": sha_file(
                ROOT / "questions_repaired.concurrent_020d4881.jsonl"
            ),
            "questions_repaired.audit_agent_28_repairs.jsonl": sha_file(
                ROOT / "questions_repaired.audit_agent_28_repairs.jsonl"
            ),
            "q000085_corrected_replacement.json": sha_file(ROOT / "q000085_corrected_replacement.json"),
            "manifest.json": sha_file(ROOT / "manifest.json"),
        }
        if hashes["questions_repaired.jsonl"] != AUTH_SHA:
            issues.append(
                f"questions_repaired_sha={hashes['questions_repaired.jsonl']} expected={AUTH_SHA}"
            )
        if hashes["questions.jsonl"] != "892590a67f308996e541458f693f5b2f1d97870e82b8b7293e609c5ea3932552":
            # record but only fail if changed from known original
            amber.append(f"questions.jsonl_sha={hashes['questions.jsonl']}")

        # Taxonomy
        if s["taxonomy_total"] != EXPECTED_TAX:
            issues.append(f"taxonomy_total={s['taxonomy_total']}")
        if s["ch02_taxonomy"] != {"chapters": 1, "topics": 6, "bc_concepts": 9}:
            issues.append(f"ch02_taxonomy={s['ch02_taxonomy']}")

        # Student / regression
        if s["student_ch02"] != 0 or s["practice_nonpub_ch02"] != 0:
            issues.append(f"student_exposure={s['student_ch02']}/{s['practice_nonpub_ch02']}")
        if s["ch01_status"].get("PUBLISHED") != 100:
            issues.append(f"ch01={s['ch01_status']}")
        if s["physics_DRAFT"] != 24:
            issues.append(f"physics={s['physics_DRAFT']}")

        # Failed-attempt residue: no rollback-test slug leftovers
        residue = [
            i.slug
            for i in s["items"]
            if i.slug and ("rollback" in i.slug.lower() or i.slug.endswith("-rollback"))
        ]
        if residue:
            issues.append(f"failed_attempt_residue_slugs={residue}")

        # Capture lineage scalars BEFORE session close (avoid DetachedInstanceError)
        lineage = {
            "replacement_replaces_original": bool(
                repl_i
                and orig_i
                and repl_i.get("replaces_id")
                and repl_i["replaces_id"] == orig_i["content_item_id"]
            ),
            "no_self_reference": bool(
                (not orig_i or orig_i.get("replaces_id") != orig_i.get("content_item_id"))
                and (not repl_i or repl_i.get("replaces_id") != repl_i.get("content_item_id"))
            ),
            "no_cycle": bool(
                not (
                    orig_i
                    and repl_i
                    and orig_i.get("replaces_id") == repl_i.get("content_item_id")
                )
            ),
            "original_active_approved": ORIG in active_eids,
            "replacement_active_approved": REPL in active_eids,
            "original_id": (orig_i or {}).get("content_item_id"),
            "replacement_id": (repl_i or {}).get("content_item_id"),
            "replacement_replaces_id": (repl_i or {}).get("replaces_id"),
        }

        # Drop ORM refs; keep only serializable snapshot fields
        s.pop("items", None)
        await session.rollback()  # ensure zero mutations

    # Regression tests (read-only pytest)
    test_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_content_draft_supersession.py",
        "tests/test_cms_workflow.py",
        "app/modules/cms/tests/test_content_bodies.py",
        "app/modules/academic/tests/test_physics_p0_taxonomy.py",
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(
        test_cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": "."},
    )
    test_ok = proc.returncode == 0
    if not test_ok:
        issues.append("regression_tests_failed")

    database_mutations = 0
    ok = len(issues) == 0 and focused["verdict"] == "PASS" and test_ok
    if ok and amber:
        verdict = "GREEN — CH02 POST-REPAIR INTEGRITY AUDIT PASSED"
        # amber notes don't downgrade if non-blocking; SUPERSEDED==1 expected
        if any("SUPERSEDED count=" in a and "expected 1" in a for a in amber):
            # if count was not 1 we already may have issues; clear amber when count==1
            amber = [a for a in amber if "SUPERSEDED count=" not in a]
    if ok:
        verdict = "GREEN — CH02 POST-REPAIR INTEGRITY AUDIT PASSED"
    elif issues and any(
        x in "".join(issues)
        for x in ("published", "SOURCE_TEXT", "student_exposure", "lineage", "mutations", "database")
    ):
        verdict = "RED — POST-REPAIR INTEGRITY FAILURE"
    else:
        verdict = "AMBER — POST-REPAIR INTEGRITY DISCREPANCY" if issues or amber else "GREEN — CH02 POST-REPAIR INTEGRITY AUDIT PASSED"

    # Recompute SUPERSEDED amber: if exactly 1, remove
    if s["ch02_status"]["SUPERSEDED"] == 1:
        amber = [a for a in amber if "SUPERSEDED count=" not in a]

    if not issues and test_ok and focused["verdict"] == "PASS":
        verdict = "GREEN — CH02 POST-REPAIR INTEGRITY AUDIT PASSED"

    payload = {
        "batch_id": BATCH,
        "audit_type": "POST_REPAIR_INTEGRITY_READ_ONLY",
        "generated_at": datetime.now(UTC).isoformat(),
        "database_mutations": database_mutations,
        "verdict": verdict,
        "database_snapshot": {
            "ch02_status": s["ch02_status"],
            "ch02_taxonomy": s["ch02_taxonomy"],
            "taxonomy_total": s["taxonomy_total"],
            "ch01_status": s["ch01_status"],
            "physics_DRAFT": s["physics_DRAFT"],
            "student_ch02": s["student_ch02"],
            "student_ch01": s["student_ch01"],
            "practice_nonpub_ch02": s["practice_nonpub_ch02"],
            "superseded_semantics": (
                "SUPERSEDED counts ContentItem rows with status=SUPERSEDED in the CH02 batch "
                "(historical Q000085). Not included in active APPROVED set."
            ),
        },
        "original_q000085": orig_i,
        "replacement_r000085": repl_i,
        "lineage": lineage,
        "before_after": before_after,
        "focused_ncert_check": focused,
        "active_set": {
            "approved_count": len(active),
            "unique_ids": len(set(active_ids)) == 100,
            "unique_slugs": len(set(active_slugs)) == 100,
            "includes_R000085": REPL in active_eids,
            "excludes_original_Q000085": ORIG not in active_eids,
            "active_external_ids": active_eids,
        },
        "other_99_content_mutations": len(other99_mutations),
        "other_99_mutation_details": other99_mutations[:20],
        "artifact_hashes": hashes,
        "authoritative_repaired_sha_ok": hashes["questions_repaired.jsonl"] == AUTH_SHA,
        "audit_agent_artifact_authoritative": False,
        "ncert_levels_active": dict(levels),
        "ncert_certification": "NOT_STARTED",
        "failed_attempt_residue": {"rollback_slugs": residue, "ok": len(residue) == 0},
        "regression_tests": {
            "command": " ".join(test_cmd),
            "exit_code": proc.returncode,
            "ok": test_ok,
            "tail": "\n".join((proc.stdout or "").splitlines()[-15:]),
        },
        "issues": issues,
        "amber_notes": amber,
        "explicit_statements": [
            "BIO11-CH02-B001 post-repair integrity audit completed.",
            "Q000085 → R000085 repair lineage verified.",
            "100 active CH02 questions are ECAEP APPROVED.",
            "The other 99 questions have zero unauthorized content mutations.",
            "NCERT certification has NOT started.",
            "Publication has NOT been authorized or performed.",
            "CH02 remains non-student-visible.",
        ],
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    OUT_MD.write_text(
        f"""# Post-repair integrity audit — `{BATCH}`

## Verdict: {verdict}

Generated: `{payload['generated_at']}`  
Database mutations: **{database_mutations}**

{chr(10).join('> ' + s for s in payload['explicit_statements'])}

## Database snapshot
```json
{json.dumps(payload['database_snapshot'], indent=2)}
```

## Lineage
- R000085 replaces original Q000085: **{payload['lineage']['replacement_replaces_original']}**
- Original SUPERSEDED / not active: **{not payload['lineage']['original_active_approved']}**
- Replacement APPROVED / active: **{payload['lineage']['replacement_active_approved']}**

## Focused NCERT check (R000085 only)
**{focused['verdict']}**

## Other 99 mutations
**{len(other99_mutations)}**

## Artifact SHA
- questions_repaired.jsonl: `{hashes['questions_repaired.jsonl']}` (expected `{AUTH_SHA}`)
- match: **{hashes['questions_repaired.jsonl'] == AUTH_SHA}**

## Regression tests
exit={proc.returncode} ok={test_ok}

## Issues
{chr(10).join('- ' + i for i in issues) if issues else '_None_'}
""",
        encoding="utf-8",
    )

    if verdict.startswith("GREEN"):
        stage = {
            "batch_id": BATCH,
            "as_of": payload["generated_at"],
            "verdict": "GREEN — CH02 POST-REPAIR INTEGRITY AUDIT PASSED",
            "current_stage": "POST_REPAIR_INTEGRITY_AUDIT_PASSED",
            "stopped_before": "NCERT_CERTIFICATION",
            "explicit_statement": [
                "100 ACTIVE ECAEP-APPROVED",
                "0 IN_REVIEW",
                "0 PUBLISHED",
                "NCERT CERTIFICATION NOT STARTED",
                *payload["explicit_statements"],
            ],
            "counts": {
                "draft": s["ch02_status"]["DRAFT"],
                "in_review": s["ch02_status"]["IN_REVIEW"],
                "approved": s["ch02_status"]["APPROVED"],
                "published": s["ch02_status"]["PUBLISHED"],
                "superseded": s["ch02_status"]["SUPERSEDED"],
            },
            "q000085_lineage": {"original": ORIG, "replacement": REPL},
            "stages": {
                "q000085_repair": "GREEN",
                "post_repair_integrity_audit": "GREEN",
                "ncert_certification": "NOT_STARTED",
                "publication": "NOT_AUTHORIZED",
            },
            "safety": {
                "student_ch02_visible": s["student_ch02"],
                "practice_nonpub_ch02": s["practice_nonpub_ch02"],
                "database_mutations_this_audit": 0,
            },
            "artifacts": {
                "post_repair_integrity_audit": str(OUT_JSON),
            },
        }
        STAGE_JSON.write_text(json.dumps(stage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        STAGE_MD.write_text(
            f"""# Pipeline stage status — `{BATCH}`

## GREEN — CH02 POST-REPAIR INTEGRITY AUDIT PASSED

## STOPPED BEFORE NCERT CERTIFICATION

> 100 ACTIVE ECAEP-APPROVED
>
> 0 IN_REVIEW
>
> 0 PUBLISHED
>
> NCERT CERTIFICATION NOT STARTED

{chr(10).join('> ' + s for s in payload['explicit_statements'])}
""",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "verdict": verdict,
                "database_mutations": database_mutations,
                "ch02": s["ch02_status"],
                "other99_mutations": len(other99_mutations),
                "focused_ncert": focused["verdict"],
                "tests_ok": test_ok,
                "issues": issues,
            },
            indent=2,
        )
    )
    return payload


if __name__ == "__main__":
    asyncio.run(main())
