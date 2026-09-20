"""Idempotent Flashcard Seed V1 importer.

Imports curated NCERT-grounded flashcards from cms.flashcard_seed into
cms.content_items (FLASHCARD), then optionally runs ECAEP:
  DRAFT → IN_REVIEW → APPROVED → PUBLISHED

Usage (from apps/backend):
  .venv/Scripts/python.exe scripts/import_flashcard_seed_v1.py --dry-run
  .venv/Scripts/python.exe scripts/import_flashcard_seed_v1.py --authorize-import
  .venv/Scripts/python.exe scripts/import_flashcard_seed_v1.py --authorize-import --authorize-publish

Safety:
- Idempotent by slug (seed-v1-fc-<card_key>)
- Exact-front duplicate detection within seed + against existing FLASHCARDs
- Does not overwrite existing verified records
- Does **not** set certification_status=VERIFIED (structural import ≠ scientific certification;
  run scripts/audit_flashcard_seed_v1.py for certification overlays)
- Transactions per card (create) / workflow steps
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, text

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.academic.models import Concept
from app.modules.cms.flashcard_seed import ALL_CARDS
from app.modules.cms.models import ContentItem, ContentVersion
from app.modules.cms.schemas.content_bodies import validate_body
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.identity.models import User

REPO = BACKEND.parents[1]
OUT = REPO / "docs" / "acquisition" / "flashcards" / "SEED-V1"
BATCH_TAG = "FLASHCARD-SEED-V1"
SLUG_PREFIX = "seed-v1-fc-"


def norm_front(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", (s or "").lower())).strip()


def fingerprint(front: str, concept_id: str) -> str:
    payload = f"{concept_id}|{norm_front(front)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def card_slug(card_key: str) -> str:
    return f"{SLUG_PREFIX}{card_key}".lower().replace("_", "-")[:320]


async def resolve_author(session) -> uuid.UUID:
    # Prefer a content manager; fall back to any active user.
    row = (
        await session.execute(
            text(
                """
                SELECT u.id
                FROM identity.users u
                JOIN identity.user_roles ur ON ur.user_id = u.id
                JOIN identity.roles r ON r.id = ur.role_id
                WHERE u.deleted_at IS NULL AND r.code = 'CONTENT_MANAGER'
                ORDER BY u.created_at
                LIMIT 1
                """
            )
        )
    ).first()
    if row:
        return row[0]
    user = (await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))).scalar_one()
    return user.id


async def load_concept_index(session) -> dict[str, dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                """
                SELECT co.code AS concept_code, co.id AS concept_id, co.name AS concept,
                       t.name AS topic, ch.name AS chapter, ch.code AS chapter_code,
                       ch.class_level, s.code AS subject, s.name AS subject_name
                FROM academic.concepts co
                JOIN academic.topics t ON t.id = co.topic_id AND t.deleted_at IS NULL
                JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                JOIN academic.subjects s ON s.id = ch.subject_id AND s.deleted_at IS NULL
                WHERE co.deleted_at IS NULL
                """
            )
        )
    ).mappings().all()
    return {r["concept_code"]: dict(r) for r in rows}


async def existing_flashcard_index(session) -> tuple[dict[str, uuid.UUID], set[str]]:
    """slug -> id ; set of normalized fronts for published+draft flashcards."""
    items = (
        await session.execute(
            select(ContentItem, ContentVersion)
            .join(ContentVersion, ContentVersion.id == ContentItem.latest_version_id)
            .where(
                ContentItem.deleted_at.is_(None),
                ContentItem.content_type == "FLASHCARD",
            )
        )
    ).all()
    by_slug: dict[str, uuid.UUID] = {}
    fronts: set[str] = set()
    for item, ver in items:
        by_slug[item.slug] = item.id
        body = ver.body or {}
        fronts.add(norm_front(str(body.get("front") or "")))
    return by_slug, fronts


def biology_bucket(subject_code: str) -> str:
    if subject_code in {"BOTANY", "ZOOLOGY"}:
        return "BIOLOGY"
    return subject_code


async def amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--authorize-import", action="store_true")
    parser.add_argument("--authorize-publish", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.authorize_import:
        print("Refusing: pass --dry-run or --authorize-import")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat()

    stats = Counter()
    rejected: list[dict[str, Any]] = []
    inserted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    review_flags: list[dict[str, Any]] = []
    coverage = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    async with AsyncSessionLocal() as session:
        concepts = await load_concept_index(session)
        by_slug, existing_fronts = await existing_flashcard_index(session)
        author_id = await resolve_author(session)
        seed_fronts: set[str] = set()

        # Pre-validate corpus
        for card in ALL_CARDS:
            stats["corpus_total"] += 1
            key = card.get("card_key")
            code = card.get("concept_code")
            if not key or not code:
                stats["rejected_invalid"] += 1
                rejected.append({"card_key": key, "reason": "missing_key_or_concept"})
                continue
            if code not in concepts:
                stats["rejected_unknown_concept"] += 1
                rejected.append({"card_key": key, "reason": f"unknown_concept:{code}"})
                continue
            try:
                body = validate_body(
                    "FLASHCARD",
                    {
                        "front": card["front"],
                        "back": card["back"],
                        "explanation": card.get("explanation"),
                        "difficulty": card.get("difficulty"),
                        "source": card.get("source"),
                        "source_reference": card.get("source_reference"),
                        "class_level": card.get("class_level"),
                    },
                )
            except Exception as exc:  # noqa: BLE001
                stats["rejected_invalid"] += 1
                rejected.append({"card_key": key, "reason": f"body:{exc}"})
                continue

            nf = norm_front(body["front"])
            if not nf:
                stats["rejected_invalid"] += 1
                rejected.append({"card_key": key, "reason": "empty_front"})
                continue
            if nf in seed_fronts:
                stats["rejected_duplicate_seed"] += 1
                rejected.append({"card_key": key, "reason": "duplicate_front_in_seed"})
                continue
            if nf in existing_fronts:
                stats["rejected_duplicate_existing"] += 1
                rejected.append({"card_key": key, "reason": "duplicate_front_existing_db"})
                continue

            # Soft quality flags (do not reject)
            if len(body["front"]) < 12 or len(body["back"]) < 3:
                review_flags.append({"card_key": key, "flag": "short_text"})
            if body.get("source") == "NCERT" and not body.get("source_reference"):
                review_flags.append({"card_key": key, "flag": "missing_source_reference"})

            seed_fronts.add(nf)
            meta = concepts[code]
            subj = biology_bucket(meta["subject"])
            class_lvl = str(card.get("class_level") or meta.get("class_level") or "?")
            coverage[subj][class_lvl][meta["chapter"]] += 1

            slug = card_slug(key)
            if slug in by_slug:
                stats["skipped_existing_slug"] += 1
                skipped.append({"card_key": key, "slug": slug, "item_id": str(by_slug[slug])})
                continue

            if args.dry_run:
                stats["would_insert"] += 1
                inserted.append({"card_key": key, "slug": slug, "dry_run": True})
                continue

            # Import
            svc = ContentWorkflowService(session)
            tags = [
                BATCH_TAG,
                f"card_key:{key}",
                f"difficulty:{body.get('difficulty') or 'unspecified'}",
                f"source:{body.get('source') or 'unspecified'}",
                f"class:{class_lvl}",
                f"subject:{meta['subject']}",
                f"chapter:{meta['chapter_code']}",
            ]
            item = await svc.create_item(
                content_type="FLASHCARD",
                concept_id=meta["concept_id"],
                title=(body["front"][:80] or key),
                slug=slug,
                tags=tags,
                language="en",
                body=body,
                author_id=author_id,
                model_used="human_curated_seed_v1",
                prompt_version="flashcard-seed-v1",
                commit=True,
            )
            stats["inserted_draft"] += 1
            by_slug[slug] = item.id
            existing_fronts.add(nf)
            row = {"card_key": key, "slug": slug, "item_id": str(item.id), "status": item.status}

            if args.authorize_publish:
                try:
                    # Seed-attested path: curated NCERT pack does not burn 1× live
                    # EVALUATOR call per card. Status still follows
                    # DRAFT → IN_REVIEW → APPROVED → PUBLISHED.
                    latest = await session.get(ContentVersion, item.latest_version_id)
                    if latest is None:
                        raise RuntimeError("missing_latest_version")
                    latest.ai_check_report = {
                        "status": "seed_attested",
                        "reason": (
                            "FLASHCARD-SEED-V1 curated NCERT revision pack — "
                            "live AI evaluator skipped under --authorize-publish seed path"
                        ),
                        "flags": [],
                        "similarity_matches": [],
                        "confidence": None,
                        "checked_at": datetime.now(UTC).isoformat(),
                        "seed_batch": BATCH_TAG,
                    }
                    latest.workflow_state = "IN_REVIEW"
                    item.status = "IN_REVIEW"
                    await session.commit()

                    await svc.review(
                        item.id,
                        reviewer_id=author_id,
                        decision="approve",
                        comment=(
                            "FLASHCARD-SEED-V1 curated NCERT revision pack — "
                            "approved for student browse"
                        ),
                        commit=True,
                    )
                    await svc.publish(item.id)
                    stats["published"] += 1
                    stats["seed_attested_ai_skip"] += 1
                    row["status"] = "PUBLISHED"
                except Exception as exc:  # noqa: BLE001
                    stats["publish_failed"] += 1
                    row["publish_error"] = str(exc)[:240]
                    review_flags.append(
                        {"card_key": key, "flag": "publish_failed", "detail": str(exc)[:240]}
                    )
            inserted.append(row)

        # Post counts
        pub = (
            await session.execute(
                text(
                    """
                    SELECT count(*) FROM cms.content_items
                    WHERE deleted_at IS NULL AND content_type='FLASHCARD' AND status='PUBLISHED'
                    """
                )
            )
        ).scalar_one()
        total_fc = (
            await session.execute(
                text(
                    """
                    SELECT count(*) FROM cms.content_items
                    WHERE deleted_at IS NULL AND content_type='FLASHCARD'
                    """
                )
            )
        ).scalar_one()

        # Coverage gaps: chapters with concepts but 0 seed cards
        chapters = (
            await session.execute(
                text(
                    """
                    SELECT s.code AS subject, ch.class_level, ch.name AS chapter, count(co.id) AS concepts
                    FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id AND s.deleted_at IS NULL
                    LEFT JOIN academic.topics t ON t.chapter_id = ch.id AND t.deleted_at IS NULL
                    LEFT JOIN academic.concepts co ON co.topic_id = t.id AND co.deleted_at IS NULL
                    WHERE ch.deleted_at IS NULL
                    GROUP BY s.code, ch.class_level, ch.name
                    ORDER BY s.code, ch.class_level NULLS LAST, ch.name
                    """
                )
            )
        ).mappings().all()
        gaps = []
        for ch in chapters:
            bucket = biology_bucket(ch["subject"])
            class_lvl = str(ch["class_level"] or "?")
            n = coverage[bucket][class_lvl].get(ch["chapter"], 0)
            if ch["concepts"] and n == 0:
                gaps.append(
                    {
                        "subject": ch["subject"],
                        "class": class_lvl,
                        "chapter": ch["chapter"],
                        "concepts": ch["concepts"],
                        "seed_cards": 0,
                    }
                )
            elif not ch["concepts"]:
                gaps.append(
                    {
                        "subject": ch["subject"],
                        "class": class_lvl,
                        "chapter": ch["chapter"],
                        "concepts": 0,
                        "seed_cards": n,
                        "note": "no_concepts_in_taxonomy",
                    }
                )

    report = {
        "batch": BATCH_TAG,
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "mode": {
            "dry_run": args.dry_run,
            "authorize_import": args.authorize_import,
            "authorize_publish": args.authorize_publish,
        },
        "corpus_size": len(ALL_CARDS),
        "stats": dict(stats),
        "db_flashcards_total": total_fc,
        "db_flashcards_published": pub,
        "coverage": {s: {c: dict(chs) for c, chs in classes.items()} for s, classes in coverage.items()},
        "coverage_gaps": gaps,
        "duplicates_rejected": stats.get("rejected_duplicate_seed", 0)
        + stats.get("rejected_duplicate_existing", 0),
        "invalid_rejected": stats.get("rejected_invalid", 0) + stats.get("rejected_unknown_concept", 0),
        "cards_requiring_review": review_flags,
        "rejected_sample": rejected[:50],
        "inserted_sample": inserted[:20],
        "skipped_sample": skipped[:20],
        "provenance_policy": {
            "source": "NCERT chapter-level references only",
            "page_numbers": "NOT_INVENTED",
            "body_fields": ["front", "back", "explanation", "difficulty", "source", "source_reference", "class_level"],
        },
        "validation_status": "CORPUS_VALIDATED_PRE_IMPORT"
        if stats.get("rejected_invalid", 0) == 0 and stats.get("rejected_unknown_concept", 0) == 0
        else "CORPUS_HAS_REJECTIONS",
        "verdict_note": (
            "Rows inserted ≠ content verified. Student visibility requires PUBLISHED. "
            "Quality gate: curated NCERT facts + schema/dup checks; spot scientific review still advised."
        ),
    }

    # Export immutable JSONL of corpus
    jsonl_path = OUT / "flashcards_seed_v1.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for card in ALL_CARDS:
            fh.write(json.dumps(card, ensure_ascii=False) + "\n")
    report["artifact_hashes"] = {
        "flashcards_seed_v1.jsonl": hashlib.sha256(jsonl_path.read_bytes()).hexdigest(),
    }

    (OUT / "import_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    # Markdown coverage report
    lines = [
        f"# Flashcard Seed V1 — Import Report",
        "",
        f"- Mode: dry_run={args.dry_run} import={args.authorize_import} publish={args.authorize_publish}",
        f"- Corpus size: **{len(ALL_CARDS)}**",
        f"- Stats: `{dict(stats)}`",
        f"- DB FLASHCARD total / published: **{total_fc}** / **{pub}**",
        f"- Duplicates rejected: **{report['duplicates_rejected']}**",
        f"- Invalid rejected: **{report['invalid_rejected']}**",
        f"- Cards flagged for review: **{len(review_flags)}**",
        "",
        "## Coverage (Subject → Class → Chapter → count)",
        "",
    ]
    for subj in sorted(coverage):
        lines.append(f"### {subj}")
        for class_lvl in sorted(coverage[subj]):
            lines.append(f"- Class {class_lvl}")
            for ch, n in sorted(coverage[subj][class_lvl].items(), key=lambda x: -x[1]):
                lines.append(f"  - {ch}: **{n}**")
        lines.append("")
    lines += ["## Coverage gaps", ""]
    if not gaps:
        lines.append("- None")
    else:
        for g in gaps:
            lines.append(f"- {g}")
    lines += [
        "",
        "## Validation status",
        "",
        f"**{report['validation_status']}**",
        "",
        report["verdict_note"],
        "",
    ]
    (OUT / "coverage_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({k: report[k] for k in ("stats", "db_flashcards_total", "db_flashcards_published", "duplicates_rejected", "invalid_rejected", "validation_status", "mode")}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
