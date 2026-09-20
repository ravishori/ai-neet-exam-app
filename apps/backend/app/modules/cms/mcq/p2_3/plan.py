"""P2.3 concept inventory and generation plan."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from app.modules.cms.mcq.p2_3.schemas import ConceptSlot, GenerationSlot
from app.modules.cms.pyq.p2_2.ncert_sources import NcertPageSource, build_ncert_source_pool

SUBJECT_TARGETS = {"BIOLOGY": 340, "CHEMISTRY": 330, "PHYSICS": 330}
DIFFICULTY_MIX = [("EASY", 0.25), ("MEDIUM", 0.50), ("HARD", 0.25)]
QUESTION_TYPES = [
    "factual",
    "conceptual",
    "statement_based",
    "application",
    "numerical",
    "assertion_reasoning",
    "match_relationship",
]
PROVIDER_ORDER = ("gemini", "openai")  # Anthropic disabled (P2.3-R1 billing)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_concept_inventory(sources: list[NcertPageSource]) -> list[ConceptSlot]:
    concepts: list[ConceptSlot] = []
    for src in sources:
        cid = f"{src.subject.lower()}:c{src.chapter or 0}:p{src.page}:{src.source_id}"
        locator = f"{src.relative_path}#page={src.page}"
        concepts.append(
            ConceptSlot(
                concept_id=cid,
                source_id=src.source_id,
                subject=src.subject,
                class_level=src.class_level,
                chapter=src.chapter,
                topic=f"chapter-{src.chapter or 'unknown'}-page-{src.page}",
                source_locator=locator,
                source_file=src.relative_path,
                source_page=src.page,
                source_excerpt_hash=src.text_hash,
                excerpt_preview=src.text[:200],
            )
        )
    return concepts


def build_generation_plan(
    concepts: list[ConceptSlot],
    *,
    total: int = 1000,
    seed: int = 20260903,
) -> tuple[list[GenerationSlot], dict[str, Any]]:
    rng = random.Random(seed)
    by_subject: dict[str, list[ConceptSlot]] = {}
    for c in concepts:
        by_subject.setdefault(c.subject, []).append(c)

    slots: list[GenerationSlot] = []
    planned: dict[str, int] = {}
    idx = 0
    for subject, target in SUBJECT_TARGETS.items():
        pool = by_subject.get(subject, concepts)[:]
        rng.shuffle(pool)
        if not pool:
            continue
        planned[subject] = target
        for i in range(target):
            concept = pool[i % len(pool)]
            diff_roll = rng.random()
            cumulative = 0.0
            difficulty = "MEDIUM"
            for label, frac in DIFFICULTY_MIX:
                cumulative += frac
                if diff_roll <= cumulative:
                    difficulty = label
                    break
            qtype = QUESTION_TYPES[(idx + i) % len(QUESTION_TYPES)]
            provider = PROVIDER_ORDER[(idx + i) % len(PROVIDER_ORDER)]
            slots.append(
                GenerationSlot(
                    slot_index=idx,
                    concept=concept,
                    question_type=qtype,
                    difficulty=difficulty,
                    generation_provider=provider,
                )
            )
            idx += 1

    while len(slots) < total:
        concept = rng.choice(concepts)
        slots.append(
            GenerationSlot(
                slot_index=len(slots),
                concept=concept,
                question_type=QUESTION_TYPES[len(slots) % len(QUESTION_TYPES)],
                difficulty="MEDIUM",
                generation_provider=PROVIDER_ORDER[len(slots) % len(PROVIDER_ORDER)],
            )
        )

    slots = slots[:total]
    meta = {
        "seed": seed,
        "total": len(slots),
        "planned_subject": planned,
        "actual_subject": _count_subjects(slots),
        "difficulty": _count_field(slots, "difficulty"),
        "question_type": _count_field(slots, "question_type"),
        "provider": _count_providers(slots),
    }
    return slots, meta


def _count_subjects(slots: list[GenerationSlot]) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in slots:
        out[s.concept.subject] = out.get(s.concept.subject, 0) + 1
    return out


def _count_field(slots: list[GenerationSlot], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in slots:
        val = getattr(s, field)
        out[str(val)] = out.get(str(val), 0) + 1
    return out


def _count_providers(slots: list[GenerationSlot]) -> dict[str, int]:
    return _count_field(slots, "generation_provider")


def inventory_from_study_dir(study_dir: Any) -> list[ConceptSlot]:
    pool = build_ncert_source_pool(study_dir)
    return build_concept_inventory(pool)
