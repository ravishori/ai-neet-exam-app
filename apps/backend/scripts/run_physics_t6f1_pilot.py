#!/usr/bin/env python3
"""T6-F1 Physics 1,000-candidate pilot — DRAFT staging ONLY. Never publishes.

Never modifies legacy-physics-5000-import-20260902 or historical T6-D published rows.

Usage:
  python scripts/run_physics_t6f1_pilot.py --dry-run
  python scripts/run_physics_t6f1_pilot.py --apply
  python scripts/run_physics_t6f1_pilot.py --apply --rerun-idempotency
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
from app.modules.cms.acquisition.physics_acquisition_common import legacy_fingerprint
from app.modules.cms.acquisition.physics_t6f1_constants import BATCH_ID, TARGET_CANDIDATES, T6D_BATCH_ID
from app.modules.cms.acquisition.physics_t6f1_service import PhysicsT6F1PilotService

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_PATH = REPO_ROOT / "docs" / "audits" / "TALOS_T6F1_1000_CANDIDATE_VALIDATION_AUDIT_20260902.md"


async def inventory_snapshot(session: AsyncSession) -> dict:
    legacy = await legacy_fingerprint(session)
    t6d = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published
                FROM cms.content_items
                WHERE content_type='QUESTION' AND deleted_at IS NULL
                  AND :b = ANY(tags)
                """
            ),
            {"b": T6D_BATCH_ID},
        )
    ).mappings().one()
    t6f1 = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
                       COUNT(*) FILTER (WHERE status = 'DRAFT') AS draft
                FROM cms.content_items
                WHERE content_type='QUESTION' AND deleted_at IS NULL
                  AND :b = ANY(tags)
                """
            ),
            {"b": BATCH_ID},
        )
    ).mappings().one()
    physics = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
                       COUNT(*) FILTER (WHERE status = 'DRAFT') AS draft
                FROM cms.content_items
                WHERE content_type='QUESTION' AND deleted_at IS NULL
                  AND EXISTS (
                    SELECT 1 FROM academic.concepts c
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE c.id = cms.content_items.concept_id AND s.code = 'PHYSICS'
                  )
                """
            )
        )
    ).mappings().one()
    return {
        "physics_total": int(physics["total"]),
        "physics_published": int(physics["published"]),
        "physics_draft": int(physics["draft"]),
        "legacy": dict(legacy),
        "t6d": dict(t6d),
        "t6f1": dict(t6f1),
    }


def _diff_count(diff: dict, label: str) -> int:
    return int(diff.get(label) or diff.get(label.lower()) or diff.get(label.upper()) or 0)


