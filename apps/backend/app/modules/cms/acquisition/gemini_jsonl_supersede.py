"""Explicit Gemini JSONL DRAFT supersession mode (--supersede-existing).

Ordinary create-only import semantics are unchanged. This module is only used
when the importer is invoked with supersede_existing=True.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.modules.cms.acquisition.gemini_jsonl_draft_importer import (
    NUMERICAL_UNSTRUCTURED_TAG,
    PROMPT_VERSION,
    GeminiJsonlDraftImporter,
    ImportReport,
    RecordOutcome,
    TaxonomyResolution,
    _PreparedCreate,
    _tax_summary,
    build_import_tags,
    build_question_body,
    import_slug,
    load_jsonl,
    validate_gemini_record,
)
from app.modules.cms.models import ContentItem

logger = get_logger("cms.acquisition.gemini_jsonl.supersede")


@dataclass
class ReplacementLineage:
    """Explicit original → replacement external ID map (no fuzzy matching)."""

    batch_id: str | None
    mapping: dict[str, str]  # original_external_id -> replacement_external_id

    @property
    def reverse(self) -> dict[str, str]:
        return {v: k for k, v in self.mapping.items()}


def load_replacement_lineage(path: Path) -> ReplacementLineage:
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}

    if isinstance(raw, dict) and "replacements" in raw:
        for row in raw.get("replacements") or []:
            old = str(row.get("original_external_question_id") or "").strip()
            new = str(row.get("replacement_external_question_id") or "").strip()
            if not old or not new:
                raise ValueError(f"invalid_lineage_row:{row}")
            if old in mapping:
                raise ValueError(f"duplicate_original_in_lineage:{old}")
            mapping[old] = new
        return ReplacementLineage(batch_id=raw.get("batch_id"), mapping=mapping)

    # repair_results.json fallback
    if isinstance(raw, dict) and "actions" in raw:
        for action in raw.get("actions") or []:
            if action.get("action") != "replaced":
                continue
            old = str(action.get("original_id") or "").strip()
            new = str(action.get("new_id") or "").strip()
            if not old or not new:
                raise ValueError(f"invalid_repair_action:{action}")
            mapping[old] = new
        return ReplacementLineage(batch_id=raw.get("batch_id"), mapping=mapping)

    raise ValueError("lineage file must contain replacements[] or repair actions[]")


def resolve_lineage_path(input_path: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"lineage not found: {explicit}")
        return explicit
    candidates = [
        input_path.parent / "replacement_lineage.json",
        input_path.parent / "repair_results.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "supersede mode requires replacement_lineage.json or repair_results.json "
        f"beside {input_path} (or pass --lineage)"
    )


def _body_fingerprint(body: dict[str, Any]) -> str:
    subset = {
        "stem": body.get("stem"),
        "options": body.get("options"),
        "correct_option": body.get("correct_option"),
        "explanation": body.get("explanation"),
        "difficulty": body.get("difficulty"),
    }
    return json.dumps(subset, sort_keys=True, ensure_ascii=False)


@dataclass
class _SupersedePlanItem:
    kind: str  # in_place_update | create_replacement | supersede_link
    external_question_id: str
    prepared: _PreparedCreate | None = None
    existing_id: uuid.UUID | None = None
    old_external_id: str | None = None
    old_item_id: uuid.UUID | None = None
    skip_reason: str | None = None


@dataclass
class SupersedeReportExtra:
    would_update: int = 0
    updated: int = 0
    would_create_replacement: int = 0
    created_replacement: int = 0
    would_supersede: int = 0
    superseded: int = 0
    unchanged: int = 0
    lineage_path: str | None = None
    lineage_pairs: list[dict[str, str]] = field(default_factory=list)


async def run_supersede(
    importer: GeminiJsonlDraftImporter,
    *,
    input_path: Path,
    author_id: uuid.UUID,
    dry_run: bool = True,
    batch_id: str | None = None,
    limit: int | None = None,
    lineage_path: Path | None = None,
) -> ImportReport:
    """Atomically install a repaired JSONL over existing DRAFT content.

    - Stable IDs: update_draft(body+tags) when content differs.
    - Replacement IDs: create DRAFT then supersede_draft(old → new).
    Ordinary create-only import is not used here.
    """
    session: AsyncSession = importer.session
    lineage_file = resolve_lineage_path(input_path, lineage_path)
    lineage = load_replacement_lineage(lineage_file)
    reverse = lineage.reverse

    report = ImportReport(batch_id=batch_id or lineage.batch_id, input_path=str(input_path), dry_run=dry_run)
    extra = SupersedeReportExtra(
        lineage_path=str(lineage_file),
        lineage_pairs=[{"original": o, "replacement": n} for o, n in sorted(lineage.mapping.items())],
    )

    records, malformed = load_jsonl(input_path)
    for err in malformed:
        report.rejected += 1
        report.outcomes.append(
            RecordOutcome(
                external_question_id=f"MALFORMED:{err}",
                status="rejected",
                reasons=[f"malformed_jsonl:{err}"],
            )
        )
    if limit is not None:
        records = records[: max(0, limit)]
    report.input_count = len(records)

    # Validate lineage coverage against input
    input_ids = {
        str(r.get("external_question_id") or "").strip()
        for r in records
        if isinstance(r, dict)
    }
    for old, new in lineage.mapping.items():
        if new not in input_ids:
            raise ValueError(f"lineage_replacement_missing_from_input:{new}")
        if old in input_ids:
            raise ValueError(f"lineage_original_must_not_appear_in_repaired_input:{old}")

    tax_snapshot: TaxonomyResolution | None = None
    plans: list[_SupersedePlanItem] = []

    for raw in records:
        normalized, errors, warnings = validate_gemini_record(raw)
        eid = str((raw or {}).get("external_question_id") or "UNKNOWN") if isinstance(raw, dict) else "UNKNOWN"
        if errors or normalized is None:
            report.rejected += 1
            report.outcomes.append(
                RecordOutcome(external_question_id=eid, status="rejected", reasons=errors or ["invalid_record"], warnings=warnings)
            )
            continue

        if batch_id is None:
            batch_id = str(normalized["provenance"].get("generation_batch_id") or "").strip() or None
            report.batch_id = batch_id
        elif str(normalized["provenance"].get("generation_batch_id") or "").strip() not in ("", batch_id):
            warnings.append(f"batch_id_mismatch_record={normalized['provenance'].get('generation_batch_id')}")

        try:
            body = build_question_body(normalized)
        except Exception as exc:  # noqa: BLE001
            report.rejected += 1
            report.outcomes.append(
                RecordOutcome(
                    external_question_id=normalized["external_question_id"],
                    status="rejected",
                    reasons=[f"body_transform:{exc}"],
                    warnings=warnings,
                )
            )
            continue

        tax = await importer.resolve_taxonomy(normalized)
        tax_snapshot = tax
        tags = build_import_tags(normalized, tax)
        if warnings and NUMERICAL_UNSTRUCTURED_TAG not in tags and any(w.startswith("numerical") for w in warnings):
            tags.append(NUMERICAL_UNSTRUCTURED_TAG)

        slug = import_slug(normalized["external_question_id"])
        model_used = (str(normalized["provenance"].get("model") or "gemini").strip() or "gemini")[:20]
        title = f"{normalized['external_question_id']}: {normalized['stem'][:200]}"[:300]
        prepared = _PreparedCreate(
            external_question_id=normalized["external_question_id"],
            slug=slug,
            title=title,
            body=body,
            tags=tags,
            concept_id=tax.concept_id,
            model_used=model_used,
            warnings=warnings,
            tax_notes=list(tax.notes),
        )

        if eid in reverse:
            old_eid = reverse[eid]
            old_item = await importer._existing_by_slug(import_slug(old_eid))
            new_item = await importer._existing_by_slug(slug)
            if not old_item:
                report.rejected += 1
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=eid,
                        status="rejected",
                        reasons=[f"original_missing_for_replacement:{old_eid}"],
                        warnings=warnings,
                    )
                )
                continue
            if old_item.status == "SUPERSEDED" and new_item and new_item.replaces_id == old_item.id:
                extra.unchanged += 1
                plans.append(
                    _SupersedePlanItem(
                        kind="already_superseded",
                        external_question_id=eid,
                        prepared=prepared,
                        existing_id=new_item.id,
                        old_external_id=old_eid,
                        old_item_id=old_item.id,
                        skip_reason="already_superseded",
                    )
                )
                continue
            if new_item is None:
                extra.would_create_replacement += 1
                extra.would_supersede += 1
                plans.append(
                    _SupersedePlanItem(
                        kind="create_replacement",
                        external_question_id=eid,
                        prepared=prepared,
                        old_external_id=old_eid,
                        old_item_id=old_item.id,
                    )
                )
            else:
                # Replacement exists but lineage not complete — update then link
                extra.would_update += 1
                extra.would_supersede += 1
                plans.append(
                    _SupersedePlanItem(
                        kind="update_then_supersede",
                        external_question_id=eid,
                        prepared=prepared,
                        existing_id=new_item.id,
                        old_external_id=old_eid,
                        old_item_id=old_item.id,
                    )
                )
            continue

        # Stable ID in-place repair
        existing = await importer._existing_by_slug(slug)
        if not existing:
            report.rejected += 1
            report.outcomes.append(
                RecordOutcome(
                    external_question_id=eid,
                    status="rejected",
                    reasons=["stable_id_missing_cannot_create_in_supersede_mode"],
                    warnings=warnings,
                )
            )
            continue
        if existing.status not in {"DRAFT", "CHANGES_REQUESTED"}:
            report.rejected += 1
            report.outcomes.append(
                RecordOutcome(
                    external_question_id=eid,
                    status="rejected",
                    reasons=[f"stable_id_not_draft_editable:{existing.status}"],
                    item_id=str(existing.id),
                    warnings=warnings,
                )
            )
            continue

        latest = next((v for v in (existing.versions or []) if v.id == existing.latest_version_id), None)
        same_body = latest is not None and _body_fingerprint(latest.body or {}) == _body_fingerprint(body)
        same_tags = list(existing.tags or []) == list(tags)
        if same_body and same_tags and existing.title == title:
            extra.unchanged += 1
            plans.append(
                _SupersedePlanItem(
                    kind="unchanged",
                    external_question_id=eid,
                    prepared=prepared,
                    existing_id=existing.id,
                    skip_reason="content_already_matches",
                )
            )
        else:
            extra.would_update += 1
            plans.append(
                _SupersedePlanItem(
                    kind="in_place_update",
                    external_question_id=eid,
                    prepared=prepared,
                    existing_id=existing.id,
                )
            )

    if report.rejected:
        report.taxonomy_summary = _tax_summary(tax_snapshot)
        report.taxonomy_summary["supersede"] = extra.__dict__
        return report

    if dry_run:
        report.would_create = extra.would_create_replacement
        for p in plans:
            status = {
                "in_place_update": "would_update",
                "create_replacement": "would_create_replacement",
                "update_then_supersede": "would_update_then_supersede",
                "already_superseded": "already_superseded",
                "unchanged": "unchanged",
            }.get(p.kind, p.kind)
            report.outcomes.append(
                RecordOutcome(
                    external_question_id=p.external_question_id,
                    status=status,
                    slug=p.prepared.slug if p.prepared else None,
                    item_id=str(p.existing_id) if p.existing_id else None,
                    reasons=[p.skip_reason] if p.skip_reason else ([f"supersedes:{p.old_external_id}"] if p.old_external_id else []),
                    warnings=p.prepared.warnings if p.prepared else [],
                )
            )
        report.db_writes = 0
        report.taxonomy_summary = _tax_summary(tax_snapshot)
        report.taxonomy_summary["supersede"] = {
            **extra.__dict__,
            "planned": len(plans),
        }
        return report

    # Atomic commit
    nested = await session.begin_nested()
    try:
        for p in plans:
            assert p.prepared is not None
            if p.kind == "unchanged" or p.kind == "already_superseded":
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=p.external_question_id,
                        status=p.kind,
                        slug=p.prepared.slug,
                        item_id=str(p.existing_id) if p.existing_id else None,
                        reasons=[p.skip_reason] if p.skip_reason else [],
                    )
                )
                continue

            if p.kind == "in_place_update":
                assert p.existing_id is not None
                item = await importer.workflow.update_draft(
                    p.existing_id,
                    body=p.prepared.body,
                    change_summary="gemini_jsonl_supersede_in_place_repair",
                    author_id=author_id,
                    title=p.prepared.title,
                    tags=p.prepared.tags,
                    commit=False,
                )
                extra.updated += 1
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=p.external_question_id,
                        status="updated",
                        slug=p.prepared.slug,
                        item_id=str(item.id),
                    )
                )
                continue

            if p.kind == "create_replacement":
                assert p.old_item_id is not None
                item = await importer.workflow.create_item(
                    content_type="QUESTION",
                    concept_id=p.prepared.concept_id,
                    title=p.prepared.title,
                    slug=p.prepared.slug,
                    tags=p.prepared.tags,
                    language="en",
                    body=p.prepared.body,
                    author_id=author_id,
                    model_used=p.prepared.model_used,
                    prompt_version=PROMPT_VERSION,
                    commit=False,
                )
                await importer.workflow.supersede_draft(
                    p.old_item_id,
                    replacement_item_id=item.id,
                    author_id=author_id,
                    commit=False,
                )
                extra.created_replacement += 1
                extra.superseded += 1
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=p.external_question_id,
                        status="created_and_superseded",
                        slug=p.prepared.slug,
                        item_id=str(item.id),
                        reasons=[f"supersedes:{p.old_external_id}"],
                    )
                )
                continue

            if p.kind == "update_then_supersede":
                assert p.existing_id is not None and p.old_item_id is not None
                item = await importer.workflow.update_draft(
                    p.existing_id,
                    body=p.prepared.body,
                    change_summary="gemini_jsonl_supersede_replacement_refresh",
                    author_id=author_id,
                    title=p.prepared.title,
                    tags=p.prepared.tags,
                    commit=False,
                )
                await importer.workflow.supersede_draft(
                    p.old_item_id,
                    replacement_item_id=item.id,
                    author_id=author_id,
                    commit=False,
                )
                extra.updated += 1
                extra.superseded += 1
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=p.external_question_id,
                        status="updated_and_superseded",
                        slug=p.prepared.slug,
                        item_id=str(item.id),
                        reasons=[f"supersedes:{p.old_external_id}"],
                    )
                )
                continue

            raise RuntimeError(f"unknown_plan_kind:{p.kind}")

        await nested.commit()
        await session.commit()
        report.created = extra.created_replacement
        report.db_writes = extra.updated + extra.created_replacement + extra.superseded
    except Exception as exc:  # noqa: BLE001
        if nested.is_active:
            await nested.rollback()
        report.created = 0
        report.db_writes = 0
        report.failed += 1
        report.outcomes.append(
            RecordOutcome(
                external_question_id="BATCH",
                status="failed",
                reasons=[f"atomic_supersede_rollback:{exc}"],
            )
        )
        logger.exception("gemini_jsonl_supersede_failed", error=str(exc))
        raise

    report.taxonomy_summary = _tax_summary(tax_snapshot)
    report.taxonomy_summary["supersede"] = extra.__dict__
    return report
