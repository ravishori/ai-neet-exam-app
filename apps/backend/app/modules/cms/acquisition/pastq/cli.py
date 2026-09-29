"""CLI for PASTQ-IMPORT-001.

Examples:
  python -m app.modules.cms.acquisition.pastq.cli --dry-run
  python -m app.modules.cms.acquisition.pastq.cli --dry-run --only NEET2019.pdf,NEET2018.pdf
  python -m app.modules.cms.acquisition.pastq.cli --import --pilot --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from app.modules.cms.acquisition.pastq.pipeline import STAGING_DIR_DEFAULT, run_pastq_pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PASTQ-IMPORT-001 past question paper pipeline")
    p.add_argument(
        "--source-root",
        default=r"D:\ravishori\AI Neet Exam App\PastQuestionPapers",
        help="Canonical PastQuestionPapers directory (read-only)",
    )
    p.add_argument("--staging-dir", default=str(STAGING_DIR_DEFAULT))
    p.add_argument("--audit-dir", default=r"D:\ravishori\AI Neet Exam App\docs\audits")
    p.add_argument("--only", default="", help="Comma-separated filenames to process")
    p.add_argument("--dry-run", action="store_true", default=False, help="Extract/stage only (default if no --import)")
    p.add_argument("--import", dest="do_import", action="store_true", help="Import ready DRAFTs (explicit)")
    p.add_argument("--pilot", action="store_true", help="Restrict import to a small ready subset")
    p.add_argument("--limit", type=int, default=5, help="Max DRAFTs to create when importing")
    p.add_argument("--author-id", default="", help="UUID of author user for create_item")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    only = [x.strip() for x in args.only.split(",") if x.strip()]
    # Default to dry-run when import not requested
    dry = args.dry_run or not args.do_import

    result = run_pastq_pipeline(
        source_root=args.source_root,
        staging_dir=args.staging_dir,
        only_files=only or None,
        write_inventory=True,
        audit_dir=args.audit_dir,
    )
    summary = result["summary"]
    print(json.dumps({"mode": "dry-run" if dry else "extract+import", "summary": summary}, indent=2))

    if not args.do_import:
        print("STOP: dry-run complete; no database mutations.")
        return 0

    return asyncio.run(_import_async(args, result))


async def _import_async(args, result: dict) -> int:
    from sqlalchemy import select

    # ContentVersion FK → knowledge.knowledge_units requires metadata registration.
    import app.modules.knowledge.models  # noqa: F401
    from app.core.database import AsyncSessionLocal
    from app.modules.cms.acquisition.pastq.dedupe import mark_existing_cms_duplicates
    from app.modules.cms.acquisition.pastq.importer import import_pastq_records, load_existing_stem_hashes
    from app.modules.cms.services.factory_candidate_validation import stem_hash
    from app.modules.identity.models.user import User

    records = list(result["records"])
    if args.pilot:
        # Prefer ready answered items from 2019 (inline Ans) and 2018/2024 text papers
        preferred = []
        for name in ("NEET2019.pdf", "NEET2018.pdf", "NEET2024.pdf", "NEET2016.pdf"):
            preferred.extend(
                [
                    r
                    for r in records
                    if r["source"]["file"].endswith(name) and r["quality"].get("ready_for_import")
                ]
            )
        records = preferred or [r for r in records if r["quality"].get("ready_for_import")]

    async with AsyncSessionLocal() as session:
        existing = await load_existing_stem_hashes(session)
        mark_existing_cms_duplicates(records, existing, stem_hash_fn=stem_hash)

        author_id: uuid.UUID
        if args.author_id:
            author_id = uuid.UUID(args.author_id)
        else:
            row = (
                await session.execute(select(User.id).where(User.deleted_at.is_(None)).limit(1))
            ).scalar_one_or_none()
            if row is None:
                print("ERROR: no user available for author_id")
                return 2
            author_id = row

        report = await import_pastq_records(
            session,
            records,
            author_id=author_id,
            limit=args.limit,
            dry_run=False,
            commit=True,
        )
        out = {
            "attempted": report.attempted,
            "created": report.created,
            "already_exists": report.already_exists,
            "skipped": report.skipped,
            "rejected": report.rejected,
            "outcomes": [o.__dict__ for o in report.outcomes],
        }
        Path(args.staging_dir).mkdir(parents=True, exist_ok=True)
        (Path(args.staging_dir) / "import_report.json").write_text(
            json.dumps(out, indent=2), encoding="utf-8"
        )
        print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
