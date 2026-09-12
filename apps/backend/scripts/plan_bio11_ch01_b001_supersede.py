"""Dry-run supersession plan for Biology repaired artifact — NO DB mutation.

Stops before mutation when canonical DRAFT supersede semantics are absent.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select, any_
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.modules.cms.acquisition.gemini_jsonl_draft_importer import (
    GeminiJsonlDraftImporter,
    import_slug,
    load_jsonl,
    validate_gemini_record,
)
from app.modules.cms.models import ContentItem
import app.modules.cms.models  # noqa: F401

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
REPAIRED = ROOT / "questions_repaired.jsonl"
PLAN = ROOT / "supersede_dry_run_plan.json"
REPORT = ROOT / "supersede_block_report.md"

MAYR = {
    "GEMINI-20260911-BIO11-CH01-B001-000095": "GEMINI-20260911-BIO11-CH01-B001-R000095",
    "GEMINI-20260911-BIO11-CH01-B001-000096": "GEMINI-20260911-BIO11-CH01-B001-R000096",
    "GEMINI-20260911-BIO11-CH01-B001-000097": "GEMINI-20260911-BIO11-CH01-B001-R000097",
    "GEMINI-20260911-BIO11-CH01-B001-000099": "GEMINI-20260911-BIO11-CH01-B001-R000099",
    "GEMINI-20260911-BIO11-CH01-B001-000100": "GEMINI-20260911-BIO11-CH01-B001-R000100",
}
OLD_MAYR = set(MAYR)
NEW_MAYR = set(MAYR.values())


def _ext_from_item(item: ContentItem) -> str | None:
    for t in item.tags or []:
        if t.startswith("external_id:"):
            return t.split(":", 1)[1]
    if item.slug and item.slug.startswith("gemini-"):
        return item.slug[len("gemini-") :]
    return None


async def main() -> None:
    records, malformed = load_jsonl(REPAIRED)
    rejected: list[tuple[str, list[str]]] = []
    for raw in records:
        _, errs, _ = validate_gemini_record(raw)
        if errs:
            rejected.append((str(raw.get("external_question_id")), errs))

    repaired = {r["external_question_id"]: r for r in records}

    async with AsyncSessionLocal() as db:
        bio = (
            await db.execute(
                select(ContentItem)
                .options(selectinload(ContentItem.versions))
                .where(ContentItem.deleted_at.is_(None), BATCH == any_(ContentItem.tags))
            )
        ).scalars().all()
        phy = (
            await db.execute(
                select(ContentItem).where(ContentItem.deleted_at.is_(None), PHY == any_(ContentItem.tags))
            )
        ).scalars().all()

        by_ext: dict[str, ContentItem] = {}
        ambiguous: list[dict] = []
        for item in bio:
            ext = _ext_from_item(item)
            if not ext:
                ambiguous.append({"db_id": str(item.id), "slug": item.slug, "reason": "missing_external_id"})
                continue
            if ext in by_ext:
                ambiguous.append(
                    {
                        "external_id": ext,
                        "db_ids": [str(by_ext[ext].id), str(item.id)],
                        "reason": "duplicate_external_id_mapping",
                    }
                )
                continue
            by_ext[ext] = item

        in_place: list[dict] = []
        create: list[dict] = []
        supersede: list[dict] = []
        missing_db: list[str] = []
        missing_repaired: list[dict] = []

        for eid, rec in repaired.items():
            if eid in NEW_MAYR:
                old = next(o for o, n in MAYR.items() if n == eid)
                old_item = by_ext.get(old)
                create.append(
                    {
                        "action": "CREATE_REPLACEMENT",
                        "new_external_id": eid,
                        "old_external_id": old,
                        "old_db_id": str(old_item.id) if old_item else None,
                        "old_slug": old_item.slug if old_item else None,
                        "new_slug": import_slug(eid),
                        "lineage": f"{old} -> {eid}",
                        "db_exists_new": by_ext.get(eid) is not None,
                        "difficulty": rec.get("difficulty"),
                        "question_type": rec.get("question_type"),
                    }
                )
                if old_item:
                    supersede.append(
                        {
                            "action": "SUPERSEDE_REQUIRED_BUT_NO_CANONICAL_PATH",
                            "old_external_id": old,
                            "old_db_id": str(old_item.id),
                            "old_slug": old_item.slug,
                            "old_status": old_item.status,
                            "replacement_external_id": eid,
                        }
                    )
                else:
                    missing_db.append(old)
                continue

            item = by_ext.get(eid)
            if not item:
                missing_db.append(eid)
                continue
            version = next((v for v in item.versions if v.id == item.latest_version_id), None)
            body = (version.body if version else {}) or {}
            qt_tag = next(
                (t.split(":", 1)[1] for t in (item.tags or []) if t.startswith("question_type:")),
                None,
            )
            in_place.append(
                {
                    "action": "UPDATE_DRAFT_BODY_VIA_update_draft",
                    "external_id": eid,
                    "db_id": str(item.id),
                    "slug": item.slug,
                    "status": item.status,
                    "current_difficulty": body.get("difficulty"),
                    "repaired_difficulty": rec.get("difficulty"),
                    "current_question_type_tag": qt_tag,
                    "repaired_question_type": rec.get("question_type"),
                    "body_update_supported_by_update_draft": True,
                    "tag_update_supported_by_update_draft": False,
                    "note": "Difficulty can move via body; question_type tag cannot via update_draft alone.",
                }
            )

        for ext, item in by_ext.items():
            if ext in OLD_MAYR:
                continue
            if ext not in repaired:
                missing_repaired.append({"external_id": ext, "db_id": str(item.id)})

        author_id = bio[0].created_by
        importer = GeminiJsonlDraftImporter(db)
        report = await importer.run(
            input_path=REPAIRED,
            author_id=author_id,
            dry_run=True,
            batch_id=BATCH,
            atomic=True,
        )

        mapping_complete = (
            not missing_db
            and not missing_repaired
            and not ambiguous
            and len(in_place) == 95
            and len(create) == 5
            and len(supersede) == 5
            and len(bio) == 100
        )

        plan = {
            "batch_id": BATCH,
            "mutation_allowed": False,
            "mapping_complete": mapping_complete,
            "overall_verdict": "AMBER — REPLACEMENT BLOCKED / MANUAL REVIEW REQUIRED",
            "architectural_gap": {
                "verdict": "ARCHITECTURAL_GAP",
                "summary": (
                    "ContentItem has no canonical DRAFT supersede/retire path. "
                    "update_draft edits body/version only (tags ignored). "
                    "archive() is PUBLISHED-only. Gemini importer is create-only idempotent."
                ),
                "evidence": [
                    "ContentWorkflowService.update_draft — body versioning only",
                    "ContentWorkflowService.archive — requires PUBLISHED",
                    "No ContentItem.superseded_by / replaces_id",
                    "GeminiJsonlDraftImporter — already_exists skips updates",
                    "KnowledgeUnit.superseded_by exists but is not ContentItem semantics",
                ],
            },
            "repaired_jsonl_validation": {
                "input": len(records),
                "eligible": len(records) - len(rejected),
                "rejected": len(rejected),
                "rejected_details": rejected[:20],
                "malformed_lines": len(malformed),
            },
            "ordinary_importer_dry_run": {
                "input_count": report.input_count,
                "would_create": report.would_create,
                "already_exists": report.already_exists,
                "rejected": report.rejected,
                "failed": report.failed,
                "db_writes": report.db_writes,
                "note": (
                    "Ordinary --commit would create only the 5 new R* rows and leave 95 unrepaired "
                    "plus 5 old Mayr DRAFTs active → 105 Biology DRAFTs (violates final count=100)."
                ),
            },
            "mapping_summary": {
                "db_active_biology_drafts": len(bio),
                "repaired_records": len(repaired),
                "in_place_candidates": len(in_place),
                "replacement_creates": len(create),
                "supersede_targets": len(supersede),
                "unchanged": 0,
                "missing_db": missing_db,
                "missing_repaired": missing_repaired,
                "ambiguous": ambiguous,
                "expected_final_active_if_canonical_existed": 100,
                "expected_active_if_naive_import_commit": len(bio)
                + sum(1 for c in create if not c["db_exists_new"]),
            },
            "in_place_updates": in_place,
            "replacement_creates": create,
            "supersede_targets": supersede,
            "records_unchanged": [],
            "physics_safety_snapshot": {
                "batch": PHY,
                "count": len(phy),
                "statuses": dict(Counter(i.status for i in phy)),
            },
            "required_before_mutation": [
                "Add canonical DRAFT supersede/retire transition with lineage (or ContentItem replaces/superseded_by).",
                "Extend ContentWorkflowService to apply tags/title on draft updates when needed.",
                "Implement explicit importer mode e.g. --supersede-existing that uses those services atomically.",
                "Do not change ordinary --commit create-only semantics.",
                "Re-run this plan until mutation_allowed=true.",
            ],
        }

        PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        lines = [
            f"# Supersede Block Report — {BATCH}",
            "",
            "## Verdict",
            "",
            "**AMBER — REPLACEMENT BLOCKED / MANUAL REVIEW REQUIRED**",
            "",
            "No database mutation was performed.",
            "",
            "## Architectural gap",
            "",
            "TALOS CMS currently provides:",
            "",
            "- `ContentWorkflowService.update_draft` — versioned **body** edit for DRAFT/CHANGES_REQUESTED (tags/title not applied).",
            "- `ContentWorkflowService.archive` — **PUBLISHED → ARCHIVED** only.",
            "- Gemini JSONL importer — **create-only**, idempotent by slug; existing rows become `already_exists`.",
            "",
            "TALOS CMS does **not** provide a canonical ContentItem mechanism for:",
            "",
            "- superseding / replacing / retiring DRAFT items",
            "- `superseded_by` / `replaces_id` lineage on content items",
            "- workflow-safe tag updates for `question_type:*`",
            "- retiring the five Mayr DRAFTs while creating `R0000xx` replacements under one atomic final count of 100",
            "",
            "Per task rules: **do not invent schema in this task; stop before mutation.**",
            "",
            "## Dry-run plan summary",
            "",
            f"- DB Biology DRAFT: **{len(bio)}**",
            f"- Repaired JSONL: **{len(repaired)}** (validator rejected: {len(rejected)}; malformed: {len(malformed)})",
            f"- Mapping complete: **{mapping_complete}**",
            f"- In-place update candidates (stable IDs): **{len(in_place)}**",
            f"- Replacement creates (new R* IDs): **{len(create)}**",
            f"- Supersede targets (old Mayr): **{len(supersede)}**",
            f"- Unchanged: **0**",
            f"- Missing DB mappings: `{missing_db or 'none'}`",
            f"- Missing repaired counterparts: `{missing_repaired or 'none'}`",
            f"- Ambiguous mappings: `{ambiguous or 'none'}`",
            "",
            "### Ordinary importer dry-run on repaired JSONL",
            "",
            f"- Input: {report.input_count}",
            f"- Would create: {report.would_create} (new R* slugs only)",
            f"- Already exists: {report.already_exists} (stable IDs)",
            f"- Rejected: {report.rejected}",
            f"- DB writes: {report.db_writes}",
            "",
            "If ordinary `--commit` were used, active Biology DRAFTs would become **105** "
            "(100 old + 5 new), which violates the required final count of **100**.",
            "",
            "## Mayr lineage (planned, not applied)",
            "",
            "| Old external ID | Old DB ID | New external ID |",
            "|---|---|---|",
        ]
        for c in create:
            lines.append(f"| `{c['old_external_id']}` | `{c['old_db_id']}` | `{c['new_external_id']}` |")
        lines += [
            "",
            "## Why partial approaches are unsafe",
            "",
            "1. **Import-only create of 5 R* rows** → 105 active DRAFTs; old Mayr remain student-invisible but still active DRAFT inventory.",
            "2. **`update_draft` on 95 only** → body/difficulty can update, but `question_type:*` tags cannot via canonical service; Mayr supersession still unresolved.",
            "3. **Raw SQL soft-delete / tag lineage** → bypasses ContentWorkflowService; forbidden by this task.",
            "4. **`archive()` on Mayr DRAFTs** → rejected by workflow (archive requires PUBLISHED).",
            "",
            "## Physics safety snapshot (read-only)",
            "",
            f"- `{PHY}`: **{len(phy)}** records, statuses=`{dict(Counter(i.status for i in phy))}`",
            "",
            "## Required next work (separate task / ADR)",
            "",
            "1. Add canonical DRAFT supersede/retire transition with explicit lineage fields **or** a content-item lineage table.",
            "2. Extend workflow service for safe draft metadata/tag updates where needed.",
            "3. Add explicit importer mode (e.g. `--supersede-existing`) that uses those services atomically and does **not** alter ordinary `--commit`.",
            "4. Re-run this dry-run until `mutation_allowed=true`, then commit.",
            "",
            f"Machine-readable plan: `{PLAN.as_posix()}`",
            "",
            "## Final state after this task",
            "",
            "- Biology active DRAFT: **still 100** (unrepaired originals)",
            "- PUBLISHED / APPROVED / ECAEP: **still 0**",
            "- Repaired GREEN artifact remains offline only",
            "- No ECAEP submission / publication performed",
            "",
        ]
        REPORT.write_text("\n".join(lines), encoding="utf-8")

        print(
            json.dumps(
                {
                    "overall_verdict": plan["overall_verdict"],
                    "mutation_allowed": False,
                    "mapping_complete": mapping_complete,
                    "bio_drafts": len(bio),
                    "in_place": len(in_place),
                    "create": len(create),
                    "supersede": len(supersede),
                    "importer_would_create": report.would_create,
                    "importer_already_exists": report.already_exists,
                    "importer_db_writes": report.db_writes,
                    "phy": len(phy),
                    "plan": str(PLAN),
                    "report": str(REPORT),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
