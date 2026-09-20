"""Export prioritized REVIEW queue for SME claim-level certification."""
from __future__ import annotations

import asyncio
import csv
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

from app.core.database import AsyncSessionLocal

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
OUT = REPO / "docs" / "acquisition" / "flashcards" / "SEED-V1"


def priority(row: dict) -> tuple[int, str]:
    prov = row.get("certification_provenance") or ""
    chapter = row.get("chapter") or ""
    if prov in {"UNSUPPORTED", "MISSING"}:
        return (0, chapter)
    if chapter in {
        "Mechanical Properties of Fluids",
        "Systems of Particles and Rotational Motion",
    }:
        return (1, chapter)
    if chapter == "Biomolecules":
        return (2, chapter)
    return (3, chapter)


async def main() -> None:
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                text(
                    """
                    SELECT ci.id::text AS id, ci.slug, ci.tags, ci.status,
                           cv.id::text AS version_id, cv.body,
                           s.code AS subject_code, s.name AS subject,
                           ch.class_level::text AS class_level_taxonomy,
                           ch.code AS chapter_code, ch.name AS chapter,
                           t.code AS topic_code, t.name AS topic,
                           co.code AS concept_code, co.name AS concept
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.current_version_id
                    JOIN academic.concepts co ON co.id = ci.concept_id
                    JOIN academic.topics t ON t.id = co.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ci.deleted_at IS NULL
                      AND ci.content_type = 'FLASHCARD'
                      AND ci.status = 'PUBLISHED'
                      AND (
                        cv.body->>'certification_status' = 'REVIEW'
                        OR 'audit:REVIEW' = ANY(ci.tags)
                      )
                    ORDER BY s.code, ch.name, ci.slug
                    """
                )
            )
        ).mappings().all()

    queue = []
    for r in rows:
        b = r["body"] or {}
        item = {
            "id": r["id"],
            "version_id": r["version_id"],
            "slug": r["slug"],
            "status": r["status"],
            "subject_code": r["subject_code"],
            "subject": r["subject"],
            "class_level_taxonomy": r["class_level_taxonomy"],
            "class_level_body": b.get("class_level"),
            "chapter": r["chapter"],
            "chapter_code": r["chapter_code"],
            "topic": r["topic"],
            "topic_code": r["topic_code"],
            "concept": r["concept"],
            "concept_code": r["concept_code"],
            "front": b.get("front"),
            "back": b.get("back"),
            "explanation": b.get("explanation"),
            "difficulty": b.get("difficulty"),
            "source": b.get("source"),
            "source_reference": b.get("source_reference"),
            "prev_status": b.get("certification_status") or "REVIEW",
            "prev_reason": b.get("certification_reason"),
            "certification_provenance": b.get("certification_provenance"),
            "certified_at": b.get("certified_at"),
        }
        p, _ = priority(item)
        item["priority"] = p
        queue.append(item)

    queue.sort(key=lambda x: (x["priority"], x["subject_code"], x["chapter"], x["slug"]))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sme_review_queue.json").write_text(
        json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    fields = [
        "priority",
        "id",
        "subject_code",
        "chapter",
        "topic",
        "front",
        "back",
        "explanation",
        "difficulty",
        "source",
        "source_reference",
        "certification_provenance",
        "class_level_body",
        "class_level_taxonomy",
        "prev_reason",
    ]
    with (OUT / "sme_review_queue.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(queue)

    by_p = defaultdict(int)
    for q in queue:
        by_p[q["priority"]] += 1
    print(json.dumps({"total": len(queue), "by_priority": dict(by_p)}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
