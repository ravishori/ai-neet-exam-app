"""P2.3 duplicate detection including P2.2 protected stems."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from app.modules.cms.mcq.p2_3.schemas import DuplicateStatus, McqRecord
from app.modules.cms.services.factory_candidate_validation import normalize_stem, stem_hash


def near_duplicate(a: str, b: str, threshold: float = 0.92) -> bool:
    return SequenceMatcher(None, normalize_stem(a), normalize_stem(b)).ratio() >= threshold


def classify_duplicates(
    records: list[McqRecord],
    *,
    protected_stems: list[str] | None = None,
) -> None:
    seen_hash: dict[str, str] = {}
    stems: dict[str, str] = {}
    protected = [normalize_stem(s) for s in (protected_stems or []) if s.strip()]

    for rec in records:
        if not rec.question.strip():
            continue
        h = stem_hash(rec.question)
        status: DuplicateStatus = "NO_DUPLICATE"
        dup_of: str | None = None
        score = 0.0

        if h in seen_hash:
            status = "EXACT_DUPLICATE"
            dup_of = seen_hash[h]
            score = 1.0
        else:
            for other_id, other_stem in stems.items():
                if near_duplicate(rec.question, other_stem):
                    status = "NEAR_DUPLICATE"
                    dup_of = other_id
                    score = SequenceMatcher(None, normalize_stem(rec.question), normalize_stem(other_stem)).ratio()
                    break
            if status == "NO_DUPLICATE" and protected:
                for ps in protected:
                    if near_duplicate(rec.question, ps):
                        status = "SEMANTIC_DUPLICATE"
                        dup_of = "p2_2_cohort"
                        score = SequenceMatcher(None, normalize_stem(rec.question), ps).ratio()
                        break

        rec.duplicate_status = status
        rec.duplicate_of = dup_of
        rec.similarity_score = round(score, 4)
        if status != "NO_DUPLICATE":
            rec.errors.append(f"duplicate:{status}")
            if rec.validation_status == "READY":
                rec.validation_status = "REJECT"
                rec.final_status = "REJECT"
        seen_hash.setdefault(h, rec.question_id)
        stems[rec.question_id] = rec.question
