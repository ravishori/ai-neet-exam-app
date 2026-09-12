"""P2.2 independent source validation."""

from __future__ import annotations

from typing import Any

from app.modules.cms.pyq.p2_2.schemas import AIRecoveryOutput, SourceFidelityGrade, ValidationVerdict


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _token_overlap(a: str, b: str) -> float:
    ta = set(_norm(a).split())
    tb = set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def validate_against_source(
    output: AIRecoveryOutput,
    evidence: dict[str, Any],
    *,
    original: dict[str, Any],
) -> tuple[ValidationVerdict, SourceFidelityGrade, list[str]]:
    reasons: list[str] = []
    if output.status == "NOT_RECOVERABLE":
        return "PASS", "INCONCLUSIVE", ["not_recoverable_expected"]
    if output.status == "INCONCLUSIVE":
        return "INCONCLUSIVE", "INCONCLUSIVE", output.uncertainties or ["model_inconclusive"]

    ocr = evidence.get("ocr_text") or ""
    if not ocr.strip():
        reasons.append("no_ocr_to_validate")
        return "INCONCLUSIVE", "INCONCLUSIVE", reasons

    if output.foreign_text_detected:
        return "FAIL", "E", ["foreign_text_detected"]

    stem_overlap = _token_overlap(output.stem, ocr)
    if output.stem.strip() and stem_overlap < 0.15 and output.stem.strip() != (original.get("stem") or "").strip():
        reasons.append(f"stem_not_in_ocr_overlap={stem_overlap:.2f}")
        return "FAIL", "D", reasons

    invented: list[str] = []
    for i in range(1, 5):
        opt = output.options.get(str(i), "")
        if not opt.strip():
            continue
        orig_key = f"option_{'abcd'[i - 1]}"
        if _token_overlap(opt, ocr) < 0.1 and opt.strip() != (original.get(orig_key) or "").strip():
            invented.append(f"option_{i}")
    if invented:
        return "FAIL", "D", [f"options_not_supported_by_ocr:{invented}"]

    complete = all(output.options.get(str(i), "").strip() for i in range(1, 5))
    if complete and stem_overlap >= 0.4:
        return "PASS", "A", ["complete_recovery_supported_by_ocr"]
    if complete:
        return "PASS", "B", ["complete_recovery_moderate_ocr_support"]
    if output.changed_fields:
        return "INCONCLUSIVE", "C", ["partial_recovery"]
    return "INCONCLUSIVE", "C", reasons or ["partial_or_uncertain"]