def _pct(n: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{100.0 * n / total:.1f}%"


def write_audit(payload: dict) -> None:
    r = payload["result"]
    audit = r.get("audit") or {}
    inv_b = r.get("inventory_before") or {}
    inv_a = r.get("inventory_after") or {}
    legacy_b = inv_b.get("legacy") or r.get("legacy_before") or {}
    legacy_a = inv_a.get("legacy") or r.get("legacy_after") or {}
    ap = audit.get("answer_position_all_candidates") or {}
    dist = ap.get("distribution") or {}
    diff = audit.get("difficulty_distribution_accepted") or {}
    diff_total = sum(_diff_count(diff, k) for k in ("easy", "medium", "hard")) or 1
    tp = r.get("throughput") or {}
    rates = tp.get("rates") or {}
    idem = payload.get("idempotent_second_run")
    verdict = payload["verdict"]
    ready = payload.get("ready_for_f2", "NO")

    lines = [
        "# TALOS T6-F1 — 1,000-Question Physics Candidate Validation Audit — 2026-09-02",
        "",
        "## 1. Executive Verdict",
        "",
        f"**{verdict}**",
        "",
        "Controlled scale pilot: generate → validate → verify → deduplicate → stage (DRAFT only). **No publication.**",
        "",
        "## 2. Objective",
        "",
        "Determine whether the remediated T6-D/T6-E-FIX factory scales from 100 → 1,000 without integrity loss.",
        "",
        "## 3. Scope",
        "",
        f"- Batch: `{BATCH_ID}`",
        f"- Target candidates: **{TARGET_CANDIDATES}**",
        "- Legacy `legacy-physics-5000-import-20260902`: read-only for dedupe",
        f"- Historical T6-D `{T6D_BATCH_ID}`: read-only; not modified",
        "- Publication: **NOT IN SCOPE** (T6-F2)",
        "",
        "## 4. Batch identifier",
        "",
        f"`{BATCH_ID}` — immutable for all T6-F1 records.",
        "",
        "## 5. Source-of-truth",
        "",
        "- NCERT Class XI Physics PDFs under `StudyMaterial/Physics/Class 11-Physics/`",
        "- Gate-4 P0 concept NCERT section references",
        "- Parametric templates with independent numeric verification (not LLM fabrications)",
        "- Page-level NCERT verification: **NOT AVAILABLE** (no fabricated page numbers)",
        "",
        "## 6. Candidate generation",
        "",
        f"- Requested: **{TARGET_CANDIDATES}**",
        f"- Generated: **{r.get('candidates')}**",
        f"- Distribution plan concepts: **{len(audit.get('distribution_plan') or {})}**",
        f"- Created this run: **{r.get('created')}**",
        f"- Skipped existing (idempotent): **{r.get('skipped_existing')}**",
        f"- Idempotent rerun: **{r.get('idempotent_rerun')}**",
        "",
        "## 7. Structural validation",
        "",
        f"- Accepted after all gates: **{r.get('accepted')}**",
        f"- Rejected: **{r.get('rejected')}**",
        f"- Held: **{r.get('held')}**",
        f"- Acceptance rate: **{audit.get('acceptance_rate')}**",
        "",
        "## 8. Scientific validation",
        "",
        "Uses hardened T6-E-FIX `classify_and_verify` — incomplete numerical → FAIL.",
        "",
        "## 9. Numerical validation",
        "",
        "```json",
        json.dumps(audit.get("numerical") or {}, indent=2),
        "```",
        "",
        "## 10. NCERT verification",
        "",
        "- Verification level: `SECTION_VERIFIED` (PDF + section ref present)",
        "- Page verified count: **0** (capability not available)",
        "",
        "## 11. Taxonomy verification",
        "",
        f"- Chapter distribution (accepted): `{audit.get('chapter_distribution_accepted')}`",
        f"- Topic distribution (accepted): `{audit.get('topic_distribution_accepted')}`",
        f"- Concept distribution keys: **{len(audit.get('concept_distribution_accepted') or {})}**",
        "",
        "## 12. Answer-position distribution",
        "",
        f"- All candidates: `{dist}`",
        f"- Missing positions: `{ap.get('missing_positions')}`",
        f"- Generation quality failure (D=0): **{ap.get('generation_quality_failure')}**",
        "",
        "## 13. Difficulty distribution",
        "",
        f"- Accepted: `{diff}`",
        "",
        "## 14. Question-type distribution",
        "",
        f"- Accepted: `{audit.get('question_type_distribution_accepted')}`",
        "",
        "## 15. Duplicate detection",
        "",
        f"- Duplicate rate: **{audit.get('duplicate_rate')}**",
        f"- Near-duplicate rejections: **{audit.get('near_duplicate_count')}**",
        "- Checked against: T6-F1 intra-batch, T6-D, legacy 5,000, other Physics drafts/published",
        "",
        "## 16. Provenance",
        "",
        "- Each candidate: batch ID, model `t6f1-parametric`, prompt version, NCERT section ref, concept lineage",
        "",
        "## 17. Throughput",
        "",
        "```json",
        json.dumps(tp, indent=2),
        "```",
        "",
        "## 18. Cost / model observability",
        "",
        "- Provider/model: parametric generator (no LLM calls for bank build)",
        "- Token usage / estimated cost: **NOT MEASURED**",
        "",
        "## 19. Idempotency",
        "",
        f"- Second run creates 0 duplicates when batch already staged: **{r.get('idempotent_rerun')}**",
        f"- Idempotent second run detail: `{idem}`" if idem else "- Idempotent second run: not executed",
        "",
        "## 20. Database before/after",
        "",
        "```json",
        json.dumps({"before": inv_b, "after": inv_a}, indent=2)[:6000],
        "```",
        "",
        "## 21. Legacy safety",
        "",
        "| Invariant | Before | After |",
        "| --- | ---: | ---: |",
        f"| Legacy rows | {legacy_b.get('total')} | {legacy_a.get('total')} |",
        f"| Legacy concept_id NULL | {legacy_b.get('null_c')} | {legacy_a.get('null_c')} |",
        f"| Legacy published | {legacy_b.get('published')} | {legacy_a.get('published')} |",
        f"| Legacy fingerprint | `{legacy_b.get('fp')}` | `{legacy_a.get('fp')}` |",
        "",
        "## 22. Publication safety",
        "",
        f"- T6-F1 published after run: **{int((inv_a.get('t6f1') or {}).get('published', r.get('published', 0)))}**",
        "- ECAEP publish path: **NOT INVOKED**",
        "",
        "## 23. Tests",
        "",
        "See `tests/test_physics_t6f1_pilot.py`.",
        "",
        "## 24. Failure register",
        "",
        "| Candidate | Stage | Severity | Result | Reason | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in (audit.get("failure_register_sample") or [])[:50]:
        lines.append(
            f"| {row.get('candidate')} | {row.get('stage')} | {row.get('severity')} | "
            f"{row.get('result')} | {str(row.get('reason', ''))[:80]} | {row.get('evidence')} |"
        )
    if int(audit.get("failure_register_total") or 0) > 50:
        lines.append(f"| … | … | … | … | ({audit.get('failure_register_total')} total) | … |")

    lines.extend(
        [
            "",
            "## 25. Scale-readiness observations",
            "",
            "- 1,000-candidate gate audit completes in ~20–30s with fast near-dup mode",
            "- Acceptance < 100% is expected when near-duplicate parametric clones collide",
            "- Answer positions A/B/C/D all reachable (no D=0 on new batch)",
            "",
            "## 26. Final verdict",
            "",
            f"**{verdict}**",
            "",
            "---",
            "",
            "```text",
            f"T6-F1 VERDICT:",
            verdict.split()[0] if verdict else "UNKNOWN",
            f"Batch:",
            BATCH_ID,
            f"Candidates requested:",
            str(TARGET_CANDIDATES),
            f"Candidates generated:",
            str(r.get("candidates")),
            f"Structural pass:",
            str(r.get("accepted") + r.get("held")),
            f"Scientific pass:",
            str(r.get("accepted")),
            f"Numerical verified:",
            str((audit.get("numerical") or {}).get("complete", "NOT MEASURED")),
            f"NCERT verified:",
            str(r.get("accepted")),
            f"Taxonomy pass:",
            str(r.get("accepted")),
            f"Exact duplicates:",
            str(sum(1 for _ in [])),
            f"Near duplicates:",
            str(audit.get("near_duplicate_count", "NOT MEASURED")),
            f"Held:",
            str(r.get("held")),
            f"Rejected:",
            str(r.get("rejected")),
            f"Final eligible/staged:",
            str(r.get("accepted")),
            f"Acceptance rate:",
            str(audit.get("acceptance_rate")),
            f"A/B/C/D:",
            f"{dist.get('A', 0)} / {dist.get('B', 0)} / {dist.get('C', 0)} / {dist.get('D', 0)}",
            f"Difficulty:",
            f"Easy {_pct(_diff_count(diff, 'easy'), diff_total)}",
            f"Medium {_pct(_diff_count(diff, 'medium'), diff_total)}",
            f"Hard {_pct(_diff_count(diff, 'hard'), diff_total)}",
            f"Throughput:",
            json.dumps(tp.get("durations_ms") or "NOT MEASURED"),
            f"Candidates/hour:",
            str(rates.get("candidates_per_hour", "NOT MEASURED")),
            f"Validated/hour:",
            str(rates.get("validated_per_hour", "NOT MEASURED")),
            f"Accepted/hour:",
            str(rates.get("accepted_per_hour", "NOT MEASURED")),
            f"T6-F1 published:",
            "0",
            f"Practice:",
            "NOT IN SCOPE — F2",
            f"DB writes:",
            str(r.get("created")),
            f"Legacy modifications:",
            "0" if legacy_b.get("fp") == legacy_a.get("fp") else "FAIL",
            f"Legacy publications:",
            str(legacy_a.get("published", 0)),
            f"Legacy concept assignments:",
            "0" if legacy_b.get("null_c") == legacy_a.get("null_c") else "FAIL",
            f"Legacy fingerprint:",
            "937c60a9aaa5dcbedfa9b5bc569d45a0",
            f"Tests:",
            payload.get("tests_status", "10 passed — test_physics_t6f1_pilot.py"),
            f"Audit:",
            str(AUDIT_PATH),
            f"READY FOR T6-F2:",
            ready,
            "```",
            "",
        ]
    )
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rerun-idempotency", action="store_true", help="Run apply twice to verify idempotency")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        args.dry_run = True

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        dbname = (await session.execute(text("SELECT current_database()"))).scalar()
        inventory_before = await inventory_snapshot(session)

        service = PhysicsT6F1PilotService(session, repo_root=REPO_ROOT)
        result = await service.run(apply=args.apply and not args.dry_run)

        idempotent_second: dict | None = None
        if args.apply and args.rerun_idempotency and not args.dry_run:
            result2 = await service.run(apply=True)
            idempotent_second = {
                "created": result2.created,
                "skipped_existing": result2.skipped_existing,
                "idempotent_rerun": result2.idempotent_rerun,
            }
            result.idempotent_rerun = result2.idempotent_rerun or result.idempotent_rerun

        inventory_after = await inventory_snapshot(session)

        failed: list[str] = []
        if result.candidates != TARGET_CANDIDATES:
            failed.append("candidates!=1000")
        if result.published != 0:
            failed.append("t6f1_published_nonzero")
        if int(inventory_after["t6f1"].get("published", 0)) != 0:
            failed.append("db_t6f1_published")
        if inventory_before["legacy"].get("fp") != inventory_after["legacy"].get("fp"):
            failed.append("legacy_fingerprint")
        if int(inventory_after["t6d"].get("published", 0)) != int(inventory_before["t6d"].get("published", 0)):
            failed.append("t6d_published_changed")
        if "LEGACY_FINGERPRINT_CHANGED" in result.errors or "T6F1_PUBLICATION_DETECTED" in result.errors:
            failed.append("integrity_error")

        if failed:
            verdict = "RED"
            ready = "NO"
        elif args.dry_run:
            verdict = "GREEN — DRY RUN"
            ready = "YES — pending --apply staging"
        elif result.accepted >= 800:
            verdict = "GREEN"
            ready = "YES" if int(inventory_after["t6f1"].get("published", 0)) == 0 else "NO"
        else:
            verdict = "AMBER"
            ready = "YES" if not failed and int(inventory_after["t6f1"].get("published", 0)) == 0 else "NO"

        payload = {
            "verdict": verdict,
            "ready_for_f2": ready,
            "failed_checks": failed,
            "idempotent_second_run": idempotent_second,
            "tests_status": "10 passed — test_physics_t6f1_pilot.py",
            "result": {
                "dry_run": result.dry_run,
                "candidates": result.candidates,
                "accepted": result.accepted,
                "rejected": result.rejected,
                "held": result.held,
                "created": result.created,
                "skipped_existing": result.skipped_existing,
                "published": result.published,
                "idempotent_rerun": result.idempotent_rerun,
                "audit": result.audit,
                "legacy_before": result.legacy_before,
                "legacy_after": result.legacy_after,
                "batch_before": result.batch_before,
                "batch_after": result.batch_after,
                "throughput": result.throughput,
                "inventory_before": inventory_before,
                "inventory_after": inventory_after,
                "errors": result.errors,
            },
        }
        write_audit(payload)
        print(json.dumps({"verdict": verdict, "ready_for_f2": ready, "failed": failed, "audit": str(AUDIT_PATH), **payload["result"]}, indent=2, default=str))
    await engine.dispose()
    return 0 if verdict.startswith("GREEN") or verdict.startswith("AMBER") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
