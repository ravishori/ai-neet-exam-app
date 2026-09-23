"""WAVE-P0-11A — Optics academic hierarchy gap concepts (idempotent).

Creates only the minimum missing Optics concepts needed for accurate
PHY-02 / PHY-08 / PHY-10 mapping. Does not modify any content_items.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.cms.acquisition.batch_a_hierarchy import BATCH_A_HIERARCHY

# Codes that close SME hierarchy gaps (subset of BATCH_A_HIERARCHY optics).
OPTICS_GAP_CONCEPT_CODES: tuple[str, ...] = (
    "principal-focus-spherical-mirror",
    "refractive-index",
    "lens-power-focal-length",
)

PHY_PILOT_IDS: tuple[str, ...] = (
    "8721e193-2d6e-433a-81d9-ceb2b31aef01",  # PHY-01
    "f51bd10d-70c1-4bc1-98f3-490f723ec549",  # PHY-02
    "fbfa14ed-b9cc-4016-8c4b-d08f997ecdd6",  # PHY-03
    "4d0ab71e-a997-4ac1-ad17-ba24f030a19c",  # PHY-04
    "f7b0f62f-1fcb-4a69-9052-455e00f7cb84",  # PHY-05
    "9a0ae17f-38f3-4141-8dad-389ae265195c",  # PHY-06
    "4b928b5f-da43-4361-89db-312b6c6950a4",  # PHY-07
    "6d7b9e60-e56f-46e0-b553-654aba9c4a47",  # PHY-08
    "961327ff-e291-4c57-a5c2-4f2de51f9004",  # PHY-09
    "18238e36-2102-4aea-acca-9c9709d0722e",  # PHY-10
)

# Intended future mapping (NOT applied in this wave)
GAP_CONCEPT_FUTURE_MAPPING: dict[str, list[str]] = {
    "principal-focus-spherical-mirror": ["PHY-02"],
    "refractive-index": ["PHY-08"],
    "lens-power-focal-length": ["PHY-10"],
}


async def audit_optics_hierarchy(session: AsyncSession) -> dict[str, Any]:
    """Read-only audit of Physics → Optics topics/concepts."""
    result = await session.execute(
        select(Subject.name, Chapter.name, Chapter.code, Topic.name, Topic.code, Concept.name, Concept.code, Concept.id)
        .select_from(Concept)
        .join(Topic, Topic.id == Concept.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .join(Subject, Subject.id == Chapter.subject_id)
        .where(Subject.name == "Physics", Chapter.code == "optics", Concept.deleted_at.is_(None))
        .order_by(Topic.display_order, Concept.display_order)
    )
    rows = []
    for subj, ch_name, ch_code, topic_name, topic_code, concept_name, concept_code, concept_id in result.all():
        rows.append(
            {
                "subject": subj,
                "chapter": ch_name,
                "chapter_code": ch_code,
                "topic": topic_name,
                "topic_code": topic_code,
                "concept": concept_name,
                "concept_code": concept_code,
                "concept_id": str(concept_id),
            }
        )
    by_code = {r["concept_code"]: r for r in rows}
    return {
        "concepts": rows,
        "gap_status": {
            code: ("exists" if code in by_code else "missing") for code in OPTICS_GAP_CONCEPT_CODES
        },
        "existing_gap_ids": {code: by_code[code]["concept_id"] for code in OPTICS_GAP_CONCEPT_CODES if code in by_code},
    }


async def ensure_optics_gap_concepts(session: AsyncSession) -> dict[str, Any]:
    """Idempotently create OPTICS_GAP_CONCEPT_CODES under existing Optics topics.

    Does not create topics/chapters (must already exist from Batch A hierarchy).
    Does not commit — caller controls the transaction.
    """
    optics_topics = BATCH_A_HIERARCHY["optics"]
    wanted: dict[str, tuple[str, str, str, str]] = {}
    # topic_code -> list of gap concepts defined there
    for topic_code, _, concepts in optics_topics:
        for concept_order, (concept_code, concept_name, summary) in enumerate(concepts):
            if concept_code in OPTICS_GAP_CONCEPT_CODES:
                wanted[concept_code] = (topic_code, concept_name, summary, concept_order)

    chapter = (
        await session.execute(select(Chapter).where(Chapter.code == "optics", Chapter.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if not chapter:
        raise RuntimeError("Optics chapter missing — cannot close hierarchy gaps")

    created: list[dict[str, str]] = []
    existing: list[dict[str, str]] = []

    for concept_code, (topic_code, concept_name, summary, concept_order) in wanted.items():
        topic = (
            await session.execute(
                select(Topic).where(
                    Topic.chapter_id == chapter.id,
                    Topic.code == topic_code,
                    Topic.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not topic:
            raise RuntimeError(f"Topic {topic_code!r} missing under Optics — abort")

        concept = (
            await session.execute(
                select(Concept).where(
                    Concept.topic_id == topic.id,
                    Concept.code == concept_code,
                    Concept.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if concept:
            existing.append(
                {
                    "code": concept_code,
                    "name": concept.name,
                    "id": str(concept.id),
                    "topic": topic.name,
                }
            )
            continue

        # Avoid duplicate names under same topic (different code)
        name_clash = (
            await session.execute(
                select(Concept).where(
                    Concept.topic_id == topic.id,
                    Concept.name == concept_name,
                    Concept.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if name_clash:
            raise RuntimeError(
                f"Name clash: concept {concept_name!r} already exists as code={name_clash.code} id={name_clash.id}"
            )

        concept = Concept(
            topic_id=topic.id,
            code=concept_code,
            name=concept_name,
            summary=summary,
            display_order=concept_order,
            difficulty="medium",
        )
        session.add(concept)
        await session.flush()
        created.append(
            {
                "code": concept_code,
                "name": concept_name,
                "id": str(concept.id),
                "topic": topic.name,
                "topic_code": topic_code,
            }
        )

    return {
        "created": created,
        "already_existed": existing,
        "wanted_codes": list(OPTICS_GAP_CONCEPT_CODES),
        "future_question_mapping": GAP_CONCEPT_FUTURE_MAPPING,
    }
