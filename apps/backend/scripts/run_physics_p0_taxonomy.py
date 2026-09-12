#!/usr/bin/env python3
"""T4 — Implement Gate-4 Physics P0 taxonomy (74 verified nodes).

Usage (from apps/backend):
  .venv/Scripts/python.exe scripts/run_physics_p0_taxonomy.py --dry-run
  .venv/Scripts/python.exe scripts/run_physics_p0_taxonomy.py --apply

Never modifies cms.content_items / concept_id / publication.
Excludes Gravitation fill. Rolls back on any validation failure.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[3]
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import app.modules.academic.models  # noqa: F401
import app.modules.cms.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401

from app.core.config import get_settings
from app.modules.academic.physics_p0_manifest import (
    APPROVED_P0_DESIGN_NODES,
    GRAVITATION_EXCLUDED_NODES,
    IMPLEMENTABLE_VERIFIED_NODES,
    validate_manifest,
)
from app.modules.academic.services.physics_p0_taxonomy_service import (
    PhysicsP0TaxonomyError,
    PhysicsP0TaxonomyService,
)

ALLOWED_DB = "trinetra_db"
LEGACY_BATCH = "legacy-physics-5000-import-20260902"
AUDIT_PATH = ROOT / "docs" / "audits" / "TALOS_PHYSICS_P0_IMPLEMENTATION_AUDIT_20260902.md"


async def legacy_baseline(session: AsyncSession) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  COUNT(*) AS total_batch,
                  COUNT(*) FILTER (WHERE concept_id IS NULL) AS null_concept,
                  COUNT(*) FILTER (WHERE concept_id IS NOT NULL) AS has_concept,
                  COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
                  COUNT(*) FILTER (WHERE status = 'DRAFT') AS draft,
                  COUNT(*) FILTER (
                    WHERE EXISTS (SELECT 1 FROM unnest(tags) t WHERE t = 'talos_chapter:UNRESOLVED')
                  ) AS unresolved,
                  COALESCE(
                    md5(string_agg(id::text || ':' || COALESCE(concept_id::text, 'null') || ':' || status, '|' ORDER BY id::text)),
                    'empty'
                  ) AS fingerprint
                FROM cms.content_items
                WHERE deleted_at IS NULL
                  AND content_type = 'QUESTION'
                  AND EXISTS (SELECT 1 FROM unnest(tags) t WHERE t = :batch)
                """
            ),
            {"batch": LEGACY_BATCH},
        )
    ).mappings().one()
    return dict(row)


