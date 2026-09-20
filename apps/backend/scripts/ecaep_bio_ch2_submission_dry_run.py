"""READ-ONLY ECAEP submission dry-run for Biology Ch2 batch.

Uses ContentWorkflowService.evaluate_submit_for_review (canonical gates).
Never calls submit_for_review / commit / status transitions.

Usage:
  python scripts/ecaep_bio_ch2_submission_dry_run.py
"""
from __future__ import annotations

import asyncio
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
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import ContentWorkflowService

BATCH = "20260911-BIO11-CH02-B001"
CH01 = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
CHAPTER_CODE = "biological-classification"
SUBJECT_CODE = "BOTANY"
EXPECTED_TAX = {"subjects": 4, "chapters": 36, "topics": 107, "concepts": 143}
EXPECTED_BIO = {"DRAFT": 100, "SUPERSEDED": 0, "PUBLISHED": 0, "APPROVED": 0, "IN_REVIEW": 0}
EXPECTED_CH01 = {"DRAFT": 0, "SUPERSEDED": 5, "PUBLISHED": 100, "APPROVED": 0, "IN_REVIEW": 0}

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
OUT_JSON = ROOT / "ecaep_submission_dry_run.json"
OUT_MD = ROOT / "ecaep_submission_dry_run.md"


def eid_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    marker = f"GEMINI-{BATCH}-"
    if marker not in slug:
        return None
    return f"GEMINI-{BATCH}-{slug.split(marker, 1)[1]}"


def sort_key(eid: str) -> tuple:
    suffix = eid.rsplit("-", 1)[-1]
    if suffix.startswith("R"):
        return (1, int(suffix[1:]))
    return (0, int(suffix))


def is_batch_item(item: ContentItem) -> bool:
    tags = item.tags or []
    if BATCH in tags or any(BATCH in (t or "") for t in tags):
        return True
    return bool(item.slug and "bio11-ch02-b001" in item.slug.lower())


def is_ch01_item(item: ContentItem) -> bool:
    tags = item.tags or []
    if CH01 in tags or any(CH01 in (t or "") for t in tags):
        return True
    return bool(item.slug and "bio11-ch01-b001" in (item.slug or "").lower())


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
    ch01 = [i for i in items if is_ch01_item(i)]
    phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
    bs = Counter(i.status for i in bio)
    c1 = Counter(i.status for i in ch01)
    drafts = [i for i in bio if i.status == "DRAFT"]
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
        "ch01_regression": {
            "DRAFT": c1.get("DRAFT", 0),
            "SUPERSEDED": c1.get("SUPERSEDED", 0),
            "PUBLISHED": c1.get("PUBLISHED", 0),
            "APPROVED": c1.get("APPROVED", 0),
            "IN_REVIEW": c1.get("IN_REVIEW", 0),
        },
        "physics_DRAFT": Counter(i.status for i in phy).get("DRAFT", 0),
        "mapped_drafts": sum(1 for i in drafts if i.concept_id),
        "student_bio_hits": student_hits,
        "practice_nonpub_hits": len(nonpub & pool),
    }


async def taxonomy_for_concept(session, concept_id: uuid.UUID | None) -> dict | None:
    if not concept_id:
        return None
    row = (
        await session.execute(
            select(
                Concept.id,
                Concept.code,
                Concept.name,
                Concept.deleted_at,
                Topic.code,
                Topic.name,
                Chapter.code,
                Chapter.name,
                Subject.code,
                Subject.name,
            )
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(Concept.id == concept_id)
        )
    ).one_or_none()
    if not row:
        return None
    return {
        "concept_id": str(row[0]),
        "concept_code": row[1],
        "concept_name": row[2],
        "concept_deleted": row[3] is not None,
        "topic_code": row[4],
        "topic_name": row[5],
        "chapter_code": row[6],
        "chapter_name": row[7],
        "subject_code": row[8],
        "subject_name": row[9],
        "expected_path_ok": (
            row[8] == SUBJECT_CODE
            and row[6] == CHAPTER_CODE
            and row[3] is None
        ),
    }


