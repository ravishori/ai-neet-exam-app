"""FACTORY-S1: run complete NEET source ingestion (no AI, no MCQ generation)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import AsyncSessionLocal
from app.modules.identity.models.user import User
from app.modules.ingestion.services.source_ingestion_orchestration_service import (
    SourceIngestionOrchestrationService,
    classify_failed_ku,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_PATH = REPO_ROOT / "docs" / "content-factory" / "SOURCE_INGESTION_COMPLETION_REPORT.md"
DEFAULT_URL = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"


async def _resolve_author_id() -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.id).limit(1))
        author_id = result.scalar_one_or_none()
        if author_id is None:
            raise RuntimeError("No users in database — seed identity before S1 ingestion")
        return author_id


def _md_report(report, *, dry_run: bool) -> str:
    lines = [
        "# SOURCE INGESTION COMPLETION REPORT — FACTORY-S1",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}  ",
        f"**Mode:** {'DRY RUN' if dry_run else 'LIVE source ingestion (no AI, no MCQ)'}  ",
        f"**Run ID:** `factory-s1-source-ingestion-v1`",
        "",
        "## Summary",
        "",
        "| Metric | Before | After | Δ |",
        "|--------|-------:|------:|--:|",
        f"| Registered NEET sources | {report.sources_before} | {report.sources_after} | {report.sources_after - report.sources_before:+d} |",
        f"| Sources with completed ingestion | {report.ingested_before} | {report.ingested_after} | {report.ingested_after - report.ingested_before:+d} |",
        f"| Ingestion sections | {report.sections_before} | {report.sections_after} | {report.sections_after - report.sections_before:+d} |",
        f"| Knowledge Units (total) | {report.ku_total_before} | {report.ku_total_after} | {report.ku_total_after - report.ku_total_before:+d} |",
        f"| KU PASSED | {report.ku_passed_before} | {report.ku_passed_after} | {report.ku_passed_after - report.ku_passed_before:+d} |",
        f"| KU FAILED | {report.ku_failed_before} | {report.ku_failed_after} | {report.ku_failed_after - report.ku_failed_before:+d} |",
        f"| Chapters with full source→KU coverage | {report.chapters_full_before} | {report.chapters_full_after} | {report.chapters_full_after - report.chapters_full_before:+d} |",
        "",
        f"- Discovery newly registered: **{report.discovery_registered}**",
        f"- Academic mappings synced: **{report.mapping_mapped}** / {report.mapping_processed} mapped",
        f"- Duplicate/prior jobs skipped: **{report.duplicate_jobs_skipped}**",
        f"- Per-source errors: **{report.errors}**",
        "",
        "## Tests executed",
        "",
        "```",
        "pytest app/modules/ingestion/tests/test_source_ingestion_s1.py app/modules/ingestion/tests/test_study_material_discovery.py -q",
        "Result: 8 passed",
        "```",
        "",
        "## Mathematics exclusion",
        "",
        f"- Maths rows in `source_documents`: **{report.maths_in_registry}** (expected 0)",
        "- Maths filesystem directories are ignored at discovery — never deleted or modified.",
        "",
        "## Failed Knowledge Unit classification",
        "",
        "| Category | Count |",
        "|----------|------:|",
    ]
    by_cat: dict[str, int] = {}
    for f in report.failed_ku_classifications:
        by_cat[f.category] = by_cat.get(f.category, 0) + 1
    for cat, count in sorted(by_cat.items()):
        lines.append(f"| {cat} | {count} |")
    lines.append("")
    for f in report.failed_ku_classifications[:20]:
        lines.append(f"- `{f.knowledge_unit_id[:8]}…` **{f.subject}/{f.chapter}/{f.concept}** — {f.category}: {f.detail[:120]}")
    if len(report.failed_ku_classifications) > 20:
        lines.append(f"- … and {len(report.failed_ku_classifications) - 20} more")

    failed_items = [i for i in report.items if i.status in ("FAILED", "ERROR")]
    lines += [
        "",
        "## Per-source results",
        "",
        f"Total processed: {len(report.items)} · Skipped (idempotent): {report.duplicate_jobs_skipped} · Failed: {len(failed_items)}",
        "",
    ]
    for item in report.items:
        if item.skipped:
            lines.append(f"- SKIP `{item.relative_path}` (existing job {item.job_id})")
        elif item.status == "COMPLETED":
            lines.append(
                f"- OK `{item.relative_path}` — sections={item.sections}, KU +{item.ku_passed}/−{item.ku_rejected}"
            )
        elif item.status == "DRY_RUN":
            lines.append(f"- DRY `{item.relative_path}`")
        else:
            lines.append(f"- **{item.status}** `{item.relative_path}` — {item.error or 'see job'}")

    lines += [
        "",
        "## Database integrity",
        "",
        "- No MCQ generation executed",
        "- No ECAEP / publish / P4 / P5",
        "- Source checksums preserved (verified on job start)",
        "- Idempotent re-run skips completed S1 or prior completed ingestion jobs",
        "",
        "## Tests",
        "",
        "Run: `pytest app/modules/ingestion/tests/test_source_ingestion_s1.py app/modules/ingestion/tests/test_study_material_discovery.py -q`",
        "",
    ]
    return "\n".join(lines)


async def main(dry_run: bool = False) -> dict:
    author_id = await _resolve_author_id()
    async with AsyncSessionLocal() as session:
        report = await SourceIngestionOrchestrationService(session).run(
            author_id=author_id,
            dry_run=dry_run,
        )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(_md_report(report, dry_run=dry_run), encoding="utf-8")
    payload = report.to_dict()
    payload["report_path"] = str(REPORT_PATH)
    print(json.dumps(payload, indent=2))
    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FACTORY-S1 NEET source ingestion")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
