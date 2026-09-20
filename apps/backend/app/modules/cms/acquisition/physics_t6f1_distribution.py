"""Reproducible distribution plan for T6-F1 — round-robin across P0 concepts."""

from __future__ import annotations

from app.modules.academic.physics_p0_manifest import PHYSICS_P0_CHAPTERS
from app.modules.cms.acquisition.physics_t6f1_constants import TARGET_CANDIDATES


def concept_codes_in_order() -> list[str]:
    codes: list[str] = []
    for ch in PHYSICS_P0_CHAPTERS:
        for topic in ch.topics:
            for concept in topic.concepts:
                codes.append(concept.code)
    return codes


def distribution_plan(requested: int = TARGET_CANDIDATES) -> dict[str, int]:
    """Assign quotas per concept; sum equals `requested` when possible."""
    codes = concept_codes_in_order()
    if not codes:
        return {}
    base, rem = divmod(requested, len(codes))
    plan: dict[str, int] = {}
    for i, code in enumerate(codes):
        plan[code] = base + (1 if i < rem else 0)
    return plan


def chapter_distribution_from_plan(plan: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for ch in PHYSICS_P0_CHAPTERS:
        n = sum(plan.get(c.code, 0) for t in ch.topics for c in t.concepts)
        if n:
            out[ch.code] = n
    return out


def topic_distribution_from_plan(plan: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for ch in PHYSICS_P0_CHAPTERS:
        for topic in ch.topics:
            n = sum(plan.get(c.code, 0) for c in topic.concepts)
            if n:
                out[topic.code] = n
    return out