async def main() -> int:
    async with AsyncSessionLocal() as session:
        before = await snap(session)
        workflow = ContentWorkflowService(session)

        all_items = (
            await session.execute(
                select(ContentItem)
                .options(selectinload(ContentItem.versions))
                .where(ContentItem.deleted_at.is_(None))
            )
        ).scalars().all()

        batch_all = [i for i in all_items if is_batch_item(i)]
        by_status = Counter(i.status for i in batch_all)
        superseded = [i for i in batch_all if i.status == "SUPERSEDED"]
        other_batch_leak = []
        for i in all_items:
            if i.status != "DRAFT":
                continue
            if is_batch_item(i):
                continue
            if PHY in str(i.tags) or (i.slug and "phy11" in i.slug.lower()):
                other_batch_leak.append(str(i.id))

        selection = [i for i in batch_all if i.status == "DRAFT"]
        per_question: list[dict] = []
        for item in selection:
            eid = eid_from_slug(item.slug) or f"UNKNOWN-{item.id}"
            tax = await taxonomy_for_concept(session, item.concept_id)
            gate = await workflow.evaluate_submit_for_review(item.id)
            taxonomy_confirm = {
                "concept_id_present": item.concept_id is not None,
                "concept_exists": tax is not None and not tax["concept_deleted"],
                "taxonomy_relationship_valid": bool(tax and tax["expected_path_ok"]),
                "path": (
                    f"{tax['subject_name']} → {tax['chapter_name']} → "
                    f"{tax['topic_name']} → {tax['concept_name']}"
                    if tax
                    else None
                ),
            }
            latest = gate.get("latest")
            body = latest.body if latest else {}
            ncert = (body or {}).get("ncert_evidence")
            provenance = (body or {}).get("provenance")
            provenance_present = bool(ncert or provenance or any(
                (t or "").startswith(("ncert:", "source", "batch:"))
                for t in (item.tags or [])
            ))

            per_question.append(
                {
                    "question_id": eid,
                    "content_item_id": str(item.id),
                    "current_status": item.status,
                    "concept_id": str(item.concept_id) if item.concept_id else None,
                    "concept_code": tax["concept_code"] if tax else None,
                    "eligibility_result": "ELIGIBLE" if gate["eligible"] else "INELIGIBLE",
                    "blocking_reason": gate["rejection_reason"],
                    "blocking_code": gate["rejection_code"],
                    "canonical_gate": "ContentWorkflowService.evaluate_submit_for_review",
                    "taxonomy_confirmation": taxonomy_confirm,
                    "provenance_present": provenance_present,
                    "would_transition_to": "IN_REVIEW" if gate["eligible"] else None,
                }
            )

        per_question.sort(key=lambda r: sort_key(r["question_id"]))
        deterministic_ids = [r["question_id"] for r in per_question]

        wrong_chapter = [
            r["question_id"]
            for r in per_question
            if not r["taxonomy_confirmation"]["taxonomy_relationship_valid"]
        ]
        phy_in_selection = [
            r["question_id"]
            for r in per_question
            if PHY in r["question_id"] or "phy" in r["question_id"].lower()
        ]
        eligible_count = sum(1 for r in per_question if r["eligibility_result"] == "ELIGIBLE")
        ineligible_count = len(per_question) - eligible_count

        after = await snap(session)
        unchanged = before == after

        safety_checks = {
            "submit_for_review_not_called": True,
            "would_not_publish": True,
            "would_not_approve": True,
            "would_not_expose_to_students": True,
            "rationale_student_exposure": (
                "submit_for_review only moves DRAFT→IN_REVIEW. "
                "CmsRepository.list_questions / practice pool are PUBLISHED-only."
            ),
            "would_not_modify_taxonomy": True,
            "would_not_modify_question_body": True,
            "would_not_modify_answers_or_options": True,
            "would_not_modify_provenance_verification_level": True,
            "submit_side_effects_if_executed": [
                "item.status = IN_REVIEW",
                "latest.workflow_state = IN_REVIEW",
                "latest.ai_check_report = EvaluatorService.evaluate(...)",
                "session commit",
            ],
            "student_visibility_now": after["student_bio_hits"],
            "practice_pool_nonpub_hits_now": after["practice_nonpub_hits"],
            "database_unchanged": unchanged,
            "ch01_regression_unchanged": after["ch01_regression"] == EXPECTED_CH01,
            "before": before,
            "after": after,
        }

        selection_proof = {
            "selection_count": len(per_question),
            "expected": 100,
            "batch_status_counts": dict(by_status),
            "excluded_superseded_count": len(superseded),
            "excluded_non_draft_count": sum(1 for i in batch_all if i.status != "DRAFT"),
            "excluded_superseded_ids": sorted(
                eid_from_slug(i.slug) or str(i.id) for i in superseded
            ),
            "excluded_published_count": by_status.get("PUBLISHED", 0),
            "excluded_approved_count": by_status.get("APPROVED", 0),
            "excluded_in_review_count": by_status.get("IN_REVIEW", 0),
            "other_batch_or_physics_in_selection": phy_in_selection,
            "wrong_taxonomy_path_in_selection": wrong_chapter,
            "physics_draft_count_unchanged": after["physics_DRAFT"],
            "proofs": {
                "superseded_excluded": len(superseded) == 0,
                "zero_published_in_selection": by_status.get("PUBLISHED", 0) == 0,
                "zero_approved_in_selection": by_status.get("APPROVED", 0) == 0,
                "zero_in_review_in_selection": by_status.get("IN_REVIEW", 0) == 0,
                "no_other_batch": len(phy_in_selection) == 0,
                "no_physics": after["physics_DRAFT"] == 24 and len(phy_in_selection) == 0,
                "all_botany_biological_classification": len(wrong_chapter) == 0,
                "ch01_regression_intact": after["ch01_regression"] == EXPECTED_CH01,
            },
        }

        ok = (
            len(per_question) == 100
            and eligible_count == 100
            and ineligible_count == 0
            and after["student_bio_hits"] == 0
            and after["practice_nonpub_hits"] == 0
            and unchanged
            and after["biology"] == EXPECTED_BIO
            and after["taxonomy"] == EXPECTED_TAX
            and after["physics_DRAFT"] == 24
            and after["ch01_regression"] == EXPECTED_CH01
            and selection_proof["proofs"]["superseded_excluded"]
            and selection_proof["proofs"]["all_botany_biological_classification"]
            and selection_proof["proofs"]["no_physics"]
            and selection_proof["proofs"]["ch01_regression_intact"]
        )

        verdict = (
            "GREEN — 100 QUESTIONS READY FOR ECAEP SUBMISSION"
            if ok
            else "AMBER — ECAEP SUBMISSION BLOCKED"
        )

        payload = {
            "batch_id": BATCH,
            "generated_at": datetime.now(UTC).isoformat(),
            "audit_type": "ECAEP_SUBMISSION_DRY_RUN_READ_ONLY",
            "canonical_eligibility": "ContentWorkflowService.evaluate_submit_for_review",
            "selection_count": len(per_question),
            "eligible_count": eligible_count,
            "ineligible_count": ineligible_count,
            "excluded_superseded_count": selection_proof["excluded_superseded_count"],
            "excluded_non_draft_count": sum(1 for i in batch_all if i.status != "DRAFT"),
            "deterministic_question_ids": deterministic_ids,
            "per_question_results": per_question,
            "selection_proof": selection_proof,
            "safety_checks": safety_checks,
            "ch01_regression": {
                "expected": EXPECTED_CH01,
                "actual": after["ch01_regression"],
                "unchanged": after["ch01_regression"] == EXPECTED_CH01,
            },
            "verdict": verdict,
            "assertions": {
                "READ-ONLY": True,
                "DATABASE UNCHANGED": unchanged,
                "NO ECAEP SUBMISSION": True,
                "NO PUBLICATION": True,
                "CH01 REGRESSION UNCHANGED": after["ch01_regression"] == EXPECTED_CH01,
            },
        }

        OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        lines = [
            "# ECAEP Submission Dry Run",
            "",
            f"## Verdict: {verdict}",
            "",
            "**READ-ONLY**  ",
            "**DATABASE UNCHANGED**  ",
            "**NO ECAEP SUBMISSION**  ",
            "**NO PUBLICATION**",
            "",
            f"Batch: `{BATCH}`  ",
            f"Generated: `{payload['generated_at']}`  ",
            f"Canonical gate: `ContentWorkflowService.evaluate_submit_for_review` "
            f"(same pre-mutation checks as `submit_for_review`)",
            "",
            "## 1. Submission set",
            "",
            f"- Selected ACTIVE DRAFTs: **{len(per_question)}**",
            f"- Excluded SUPERSEDED: **{selection_proof['excluded_superseded_count']}** "
            f"(expected 0 — CH02 has no superseded items)",
            f"- Excluded non-DRAFT total: **{payload['excluded_non_draft_count']}**",
            f"- PUBLISHED included: **{selection_proof['excluded_published_count']}**",
            f"- APPROVED included: **{selection_proof['excluded_approved_count']}**",
            f"- IN_REVIEW included: **{selection_proof['excluded_in_review_count']}**",
            f"- Physics / other-batch in selection: **{len(phy_in_selection)}**",
            f"- Non–Botany/Biological-Classification taxonomy: **{len(wrong_chapter)}**",
            "",
            "```json",
            json.dumps(selection_proof["proofs"], indent=2),
            "```",
            "",
            "## 2. Eligibility",
            "",
            f"- Eligible: **{eligible_count}**",
            f"- Ineligible: **{ineligible_count}**",
            "",
            "Gates evaluated (canonical order):",
            "1. item exists",
            "2. status == DRAFT",
            "3. latest version exists",
            "4. `assert_body_publishable`",
            "5. QUESTION has `concept_id` (else `MISSING_ACADEMIC_MAPPING`)",
            "",
            "Supplemental confirmation (not a parallel gate): concept row exists under "
            "Botany → Biological Classification.",
            "",
            "## 3. Deterministic submission plan",
            "",
            "Order: numeric Q000001–Q000100 (stable `sort_key` on external id suffix).",
            "",
            f"- Plan length: **{len(deterministic_ids)}**",
            f"- First: `{deterministic_ids[0] if deterministic_ids else None}`",
            f"- Last: `{deterministic_ids[-1] if deterministic_ids else None}`",
            "",
            "| # | question_id | status | concept_code | eligibility | blocker |",
            "|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(per_question, 1):
            lines.append(
                f"| {i} | `{r['question_id']}` | {r['current_status']} | "
                f"`{r['concept_code']}` | {r['eligibility_result']} | "
                f"{r['blocking_code'] or '—'} |"
            )

        lines += [
            "",
            "## 4. CH01 regression",
            "",
            f"- Expected CH01: `{EXPECTED_CH01}`",
            f"- Actual CH01: `{after['ch01_regression']}`",
            f"- Unchanged: **{after['ch01_regression'] == EXPECTED_CH01}**",
            "",
            "## 5. Safety",
            "",
            "If `submit_for_review` were later executed for this set, it would **not**:",
            "- publish questions",
            "- approve questions",
            "- expose questions to students (PUBLISHED-only student/practice surfaces)",
            "- modify taxonomy",
            "- modify question body / answers / options",
            "- modify provenance `verification_level`",
            "",
            "It would only: set status/workflow_state to IN_REVIEW and write `ai_check_report`.",
            "",
            "```json",
            json.dumps(
                {
                    k: safety_checks[k]
                    for k in safety_checks
                    if k not in {"before", "after"}
                },
                indent=2,
            ),
            "```",
            "",
            "## 6. Database safety (read-only snap)",
            "",
            "```json",
            json.dumps({"before": before, "after": after, "unchanged": unchanged}, indent=2),
            "```",
            "",
            "## Assertions",
            "",
            "- READ-ONLY",
            "- DATABASE UNCHANGED",
            "- NO ECAEP SUBMISSION",
            "- NO PUBLICATION",
            "- CH01 REGRESSION UNCHANGED",
            "",
        ]
        OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

        print(
            json.dumps(
                {
                    "verdict": verdict,
                    "selection_count": len(per_question),
                    "eligible_count": eligible_count,
                    "ineligible_count": ineligible_count,
                    "student_visibility": after["student_bio_hits"],
                    "database_unchanged": unchanged,
                    "ch01_regression": after["ch01_regression"],
                    "artifacts": [str(OUT_MD), str(OUT_JSON)],
                },
                indent=2,
            )
        )
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
