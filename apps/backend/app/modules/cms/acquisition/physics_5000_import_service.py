"""Controlled legacy Physics 5000 MCQ import into TALOS CMS (DRAFT only).

Uses ContentWorkflowService.create_item — never publishes or approves.
Idempotent by slug = legacy-phy11-{legacy_id}.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sqlite3
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.cms.acquisition.physics_5000_mapping import (
    BATCH_ID,
    LEGACY_SOURCE_REF,
    MODEL_USED,
    PROMPT_VERSION,
    build_provenance_tags,
    legacy_slug,
    legacy_to_question_body,
    stem_hash,
    diagram_sha256,
    LEGACY_CHAPTER_MAP,
)
from app.modules.cms.models import ContentItem
from app.modules.cms.schemas.content_bodies import assert_body_publishable
from app.modules.cms.services.content_workflow_service import ContentWorkflowService

logger = get_logger("cms.acquisition.physics_5000")

SVG_OPEN = re.compile(r"^\s*<svg[\s>]", re.I)
SVG_CLOSE = re.compile(r"</svg>\s*$", re.I)
OverlapClass = Literal["EXACT_DUPLICATE", "POSSIBLE_DUPLICATE", "EXISTING_DIFFERENT_RECORD", "NO_MATCH"]
DiagramClass = Literal[
    "VALID_DIAGRAM", "MISSING_DIAGRAM", "BROKEN_REFERENCE", "INVALID_IMAGE", "DUPLICATE_ASSET", "TEXT_ONLY"
]


@dataclass
class SourceSnapshot:
    filename: str
    byte_size: int
    sha256: str
    record_count: int | None
    id_min: str | None
    id_max: str | None
    diagram_count: int | None
    schema_summary: str


@dataclass
class ImportStats:
    source_total: int = 0
    valid: int = 0
    invalid: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    overlap_exact: int = 0
    overlap_possible: int = 0
    overlap_existing_diff: int = 0
    overlap_none: int = 0
    diagram_valid: int = 0
    diagram_text_only: int = 0
    diagram_missing: int = 0
    diagram_invalid: int = 0
    validation: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)


def _sha256_file(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            size += len(chunk)
            h.update(chunk)
    return size, h.hexdigest()


def load_legacy_records(json_path: Path) -> list[dict[str, Any]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Legacy JSON must be a list of records")
    return data


def classify_diagram(record: dict[str, Any]) -> tuple[DiagramClass, str | None]:
    if not record.get("has_diagram"):
        if (record.get("diagram_svg") or "").strip():
            return "BROKEN_REFERENCE", None
        return "TEXT_ONLY", None
    svg = (record.get("diagram_svg") or "").strip()
    desc = (record.get("diagram_description") or "").strip()
    if not svg:
        return "MISSING_DIAGRAM", None
    if not desc:
        return "INVALID_IMAGE", diagram_sha256(svg)
    if not SVG_OPEN.search(svg) or not SVG_CLOSE.search(svg):
        return "INVALID_IMAGE", diagram_sha256(svg)
    try:
        ET.fromstring(svg)
    except ET.ParseError:
        return "INVALID_IMAGE", diagram_sha256(svg)
    return "VALID_DIAGRAM", diagram_sha256(svg)


def validate_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not (record.get("question") or "").strip():
        errors.append("missing_stem")
    opts = record.get("options") or {}
    if set(opts.keys()) != {"A", "B", "C", "D"}:
        errors.append("missing_option")
    elif any(not str(opts[k]).strip() for k in "ABCD"):
        errors.append("missing_option")
    ans = str(record.get("correct_answer", "")).strip().upper()
    if ans not in ("A", "B", "C", "D"):
        errors.append("missing_answer")
    elif ans not in opts:
        errors.append("missing_answer")
    if not (record.get("explanation") or "").strip():
        errors.append("missing_explanation")
    if not record.get("id"):
        errors.append("missing_provenance")
    if record.get("source") != "algorithmic":
        errors.append("missing_provenance")
    if not record.get("chapter_id"):
        errors.append("missing_chapter")
    if not record.get("topic"):
        errors.append("missing_topic")
    diag_class, _ = classify_diagram(record)
    if record.get("has_diagram") and diag_class in ("MISSING_DIAGRAM", "INVALID_IMAGE", "BROKEN_REFERENCE"):
        errors.append("broken_diagram")
    try:
        body = legacy_to_question_body(record)
        assert_body_publishable("QUESTION", body)
    except (AppError, ValueError) as exc:
        msg = getattr(exc, "message", str(exc))
        if "duplicate" in msg.lower():
            errors.append("duplicate_options")
        else:
            errors.append("invalid_body")
    return errors


class Physics5000ImportService:
    def __init__(self, session: AsyncSession, *, repo_root: Path):
        self.session = session
        self.repo_root = repo_root
        self.workflow = ContentWorkflowService(session)
        self.legacy_json = repo_root / "physics-question-bank" / "output" / "physics_11_5000_mcqs.json"

    def source_inventory(self) -> tuple[list[dict[str, Any]], list[SourceSnapshot]]:
        out_dir = self.repo_root / "physics-question-bank" / "output"
        files = [
            ("physics_11_5000_mcqs.json", True),
            ("physics_11_5000_mcqs.csv", False),
            ("physics_11_mcqs.zip", False),
        ]
        snapshots: list[SourceSnapshot] = []
        records: list[dict[str, Any]] = []
        for name, is_canonical in files:
            path = out_dir / name
            if not path.exists():
                snapshots.append(
                    SourceSnapshot(name, 0, "", None, None, None, None, "MISSING")
                )
                continue
            size, digest = _sha256_file(path)
            if is_canonical:
                records = load_legacy_records(path)
                ids = [r["id"] for r in records]
                snapshots.append(
                    SourceSnapshot(
                        name,
                        size,
                        digest,
                        len(records),
                        min(ids) if ids else None,
                        max(ids) if ids else None,
                        sum(1 for r in records if r.get("has_diagram")),
                        "list[PhysicsMcqSchema] — canonical structured source",
                    )
                )
            else:
                snapshots.append(
                    SourceSnapshot(name, size, digest, None, None, None, None, "export derivative")
                )
        db_paths = [
            self.repo_root / "physics-question-bank" / "physics_test.db",
            out_dir / "physics_test.db",
        ]
        for db_path in db_paths:
            if db_path.exists():
                con = sqlite3.connect(db_path)
                count = con.execute("SELECT COUNT(*) FROM physics_mcq_questions").fetchone()[0]
                size, digest = _sha256_file(db_path)
                con.close()
                snapshots.append(
                    SourceSnapshot(
                        str(db_path.relative_to(self.repo_root)),
                        size,
                        digest,
                        count,
                        None,
                        None,
                        None,
                        "SQLite physics_mcq_questions mirror",
                    )
                )
                break
        return records, snapshots

    async def cms_baseline(self) -> dict[str, int]:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      COUNT(*) FILTER (WHERE deleted_at IS NULL) AS total,
                      COUNT(*) FILTER (WHERE deleted_at IS NULL AND status='PUBLISHED') AS published,
                      COUNT(*) FILTER (WHERE deleted_at IS NULL AND status='DRAFT') AS draft,
                      COUNT(*) FILTER (
                        WHERE deleted_at IS NULL
                        AND EXISTS (
                          SELECT 1 FROM academic.concepts c
                          JOIN academic.topics t ON t.id = c.topic_id
                          JOIN academic.chapters ch ON ch.id = t.chapter_id
                          JOIN academic.subjects s ON s.id = ch.subject_id
                          WHERE c.id = ci.concept_id AND s.code = 'PHYSICS'
                        )
                      ) AS physics
                    FROM cms.content_items ci
                    WHERE content_type = 'QUESTION'
                    """
                )
            )
        ).mappings().one()
        phy11 = (
            await self.session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.content_items
                    WHERE content_type='QUESTION' AND deleted_at IS NULL
                    AND (
                      slug LIKE 'legacy-phy11-%'
                      OR EXISTS (SELECT 1 FROM unnest(tags) t WHERE t LIKE 'legacy_id:PHY11-%')
                    )
                    """
                )
            )
        ).scalar()
        legacy_physics = (
            await self.session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.content_items
                    WHERE content_type='QUESTION' AND deleted_at IS NULL
                    AND EXISTS (SELECT 1 FROM unnest(tags) t WHERE t = 'subject:physics')
                    """
                )
            )
        ).scalar()
        return {
            "total": int(row["total"]),
            "published": int(row["published"]),
            "draft": int(row["draft"]),
            "physics": int(row["physics"]),
            "legacy_physics_tagged": int(legacy_physics or 0),
            "phy11_overlap": int(phy11 or 0),
        }

    async def _stem_index(self) -> dict[str, list[str]]:
        result = await self.session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.deleted_at.is_(None),
                ContentItem.status != "ARCHIVED",
            )
        )
        index: dict[str, list[str]] = {}
        for item in result.scalars().unique().all():
            by_id = {v.id: v for v in item.versions}
            latest = by_id.get(item.latest_version_id)
            stem = (latest.body or {}).get("stem") if latest else None
            if isinstance(stem, str) and stem.strip():
                index.setdefault(normalize_stem(stem), []).append(str(item.id))
        return index

    async def _existing_by_slug(self, slug: str) -> ContentItem | None:
        result = await self.session.execute(select(ContentItem).where(ContentItem.slug == slug))
        return result.scalar_one_or_none()

    def classify_overlap(
        self,
        record: dict[str, Any],
        *,
        existing_by_slug: ContentItem | None,
        stem_index: dict[str, list[str]],
    ) -> OverlapClass:
        if existing_by_slug:
            return "EXACT_DUPLICATE"
        norm = normalize_stem(record["question"])
        owners = stem_index.get(norm, [])
        if owners:
            return "POSSIBLE_DUPLICATE"
        return "NO_MATCH"

    async def run(
        self,
        *,
        author_id: uuid.UUID,
        dry_run: bool = True,
        sample_size: int = 20,
    ) -> ImportStats:
        stats = ImportStats()
        records, _snapshots = self.source_inventory()
        stats.source_total = len(records)
        if stats.source_total != 5000:
            raise RuntimeError(f"Source count {stats.source_total} != 5000 — STOP")

        ids = [r["id"] for r in records]
        if len(set(ids)) != 5000:
            raise RuntimeError("Duplicate legacy IDs in source")

        stem_index = await self._stem_index()
        seen_stems: dict[str, str] = {}

        for record in records:
            errs = validate_record(record)
            if errs:
                stats.invalid += 1
                for e in errs:
                    stats.validation[e] = stats.validation.get(e, 0) + 1
                continue

            h = stem_hash(record["question"])
            if h in seen_stems:
                stats.invalid += 1
                stats.validation["duplicate"] = stats.validation.get("duplicate", 0) + 1
                continue
            seen_stems[h] = record["id"]

            slug = legacy_slug(record["id"])
            existing = await self._existing_by_slug(slug)
            overlap = self.classify_overlap(record, existing_by_slug=existing, stem_index=stem_index)
            if overlap == "EXACT_DUPLICATE":
                stats.overlap_exact += 1
                stats.skipped += 1
                continue
            if overlap == "POSSIBLE_DUPLICATE":
                stats.overlap_possible += 1
                stats.skipped += 1
                continue
            stats.overlap_none += 1
            stats.valid += 1

            diag_class, diag_hash = classify_diagram(record)
            if diag_class == "VALID_DIAGRAM":
                stats.diagram_valid += 1
            elif diag_class == "TEXT_ONLY":
                stats.diagram_text_only += 1
            elif diag_class == "MISSING_DIAGRAM":
                stats.diagram_missing += 1
            else:
                stats.diagram_invalid += 1

            if dry_run:
                continue

            body = legacy_to_question_body(record)
            tags = build_provenance_tags(record, diagram_status=diag_class, diagram_hash=diag_hash)
            title = f"{record['id']}: {record['question'][:200]}"
            try:
                item = await self.workflow.create_item(
                    content_type="QUESTION",
                    concept_id=None,
                    title=title[:300],
                    slug=slug[:320],
                    tags=tags,
                    language="en",
                    body=body,
                    author_id=author_id,
                    model_used=MODEL_USED,
                    prompt_version=PROMPT_VERSION,
                    commit=True,
                )
            except AppError as exc:
                stats.failed += 1
                stats.errors.append({"legacy_id": record["id"], "reason": exc.message, "code": exc.code})
                continue

            if item.status != "DRAFT":
                stats.failed += 1
                stats.errors.append(
                    {"legacy_id": record["id"], "reason": f"Unexpected status {item.status}", "code": "UNEXPECTED_STATUS"}
                )
                continue

            stats.imported += 1
            stem_index.setdefault(normalize_stem(record["question"]), []).append(str(item.id))

        if not dry_run and stats.imported > 0:
            await self._verify_samples(records, stats, sample_size=sample_size)

        return stats

    async def _verify_samples(
        self, records: list[dict[str, Any]], stats: ImportStats, *, sample_size: int
    ) -> None:
        text_only = [r for r in records if not r.get("has_diagram")]
        diagram = [r for r in records if r.get("has_diagram")]
        rng = random.Random(20260902)
        picks: list[dict[str, Any]] = []
        picks.extend(rng.sample(text_only, min(sample_size, len(text_only))))
        picks.extend(rng.sample(diagram, min(sample_size, len(diagram))))
        by_chapter: dict[int, list[dict[str, Any]]] = {}
        for r in records:
            by_chapter.setdefault(int(r["chapter_id"]), []).append(r)
        for ch in range(1, 11):
            pool = by_chapter.get(ch, [])
            picks.extend(rng.sample(pool, min(10, len(pool))))

        seen: set[str] = set()
        for record in picks:
            if record["id"] in seen:
                continue
            seen.add(record["id"])
            slug = legacy_slug(record["id"])
            item = await self._existing_by_slug(slug)
            if not item:
                stats.samples.append({"legacy_id": record["id"], "verdict": "MISSING_IN_TALOS"})
                continue
            result = await self.session.execute(
                select(ContentItem)
                .options(selectinload(ContentItem.versions))
                .where(ContentItem.id == item.id)
            )
            loaded = result.scalar_one()
            latest = next(v for v in loaded.versions if v.id == loaded.latest_version_id)
            body = latest.body or {}
            ok = (
                body.get("stem") == record["question"].strip()
                and body.get("correct_option") == str(record["correct_answer"]).strip().upper()
                and body.get("explanation") == record["explanation"].strip()
                and f"legacy_id:{record['id']}" in (loaded.tags or [])
            )
            stats.samples.append(
                {
                    "legacy_id": record["id"],
                    "verdict": "MATCH" if ok else "MISMATCH",
                    "status": loaded.status,
                    "has_diagram_tag": any(t.startswith("legacy_diagram_status:") for t in (loaded.tags or [])),
                }
            )


def normalize_stem(stem: str) -> str:
    return re.sub(r"\s+", " ", stem.strip().lower())
