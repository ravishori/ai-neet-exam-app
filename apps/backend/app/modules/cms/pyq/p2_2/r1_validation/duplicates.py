"""Duplicate detection for P2.2-R1."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from app.modules.cms.pyq.p2_2.r1_validation.schemas import DuplicateClass
from app.modules.cms.services.factory_candidate_validation import normalize_stem, stem_hash


def near_duplicate(a: str, b: str, threshold: float = 0.92) -> bool:
    return SequenceMatcher(None, normalize_stem(a), normalize_stem(b)).ratio() >= threshold


def classify_duplicates(
    candidates: list[dict[str, Any]],
    *,
    r3_stems: list[str] | None = None,
) -> dict[str, DuplicateClass]:
    classes: dict[str, DuplicateClass] = {}
    by_hash: dict[str, str] = {}
    stems_by_id: dict[str, str] = {}
    r3_norm = [normalize_stem(s) for s in (r3_stems or []) if s.strip()]

    for row in candidates:
        mcq_id = row["mcq_id"]
        stem = row.get("question") or ""
        h = stem_hash(stem)
        dup: DuplicateClass = "NO_DUPLICATE"
        if h in by_hash:
            dup = "EXACT_DUPLICATE"
        else:
            for _, other_stem in stems_by_id.items():
                if near_duplicate(stem, other_stem):
                    dup = "NEAR_DUPLICATE"
                    break
            if dup == "NO_DUPLICATE" and r3_norm:
                for rs in r3_norm:
                    if near_duplicate(stem, rs):
                        dup = "SEMANTIC_DUPLICATE"
                        break
        by_hash.setdefault(h, mcq_id)
        stems_by_id[mcq_id] = stem
        classes[mcq_id] = dup
    return classes
