"""Agreement and quality metrics for human-gold gate."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.modules.cms.mcq.p2_3.human_gold_gate.human_review import human_review_status
from app.modules.cms.mcq.p2_3.human_gold_gate.normalization import (
    ai_failed,
    ai_passed,
    difficulty_within_one,
    normalize_ai_verdict,
    normalize_answer_key,
    normalize_difficulty,
    normalize_human_overall,
    normalize_ncert,
    normalize_neet,
)
from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import GoldLabel
from app.modules.cms.mcq.p2_3.human_gold_gate.taxonomy import classify_disagreement, recommended_pipeline_fix

LABELS: list[GoldLabel] = ["ACCEPT", "MINOR", "MAJOR", "REJECT", "INCONCLUSIVE"]


def eligible_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if human_review_status(r) == "HUMAN_REVIEW_COMPLETE"]


def compute_metrics(
    rows: list[dict[str, Any]],
    preaudit_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    complete = eligible_rows(rows)
    stats = _completion_block(rows)

    if not complete:
        return {
            **stats,
            "eligible_human_reviewed_questions": 0,
            "overall_agreement_rate": None,
            "answer_key_agreement_rate": None,
            "answer_key_disagreement_count": None,
            "false_pass_count": None,
            "false_pass_rate": None,
            "false_pass_denominator": None,
            "false_reject_count": None,
            "false_reject_rate": None,
            "false_reject_denominator": None,
            "human_outcomes": _empty_human_outcomes(),
            "confusion_matrix": _empty_confusion_matrix(),
            "subject_breakdown": {},
            "chapter_breakdown": {},
            "provider_breakdown": {},
            "difficulty_analysis": {},
            "neet_analysis": {},
            "ncert_analysis": {},
            "gate_results": [],
            "false_passes": [],
            "failure_records": [],
        }

    overall_agree = 0
    answer_agree = 0
    answer_disagree = 0
    false_pass = 0
    false_reject = 0
    ai_pass_denominator = 0
    ai_fail_denominator = 0
    confusion = {ai: Counter() for ai in LABELS}
    human_counts = Counter()
    subject_data: dict[str, dict[str, Any]] = {}
    chapter_data: dict[str, dict[str, Any]] = {}
    provider_data: dict[str, dict[str, Any]] = {}
    diff_exact = 0
    diff_within = 0
    diff_total = 0
    neet_agree = 0
    neet_total = 0
    neet_ai_ok_human_bad = 0
    ncert_agree = 0
    ncert_total = 0
    gate_results: list[dict[str, Any]] = []
    false_passes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for row in complete:
        qid = row["question_id"]
        pa = preaudit_by_id.get(qid) or {}
        ai_label = normalize_ai_verdict(row)
        human_label = normalize_human_overall(row)

        if human_label != "INVALID_HUMAN_LABEL":
            human_counts[human_label] += 1

        if ai_label != "INVALID_HUMAN_LABEL" and human_label != "INVALID_HUMAN_LABEL":
            if ai_label == human_label:
                overall_agree += 1
            confusion[ai_label][human_label] += 1

        prop = normalize_answer_key(row.get("proposed_answer"))
        human_ans = normalize_answer_key(row.get("human_answer"))
        if prop and human_ans:
            if prop == human_ans:
                answer_agree += 1
            else:
                answer_disagree += 1

        if ai_passed(row):
            ai_pass_denominator += 1
            if human_label in ("MAJOR", "REJECT"):
                false_pass += 1
                failure = classify_disagreement(row, pa)
                rec = _false_pass_record(row, pa, failure)
                false_passes.append(rec)

        if ai_failed(row):
            ai_fail_denominator += 1
            if human_label == "ACCEPT":
                false_reject += 1

        if ai_label != human_label and human_label != "INVALID_HUMAN_LABEL":
            failure = classify_disagreement(row, pa)
            failures.append(
                {
                    "question_id": qid,
                    "subject": row.get("subject"),
                    "chapter": row.get("chapter"),
                    **failure,
                    "ai_verdict": ai_label,
                    "human_verdict": human_label,
                }
            )

        _accum_subject(subject_data, row, ai_label, human_label, prop, human_ans, ai_passed(row), human_label == "ACCEPT")
        _accum_chapter(chapter_data, row, ai_label, human_label, prop, human_ans)
        provider = row.get("r1_validator_provider") or row.get("provider") or "unknown"
        _accum_provider(provider_data, provider, row, ai_label, human_label, prop, human_ans, ai_passed(row), human_label == "ACCEPT")

        ai_diff = normalize_difficulty(row.get("difficulty"))
        human_diff = normalize_difficulty(row.get("human_difficulty"))
        if ai_diff and human_diff:
            diff_total += 1
            if ai_diff == human_diff:
                diff_exact += 1
            if difficulty_within_one(ai_diff, human_diff):
                diff_within += 1

        ai_neet = normalize_neet(pa.get("preaudit_neet_suitability"))
        human_neet = normalize_neet(row.get("human_neet_suitability"))
        if ai_neet and human_neet:
            neet_total += 1
            if ai_neet == human_neet:
                neet_agree += 1
            if ai_neet in ("SUITABLE", "SUITABLE_WITH_MINOR_EDIT") and human_neet == "UNSUITABLE":
                neet_ai_ok_human_bad += 1

        ai_ncert = normalize_ncert(pa.get("preaudit_ncert_support"))
        human_ncert = normalize_ncert(row.get("human_ncert_support"))
        if ai_ncert and human_ncert:
            ncert_total += 1
            if ai_ncert == human_ncert:
                ncert_agree += 1

        gate_results.append(
            {
                "question_id": qid,
                "human_review_status": "HUMAN_REVIEW_COMPLETE",
                "ai_verdict_normalized": ai_label,
                "human_overall_normalized": human_label,
                "proposed_answer_normalized": prop,
                "human_answer_normalized": human_ans,
                "overall_agreement": ai_label == human_label,
                "answer_key_agreement": prop == human_ans if prop and human_ans else None,
                "is_false_pass": ai_passed(row) and human_label in ("MAJOR", "REJECT"),
                "is_false_reject": ai_failed(row) and human_label == "ACCEPT",
                "preaudit_priority": row.get("preaudit_priority"),
            }
        )

    eligible = len([r for r in complete if normalize_human_overall(r) != "INVALID_HUMAN_LABEL"])
    eligible_ai = len(
        [
            r
            for r in complete
            if normalize_human_overall(r) != "INVALID_HUMAN_LABEL" and normalize_ai_verdict(r) != "INVALID_HUMAN_LABEL"
        ]
    )

    return {
        **stats,
        "eligible_human_reviewed_questions": eligible,
        "overall_agreement_rate": round(overall_agree / eligible_ai, 4) if eligible_ai else None,
        "answer_key_agreement_rate": round(answer_agree / (answer_agree + answer_disagree), 4)
        if (answer_agree + answer_disagree)
        else None,
        "answer_key_disagreement_count": answer_disagree,
        "false_pass_count": false_pass,
        "false_pass_rate": round(false_pass / ai_pass_denominator, 4) if ai_pass_denominator else None,
        "false_pass_denominator": ai_pass_denominator,
        "false_reject_count": false_reject,
        "false_reject_rate": round(false_reject / ai_fail_denominator, 4) if ai_fail_denominator else None,
        "false_reject_denominator": ai_fail_denominator,
        "human_outcomes": dict(human_counts),
        "confusion_matrix": {ai: dict(confusion[ai]) for ai in LABELS},
        "subject_breakdown": subject_data,
        "chapter_breakdown": chapter_data,
        "provider_breakdown": provider_data,
        "difficulty_analysis": {
            "difficulty_exact_agreement": diff_exact,
            "difficulty_within_one_level": diff_within,
            "difficulty_compared": diff_total,
            "difficulty_exact_rate": round(diff_exact / diff_total, 4) if diff_total else None,
            "difficulty_within_one_rate": round(diff_within / diff_total, 4) if diff_total else None,
        },
        "neet_analysis": {
            "neet_suitability_agreement": round(neet_agree / neet_total, 4) if neet_total else None,
            "neet_compared": neet_total,
            "ai_suitable_human_unsuitable": neet_ai_ok_human_bad,
        },
        "ncert_analysis": {
            "ncert_support_agreement": round(ncert_agree / ncert_total, 4) if ncert_total else None,
            "ncert_compared": ncert_total,
        },
        "human_verified_acceptance": {
            "strict_acceptance_rate": round(human_counts.get("ACCEPT", 0) / len(complete), 4),
            "accept_or_minor_rate": round(
                (human_counts.get("ACCEPT", 0) + human_counts.get("MINOR", 0)) / len(complete), 4
            ),
        },
        "gate_results": gate_results,
        "false_passes": [_enrich_false_pass(fp, preaudit_by_id) for fp in false_passes],
        "failure_records": failures,
    }


def _completion_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from app.modules.cms.mcq.p2_3.human_gold_gate.human_review import completion_stats

    s = completion_stats(rows)
    return {
        "sample_size": len(rows),
        "human_reviewed": s["reviewed_count"],
        "pending": s["pending_count"],
        "partial": s["partial_count"],
        "completion_rate": s["completion_rate"],
    }


def _empty_human_outcomes() -> dict[str, int]:
    return {k: 0 for k in LABELS}


def _empty_confusion_matrix() -> dict[str, dict[str, int]]:
    return {ai: {h: 0 for h in LABELS} for ai in LABELS}


def _false_pass_record(row: dict[str, Any], pa: dict[str, Any], failure: dict[str, str]) -> dict[str, Any]:
    return {
        "question_id": row["question_id"],
        "subject": row.get("subject"),
        "chapter": row.get("chapter"),
        "ai_verdict": normalize_ai_verdict(row),
        "human_verdict": normalize_human_overall(row),
        "proposed_answer": row.get("proposed_answer"),
        "human_answer": row.get("human_answer"),
        "preaudit_priority": row.get("preaudit_priority"),
        **failure,
        "recommended_pipeline_fix": recommended_pipeline_fix(row, failure),
    }


def _enrich_false_pass(fp: dict[str, Any], preaudit_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return fp


def _accum_subject(
    data: dict[str, dict[str, Any]],
    row: dict[str, Any],
    ai: GoldLabel,
    human: GoldLabel,
    prop: str | None,
    human_ans: str | None,
    ai_pass: bool,
    human_accept: bool,
) -> None:
    subj = (row.get("subject") or "UNKNOWN").upper()
    bucket = data.setdefault(
        subj,
        {
            "reviewed": 0,
            "agreement": 0,
            "agreement_eligible": 0,
            "answer_agree": 0,
            "answer_compared": 0,
            "false_pass": 0,
            "ai_pass_reviewed": 0,
            "false_reject": 0,
            "ai_fail_reviewed": 0,
            "human_accept": 0,
            "human_minor": 0,
            "human_major": 0,
            "human_reject": 0,
        },
    )
    bucket["reviewed"] += 1
    if human != "INVALID_HUMAN_LABEL" and ai != "INVALID_HUMAN_LABEL":
        bucket["agreement_eligible"] += 1
        if ai == human:
            bucket["agreement"] += 1
    if prop and human_ans:
        bucket["answer_compared"] += 1
        if prop == human_ans:
            bucket["answer_agree"] += 1
    if ai_pass:
        bucket["ai_pass_reviewed"] += 1
        if human in ("MAJOR", "REJECT"):
            bucket["false_pass"] += 1
    if ai_failed(row):
        bucket["ai_fail_reviewed"] += 1
        if human == "ACCEPT":
            bucket["false_reject"] += 1
    if human == "ACCEPT":
        bucket["human_accept"] += 1
    elif human == "MINOR":
        bucket["human_minor"] += 1
    elif human == "MAJOR":
        bucket["human_major"] += 1
    elif human == "REJECT":
        bucket["human_reject"] += 1


def _accum_chapter(
    data: dict[str, dict[str, Any]],
    row: dict[str, Any],
    ai: GoldLabel,
    human: GoldLabel,
    prop: str | None,
    human_ans: str | None,
) -> None:
    key = f"{row.get('subject')}:{row.get('chapter')}"
    bucket = data.setdefault(key, {"reviewed": 0, "agreement": 0, "agreement_eligible": 0, "low_sample": False})
    bucket["reviewed"] += 1
    if human != "INVALID_HUMAN_LABEL" and ai != "INVALID_HUMAN_LABEL":
        bucket["agreement_eligible"] += 1
        if ai == human:
            bucket["agreement"] += 1
    if bucket["reviewed"] < 5:
        bucket["low_sample"] = True
        bucket["agreement_rate"] = "LOW_SAMPLE_SIZE"
    elif bucket["agreement_eligible"]:
        bucket["agreement_rate"] = round(bucket["agreement"] / bucket["agreement_eligible"], 4)


def _accum_provider(
    data: dict[str, dict[str, Any]],
    provider: str,
    row: dict[str, Any],
    ai: GoldLabel,
    human: GoldLabel,
    prop: str | None,
    human_ans: str | None,
    ai_pass: bool,
    human_accept: bool,
) -> None:
    bucket = data.setdefault(
        provider,
        {
            "reviewed": 0,
            "agreement": 0,
            "agreement_eligible": 0,
            "answer_agree": 0,
            "answer_compared": 0,
            "false_pass": 0,
            "ai_pass_reviewed": 0,
            "false_reject": 0,
            "ai_fail_reviewed": 0,
            "human_accept": 0,
        },
    )
    bucket["reviewed"] += 1
    if human != "INVALID_HUMAN_LABEL" and ai != "INVALID_HUMAN_LABEL":
        bucket["agreement_eligible"] += 1
        if ai == human:
            bucket["agreement"] += 1
    if prop and human_ans:
        bucket["answer_compared"] += 1
        if prop == human_ans:
            bucket["answer_agree"] += 1
    if ai_pass:
        bucket["ai_pass_reviewed"] += 1
        if human in ("MAJOR", "REJECT"):
            bucket["false_pass"] += 1
    if ai_failed(row):
        bucket["ai_fail_reviewed"] += 1
        if human == "ACCEPT":
            bucket["false_reject"] += 1
    if human_accept:
        bucket["human_accept"] += 1
