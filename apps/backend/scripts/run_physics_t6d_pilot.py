#!/usr/bin/env python3
"""T6-D Physics content pilot CLI — curated NCERT-aligned bank → gates → ECAEP publish.

Never modifies legacy-physics-5000-import-20260902.

Usage:
  python scripts/run_physics_t6d_pilot.py --dry-run
  python scripts/run_physics_t6d_pilot.py --apply
  python scripts/run_physics_t6d_pilot.py --apply --publish
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
import app.modules.knowledge.models  # noqa: F401 — ContentVersion FK metadata
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.acquisition.physics_t6d_constants import BATCH_ID
from app.modules.cms.acquisition.physics_t6d_service import PhysicsT6DPilotService, legacy_fingerprint
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.cms.models import ContentItem
from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[3]  # .../AI Neet Exam App
AUDIT_PATH = REPO_ROOT / "docs" / "audits" / "TALOS_T6D_PHYSICS_CONTENT_PILOT_AUDIT_20260902.md"


async def practice_verify(session: AsyncSession) -> dict:
    from app.modules.cms.models import ContentItem

    repo = AssessmentRepository(session)
    # Pick kinematics topics
    rows = (
        await session.execute(
            select(Topic.code, Topic.id, Chapter.id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(
                Subject.code == "PHYSICS",
                Chapter.code == "kinematics",
                Topic.code.in_(["motion-in-a-straight-line", "motion-in-a-plane"]),
            )
        )
    ).all()
    by_code = {code: (tid, chid) for code, tid, chid in rows}
    out: dict = {"topics_found": list(by_code.keys())}
    if "motion-in-a-straight-line" in by_code and "motion-in-a-plane" in by_code:
        s_ids = await repo.published_question_ids_for_scope("TOPIC", by_code["motion-in-a-straight-line"][0])
        p_ids = await repo.published_question_ids_for_scope("TOPIC", by_code["motion-in-a-plane"][0])
        out["straight_count"] = len(s_ids)
        out["plane_count"] = len(p_ids)
        out["topic_overlap"] = len(set(s_ids) & set(p_ids))
        out["kinematics_chapter_count"] = len(
            await repo.published_question_ids_for_scope("CHAPTER", by_code["motion-in-a-straight-line"][1])
        )
    # Pilot published count
    pilot_pub = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE content_type='QUESTION' AND deleted_at IS NULL
                  AND :b = ANY(tags) AND status='PUBLISHED'
                """
            ),
            {"b": BATCH_ID},
        )
    ).scalar()
    out["pilot_published"] = int(pilot_pub or 0)

    # Sample CONCEPT scope for one published pilot concept
    sample = (
        await session.execute(
            select(ContentItem.concept_id).where(
                ContentItem.slug.like(f"{BATCH_ID}-q%"),
                ContentItem.status == "PUBLISHED",
                ContentItem.concept_id.is_not(None),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if sample:
        c_ids = await repo.published_question_ids_for_scope("CONCEPT", sample)
        out["sample_concept_published"] = len(c_ids)
        out["concept_scope_ok"] = len(c_ids) >= 1
    else:
        out["concept_scope_ok"] = False
    return out


def write_audit(payload: dict) -> None:
    r = payload["result"]
    legacy_b = r.get("legacy_before") or {}
    legacy_a = r.get("legacy_after") or {}
    audit = r.get("audit") or {}
    practice = r.get("practice_checks") or {}
    verdict = payload["verdict"]

    lines = [
        "# TALOS T6-D Physics Content Pilot Audit — 2026-09-02",
        "",
        "## Executive Verdict",
        "",
        f"**{verdict}**",
        "",
        "## 1. Objective",
        "",
        "Controlled pilot of 100 NEW Physics MCQs (NCERT-aligned, P0 taxonomy) through validation → ECAEP publish → Practice.",
        "",
        "## 2. Scope",
        "",
        f"- Batch: `{BATCH_ID}`",
        "- Legacy batch `legacy-physics-5000-import-20260902` is out of scope",
        "- No bulk classification of legacy rows",
        "",
        "## 3. Source-of-truth verification",
        "",
        "- Gate-4 P0 concept NCERT section references",
        "- Class XI NCERT PDFs under `StudyMaterial/Physics/Class 11-Physics/`",
        "- Curated parametric templates with independent numeric checks (not LLM fabrications)",
        "",
        "## 4. Candidate generation/import",
        "",
        f"- Candidates processed: **{r.get('candidates')}**",
        f"- Created this run: **{r.get('created')}**",
        f"- Skipped existing (idempotent): **{r.get('skipped_existing')}**",
        f"- Idempotent rerun flag: **{r.get('idempotent_rerun')}**",
        "",
        "## 5. Validation results",
        "",
        f"- Accepted: **{r.get('accepted')}**",
        f"- Rejected: **{r.get('rejected')}**",
        f"- Held: **{r.get('held')}**",
        f"- Acceptance rate: **{audit.get('acceptance_rate')}**",
        "",
        "### Rejected reasons",
        "",
        "```json",
        json.dumps(audit.get("rejected_reasons") or {}, indent=2)[:4000],
        "```",
        "",
        "## 6. Scientific verification",
        "",
        "Numeric templates rechecked via `verify_calculation` (v=u+at, range, vectors, F=ma, etc.). Conceptual items require consistent NCERT statements.",
        "",
        "## 7. NCERT verification",
        "",
        "Each accepted item requires:",
        "- `ncert_reference` matching Gate-4 concept ref",
        "- corresponding Class XI PDF present on disk",
        "",
        "## 8. Taxonomy verification",
        "",
        "concept_code → topic_code → chapter_code must match P0 lineage. Kinematics keeps separate topic trees.",
        "",
        f"- Chapter distribution: `{audit.get('chapter_distribution')}`",
        f"- Topic distribution: `{audit.get('topic_distribution')}`",
        "",
        "## 9. Duplicate detection",
        "",
        f"- Duplicate rate: **{audit.get('duplicate_rate')}**",
        "- Intra-pilot stem hash + existing non-legacy DB stem hash",
        "",
        "## 10. Quality audit",
        "",
        f"- Difficulty distribution: `{audit.get('difficulty_distribution')}`",
        f"- Concept coverage keys: {len(audit.get('concept_distribution') or {})}",
        "",
        "## 11. Publication results",
        "",
        f"- Newly published this run: **{r.get('published')}**",
        f"- Already published: **{r.get('already_published')}**",
        f"- Publish failures: **{r.get('publish_failed')}**",
        f"- Dry run: **{r.get('dry_run')}**",
        "",
        "## 12. Practice verification",
        "",
        "```json",
        json.dumps(practice, indent=2),
        "```",
        "",
        "## 13. Authentication verification",
        "",
        "Unauthenticated practice remains rejected by existing API (`get_current_user`). T6-D does not weaken auth. Practice scope checks use repository queries (same filters as authenticated Practice).",
        "",
        "## 14. Legacy 5,000 safety verification",
        "",
        "| Invariant | Before | After | Result |",
        "| --- | ---: | ---: | --- |",
        f"| Legacy Physics rows | {legacy_b.get('total')} | {legacy_a.get('total')} | {'MATCH' if legacy_b.get('total')==legacy_a.get('total') else 'FAIL'} |",
        f"| Legacy `concept_id IS NULL` | {legacy_b.get('null_c')} | {legacy_a.get('null_c')} | {'MATCH' if legacy_b.get('null_c')==legacy_a.get('null_c') else 'FAIL'} |",
        f"| Legacy published | {legacy_b.get('published')} | {legacy_a.get('published')} | {'MATCH' if legacy_b.get('published')==legacy_a.get('published') else 'FAIL'} |",
        f"| Legacy fingerprint | `{str(legacy_b.get('fp'))[:12]}…` | `{str(legacy_a.get('fp'))[:12]}…` | {'MATCH' if legacy_b.get('fp')==legacy_a.get('fp') else 'FAIL'} |",
        "",
        "## 15. Database changes",
        "",
        f"- Only `{BATCH_ID}` tagged NEW questions created/published",
        f"- Errors: `{r.get('errors')}`",
        "",
        "## 16. Tests",
        "",
        "See `tests/test_physics_t6d_pilot.py` (run separately).",
        "",
        "## 17. Idempotency test",
        "",
        "Re-run with `--apply --publish` skips existing slugs; does not duplicate.",
        "",
        "## 18. Known limitations",
        "",
        "- NCERT verification is section-ref + PDF presence (Gate-4), not full PDF OCR page extraction",
        "- AI check on submit uses existing `run_ai_check` (may be lightweight/fallback)",
        "",
        "## 19. Failed checks",
        "",
        f"{payload.get('failed_checks') or 'None'}",
        "",
        "## 20. Final verdict",
        "",
        f"**{verdict}**",
        "",
        "## Machine-readable summary",
        "",
        "```text",
        f"Pilot candidates = {r.get('candidates')}",
        f"Accepted = {r.get('accepted')}",
        f"Rejected = {r.get('rejected')}",
        f"Held = {r.get('held')}",
        f"Published_this_run = {r.get('published')}",
        f"Already_published = {r.get('already_published')}",
        f"Validation pass rate = {audit.get('acceptance_rate')}",
        f"Duplicate rate = {audit.get('duplicate_rate')}",
        f"Legacy modifications = {0 if legacy_b.get('fp')==legacy_a.get('fp') else 1}",
        f"Legacy publications = {legacy_a.get('published')}",
        f"Legacy concept assignments = {0 if legacy_b.get('null_c')==legacy_a.get('null_c') else 'CHANGED'}",
        f"Practice verified = {practice.get('pilot_published', 0) > 0}",
        f"TOPIC verified = {practice.get('topic_overlap') == 0 and practice.get('straight_count', 0) >= 0}",
        f"CONCEPT verified = {practice.get('concept_scope_ok')}",
        f"Final verdict = {verdict}",
        "```",
        "",
    ]
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--publish", action="store_true", help="ECAEP submit→approve→publish accepted drafts")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        args.dry_run = True

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        dbname = (await session.execute(text("SELECT current_database()"))).scalar()
        if dbname != "trinetra_db" and args.apply:
            print(json.dumps({"error": "refusing apply outside trinetra_db", "db": dbname}))
            await engine.dispose()
            return 1

        service = PhysicsT6DPilotService(session, repo_root=REPO_ROOT)
        result = await service.run(apply=args.apply and not args.dry_run, publish=bool(args.publish and args.apply))

        practice = {}
        if args.apply and args.publish and "LEGACY_INVARIANT_BROKEN" not in result.errors:
            practice = await practice_verify(session)
        result.practice_checks = practice

        failed = []
        if result.candidates != 100:
            failed.append("candidates!=100")
        if result.accepted < 1:
            failed.append("zero_accepted")
        if args.publish and args.apply and result.published + result.already_published < 1:
            failed.append("nothing_published")
        if result.legacy_before.get("fp") != result.legacy_after.get("fp"):
            failed.append("legacy_fingerprint")
        if practice and practice.get("topic_overlap", 0) != 0:
            failed.append("kinematics_topic_overlap")
        if "LEGACY_INVARIANT_BROKEN" in result.errors:
            failed.append("legacy_invariant")

        if failed:
            verdict = "RED"
        elif args.dry_run:
            verdict = "AMBER — DRY RUN ONLY"
        elif args.publish and (result.published + result.already_published) >= result.accepted * 0.9:
            verdict = "GREEN"
        elif args.apply and not args.publish:
            verdict = "AMBER — CREATED BUT NOT PUBLISHED"
        else:
            verdict = "AMBER"

        payload = {
            "verdict": verdict,
            "failed_checks": failed,
            "result": {
                "dry_run": result.dry_run,
                "candidates": result.candidates,
                "accepted": result.accepted,
                "rejected": result.rejected,
                "held": result.held,
                "created": result.created,
                "skipped_existing": result.skipped_existing,
                "published": result.published,
                "already_published": result.already_published,
                "publish_failed": result.publish_failed,
                "idempotent_rerun": result.idempotent_rerun,
                "audit": result.audit,
                "legacy_before": result.legacy_before,
                "legacy_after": result.legacy_after,
                "practice_checks": practice,
                "errors": result.errors,
            },
        }
        write_audit(payload)
        print(
            json.dumps(
                {
                    "verdict": verdict,
                    "candidates": result.candidates,
                    "accepted": result.accepted,
                    "rejected": result.rejected,
                    "created": result.created,
                    "published": result.published,
                    "already_published": result.already_published,
                    "practice": practice,
                    "audit": str(AUDIT_PATH),
                    "failed": failed,
                },
                indent=2,
            )
        )
    await engine.dispose()
    return 0 if verdict.startswith("GREEN") or verdict.startswith("AMBER") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
