#!/usr/bin/env python3
"""T6-F2 integrity + deep idempotency evidence (safe no-op publish rerun).

Captures content fingerprints for T6-D, legacy, protected non-F1 CMS, and
published T6-F1 bodies; runs an idempotent publish pass; re-fingerprints.

Does NOT modify T6-D/legacy bodies. Second publish is expected to create 0
new publications when the batch is already fully published.

Usage:
  python scripts/run_physics_t6f2_integrity_verify.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
import app.modules.knowledge.models  # noqa: F401
from app.modules.cms.acquisition.physics_integrity_fingerprints import (
    collect_integrity_snapshot,
    diff_row_canons,
)
from app.modules.cms.acquisition.physics_t6f2_service import PhysicsT6F2PublishService

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_PATH = REPO_ROOT / "docs" / "audits" / "TALOS_T6F2_INTEGRITY_IDEMPOTENCY_EVIDENCE_20260902.json"


async def main() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        db = (await session.execute(text("SELECT current_database()"))).scalar()
        before = await collect_integrity_snapshot(session)

        service = PhysicsT6F2PublishService(session, repo_root=REPO_ROOT)
        # Safe: already-published batch → staged=0 short-circuit or skip-all
        result = await service.run(apply=True, publish=True)

        after = await collect_integrity_snapshot(session)

        t6d_diff = diff_row_canons(before["t6d_row_canons"], after["t6d_row_canons"])
        protected_diff = diff_row_canons(
            before["protected_row_canons"], after["protected_row_canons"]
        )

        # Strip bulky row maps from persisted before/after (keep counts + fps)
        before_out = {k: v for k, v in before.items() if not k.endswith("_row_canons")}
        after_out = {k: v for k, v in after.items() if not k.endswith("_row_canons")}

        t6d_report = {
            "population": "physics-t6d-pilot-20260902",
            "before_count": before["t6d"]["total"],
            "before_fingerprint": before["t6d"]["content_fp"],
            "after_count": after["t6d"]["total"],
            "after_fingerprint": after["t6d"]["content_fp"],
            **t6d_diff,
            "historical_pre_f2": "NOT RETROACTIVELY VERIFIABLE",
        }
        protected_report = {
            "population": "all CMS QUESTION except T6-F1 batch (intentional F2 publish excluded)",
            "protected_population_before": before["protected_non_f1_cms"]["total"],
            "protected_population_after": after["protected_non_f1_cms"]["total"],
            "before_fingerprint": before["protected_non_f1_cms"]["content_fp"],
            "after_fingerprint": after["protected_non_f1_cms"]["content_fp"],
            "unexpected_updates": protected_diff["unexpected_updates"],
            "unexpected_inserts": protected_diff["unexpected_inserts"],
            "unexpected_deletes": protected_diff["unexpected_deletes"],
            "unexpected_status_changes": protected_diff["unexpected_status_or_content_changes"],
            "unexpected_content_changes": protected_diff["unexpected_status_or_content_changes"],
            "historical_pre_f2": "NOT RETROACTIVELY VERIFIABLE",
        }

        payload = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "database": db,
            "historical_pre_f2_note": (
                "Deep T6-D / protected-CMS content fingerprints were NOT captured "
                "immediately before the original T6-F2 publication. That historical "
                "window is NOT RETROACTIVELY VERIFIABLE. This artifact proves "
                "post-publication stability across an idempotent rerun."
            ),
            "before": before_out,
            "idempotent_run": {
                "first_run_context": "batch already published (938); this is SECOND-RUN evidence",
                "eligible_population": result.eligible,
                "published_new": result.published,
                "already_published": result.already_published,
                "staged": result.staged,
                "errors": result.errors,
                "idempotent_rerun": result.idempotent_rerun or result.published == 0,
                "t6f1_content_fp_before": before["t6f1_published"]["content_fp"],
                "t6f1_content_fp_after": after["t6f1_published"]["content_fp"],
                "t6f1_content_unchanged": before["t6f1_published"]["content_fp"]
                == after["t6f1_published"]["content_fp"],
            },
            "after": after_out,
            "t6d_integrity": t6d_report,
            "protected_cms_mutations": protected_report,
            "comparisons": {
                "t6d_count_stable": before["t6d"]["total"] == after["t6d"]["total"] == 100,
                "t6d_fp_stable": before["t6d"]["content_fp"] == after["t6d"]["content_fp"],
                "t6d_changed_rows": t6d_diff["changed_rows"],
                "t6d_added_rows": t6d_diff["added_rows"],
                "t6d_deleted_rows": t6d_diff["deleted_rows"],
                "legacy_count_stable": before["legacy"]["total"] == after["legacy"]["total"] == 5000,
                "legacy_fp_stable": before["legacy"]["content_fp"] == after["legacy"]["content_fp"],
                "protected_cms_fp_stable": before["protected_non_f1_cms"]["content_fp"]
                == after["protected_non_f1_cms"]["content_fp"],
                "protected_unexpected_updates": protected_diff["unexpected_updates"],
                "protected_unexpected_inserts": protected_diff["unexpected_inserts"],
                "protected_unexpected_deletes": protected_diff["unexpected_deletes"],
                "t6f1_published_fp_stable": before["t6f1_published"]["content_fp"]
                == after["t6f1_published"]["content_fp"],
                "t6f1_published_count": int(after["t6f1_published"]["total"]),
                "new_publications_on_rerun": result.published,
            },
        }
        payload["comparisons"]["all_required_stable"] = all(
            [
                payload["comparisons"]["t6d_count_stable"],
                payload["comparisons"]["t6d_fp_stable"],
                payload["comparisons"]["t6d_changed_rows"] == 0,
                payload["comparisons"]["t6d_added_rows"] == 0,
                payload["comparisons"]["t6d_deleted_rows"] == 0,
                payload["comparisons"]["legacy_count_stable"],
                payload["comparisons"]["legacy_fp_stable"],
                payload["comparisons"]["protected_cms_fp_stable"],
                payload["comparisons"]["protected_unexpected_updates"] == 0,
                payload["comparisons"]["protected_unexpected_inserts"] == 0,
                payload["comparisons"]["protected_unexpected_deletes"] == 0,
                payload["comparisons"]["t6f1_published_fp_stable"],
                payload["comparisons"]["new_publications_on_rerun"] == 0,
                payload["comparisons"]["t6f1_published_count"] == 938,
            ]
        )

        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": payload["comparisons"]["all_required_stable"],
                    "artifact": str(OUT_PATH),
                    **payload["comparisons"],
                    "t6d_integrity": t6d_report,
                    "protected_cms_mutations": protected_report,
                },
                indent=2,
                default=str,
            )
        )
    await engine.dispose()
    return 0 if payload["comparisons"]["all_required_stable"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
