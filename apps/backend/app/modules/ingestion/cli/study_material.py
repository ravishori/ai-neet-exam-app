"""CLI: discover NEET StudyMaterial PDFs into ingestion.source_documents.

Run from apps/backend::

    python -m app.modules.ingestion.cli.study_material discover
    python -m app.modules.ingestion.cli.study_material discover --dry-run
    python -m app.modules.ingestion.cli.study_material import-inventory

Uses Settings.study_material_dir only — never a client-supplied root.
Does not generate MCQs (ADR-0030 Phase A).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

# Allow `python -m app.modules.ingestion.cli.study_material` from apps/backend
# and also `python scripts/...` style when sys.path is already set.
from app.core.database import AsyncSessionLocal
from app.modules.ingestion.models.source_document import NEET_SUBJECT_CODES, SourceDocument
from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.pilot_mcq_orchestration_service import PilotMcqOrchestrationService
from app.modules.ingestion.services.source_academic_mapping_service import SourceAcademicMappingService
from app.modules.ingestion.services.study_material_discovery_service import StudyMaterialDiscoveryService
from app.modules.ingestion.services.study_material_path_parser import StudyMaterialPathError, parse_study_material_path


def _print_report(report) -> None:
    print("NEET StudyMaterial Discovery")
    print("----------------------------")
    subject_order = ("PHYSICS", "CHEMISTRY", "BIOLOGY")
    by = report.by_subject_class or {}
    for subject in subject_order:
        class_counts = by.get(subject, {})
        print(f"{subject.title()}:")
        print(f"  Class 11: {class_counts.get('11', 0)}")
        print(f"  Class 12: {class_counts.get('12', 0)}")
    print(f"Total NEET PDFs: {report.discovered}")
    print(f"Registered: {report.registered}")
    print(f"Duplicates: {report.duplicates}")
    print(f"Skipped: {report.skipped}")
    print(f"Errors: {report.errors}")
    if report.page_count_total:
        print(f"Pages: {report.page_count_total}")
    if report.dry_run:
        print("(dry-run - no rows written)")


async def _cmd_map() -> int:
    async with AsyncSessionLocal() as session:
        report = await SourceAcademicMappingService(session).sync_all()
    print("NEET Source Academic Mapping")
    print("----------------------------")
    print(f"Processed: {report.processed}")
    print(f"Mapped: {report.mapped}")
    print(f"Unmapped: {report.unmapped}")
    print(f"Pilot-ready: {report.pilot_ready}")
    print(f"Created: {report.created}")
    print(f"Updated: {report.updated}")
    if report.pilot_sources:
        print("Pilot sources:")
        for row in report.pilot_sources:
            print(f"  - {row['relative_source_path']} -> {row['academic_subject_code']}/{row['chapter_code']}")
    return 0


async def _cmd_coverage() -> int:
    async with AsyncSessionLocal() as session:
        report = await SourceAcademicMappingService(session).coverage_report()
    print("NEET Source Coverage")
    print("--------------------")
    print(f"Present: {report.present}")
    print(f"Mapped: {report.mapped}")
    print(f"Unmapped: {report.unmapped}")
    print(f"Pilot-ready: {report.pilot_ready}")
    for subject, counts in sorted(report.by_subject.items()):
        print(f"{subject}: {counts}")
    return 0


async def _resolve_author_id(session) -> uuid.UUID:
    from sqlalchemy import select

    from app.modules.identity.models.user import User

    result = await session.execute(select(User.id).limit(1))
    author_id = result.scalar_one_or_none()
    if author_id is None:
        raise RuntimeError("No users in database — seed identity before running pilot")
    return author_id


async def _cmd_pilot_mcq(*, force: bool, dry_run: bool, pilot_run_id: str | None) -> int:
    async with AsyncSessionLocal() as session:
        author_id = await _resolve_author_id(session)
        kwargs: dict = {"author_id": author_id, "force": force, "dry_run": dry_run}
        if pilot_run_id:
            kwargs["pilot_run_id"] = pilot_run_id
        report = await PilotMcqOrchestrationService(session).run(**kwargs)
    print("Phase D — 30-MCQ Pilot")
    print("----------------------")
    print(f"Pilot run: {report.pilot_run_id}")
    if report.blocked:
        print(f"BLOCKED: {report.block_reason}")
        return 1
    for subj in report.subjects:
        print(
            f"{subj.label}: {subj.questions_generated}/{subj.questions_target} "
            f"status={subj.status} job={subj.ingestion_job_id}"
        )
        if subj.error:
            print(f"  error: {subj.error}")
    print(f"Total: {report.total_generated}/{report.total_target}")
    return 0 if report.total_generated >= report.total_target or dry_run else 1


async def _cmd_discover(*, dry_run: bool) -> int:
    async with AsyncSessionLocal() as session:
        service = StudyMaterialDiscoveryService(session)
        report = await service.discover(dry_run=dry_run)
    _print_report(report)
    return 0 if report.errors == 0 else 1


async def _cmd_import_inventory(inventory_path: Path) -> int:
    """One-shot import of scripts/StudyMaterial_INVENTORY.json.

    Runtime source of truth remains filesystem + source_documents.
    Maths entries in the JSON are ignored.
    """
    if not inventory_path.is_file():
        print(f"Inventory not found: {inventory_path}", file=sys.stderr)
        return 1

    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    files = payload.get("files") or []
    registered = 0
    duplicates = 0
    skipped = 0
    errors = 0

    async with AsyncSessionLocal() as session:
        repo = SourceDocumentRepository(session)
        for row in files:
            rel = row.get("relative_source_path") or ""
            subject = (row.get("subject") or "").strip()
            if subject.lower() == "maths" or subject.upper() == "MATHS":
                skipped += 1
                continue
            try:
                parsed = parse_study_material_path(rel)
            except StudyMaterialPathError:
                skipped += 1
                continue
            if parsed.subject_code not in NEET_SUBJECT_CODES:
                skipped += 1
                continue

            checksum = row.get("checksum_sha256")
            if not checksum:
                errors += 1
                continue
            existing = await repo.get_by_checksum(checksum)
            if existing:
                duplicates += 1
                continue

            doc = SourceDocument(
                relative_source_path=parsed.relative_source_path,
                file_name=parsed.file_name,
                file_type=row.get("file_type") or "pdf",
                file_size=int(row.get("file_size") or 0),
                checksum_sha256=checksum,
                absolute_source_path_dev=row.get("absolute_source_path_dev"),
                storage_key=None,
                class_level=parsed.class_level,
                subject_code=parsed.subject_code,
                title=row.get("title") or Path(parsed.file_name).stem,
                publisher=row.get("publisher"),
                edition=row.get("edition"),
                page_count=row.get("page_count"),
                ingestion_status="DISCOVERED",
            )
            repo.add(doc)
            registered += 1

        if registered:
            await repo.commit()

    print("NEET inventory import")
    print("---------------------")
    print(f"Registered: {registered}")
    print(f"Duplicates: {duplicates}")
    print(f"Skipped (Maths/Uploads/invalid): {skipped}")
    print(f"Errors: {errors}")
    return 0 if errors == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="study-material", description="NEET StudyMaterial source registry CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="Discover and register NEET Physics/Chemistry/Biology PDFs")
    discover.add_argument("--dry-run", action="store_true", help="Enumerate without writing rows")

    sub.add_parser("map", help="Sync explicit academic mappings for all source documents")
    sub.add_parser("coverage", help="Report present/mapped/unmapped/pilot-ready counts")

    pilot = sub.add_parser("pilot-mcq", help="Run Phase D 30-MCQ pilot (10+10+10)")
    pilot.add_argument("--force", action="store_true", help="Re-run even if pilot jobs exist")
    pilot.add_argument("--dry-run", action="store_true", help="Verify sources only")
    pilot.add_argument(
        "--pilot-run-id",
        default=None,
        help="Unique pilot run id (default: phase-d-30-mcq-v1). Use a new id to isolate from historical runs.",
    )

    inv = sub.add_parser("import-inventory", help="One-shot import of StudyMaterial_INVENTORY.json (Maths ignored)")
    inv.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Path to inventory JSON (default: <repo>/scripts/StudyMaterial_INVENTORY.json)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "discover":
        return asyncio.run(_cmd_discover(dry_run=args.dry_run))

    if args.command == "map":
        return asyncio.run(_cmd_map())

    if args.command == "coverage":
        return asyncio.run(_cmd_coverage())

    if args.command == "pilot-mcq":
        return asyncio.run(
            _cmd_pilot_mcq(force=args.force, dry_run=args.dry_run, pilot_run_id=args.pilot_run_id)
        )

    if args.command == "import-inventory":
        if args.path is not None:
            inventory_path = args.path
        else:
            # apps/backend/app/modules/ingestion/cli/study_material.py → repo root is parents[6]
            inventory_path = Path(__file__).resolve().parents[6] / "scripts" / "StudyMaterial_INVENTORY.json"
        return asyncio.run(_cmd_import_inventory(inventory_path))

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