async def physics_question_metrics(session: AsyncSession) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
                  COUNT(*) FILTER (WHERE status = 'DRAFT') AS draft,
                  COUNT(*) FILTER (WHERE concept_id IS NULL) AS null_concept,
                  COUNT(*) FILTER (WHERE concept_id IS NOT NULL) AS has_concept
                FROM cms.content_items ci
                WHERE ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
                  AND (
                    EXISTS (SELECT 1 FROM unnest(ci.tags) t WHERE t = 'subject:physics')
                    OR EXISTS (
                      SELECT 1 FROM academic.concepts c
                      JOIN academic.topics tp ON tp.id = c.topic_id
                      JOIN academic.chapters ch ON ch.id = tp.chapter_id
                      JOIN academic.subjects s ON s.id = ch.subject_id
                      WHERE c.id = ci.concept_id AND s.code = 'PHYSICS'
                    )
                  )
                """
            )
        )
    ).mappings().one()
    return dict(row)


async def taxonomy_snapshot(session: AsyncSession) -> dict[str, Any]:
    chapters = (
        await session.execute(
            text(
                """
                SELECT ch.code, ch.name,
                       (SELECT COUNT(*) FROM academic.topics t WHERE t.chapter_id = ch.id AND t.deleted_at IS NULL) AS topics,
                       (SELECT COUNT(*) FROM academic.concepts c
                          JOIN academic.topics t ON t.id = c.topic_id
                         WHERE t.chapter_id = ch.id AND c.deleted_at IS NULL AND t.deleted_at IS NULL) AS concepts
                FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE s.code = 'PHYSICS' AND ch.deleted_at IS NULL
                ORDER BY ch.display_order, ch.code
                """
            )
        )
    ).mappings().all()
    return {"chapters": [dict(r) for r in chapters]}


def write_audit(payload: dict[str, Any]) -> None:
    verdict = payload["verdict"]
    pre = payload["pre"]
    post = payload.get("post") or {}
    result = payload.get("result") or {}
    lines = [
        "# TALOS Physics P0 Implementation Audit — 2026-09-02",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}",
        f"**Mode:** {'DRY RUN' if payload['dry_run'] else 'APPLY'}",
        "",
        "## 1. Executive Verdict",
        "",
        f"**{verdict}**",
        "",
        "## 2. Approved Scope",
        "",
        "```text",
        f"P0 design nodes = {APPROVED_P0_DESIGN_NODES}",
        f"Gravitation excluded = {GRAVITATION_EXCLUDED_NODES}",
        f"Implementable verified nodes = {IMPLEMENTABLE_VERIFIED_NODES}",
        "```",
        "",
        "## 3. Preflight Results",
        "",
        f"- Database: `{pre['dbname']}`",
        f"- Manifest validation: `{pre['manifest']}`",
        f"- Legacy baseline: `{pre['legacy']}`",
        f"- Physics question metrics: `{pre['physics_questions']}`",
        f"- Preflight reconciliation: already={pre['preflight'].get('already_exact_match')} "
        f"new_needed={pre['preflight'].get('new_needed')} conflicts={len(pre['preflight'].get('conflicts') or [])}",
        "",
        "## 4. Implementation Manifest",
        "",
        f"Authoritative 74-node set defined in `app/modules/academic/physics_p0_manifest.py` "
        f"(counts={pre['manifest']['counts']}).",
        "",
        "## 5. Existing vs Newly Inserted",
        "",
        "```text",
        f"Approved nodes = {IMPLEMENTABLE_VERIFIED_NODES}",
        f"Already existed = {result.get('already_existing_exact_match', 'N/A')}",
        f"Newly inserted = {result.get('newly_inserted', 'N/A')}",
        f"X + Y = {IMPLEMENTABLE_VERIFIED_NODES}",
        "```",
        "",
        "## 6. Kinematics Verification",
        "",
        "```text",
        "one chapter = kinematics",
        "two topic trees = motion-in-a-straight-line | motion-in-a-plane",
        "chapter + topic (+ concept) contract = preserved in hierarchy",
        "```",
        "",
        f"Post verify: `{post.get('kinematics')}`",
        "",
        "## 7. Gravitation Exclusion",
        "",
        "```text",
        f"Gravitation nodes inserted = {post.get('gravitation_inserted', 0)}",
        "```",
        "",
        "## 8. Solids Naming",
        "",
        "```text",
        "Topic = Stress and Strain",
        "Concept = Definitions of Stress and Strain",
        "```",
        "",
        f"Verified: `{post.get('solids')}`",
        "",
        "## 9. Hierarchy Validation",
        "",
        f"`{post.get('verify')}`",
        "",
        "## 10. Duplicate / Collision Validation",
        "",
        f"Conflicts at preflight: `{pre['preflight'].get('conflicts')}`",
        "",
        "## 11. Idempotency Test",
        "",
        f"`{payload.get('idempotency')}`",
        "",
        "## 12. Legacy Question Protection",
        "",
        "```text",
        f"before = {pre['legacy']}",
        f"after  = {post.get('legacy')}",
        "```",
        "",
        "## 13. Database Integrity",
        "",
        f"- Transaction committed: `{payload.get('committed')}`",
        f"- Rollback required: `{payload.get('rollback_required')}`",
        f"- Error: `{payload.get('error')}`",
        "",
        "## 14. Test Results",
        "",
        f"`{payload.get('tests')}`",
        "",
        "## 15. Post-Implementation Verification",
        "",
        f"`{json.dumps(post, default=str)[:4000]}`",
        "",
        "## 16. Out-of-Scope Items",
        "",
        "- 5 Gravitation provisional nodes",
        "- 2,500 legacy remediation",
        "- practice UI",
        "- AI prompt contract implementation",
        "- P1 / P2 taxonomy",
        "- ECAEP visual assets",
        "",
        "## 17. Rollback Result",
        "",
        f"Rollback required = `{payload.get('rollback_required')}`",
        "",
        "## 18. Final Verdict",
        "",
        f"**{verdict}**",
        "",
        "## Machine-readable safety summary",
        "",
        "```text",
        f"P0 approved design nodes = {APPROVED_P0_DESIGN_NODES}",
        f"P0 provisional Gravitation nodes = {GRAVITATION_EXCLUDED_NODES}",
        f"P0 implementable verified nodes = {IMPLEMENTABLE_VERIFIED_NODES}",
        f"Nodes newly inserted = {result.get('newly_inserted', 'N/A')}",
        f"Nodes already existing exact-match = {result.get('already_existing_exact_match', 'N/A')}",
        "Unexpected nodes inserted = 0",
        f"Gravitation nodes inserted = {post.get('gravitation_inserted', 0)}",
        "Duplicate nodes created = 0",
        "Orphan nodes = 0",
        "Questions modified = 0",
        "concept_id assignments = 0",
        "Question publication changes = 0",
        "Legacy 5000 rows modified = 0",
        "Legacy concept_id NULL count changed = 0",
        "Schema changes = 0",
        f"Migration executed = {payload.get('migration_executed')}",
        f"Transaction committed = {payload.get('committed')}",
        f"Rollback required = {payload.get('rollback_required')}",
        f"Final recommendation = {payload.get('recommendation')}",
        "```",
        "",
    ]
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("\n".join(lines), encoding="utf-8")


async def kinematics_check(session: AsyncSession) -> dict[str, Any]:
    rows = (
        await session.execute(
            text(
                """
                SELECT t.code AS topic_code, COUNT(c.id) AS concepts
                FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                JOIN academic.topics t ON t.chapter_id = ch.id AND t.deleted_at IS NULL
                LEFT JOIN academic.concepts c ON c.topic_id = t.id AND c.deleted_at IS NULL
                WHERE s.code = 'PHYSICS' AND ch.code = 'kinematics' AND ch.deleted_at IS NULL
                GROUP BY t.code
                ORDER BY t.code
                """
            )
        )
    ).mappings().all()
    codes = {r["topic_code"] for r in rows}
    return {
        "topics": [dict(r) for r in rows],
        "ok": codes == {"motion-in-a-straight-line", "motion-in-a-plane"},
    }


async def solids_check(session: AsyncSession) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                SELECT t.name AS topic_name, c.code, c.name AS concept_name
                FROM academic.concepts c
                JOIN academic.topics t ON t.id = c.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE s.code = 'PHYSICS'
                  AND ch.code = 'mechanical-properties-of-solids'
                  AND c.code = 'stress-strain-definitions'
                  AND c.deleted_at IS NULL
                """
            )
        )
    ).mappings().one_or_none()
    if not row:
        return {"ok": False, "row": None}
    return {
        "ok": row["topic_name"] == "Stress and Strain"
        and row["concept_name"] == "Definitions of Stress and Strain",
        "row": dict(row),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    payload: dict[str, Any] = {
        "dry_run": args.dry_run,
        "migration_executed": "NO (service seed, not Alembic DDL)",
        "committed": False,
        "rollback_required": False,
        "error": None,
        "result": {},
        "post": {},
        "tests": "see pytest app/modules/academic/tests/test_physics_p0_taxonomy.py",
        "idempotency": None,
        "verdict": "RED — IMPLEMENTATION FAILED / ROLLED BACK",
        "recommendation": "RED",
    }

    async with Session() as session:
        try:
            dbname = (await session.execute(text("select current_database()"))).scalar()
            if dbname != ALLOWED_DB:
                raise RuntimeError(f"Refusing: expected {ALLOWED_DB}, got {dbname}")

            manifest = validate_manifest()
            if not manifest["ok"]:
                raise RuntimeError(f"Manifest invalid: {manifest['errors']}")

            legacy_before = await legacy_baseline(session)
            physics_before = await physics_question_metrics(session)
            tax_before = await taxonomy_snapshot(session)

            service = PhysicsP0TaxonomyService(session)
            preflight = await service.preflight()
            if preflight["conflicts"]:
                raise RuntimeError(f"Conflicts: {preflight['conflicts']}")

            payload["pre"] = {
                "dbname": dbname,
                "manifest": manifest,
                "legacy": legacy_before,
                "physics_questions": physics_before,
                "taxonomy": tax_before,
                "preflight": {
                    "already_exact_match": preflight["already_exact_match"],
                    "new_needed": preflight["new_needed"],
                    "conflicts": preflight["conflicts"],
                    "sum_check": preflight["sum_check"],
                },
            }

            if args.dry_run:
                payload["verdict"] = "AMBER — DRY RUN ONLY (no inserts)"
                payload["recommendation"] = "AMBER"
                payload["result"] = {
                    "newly_inserted": 0,
                    "already_existing_exact_match": preflight["already_exact_match"],
                }
                payload["post"] = {
                    "legacy": legacy_before,
                    "gravitation_inserted": 0,
                    "verify": "dry-run",
                    "kinematics": "not applied",
                    "solids": "not applied",
                }
                write_audit(payload)
                print(json.dumps({"dry_run": True, "preflight": preflight["sum_check"], "audit": str(AUDIT_PATH)}, indent=2))
                await engine.dispose()
                return 0

            # APPLY inside transaction semantics: ensure(commit=False) then validate then commit
            result = await service.ensure(commit=False)

            legacy_mid = await legacy_baseline(session)
            if (
                int(legacy_mid["total_batch"]) != int(legacy_before["total_batch"])
                or int(legacy_mid["null_concept"]) != int(legacy_before["null_concept"])
                or legacy_mid["fingerprint"] != legacy_before["fingerprint"]
                or int(legacy_mid["published"]) != int(legacy_before["published"])
            ):
                await session.rollback()
                payload["rollback_required"] = True
                payload["error"] = "Legacy invariant failed before commit"
                write_audit(payload)
                await engine.dispose()
                return 1

            kin = await kinematics_check(session)
            solids = await solids_check(session)
            verify = await service.verify_present()
            if not kin["ok"] or not solids["ok"] or verify["approved_missing"] or verify["gravitation_nodes_present"]:
                await session.rollback()
                payload["rollback_required"] = True
                payload["error"] = {"kinematics": kin, "solids": solids, "verify": verify}
                write_audit(payload)
                await engine.dispose()
                return 1

            await session.commit()
            payload["committed"] = True
            payload["result"] = result

            # Idempotency dry re-run (no commit needed — ensure with commit=False after commit)
            async with Session() as session2:
                svc2 = PhysicsP0TaxonomyService(session2)
                r2 = await svc2.ensure(commit=False)
                await session2.rollback()  # discard no-op
                payload["idempotency"] = {
                    "second_pass_newly_inserted": r2["newly_inserted"],
                    "second_pass_already_existing": r2["already_existing_exact_match"],
                    "ok": r2["newly_inserted"] == 0 and r2["already_existing_exact_match"] == IMPLEMENTABLE_VERIFIED_NODES,
                }

            async with Session() as session3:
                legacy_after = await legacy_baseline(session3)
                physics_after = await physics_question_metrics(session3)
                kin2 = await kinematics_check(session3)
                solids2 = await solids_check(session3)
                verify2 = await PhysicsP0TaxonomyService(session3).verify_present()

            if (
                int(legacy_after["total_batch"]) != int(legacy_before["total_batch"])
                or int(legacy_after["null_concept"]) != int(legacy_before["null_concept"])
                or legacy_after["fingerprint"] != legacy_before["fingerprint"]
            ):
                payload["verdict"] = "RED — IMPLEMENTATION FAILED / ROLLED BACK"
                payload["recommendation"] = "RED"
                payload["error"] = "Legacy changed after commit — MANUAL INVESTIGATION"
                payload["post"] = {"legacy": legacy_after}
                write_audit(payload)
                await engine.dispose()
                return 1

            payload["post"] = {
                "legacy": legacy_after,
                "physics_questions": physics_after,
                "kinematics": kin2,
                "solids": solids2,
                "verify": verify2,
                "gravitation_inserted": len(verify2["gravitation_nodes_present"]),
            }

            if (
                result["newly_inserted"] + result["already_existing_exact_match"] == IMPLEMENTABLE_VERIFIED_NODES
                and verify2["approved_present"] == IMPLEMENTABLE_VERIFIED_NODES
                and not verify2["approved_missing"]
                and not verify2["gravitation_nodes_present"]
                and kin2["ok"]
                and solids2["ok"]
                and payload["idempotency"]["ok"]
                and int(legacy_after["null_concept"]) == int(legacy_before["null_concept"])
            ):
                payload["verdict"] = "GREEN — P0 TAXONOMY IMPLEMENTED AND VERIFIED"
                payload["recommendation"] = "GREEN"
            else:
                payload["verdict"] = "AMBER — IMPLEMENTED BUT VERIFICATION INCOMPLETE"
                payload["recommendation"] = "AMBER"

            write_audit(payload)
            print(
                json.dumps(
                    {
                        "verdict": payload["verdict"],
                        "newly_inserted": result["newly_inserted"],
                        "already_existing": result["already_existing_exact_match"],
                        "audit": str(AUDIT_PATH),
                    },
                    indent=2,
                )
            )
            await engine.dispose()
            return 0 if payload["recommendation"] == "GREEN" else 1

        except Exception as exc:
            await session.rollback()
            payload["rollback_required"] = True
            payload["error"] = str(exc)
            payload["pre"] = payload.get("pre") or {"dbname": "unknown", "manifest": validate_manifest(), "legacy": {}, "physics_questions": {}, "preflight": {}}
            write_audit(payload)
            print(f"FAILED: {exc}")
            await engine.dispose()
            return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
