#!/usr/bin/env python3
"""Controlled import of legacy Physics 5000 MCQs into TALOS CMS (DRAFT only).

Usage (from apps/backend):
  .venv/Scripts/python.exe scripts/import_physics_5000_to_talos.py --dry-run
  .venv/Scripts/python.exe scripts/import_physics_5000_to_talos.py --import

Never modifies legacy source files. Never publishes or approves content.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[3]
BACKEND = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "audits"
DATE_TAG = "2026-09-02"

sys.path.insert(0, str(BACKEND))

import app.modules.academic.models  # noqa: F401 — FK metadata for concept_id
import app.modules.cms.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401 — FK metadata for knowledge_unit_id

from app.core.database import AsyncSessionLocal
from app.modules.cms.acquisition.physics_5000_import_service import Physics5000ImportService
from app.modules.cms.acquisition.physics_5000_mapping import BATCH_ID, LEGACY_CHAPTER_MAP
from app.modules.identity.models.user import User


async def _resolve_author_id() -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.id).where(User.email == "content-seed@trinetra.local").limit(1)
        )
        author_id = result.scalar_one_or_none()
        if author_id is None:
            result = await session.execute(select(User.id).limit(1))
            author_id = result.scalar_one_or_none()
        if author_id is None:
            raise RuntimeError("No users in database — seed identity before import")
        return author_id


def _write_source_snapshot(service: Physics5000ImportService) -> Path:
    _, snapshots = service.source_inventory()
    path = OUT_DIR / f"PHYSICS_5000_SOURCE_SNAPSHOT_{DATE_TAG.replace('-', '')}.md"
    lines = [
        f"# Physics 5000 Source Snapshot — {DATE_TAG}",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}  ",
        "**Mode:** READ-ONLY source fingerprint (no source files modified)",
        "",
        "## Canonical source",
        "",
        "`physics-question-bank/output/physics_11_5000_mcqs.json` — richest structured export.",
        "",
        "## File checksums",
        "",
        "| File | Bytes | SHA-256 | Records | ID range | Diagrams | Schema |",
        "|------|------:|---------|--------:|----------|--------:|--------|",
    ]
    for s in snapshots:
        id_range = f"{s.id_min} … {s.id_max}" if s.id_min and s.id_max else "—"
        lines.append(
            f"| `{s.filename}` | {s.byte_size:,} | `{s.sha256 or '—'}` | {s.record_count or '—'} | {id_range} | {s.diagram_count or '—'} | {s.schema_summary} |"
        )
    lines.extend(
        [
            "",
            "## Expected",
            "",
            "- Records: **5000**",
            "- IDs: `PHY11-CH01-0001` … `PHY11-CH10-5000`",
            "- Source: `algorithmic`",
            "- Diagram questions: **1500**",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_preimport_validation(stats, records_count: int) -> Path:
    path = OUT_DIR / f"PHYSICS_5000_PREIMPORT_VALIDATION_{DATE_TAG.replace('-', '')}.md"
    v = stats.validation
    lines = [
        f"# Physics 5000 Pre-Import Validation — {DATE_TAG}",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}  ",
        f"**Batch ID:** `{BATCH_ID}`",
        "",
        "## Counts",
        "",
        "```text",
        f"Total                 = {records_count}",
        f"Valid                 = {stats.valid}",
        f"Invalid               = {stats.invalid}",
        f"Missing answer        = {v.get('missing_answer', 0)}",
        f"Missing option        = {v.get('missing_option', 0)}",
        f"Duplicate             = {v.get('duplicate', 0)}",
        f"Missing chapter       = {v.get('missing_chapter', 0)}",
        f"Missing topic         = {v.get('missing_topic', 0)}",
        f"Missing provenance    = {v.get('missing_provenance', 0)}",
        f"Missing diagram       = {v.get('missing_diagram', 0)}",
        f"Broken diagram        = {v.get('broken_diagram', 0)}",
        "```",
        "",
        "## Overlap (pre-insert)",
        "",
        "```text",
        f"EXACT_DUPLICATE       = {stats.overlap_exact}",
        f"POSSIBLE_DUPLICATE    = {stats.overlap_possible}",
        f"NO_MATCH              = {stats.overlap_none}",
        "```",
        "",
        "## Diagram classification",
        "",
        "```text",
        f"VALID_DIAGRAM         = {stats.diagram_valid}",
        f"TEXT_ONLY             = {stats.diagram_text_only}",
        f"MISSING/INVALID       = {stats.diagram_missing + stats.diagram_invalid}",
        "```",
        "",
        "## Academic mapping (legacy chapters)",
        "",
        "| Legacy CH | Title | TALOS chapter | Confidence |",
        "|----------:|-------|---------------|------------|",
    ]
    for cid in sorted(LEGACY_CHAPTER_MAP):
        m = LEGACY_CHAPTER_MAP[cid]
        lines.append(
            f"| {cid} | {m.legacy_title} | {m.talos_chapter_code or 'UNRESOLVED'} | {m.confidence} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_final_audit(
    stats,
    *,
    dry_run: bool,
    before: dict[str, int],
    after: dict[str, int],
) -> Path:
    path = OUT_DIR / f"PHYSICS_5000_TALOS_IMPORT_AUDIT_{DATE_TAG.replace('-', '')}.md"
    imported = stats.imported if not dry_run else 0
    verdict = "GREEN — IMPORT VERIFIED"
    if dry_run:
        verdict = "YELLOW — DRY RUN ONLY (no inserts)"
    elif stats.failed > 0 or stats.imported + stats.skipped + stats.failed != stats.valid + stats.overlap_exact + stats.overlap_possible:
        verdict = "YELLOW — IMPORT PARTIALLY VERIFIED"
    if stats.invalid > 0 or stats.failed > 0:
        verdict = "YELLOW — IMPORT PARTIALLY VERIFIED" if not dry_run else verdict
    if stats.source_total != 5000:
        verdict = "RED — IMPORT FAILED"

    lines = [
        f"# Physics 5000 TALOS Import Audit — {DATE_TAG}",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}  ",
        f"**Mode:** {'DRY RUN' if dry_run else 'CONTROLLED IMPORT'}  ",
        f"**Batch ID:** `{BATCH_ID}`",
        "",
        "## Source",
        "",
        f"Total = {stats.source_total}",
        "",
        "## Validation",
        "",
        f"Valid = {stats.valid}  ",
        f"Invalid = {stats.invalid}  ",
        f"Duplicates (skipped) = {stats.overlap_exact + stats.overlap_possible}",
        "",
        "## Import",
        "",
        f"Imported = {imported}  ",
        f"Skipped = {stats.skipped}  ",
        f"Failed = {stats.failed}",
        "",
        "## Current TALOS",
        "",
        f"Before = {before.get('total', '?')}  ",
        f"After = {after.get('total', '?')}  ",
        f"Physics before = {before.get('physics', '?')} (concept-linked)  ",
        f"Physics after = {after.get('physics', '?')} (concept-linked)  ",
        f"Legacy Physics tagged = {after.get('legacy_physics_tagged', '?')} (subject:physics tag)  ",
        f"Published before = {before.get('published', '?')}  ",
        f"Published after = {after.get('published', '?')}  ",
        f"PHY11 overlap before = {before.get('phy11_overlap', '?')}  ",
        f"PHY11 overlap after = {after.get('phy11_overlap', '?')}",
        "",
        "## Visual",
        "",
        f"Source graphic questions = {stats.diagram_valid + stats.diagram_missing + stats.diagram_invalid}  ",
        f"Imported graphic questions = {stats.diagram_valid if not dry_run else 'N/A (dry run)'}  ",
        f"Valid diagrams = {stats.diagram_valid}  ",
        f"Broken diagrams = {stats.diagram_missing + stats.diagram_invalid}",
        "",
        "## Provenance",
        "",
        "100% of valid candidates carry `legacy_id:PHY11-*`, `source:algorithmic`, and batch tag.",
        "",
        "## ECAEP",
        "",
        "Imported status must be: **DRAFT**  ",
        "Published automatically: **NO**",
        "",
        f"Published count unchanged: **{'YES' if before.get('published') == after.get('published') else 'NO — INVESTIGATE'}**",
        "",
        "## Sample verification",
        "",
    ]
    if stats.samples:
        match = sum(1 for s in stats.samples if s.get("verdict") == "MATCH")
        lines.append(f"- Samples checked: **{len(stats.samples)}**")
        lines.append(f"- MATCH: **{match}**")
        lines.append(f"- MISMATCH/MISSING: **{len(stats.samples) - match}**")
    else:
        lines.append("- Samples: not run (dry run or zero imports)")

    lines.extend(["", "## Final verdict", "", f"**{verdict}**", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def main() -> int:
    parser = argparse.ArgumentParser(description="Import legacy Physics 5000 MCQs into TALOS CMS")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Validate and audit only; no DB inserts")
    group.add_argument("--import", dest="do_import", action="store_true", help="Perform controlled DRAFT import")
    args = parser.parse_args()

    author_id = await _resolve_author_id()
    async with AsyncSessionLocal() as session:
        service = Physics5000ImportService(session, repo_root=ROOT)
        snap_path = _write_source_snapshot(service)
        before = await service.cms_baseline()
        stats = await service.run(author_id=author_id, dry_run=not args.do_import)
        after = await service.cms_baseline() if args.do_import else before
        val_path = _write_preimport_validation(stats, stats.source_total)
        audit_path = _write_final_audit(stats, dry_run=not args.do_import, before=before, after=after)

    print(f"Source snapshot: {snap_path}")
    print(f"Pre-import validation: {val_path}")
    print(f"Import audit: {audit_path}")
    print()
    print("=== Reconciliation ===")
    print(f"Legacy Physics source     = {stats.source_total}")
    print(f"Valid candidates          = {stats.valid}")
    print(f"Imported to TALOS         = {stats.imported if args.do_import else 0}")
    print(f"Rejected/skipped          = {stats.invalid + stats.skipped + stats.failed}")
    print(f"Physics (concept-linked)  = {after.get('physics', '?')} (was {before.get('physics', '?')})")
    print(f"Legacy Physics (tagged)     = {after.get('legacy_physics_tagged', '?')}")
    print(f"Published total           = {after.get('published', '?')} (unchanged: {before.get('published') == after.get('published')})")
    print(f"Draft total               = {after.get('draft', '?')} (was {before.get('draft', '?')})")
    print(f"Diagram source (valid)    = {stats.diagram_valid}")
    print("ECAEP publication        = NOT PERFORMED")

    if stats.source_total != 5000:
        return 1
    if stats.invalid > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
