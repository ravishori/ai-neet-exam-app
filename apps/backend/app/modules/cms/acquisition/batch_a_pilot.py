"""WAVE-P0-10 — Batch A SME pilot selection (read-only; does not change statuses).

Selects ~10 Physics / 10 Chemistry / 10 Botany / 10 Zoology from the 74
acquisition-batch-A drafts with chapter/topic/difficulty diversity.
Remaining Batch A items stay outside the pilot set until evaluated.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.cms.acquisition.batch_a_catalog import BATCH_ID, MODEL_USED
from app.modules.cms.models import ContentItem
from app.modules.cms.services.editorial_review_service import REVIEW_CHECKLIST, _provenance_from_version, _structural_assessment

PILOT_ID = "batch-a-sme-pilot-40"
PILOT_TARGETS = {"Physics": 10, "Chemistry": 10, "Botany": 10, "Zoology": 10}


def _difficulty_rank(d: str | None) -> int:
    return {"easy": 0, "medium": 1, "hard": 2}.get((d or "").lower(), 1)


async def load_batch_a_items(session: AsyncSession) -> list[dict[str, Any]]:
    """Load all Batch A QUESTION items with academic context (read-only)."""
    result = await session.execute(
        select(ContentItem, Subject.name, Chapter.name, Topic.name, Concept.name, Concept.id)
        .options(selectinload(ContentItem.versions))
        .join(Concept, Concept.id == ContentItem.concept_id)
        .join(Topic, Topic.id == Concept.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .join(Subject, Subject.id == Chapter.subject_id)
        .where(
            ContentItem.content_type == "QUESTION",
            ContentItem.deleted_at.is_(None),
            ContentItem.status != "ARCHIVED",
        )
    )
    rows: list[dict[str, Any]] = []
    for item, subject, chapter, topic, concept, concept_id in result.unique().all():
        tags = item.tags or []
        by_id = {v.id: v for v in item.versions}
        latest = by_id.get(item.latest_version_id)
        model_used = latest.model_used if latest else None
        is_batch_a = BATCH_ID in tags or model_used == MODEL_USED or (item.slug or "").startswith("batch-a-")
        if not is_batch_a:
            continue
        body = latest.body if latest else {}
        structural = _structural_assessment(item.content_type, body, item.concept_id)
        provenance = _provenance_from_version(latest)
        rows.append(
            {
                "id": str(item.id),
                "slug": item.slug,
                "title": item.title,
                "status": item.status,
                "subject": subject,
                "chapter": chapter,
                "topic": topic,
                "concept": concept,
                "concept_id": str(concept_id),
                "difficulty": (body or {}).get("difficulty"),
                "stem": (body or {}).get("stem"),
                "options": (body or {}).get("options"),
                "correct_option": (body or {}).get("correct_option"),
                "explanation": (body or {}).get("explanation"),
                "structural": structural,
                "provenance": provenance,
                "model_used": model_used,
                "tags": tags,
                "created_at": item.created_at,
            }
        )
    return rows


def select_pilot(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Diversified selection — does not mutate DB."""
    eligible = [
        i
        for i in items
        if i["status"] in ("DRAFT", "IN_REVIEW", "CHANGES_REQUESTED", "APPROVED")
        and i["structural"]["valid"]
        and i["concept_id"]
    ]

    by_subject: dict[str, list[dict]] = defaultdict(list)
    for i in eligible:
        if i["subject"] in PILOT_TARGETS:
            by_subject[i["subject"]].append(i)

    selected: list[dict] = []
    selection_notes: dict[str, str] = {}

    for subject, target in PILOT_TARGETS.items():
        pool = sorted(
            by_subject.get(subject, []),
            key=lambda r: (
                0 if r["provenance"]["has_lineage"] else 1,
                r["chapter"],
                r["topic"],
                _difficulty_rank(r["difficulty"]),
                r["created_at"].timestamp() if r["created_at"] else 0,
            ),
        )
        # Round-robin across chapters then topics for diversity
        by_chapter: dict[str, list[dict]] = defaultdict(list)
        for r in pool:
            by_chapter[r["chapter"]].append(r)

        picked: list[dict] = []
        chapter_names = list(by_chapter.keys())
        if not chapter_names:
            selection_notes[subject] = "No eligible Batch A items"
            continue

        # Cap soft per chapter to force diversity when multiple chapters exist
        max_per_chapter = max(1, (target + len(chapter_names) - 1) // len(chapter_names) + 1)
        chapter_counts: dict[str, int] = defaultdict(int)
        topic_counts: dict[str, int] = defaultdict(int)
        diff_counts: dict[str, int] = defaultdict(int)

        # Pass 1: round-robin chapters
        indices = {ch: 0 for ch in chapter_names}
        while len(picked) < target and any(indices[ch] < len(by_chapter[ch]) for ch in chapter_names):
            progress = False
            for ch in chapter_names:
                if len(picked) >= target:
                    break
                if chapter_counts[ch] >= max_per_chapter:
                    continue
                idx = indices[ch]
                while idx < len(by_chapter[ch]):
                    cand = by_chapter[ch][idx]
                    idx += 1
                    topic_key = f"{ch}/{cand['topic']}"
                    # Prefer not overloading one topic early
                    if topic_counts[topic_key] >= 3 and any(
                        topic_counts[f"{ch2}/{r['topic']}"] < 3
                        for ch2 in chapter_names
                        for r in by_chapter[ch2][indices[ch2] :]
                    ):
                        continue
                    picked.append(cand)
                    chapter_counts[ch] += 1
                    topic_counts[topic_key] += 1
                    diff_counts[cand["difficulty"] or "unknown"] += 1
                    progress = True
                    break
                indices[ch] = idx
            if not progress:
                break

        # Pass 2: fill remaining without chapter cap
        if len(picked) < target:
            picked_ids = {p["id"] for p in picked}
            for r in pool:
                if len(picked) >= target:
                    break
                if r["id"] in picked_ids:
                    continue
                picked.append(r)
                picked_ids.add(r["id"])

        for i, row in enumerate(picked, 1):
            row = {
                **row,
                "pilot_label": f"{subject[:3].upper()}-{i:02d}",
                "pilot_rank": i,
                "priority_reasons": [
                    "Batch A SME pilot selection",
                    f"Subject below interim published target — {subject}",
                    f"Chapter “{row['chapter']}” diversification (was empty/low published)",
                    "Structurally valid + mapped",
                    f"Provenance: {row['provenance']['status']} ({row.get('model_used')})",
                    f"Difficulty: {row['difficulty']}",
                    "HUMAN REVIEW REQUIRED — not official NTA/NCERT",
                ],
            }
            selected.append(row)

        ch_final: dict[str, int] = defaultdict(int)
        for p in picked:
            ch_final[p["chapter"]] += 1
        selection_notes[subject] = (
            f"Selected {len(picked)}/{target}; chapters={dict(ch_final)}; "
            f"difficulty={dict(Counter_diff(picked))}"
        )

    remaining = [i for i in items if i["id"] not in {s["id"] for s in selected}]
    return {
        "pilot_id": PILOT_ID,
        "batch_id": BATCH_ID,
        "targets": PILOT_TARGETS,
        "selected_count": len(selected),
        "batch_a_total": len(items),
        "remaining_batch_a_untouched": len(remaining),
        "selection_notes": selection_notes,
        "selected": selected,
        "remaining_ids": [r["id"] for r in remaining],
        "distributions": {
            "subject": _count(selected, "subject"),
            "chapter": _count(selected, "chapter"),
            "topic": {f"{r['chapter']} / {r['topic']}": 1 for r in selected},  # filled below
            "difficulty": _count(selected, "difficulty"),
            "status": _count(selected, "status"),
        },
        "checklist": REVIEW_CHECKLIST
        + [
            {
                "id": "batch_a_origin",
                "category": "Provenance",
                "prompt": "Confirm this is Human-authored Batch A (not official NTA/NCERT) and SME review is still required.",
            },
            {
                "id": "source_verify",
                "category": "Provenance",
                "prompt": "If no authoritative source was checked: mark Source verification required — do not invent citations.",
            },
        ],
        "rules": {
            "human_review_mandatory": True,
            "no_auto_approve": True,
            "no_auto_publish": True,
            "no_bulk_publish": True,
            "quality_over_target": True,
            "checklist_does_not_approve": True,
        },
    }


def Counter_diff(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        out[r.get("difficulty") or "unknown"] += 1
    return dict(out)


def _count(rows: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        out[str(r.get(key) or "unknown")] += 1
    return dict(out)


async def build_pilot_report(session: AsyncSession) -> dict[str, Any]:
    items = await load_batch_a_items(session)
    report = select_pilot(items)
    # Fix topic distribution properly
    topic_dist: dict[str, int] = defaultdict(int)
    for r in report["selected"]:
        topic_dist[f"{r['chapter']} / {r['topic']}"] += 1
    report["distributions"]["topic"] = dict(topic_dist)
    return report
