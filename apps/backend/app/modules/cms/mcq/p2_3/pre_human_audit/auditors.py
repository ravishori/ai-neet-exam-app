"""Deterministic auditors for pre-human gold sample screening."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

import fitz

from app.modules.cms.mcq.p2_3.duplicates import near_duplicate
from app.modules.cms.mcq.p2_3.pre_human_audit.numerical import audit_numerical
from app.modules.cms.mcq.p2_3.pre_human_audit.schemas import empty_audit_record
from app.modules.cms.services.factory_candidate_validation import normalize_stem, stem_hash

_AR_PATTERNS = (
    re.compile(r"assertion\s*[aA]?\s*:?\s*(.+?)(?:reason\s*[rR]|$)", re.I | re.S),
    re.compile(r"reason\s*[rR]?\s*:?\s*(.+?)(?:$)", re.I | re.S),
)
_NEET_AR_OPTIONS = {
    "A": "both true and reason explains",
    "B": "both true but reason does not",
    "C": "assertion true reason false",
    "D": "assertion false reason true",
}


def _options_dict(row: dict[str, Any]) -> dict[str, str]:
    return {
        "A": (row.get("option_A") or "").strip(),
        "B": (row.get("option_B") or "").strip(),
        "C": (row.get("option_C") or "").strip(),
        "D": (row.get("option_D") or "").strip(),
    }


def audit_options(row: dict[str, Any]) -> dict[str, Any]:
    opts = _options_dict(row)
    texts = list(opts.values())
    issues: list[str] = []
    severity = "NONE"
    quality: str = "GOOD"

    if any(not t for t in texts):
        issues.append("empty_option")
        quality, severity = "BAD", "CRITICAL"
    elif len(set(texts)) < 4:
        issues.append("duplicate_options")
        quality, severity = "BAD", "CRITICAL"
    else:
        for _, a in enumerate("ABCD"):
            for b in "ABCD":
                if a >= b:
                    continue
                if near_duplicate(opts[a], opts[b], threshold=0.88):
                    issues.append("near_duplicate_options")
                    quality, severity = "WEAK", "MAJOR"
        lengths = [len(t) for t in texts]
        if max(lengths) > 2.5 * max(min(lengths), 1):
            issues.append("length_clue")
            if quality == "GOOD":
                quality, severity = "ACCEPTABLE", "MINOR"
        if any(len(t) < 2 for t in texts):
            issues.append("trivial_distractor")
            quality, severity = "WEAK", "MAJOR"

    proposed = (row.get("proposed_answer") or "").upper()
    if proposed not in opts or not opts.get(proposed):
        issues.append("proposed_answer_missing_option")
        quality, severity = "BAD", "CRITICAL"

    return {
        "preaudit_option_quality": quality,
        "preaudit_option_issue": "; ".join(issues),
        "preaudit_option_severity": severity,
    }


def audit_stem(row: dict[str, Any]) -> dict[str, Any]:
    stem = (row.get("question") or "").strip()
    issues: list[str] = []
    severity = "NONE"
    if len(stem) < 20:
        issues.append("stem_too_short")
        severity = "MAJOR"
    if stem.count("?") > 2:
        issues.append("multiple_questions")
        severity = "MAJOR"
    if re.search(r"\b(which of the following)\b.*\b(which of the following)\b", stem, re.I):
        issues.append("redundant_wording")
        severity = "MINOR"
    if re.search(r"\bundefined\b|\bnot (?:given|provided)\b", stem, re.I):
        issues.append("missing_conditions")
        severity = "MAJOR"
    if len(stem) > 1200:
        issues.append("excessively_long_stem")
        severity = "MINOR"
    return {
        "preaudit_stem_issue": "; ".join(issues),
        "preaudit_stem_severity": severity,
    }


def audit_question_type(row: dict[str, Any]) -> dict[str, Any]:
    declared = (row.get("question_type") or "").lower()
    stem = (row.get("question") or "").lower()
    detected = "factual"
    if "assertion" in stem and "reason" in stem:
        detected = "assertion_reasoning"
    elif "match" in stem or "column i" in stem:
        detected = "match_relationship"
    elif "statement" in stem and ("statement i" in stem or "statement 1" in stem):
        detected = "statement_based"
    elif any(k in stem for k in ("calculate", "what is the value", "round off", "numerical")):
        detected = "numerical"
    elif any(k in stem for k in ("application", "wire carries", "particle moving")):
        detected = "application"
    elif any(k in stem for k in ("concept", "which of the following statements", "consider the following")):
        detected = "conceptual"

    if declared == detected:
        return {"preaudit_question_type_check": "TYPE_CORRECT"}
    if declared in ("conceptual", "factual") and detected in ("conceptual", "factual"):
        return {"preaudit_question_type_check": "TYPE_CORRECT"}
    if declared == "numerical" and detected != "numerical" and not _extract_numbers(stem):
        return {"preaudit_question_type_check": "TYPE_MISMATCH"}
    if declared != detected:
        return {"preaudit_question_type_check": "TYPE_MISMATCH"}
    return {"preaudit_question_type_check": "QUESTION_TYPE_UNCLEAR"}


def _extract_numbers(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?\d*\.?\d+", text)]


def audit_assertion_reason(row: dict[str, Any]) -> dict[str, Any]:
    qtype = (row.get("question_type") or "").lower()
    stem = row.get("question") or ""
    if qtype != "assertion_reasoning" and "assertion" not in stem.lower():
        return {"preaudit_assertion_reason_check": ""}

    proposed = (row.get("proposed_answer") or "").upper()
    opts = _options_dict(row)
    opt_text = (opts.get(proposed) or "").lower()

    # Heuristic: if proposed is A, check option text claims reason explains assertion
    explains = any(w in opt_text for w in ("explains", "because", "therefore", "accounts for"))
    both_true = "both" in opt_text and "true" in opt_text
    reason_not_explain = "does not explain" in opt_text or "not explain" in opt_text

    # Position vector / displacement classic trap
    if "position vector" in stem.lower() and "displacement" in stem.lower() and proposed == "A":
        return {
            "preaudit_assertion_reason_check": (
                "assertion_true=LIKELY;reason_true=LIKELY;reason_explains_assertion=FALSE;"
                "proposed_option_correct=QUESTIONABLE"
            ),
            "preaudit_answer_check": "INCONCLUSIVE",
            "preaudit_answer_confidence": 0.75,
            "preaudit_scientific_issue": "Reason may not explain Assertion (displacement vs position vector)",
            "preaudit_scientific_severity": "MAJOR",
        }

    if proposed == "A" and both_true and not explains:
        return {
            "preaudit_assertion_reason_check": (
                "assertion_true=UNKNOWN;reason_true=UNKNOWN;reason_explains_assertion=FALSE;"
                "proposed_option_correct=QUESTIONABLE"
            ),
            "preaudit_answer_check": "INCONCLUSIVE",
            "preaudit_answer_confidence": 0.6,
        }

    if reason_not_explain and proposed == "A":
        return {
            "preaudit_assertion_reason_check": (
                "assertion_true=UNKNOWN;reason_true=UNKNOWN;reason_explains_assertion=FALSE;"
                "proposed_option_correct=FALSE"
            ),
            "preaudit_answer_check": "WRONG",
            "preaudit_answer_confidence": 0.8,
        }

    return {
        "preaudit_assertion_reason_check": (
            f"assertion_true=UNVERIFIED;reason_true=UNVERIFIED;"
            f"reason_explains_assertion=UNVERIFIED;proposed_option={proposed}"
        ),
    }


def load_ncert_excerpt(source_file: str, source_page: int, study_root: Path) -> tuple[str, bool]:
    return _load_ncert_excerpt_cached(source_file, source_page, str(study_root.resolve()))


@lru_cache(maxsize=512)
def _load_ncert_excerpt_cached(source_file: str, source_page: int, study_root_str: str) -> tuple[str, bool]:
    if not source_file:
        return "", False
    from app.modules.ingestion.services.ncert_canonical_source import (
        NcertSourceError,
        assert_ncert_generation_root,
        validate_ncert_generation_source,
    )

    try:
        study_root = assert_ncert_generation_root(Path(study_root_str))
        validated = validate_ncert_generation_source(
            study_root / source_file.replace("\\", "/"),
            root=study_root,
        )
    except NcertSourceError:
        return "", False
    doc = fitz.open(validated.resolved_path)
    try:
        idx = max(0, int(source_page) - 1)
        if idx >= doc.page_count:
            return "", False
        text = (doc.load_page(idx).get_text("text") or "").strip()
        return text[:6000], len(text) >= 80
    finally:
        doc.close()


def audit_ncert(row: dict[str, Any], *, study_root: Path) -> dict[str, Any]:
    source = row.get("NCERT_source") or row.get("_source_locator") or ""
    page = int(row.get("_source_page") or 1)
    excerpt, available = load_ncert_excerpt(source, page, study_root)

    if not source:
        return {
            "preaudit_ncert_support": "NOT_VERIFIABLE",
            "preaudit_ncert_issue": "missing_source_reference",
        }
    if not available:
        pdf = study_root / source.replace("\\", "/")
        if not pdf.exists():
            return {
                "preaudit_ncert_support": "INCORRECT_CITATION",
                "preaudit_ncert_issue": "source_file_not_found",
            }
        return {
            "preaudit_ncert_support": "NOT_VERIFIABLE",
            "preaudit_ncert_issue": "excerpt_unavailable_or_page_out_of_range",
        }

    stem = normalize_stem(row.get("question") or "")
    words = [w for w in stem.split() if len(w) > 5][:12]
    hits = sum(1 for w in words if w in normalize_stem(excerpt))
    ratio = hits / max(len(words), 1)

    if ratio >= 0.45:
        support = "DIRECT"
    elif ratio >= 0.25:
        support = "SUPPORTED_INFERENCE"
    elif ratio >= 0.12:
        support = "WEAK_SUPPORT"
    else:
        support = "UNSUPPORTED"

    return {
        "preaudit_ncert_support": support,
        "preaudit_ncert_issue": "" if support in ("DIRECT", "SUPPORTED_INFERENCE") else "low_term_overlap_with_cited_page",
    }


def audit_duplicates(
    row: dict[str, Any],
    *,
    sample_stems: dict[str, str],
    corpus_stems: dict[str, str],
) -> dict[str, Any]:
    qid = row["question_id"]
    stem = row.get("question") or ""
    h = stem_hash(stem)

    for other_id, other_stem in sample_stems.items():
        if other_id == qid:
            continue
        if stem_hash(other_stem) == h:
            return {
                "preaudit_duplicate_status": "EXACT_DUPLICATE",
                "preaudit_duplicate_question_id": other_id,
                "preaudit_duplicate_similarity": 1.0,
            }
        sim = SequenceMatcher(None, normalize_stem(stem), normalize_stem(other_stem)).ratio()
        if sim >= 0.92:
            return {
                "preaudit_duplicate_status": "NEAR_DUPLICATE",
                "preaudit_duplicate_question_id": other_id,
                "preaudit_duplicate_similarity": round(sim, 4),
            }

    for other_id, other_stem in corpus_stems.items():
        if other_id == qid or other_id in sample_stems:
            continue
        if near_duplicate(stem, other_stem, threshold=0.92):
            sim = SequenceMatcher(None, normalize_stem(stem), normalize_stem(other_stem)).ratio()
            return {
                "preaudit_duplicate_status": "SEMANTIC_DUPLICATE",
                "preaudit_duplicate_question_id": other_id,
                "preaudit_duplicate_similarity": round(sim, 4),
            }
        sim = SequenceMatcher(None, normalize_stem(stem), normalize_stem(other_stem)).ratio()
        if sim >= 0.85:
            return {
                "preaudit_duplicate_status": "POSSIBLE_DUPLICATE",
                "preaudit_duplicate_question_id": other_id,
                "preaudit_duplicate_similarity": round(sim, 4),
            }

    return {
        "preaudit_duplicate_status": "UNIQUE",
        "preaudit_duplicate_question_id": "",
        "preaudit_duplicate_similarity": 0.0,
    }


def audit_neet_suitability(row: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    declared = (row.get("difficulty") or "MEDIUM").upper()
    stem = row.get("question") or ""
    est = declared if declared in ("EASY", "MEDIUM", "HARD") else "MEDIUM"
    if len(stem) < 40 and (row.get("question_type") or "") == "factual":
        est = "EASY"
    if "round off" in stem.lower() or "standard electrode" in stem.lower():
        est = "HARD" if declared == "HARD" else "MEDIUM"

    suitability = "SUITABLE"
    if audit.get("preaudit_question_type_check") == "TYPE_MISMATCH":
        suitability = "QUESTIONABLE"
    if audit.get("preaudit_ncert_support") in ("UNSUPPORTED", "INCORRECT_CITATION"):
        suitability = "QUESTIONABLE"
    if audit.get("preaudit_option_quality") == "BAD":
        suitability = "UNSUITABLE"
    if audit.get("preaudit_stem_severity") == "CRITICAL":
        suitability = "UNSUITABLE"
    if audit.get("preaudit_option_severity") == "MINOR" and suitability == "SUITABLE":
        suitability = "SUITABLE_WITH_MINOR_EDIT"

    return {
        "preaudit_neet_suitability": suitability,
        "preaudit_independent_difficulty": est,
    }


def score_priority_and_verdict(audit: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    action = "LIKELY_ACCEPT"
    priority = "LOW"
    verdict = "PREAUDIT_LIKELY_PASS"

    if audit.get("preaudit_answer_check") == "WRONG":
        reasons.append("proposed_answer_likely_wrong")
        priority, action = "CRITICAL", "HUMAN_REVIEW_ANSWER"
    elif audit.get("preaudit_answer_check") == "MULTIPLE_CORRECT":
        reasons.append("multiple_correct_risk")
        priority, action = "CRITICAL", "HUMAN_REVIEW_ANSWER"
    elif audit.get("preaudit_calculation_check") == "FAIL":
        reasons.append("calculation_mismatch")
        priority, action = "CRITICAL", "HUMAN_RECALCULATE"

    if audit.get("preaudit_duplicate_status") in ("EXACT_DUPLICATE", "NEAR_DUPLICATE"):
        reasons.append("duplicate_in_sample")
        priority, action = "CRITICAL", "HUMAN_REVIEW_DUPLICATE"

    if "proposed_option_correct=FALSE" in (audit.get("preaudit_assertion_reason_check") or ""):
        reasons.append("assertion_reason_key_questionable")
        priority, action = "CRITICAL", "HUMAN_REVIEW_ASSERTION_REASON"

    if audit.get("preaudit_ncert_support") in ("UNSUPPORTED", "INCORRECT_CITATION"):
        reasons.append("ncert_support_issue")
        if priority not in ("CRITICAL",):
            priority, action = "HIGH", "HUMAN_CHECK_NCERT"

    if audit.get("preaudit_stem_severity") in ("MAJOR", "CRITICAL"):
        reasons.append("stem_wording_issue")
        if priority == "LOW":
            priority, action = "HIGH", "HUMAN_REVIEW_WORDING"

    if audit.get("preaudit_option_quality") in ("WEAK", "BAD"):
        reasons.append("distractor_quality_issue")
        if priority in ("LOW", "MEDIUM"):
            priority, action = "HIGH", "HUMAN_REVIEW_OPTIONS"

    if audit.get("preaudit_question_type_check") == "TYPE_MISMATCH":
        reasons.append("question_type_mismatch")
        if priority == "LOW":
            priority = "MEDIUM"

    if audit.get("preaudit_neet_suitability") in ("QUESTIONABLE", "UNSUITABLE"):
        reasons.append("neet_suitability_concern")
        if priority == "LOW":
            priority = "MEDIUM"

    if audit.get("preaudit_scientific_severity") in ("MAJOR", "CRITICAL"):
        reasons.append("scientific_content_concern")
        if priority not in ("CRITICAL",):
            priority, action = "HIGH", "HUMAN_VERIFY"

    if audit.get("preaudit_answer_check") == "INCONCLUSIVE" and priority == "LOW":
        reasons.append("answer_not_fully_verified_automatically")
        priority, action = "MEDIUM", "HUMAN_VERIFY"

    if priority == "CRITICAL":
        verdict = "PREAUDIT_FLAGGED"
    elif priority in ("HIGH", "MEDIUM"):
        verdict = "PREAUDIT_REVIEW"
    elif audit.get("preaudit_answer_check") == "INCONCLUSIVE":
        verdict = "PREAUDIT_REVIEW"
    else:
        verdict = "PREAUDIT_LIKELY_PASS"

    if priority == "CRITICAL" and action == "LIKELY_ACCEPT":
        action = "REJECT_AFTER_HUMAN_CONFIRMATION"

    confidence = float(audit.get("preaudit_answer_confidence") or 0.0)
    if verdict == "PREAUDIT_LIKELY_PASS" and confidence < 0.5:
        verdict = "PREAUDIT_REVIEW"

    return {
        "preaudit_priority": priority,
        "preaudit_verdict": verdict,
        "preaudit_reason": "; ".join(reasons) if reasons else "no_obvious_defect_in_automated_screening",
        "preaudit_recommended_action": action,
        "preaudit_answer_confidence": confidence,
    }


def audit_one_row(
    row: dict[str, Any],
    *,
    sample_stems: dict[str, str],
    corpus_stems: dict[str, str],
    study_root: Path,
) -> dict[str, Any]:
    audit = empty_audit_record(row)
    audit.update(audit_options(row))
    audit.update(audit_stem(row))
    audit.update(audit_question_type(row))
    audit.update(audit_numerical(row))
    audit.update(audit_assertion_reason(row))
    audit.update(audit_ncert(row, study_root=study_root))
    audit.update(audit_duplicates(row, sample_stems=sample_stems, corpus_stems=corpus_stems))
    audit.update(audit_neet_suitability(row, audit))
    audit.update(score_priority_and_verdict(audit))
    return audit
