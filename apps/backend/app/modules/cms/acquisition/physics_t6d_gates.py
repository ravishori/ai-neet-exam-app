"""T6-D validation gates — structure, science, NCERT provenance, taxonomy, duplicates.

T6-E-FIX: numerical soft-pass removed; near-duplicate bands; batch distribution audits.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

from app.modules.cms.acquisition.physics_t6d_bank import PilotCandidate, build_bank, lineage_by_concept
from app.modules.cms.acquisition.physics_t6d_constants import MAX_CANDIDATES
from app.modules.cms.schemas.content_bodies import QuestionBody
from app.modules.cms.schemas.question_evidence import SimilarityBand
from app.modules.cms.services.factory_candidate_validation import normalize_stem, stem_hash
from app.modules.cms.services.numerical_validation import classify_and_verify

GateResult = Literal["ACCEPT", "REJECT", "HOLD"]


@dataclass
class GateReport:
    pilot_qid: str
    slug: str
    result: GateResult
    reasons: list[str] = field(default_factory=list)
    structural_ok: bool = False
    scientific_ok: bool = False
    ncert_ok: bool = False
    taxonomy_ok: bool = False
    duplicate_ok: bool = False
    numerical_status: str = "NOT_NUMERICAL"
    similarity_band: SimilarityBand = "UNIQUE"
    ncert_verification_level: str = "SECTION_VERIFIED"

    @property
    def accepted(self) -> bool:
        return self.result == "ACCEPT"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def verify_calculation(candidate: PilotCandidate) -> tuple[bool, str, str]:
    """Scientific gate — incomplete numerical payloads FAIL (no soft-pass)."""
    status, msg = classify_and_verify(candidate.calculation_check or {})
    if status == "NOT_NUMERICAL":
        return True, msg, status
    if status == "NUMERICAL_COMPLETE":
        return True, msg, status
    return False, msg, status


def similarity_band(stem_a: str, stem_b: str, *, fast: bool = False) -> SimilarityBand:
    """Exact / template-near-duplicate / review bands.

    Parametric clones (same wording, different numbers) are NEAR_DUPLICATE.
    Distinct questions that merely share vocabulary stay UNIQUE/REVIEW.
    When fast=True, skip expensive SequenceMatcher (for large batch audits).
    """
    import re

    na, nb = normalize_stem(stem_a), normalize_stem(stem_b)
    if na == nb:
        return "DUPLICATE"
    folded_a = re.sub(r"\d+", "#", na)
    folded_b = re.sub(r"\d+", "#", nb)
    if folded_a == folded_b:
        return "NEAR_DUPLICATE"
    if fast:
        return "UNIQUE"
    ratio = SequenceMatcher(None, na, nb).ratio()
    if ratio >= 0.97:
        return "NEAR_DUPLICATE"
    if ratio >= 0.88:
        return "REVIEW"
    return "UNIQUE"


def validate_candidate(
    candidate: PilotCandidate,
    *,
    seen_hashes: dict[str, str],
    existing_hashes: set[str],
    seen_stems: list[tuple[str, str]],
    repo_root: Path | None = None,
    fast_near_dup: bool = False,
) -> GateReport:
    report = GateReport(pilot_qid=candidate.pilot_qid, slug=candidate.slug, result="ACCEPT")
    root = repo_root or _repo_root()
    lineage = lineage_by_concept().get(candidate.concept_code)

    try:
        QuestionBody.model_validate(candidate.body())
        report.structural_ok = True
    except Exception as exc:  # noqa: BLE001
        report.structural_ok = False
        report.reasons.append(f"structural:{exc}")

    if lineage is None:
        report.taxonomy_ok = False
        report.reasons.append("taxonomy:unknown_concept_code")
    elif (
        lineage.topic_code != candidate.topic_code
        or lineage.chapter_code != candidate.chapter_code
        or lineage.ncert_reference != candidate.ncert_reference
    ):
        report.taxonomy_ok = False
        report.reasons.append("taxonomy:lineage_mismatch")
    else:
        report.taxonomy_ok = True

    # NCERT — section + PDF; never claim page-level here
    pdf_path = root / candidate.source_pdf_relpath
    report.ncert_verification_level = "SECTION_VERIFIED"
    if not candidate.ncert_reference.startswith("NCERT XI Physics"):
        report.ncert_ok = False
        report.reasons.append("ncert:bad_reference_prefix")
    elif not pdf_path.is_file():
        report.ncert_ok = False
        report.reasons.append(f"ncert:missing_pdf:{pdf_path}")
    elif lineage and candidate.ncert_reference != lineage.ncert_reference:
        report.ncert_ok = False
        report.reasons.append("ncert:ref_not_on_concept")
    else:
        # Reject fabricated page claims if present on candidate tags/body
        body = candidate.body()
        ncert_ev = body.get("ncert_evidence") or {}
        if ncert_ev.get("verification_level") == "PAGE_VERIFIED" and ncert_ev.get("page_number") is None:
            report.ncert_ok = False
            report.reasons.append("ncert:fabricated_page_claim")
            report.ncert_verification_level = "NOT_VERIFIED"
        else:
            report.ncert_ok = True
            report.ncert_verification_level = ncert_ev.get("verification_level") or "SECTION_VERIFIED"

    ok, msg, num_status = verify_calculation(candidate)
    report.scientific_ok = ok
    report.numerical_status = num_status
    if not ok:
        report.reasons.append(f"scientific:{msg}")

    h = stem_hash(candidate.stem)
    band: SimilarityBand = "UNIQUE"
    if h in seen_hashes:
        report.duplicate_ok = False
        band = "DUPLICATE"
        report.reasons.append(f"duplicate:intra_pilot:{seen_hashes[h]}")
    elif h in existing_hashes:
        report.duplicate_ok = False
        band = "DUPLICATE"
        report.reasons.append("duplicate:existing_db_stem")
    else:
        for other_qid, other_stem in seen_stems:
            band = similarity_band(candidate.stem, other_stem, fast=fast_near_dup)
            if band in ("NEAR_DUPLICATE", "DUPLICATE"):
                report.duplicate_ok = False
                report.reasons.append(f"duplicate:{band.lower()}:{other_qid}")
                break
            if band == "REVIEW":
                # Flag but do not auto-reject REVIEW — HOLD via reasons
                report.reasons.append(f"similarity:REVIEW:{other_qid}")
        else:
            report.duplicate_ok = True
            seen_hashes[h] = candidate.pilot_qid
            seen_stems.append((candidate.pilot_qid, candidate.stem))

    report.similarity_band = band

    if all(
        [
            report.structural_ok,
            report.scientific_ok,
            report.ncert_ok,
            report.taxonomy_ok,
            report.duplicate_ok,
        ]
    ):
        report.result = "ACCEPT"
    elif not report.structural_ok or not report.taxonomy_ok:
        report.result = "REJECT"
    else:
        report.result = "REJECT"
        if not report.scientific_ok or not report.ncert_ok or not report.duplicate_ok:
            report.result = "REJECT"

    return report


def answer_position_distribution(bank: list[PilotCandidate]) -> dict[str, int]:
    return dict(Counter(c.correct_option for c in bank))


def difficulty_distribution(bank: list[PilotCandidate]) -> dict[str, int]:
    return dict(Counter(c.difficulty for c in bank))


def audit_answer_position(bank: list[PilotCandidate]) -> dict[str, Any]:
    dist = answer_position_distribution(bank)
    missing = [lab for lab in ("A", "B", "C", "D") if dist.get(lab, 0) == 0]
    return {
        "distribution": dist,
        "missing_positions": missing,
        "generation_quality_failure": bool(missing) and len(bank) >= 20,
    }


def audit_difficulty(bank: list[PilotCandidate]) -> dict[str, Any]:
    dist = difficulty_distribution(bank)
    total = len(bank) or 1
    pct = {k: round(100 * v / total, 1) for k, v in dist.items()}
    return {
        "distribution": dist,
        "percentages": pct,
        "collapse_toward_easy": dist.get("easy", 0) / total >= 0.75 and dist.get("hard", 0) == 0,
        "note": "Difficulty is metadata — not a reject gate; collapse is a batch quality warning",
    }


def audit_bank(existing_hashes: set[str] | None = None, *, repo_root: Path | None = None) -> dict[str, Any]:
    bank = build_bank()
    assert len(bank) <= MAX_CANDIDATES, len(bank)
    seen: dict[str, str] = {}
    seen_stems: list[tuple[str, str]] = []
    reports = [
        validate_candidate(
            c,
            seen_hashes=seen,
            existing_hashes=existing_hashes or set(),
            seen_stems=seen_stems,
            repo_root=repo_root,
        )
        for c in bank
    ]
    accepted = [r for r in reports if r.accepted]
    rejected = [r for r in reports if r.result == "REJECT"]
    held = [r for r in reports if r.result == "HOLD"]
    accepted_bank = [c for c, r in zip(bank, reports, strict=True) if r.accepted]

    by_chapter: dict[str, int] = {}
    by_topic: dict[str, int] = {}
    by_concept: dict[str, int] = {}
    by_diff: dict[str, int] = {}
    for c in accepted_bank:
        by_chapter[c.chapter_code] = by_chapter.get(c.chapter_code, 0) + 1
        by_topic[c.topic_code] = by_topic.get(c.topic_code, 0) + 1
        by_concept[c.concept_code] = by_concept.get(c.concept_code, 0) + 1
        by_diff[c.difficulty] = by_diff.get(c.difficulty, 0) + 1

    pos_audit = audit_answer_position(accepted_bank)
    diff_audit = audit_difficulty(accepted_bank)

    return {
        "candidates": len(bank),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "held": len(held),
        "acceptance_rate": round(len(accepted) / len(bank), 4) if bank else 0,
        "duplicate_rate": round(sum(1 for r in reports if not r.duplicate_ok) / len(bank), 4) if bank else 0,
        "reports": reports,
        "bank": bank,
        "chapter_distribution": by_chapter,
        "topic_distribution": by_topic,
        "concept_distribution": by_concept,
        "difficulty_distribution": by_diff,
        "answer_position_audit": pos_audit,
        "difficulty_audit": diff_audit,
        "ncert_page_level_capability": "NOT AVAILABLE",
        "ncert_verification_policy": {
            "aligned": True,
            "section_verified_gate": True,
            "page_verified_gate": False,
            "do_not_claim_page_level": True,
        },
        "rejected_reasons": {r.pilot_qid: r.reasons for r in rejected},
        "held_reasons": {r.pilot_qid: r.reasons for r in held},
        "quality_over_quantity": True,
        "max_candidates": MAX_CANDIDATES,
    }


def normalize_stem_public(stem: str) -> str:
    return normalize_stem(stem)
