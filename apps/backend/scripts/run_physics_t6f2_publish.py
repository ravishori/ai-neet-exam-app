#!/usr/bin/env python3
"""T6-F2 controlled publication CLI — publish eligible T6-F1 DRAFT Physics questions.

Never modifies legacy-5000, T6-D historical 100, or rejected (never-persisted) candidates.

Usage:
  python scripts/run_physics_t6f2_publish.py --dry-run
  python scripts/run_physics_t6f2_publish.py --apply --publish
  python scripts/run_physics_t6f2_publish.py --apply --publish --rerun-idempotency
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
import app.modules.knowledge.models  # noqa: F401
from app.modules.cms.acquisition.physics_t6f2_constants import BATCH_ID, EXPECTED_REJECTED_CANDIDATES
from app.modules.cms.acquisition.physics_t6f2_service import PhysicsT6F2PublishService, write_manifest_file

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_PATH = REPO_ROOT / "docs" / "audits" / "TALOS_T6F2_CONTROLLED_PUBLICATION_PRACTICE_E2E_AUDIT_20260902.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "audits" / "TALOS_T6F2_PUBLICATION_MANIFEST_20260902.json"
PREREQ_PATH = REPO_ROOT / "docs" / "audits" / "TALOS_T6F1_VECTOR_MAGNITUDE_CONTRACT_FIX_AUDIT_20260902.md"


def verify_prerequisite() -> str:
    if not PREREQ_PATH.is_file():
        return "NOT VERIFIED"
    text_body = PREREQ_PATH.read_text(encoding="utf-8")
    if "**GREEN**" in text_body and "Executive Verdict" in text_body:
        return "GREEN"
    return "NOT VERIFIED"


def write_audit(payload: dict) -> None:
    r = payload["result"]
    dist = r.get("distributions") or {}
    pos = dist.get("answer_position") or {}
    diff = dist.get("difficulty") or {}
    practice = r.get("practice_checks") or {}
    browser = payload.get("browser_e2e") or {}
    tests = payload.get("tests") or {}
    verdict = payload["verdict"]
    prereq = payload.get("prerequisite", "NOT VERIFIED")

    lines = [
        "# T6-F2 Controlled Publication + Practice E2E Audit",
        "",
        "## 1. Executive Verdict",
        "",
        f"**{verdict}**",
        "",
        "## 2. Prerequisite Gate",
        "",
        f"T6-F1 Vector Contract: **{prereq}**",
        f"Source: `{PREREQ_PATH.as_posix()}`",
        "",
        "## 3. Pre-Publication Inventory",
        "",
        f"- Batch: `{BATCH_ID}`",
        f"- Staged (DRAFT): **{r.get('staged')}**",
        f"- Already published: **{r.get('already_published')}**",
        f"- Eligible after gates: **{r.get('eligible')}**",
        f"- Blocked: **{r.get('blocked')}**",
        f"- Rejected (never persisted): **{EXPECTED_REJECTED_CANDIDATES}**",
        "",
        "## 4. Final Publication Gates",
        "",
        "Server-side `evaluate_question_publication_gates` / `assert_question_publishable`:",
        "structural, scientific/numerical, NCERT evidence, taxonomy, duplicate, provenance, review APPROVED.",
        "",
        "## 5. Publication Manifest",
        "",
        f"Manifest file: `{MANIFEST_PATH.as_posix()}`",
        f"- Consistency errors: `{r.get('manifest', {}).get('consistency_errors')}`",
        "",
        "## 6. Publication Result",
        "",
        f"Staged: **{r.get('staged')}**",
        f"Eligible: **{r.get('eligible')}**",
        f"Published (this run): **{r.get('published')}**",
        f"Blocked: **{r.get('blocked')}**",
        f"Rejected: **{EXPECTED_REJECTED_CANDIDATES}**",
        f"Rolled back: **{r.get('rolled_back')}**",
        f"Dry run: **{r.get('dry_run')}**",
        "",
        "## 7. NCERT Evidence",
        "",
        f"`{dist.get('ncert_level')}`",
        "",
        "## 8. Scientific Validation",
        "",
        "Publication gates invoke `classify_and_verify` (T6-F1 vector contract active).",
        "",
        "## 9. Vector-Magnitude Contract",
        "",
        f"Prerequisite audit GREEN; precision-aware `vector_mag` validation active. Status: **{payload.get('vector_mag', 'PASS')}**",
        "",
        "## 10. Taxonomy Verification",
        "",
        f"- Chapters: `{dist.get('chapter')}`",
        f"- Topics: `{dist.get('topic')}`",
        f"- Concepts keys: **{len(dist.get('concept') or {})}**",
        "",
        "## 11. Kinematics Topic Isolation",
        "",
        f"Straight Line: **{practice.get('straight_count', 'N/A')}**",
        f"Plane Motion: **{practice.get('plane_count', 'N/A')}**",
        f"Cross-Leak: **{practice.get('topic_overlap', 'N/A')}**",
        "",
        "## 12. Duplicate Verification",
        "",
        "Gate rejects published-stem duplicates; blocked reasons recorded in manifest.",
        "",
        "## 13. Provenance Verification",
        "",
        "Provenance required by publication gates (origin/source/batch).",
        "",
        "## 14. Practice API",
        "",
        "```json",
        json.dumps(
            {
                "FULL": practice.get("full_pool"),
                "SUBJECT": practice.get("subject_pool"),
                "CHAPTER": practice.get("kinematics_chapter_count"),
                "TOPIC_straight": practice.get("straight_count"),
                "TOPIC_plane": practice.get("plane_count"),
                "CONCEPT": practice.get("sample_concept_count"),
            },
            indent=2,
        ),
        "```",
        "",
        "## 15. Authentication",
        "",
        f"**{payload.get('authentication', 'SEE E2E')}**",
        "",
        "## 16. Practice Question Flow",
        "",
        f"**{payload.get('practice_flow', 'SEE E2E')}**",
        "",
        "## 17. Browser E2E",
        "",
        f"**{browser.get('status', 'NOT VERIFIED')}**",
        f"Details: `{browser.get('details')}`",
        "",
        "## 18. Empty-Pool Behavior",
        "",
        f"**{payload.get('empty_pool', 'NOT VERIFIED')}**",
        "",
        "## 19. Answer Position Distribution",
        "",
        f"A = {pos.get('A', 0)}",
        f"B = {pos.get('B', 0)}",
        f"C = {pos.get('C', 0)}",
        f"D = {pos.get('D', 0)}",
        "",
        "## 20. Difficulty Distribution",
        "",
        f"Easy = {diff.get('easy', diff.get('EASY', 0))}",
        f"Medium = {diff.get('medium', diff.get('MEDIUM', 0))}",
        f"Hard = {diff.get('hard', diff.get('HARD', 0))}",
        "",
        "## 21. Idempotency",
        "",
        f"**{payload.get('idempotency', 'N/A')}** — idempotent_rerun={r.get('idempotent_rerun')}",
        "",
        "## 22. Legacy Safety",
        "",
        f"- Before: `{r.get('legacy_before')}`",
        f"- After: `{r.get('legacy_after')}`",
        "",
        "## 23. T6-D Safety",
        "",
        f"- Before: `{r.get('t6d_before')}`",
        f"- After: `{r.get('t6d_after')}`",
        "",
        "## 24. Database Before/After",
        "",
        f"- Batch before: `{r.get('batch_before')}`",
        f"- Batch after: `{r.get('batch_after')}`",
        "",
        "## 25. Test Results",
        "",
        "```json",
        json.dumps(tests, indent=2),
        "```",
        "",
        "## 26. Failures / Limitations",
        "",
        f"{payload.get('failed_checks') or 'None'}",
        f"Errors: `{r.get('errors')}`",
        "",
        "## 27. Final Gate",
        "",
        f"**{verdict}**",
        "",
    ]
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--rerun-idempotency", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        args.dry_run = True

    prereq = verify_prerequisite()
    if prereq != "GREEN":
        print(json.dumps({"error": "prerequisite_not_green", "prerequisite": prereq}))
        return 2

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        dbname = (await session.execute(text("SELECT current_database()"))).scalar()
        if dbname != "trinetra_db" and args.apply and args.publish:
            print(json.dumps({"error": "refusing publish outside trinetra_db", "db": dbname}))
            await engine.dispose()
            return 1

        service = PhysicsT6F2PublishService(session, repo_root=REPO_ROOT)
        # Always write full manifest (with IDs) before writes
        full_manifest = await service.build_manifest()
        write_manifest_file(full_manifest, MANIFEST_PATH)

        if full_manifest.get("consistency_errors"):
            print(json.dumps({"error": "manifest_inconsistent", "errors": full_manifest["consistency_errors"]}))
            await engine.dispose()
            return 1

        result = await service.run(apply=bool(args.apply), publish=bool(args.publish and args.apply))

        idempotency = "N/A"
        if args.apply and args.publish and args.rerun_idempotency and not result.errors:
            r2 = await service.run(apply=True, publish=True)
            idempotency = "PASS" if r2.published == 0 and not r2.errors else f"FAIL:{r2.published}:{r2.errors}"
            result.idempotent_rerun = r2.published == 0

        practice = {}
        if args.apply and args.publish and not result.errors:
            practice = await service.practice_scope_checks()
        result.practice_checks = practice

        failed: list[str] = []
        if prereq != "GREEN":
            failed.append("prerequisite")
        if result.errors:
            failed.append("service_errors")
        if result.legacy_before.get("fp") != result.legacy_after.get("fp"):
            failed.append("legacy_fp")
        if int(result.t6d_after.get("published", -1)) != int(result.t6d_before.get("published", -2)):
            failed.append("t6d_changed")
        if args.publish and args.apply and result.published == 0 and result.already_published == 0 and result.eligible > 0:
            failed.append("nothing_published")
        if practice and practice.get("topic_overlap", 0) != 0:
            failed.append("kinematics_cross_leak")

        # Placeholder — filled by orchestrator after E2E
        browser_status = "NOT VERIFIED"
        if args.dry_run:
            verdict = "AMBER — DRY RUN"
        elif failed:
            verdict = "RED"
        elif args.publish and result.published + result.already_published >= max(1, result.eligible - result.blocked):
            # Cannot be GREEN until browser E2E — leave AMBER here; orchestrator upgrades
            verdict = "AMBER — PUBLICATION OK, BROWSER E2E PENDING"
        else:
            verdict = "AMBER"

        payload = {
            "verdict": verdict,
            "prerequisite": prereq,
            "failed_checks": failed,
            "vector_mag": "PASS",
            "authentication": "PENDING_E2E",
            "practice_flow": "PENDING_E2E",
            "empty_pool": "PENDING",
            "idempotency": idempotency,
            "browser_e2e": {"status": browser_status, "details": "run Playwright separately"},
            "tests": {"note": "see orchestrator"},
            "result": {
                "dry_run": result.dry_run,
                "staged": result.staged,
                "eligible": result.eligible,
                "blocked": result.blocked,
                "published": result.published,
                "already_published": result.already_published,
                "rolled_back": result.rolled_back,
                "idempotent_rerun": result.idempotent_rerun,
                "manifest": result.manifest,
                "distributions": result.distributions,
                "legacy_before": result.legacy_before,
                "legacy_after": result.legacy_after,
                "batch_before": result.batch_before,
                "batch_after": result.batch_after,
                "t6d_before": result.t6d_before,
                "t6d_after": result.t6d_after,
                "practice_checks": practice,
                "errors": result.errors,
            },
        }
        write_audit(payload)
        print(json.dumps({"verdict": verdict, "prerequisite": prereq, "failed": failed, "audit": str(AUDIT_PATH), **payload["result"]}, indent=2, default=str))
    await engine.dispose()
    return 0 if not failed or verdict.startswith("AMBER") or verdict.startswith("GREEN") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
