"""Deterministic GREEN/YELLOW/RED gate decision engine."""

from __future__ import annotations

from typing import Any

from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import GateThresholds, TenKRecommendation


def decide_gate(
    metrics: dict[str, Any],
    *,
    thresholds: GateThresholds,
    integrity_errors: list[str],
) -> dict[str, Any]:
    reviewed = metrics.get("human_reviewed") or 0
    sample = metrics.get("sample_size") or 100

    if integrity_errors:
        return _result(
            gate_status="RED",
            gate_reason="DATA_INTEGRITY_FAILURE",
            ten_k="DO_NOT_PROCEED",
            integrity_errors=integrity_errors,
        )

    if reviewed < thresholds.human_gold_min_reviewed:
        return _result(
            gate_status="YELLOW",
            gate_reason="HUMAN_REVIEW_INCOMPLETE",
            ten_k="DO_NOT_PROCEED",
            reviewed=reviewed,
            sample=sample,
        )

    if metrics.get("partial", 0) > 0:
        return _result(
            gate_status="YELLOW",
            gate_reason="HUMAN_REVIEW_PARTIAL_RECORDS",
            ten_k="DO_NOT_PROCEED",
        )

    if thresholds.thresholds_pending():
        return _result(
            gate_status="YELLOW",
            gate_reason="THRESHOLDS_PENDING_POLICY",
            ten_k="REMEDIATE_FIRST",
            note="Human review complete; quality thresholds not configured for definitive GREEN",
        )

    false_pass = metrics.get("false_pass_count") or 0
    critical_fp = sum(
        1
        for fp in metrics.get("false_passes") or []
        if fp.get("failure_severity") == "CRITICAL"
    )

    if critical_fp > thresholds.max_critical_false_pass_green:
        return _result(
            gate_status="RED",
            gate_reason="CRITICAL_FALSE_PASS",
            ten_k="DO_NOT_PROCEED",
            false_pass=false_pass,
            critical_false_pass=critical_fp,
        )

    fp_rate = metrics.get("false_pass_rate")
    ak_rate = metrics.get("answer_key_agreement_rate")
    overall_rate = metrics.get("overall_agreement_rate")

    if fp_rate is not None and fp_rate > (thresholds.max_false_pass_rate_green or 1.0):
        return _result(
            gate_status="YELLOW",
            gate_reason="FALSE_PASS_RATE_EXCEEDED",
            ten_k="REMEDIATE_FIRST",
            false_pass_rate=fp_rate,
        )

    if ak_rate is not None and ak_rate < (thresholds.min_answer_key_agreement_green or 0.0):
        return _result(
            gate_status="YELLOW",
            gate_reason="ANSWER_KEY_AGREEMENT_BELOW_THRESHOLD",
            ten_k="REMEDIATE_FIRST",
            answer_key_agreement_rate=ak_rate,
        )

    if overall_rate is not None and overall_rate < (thresholds.min_overall_agreement_green or 0.0):
        return _result(
            gate_status="YELLOW",
            gate_reason="OVERALL_AGREEMENT_BELOW_THRESHOLD",
            ten_k="REMEDIATE_FIRST",
            overall_agreement_rate=overall_rate,
        )

    return _result(
        gate_status="GREEN",
        gate_reason="HUMAN_GOLD_THRESHOLDS_MET",
        ten_k="PROCEED",
    )


def _result(
    *,
    gate_status: str,
    gate_reason: str,
    ten_k: TenKRecommendation,
    **extra: Any,
) -> dict[str, Any]:
    out = {
        "gate_status": gate_status,
        "gate_reason": gate_reason,
        "ten_k_recommendation": ten_k,
    }
    out.update(extra)
    return out
