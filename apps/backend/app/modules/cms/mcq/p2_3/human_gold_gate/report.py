"""Markdown and artifact writers for human-gold gate."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.cms.mcq.p2_3.human_gold_gate.human_review import human_review_status
from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import GATE_VERSION


def build_summary_json(metrics: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    human = metrics.get("human_outcomes") or {}
    return {
        "gate": "P2.3_HUMAN_GOLD",
        "gate_version": GATE_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "sample_size": metrics.get("sample_size"),
        "human_reviewed": metrics.get("human_reviewed"),
        "pending": metrics.get("pending"),
        "partial": metrics.get("partial"),
        "completion_rate": metrics.get("completion_rate"),
        "overall_agreement_rate": metrics.get("overall_agreement_rate"),
        "answer_key_agreement_rate": metrics.get("answer_key_agreement_rate"),
        "false_pass_count": metrics.get("false_pass_count"),
        "false_pass_rate": metrics.get("false_pass_rate"),
        "false_pass_denominator": metrics.get("false_pass_denominator"),
        "false_reject_count": metrics.get("false_reject_count"),
        "false_reject_rate": metrics.get("false_reject_rate"),
        "false_reject_denominator": metrics.get("false_reject_denominator"),
        "human_accept_count": human.get("ACCEPT"),
        "human_minor_count": human.get("MINOR"),
        "human_major_count": human.get("MAJOR"),
        "human_reject_count": human.get("REJECT"),
        "human_inconclusive_count": human.get("INCONCLUSIVE"),
        "gate_status": gate.get("gate_status"),
        "gate_reason": gate.get("gate_reason"),
        "ten_k_recommendation": gate.get("ten_k_recommendation"),
        "production_db_writes": 0,
        "label_mapping": {
            "ai_to_gold": {
                "READY/PASS": "ACCEPT",
                "MINOR_REVISION": "MINOR",
                "MAJOR_REVISION": "MAJOR",
                "REJECT/FAIL": "REJECT",
                "INCONCLUSIVE": "INCONCLUSIVE",
            },
            "human_to_gold": {
                "ACCEPT/PASS/OK": "ACCEPT",
                "MINOR*": "MINOR",
                "MAJOR*": "MAJOR",
                "REJECT/FAIL": "REJECT",
                "INCONCLUSIVE/UNCLEAR": "INCONCLUSIVE",
            },
            "false_pass_definition": "AI ACCEPT (READY/PASS) AND human MAJOR or REJECT",
            "false_reject_definition": "AI MAJOR/REJECT AND human ACCEPT",
        },
    }


def write_gate_report_md(path: Path, summary: dict[str, Any], metrics: dict[str, Any], gate: dict[str, Any]) -> None:
    human = metrics.get("human_outcomes") or {}
    lines = [
        "# P2.3 Human-Gold Validation Gate",
        "",
        f"Generated: {summary.get('generated_at')}",
        "",
        "> Human review is the gold standard. AI validation does not overwrite human decisions.",
        "",
        "## Executive Verdict",
        f"**{gate.get('gate_status')}** — {gate.get('gate_reason')}",
        "",
        "## Review Completion",
        f"- Total sample: **{metrics.get('sample_size')}**",
        f"- Human reviewed: **{metrics.get('human_reviewed')}**",
        f"- Pending: **{metrics.get('pending')}**",
        f"- Partial: **{metrics.get('partial')}**",
        f"- Completion: **{metrics.get('completion_rate')}**",
        "",
        "## AI vs Human",
        f"- Overall agreement: **{_fmt(metrics.get('overall_agreement_rate'))}**",
        f"- Answer-key agreement: **{_fmt(metrics.get('answer_key_agreement_rate'))}**",
        f"- False-pass: **{_fmt(metrics.get('false_pass_count'))}** (rate {_fmt(metrics.get('false_pass_rate'))}, "
        f"denominator {metrics.get('false_pass_denominator')})",
        f"- False-reject: **{_fmt(metrics.get('false_reject_count'))}** (rate {_fmt(metrics.get('false_reject_rate'))}, "
        f"denominator {metrics.get('false_reject_denominator')})",
        "",
        "## Human Outcomes",
        f"- ACCEPT: **{human.get('ACCEPT', 0)}**",
        f"- MINOR: **{human.get('MINOR', 0)}**",
        f"- MAJOR: **{human.get('MAJOR', 0)}**",
        f"- REJECT: **{human.get('REJECT', 0)}**",
        f"- INCONCLUSIVE: **{human.get('INCONCLUSIVE', 0)}**",
        "",
    ]
    ncert = metrics.get("ncert_analysis") or {}
    lines.extend(
        [
            "## NCERT",
            f"- NCERT support agreement: **{_fmt(ncert.get('ncert_support_agreement'))}**",
            f"- Compared: **{ncert.get('ncert_compared')}**",
            "",
            "## Question Quality",
            f"- Ambiguous (from failure taxonomy): **{_count_category(metrics, 'AMBIGUOUS_STEM')}**",
            f"- Bad distractors: **{_count_category(metrics, 'BAD_DISTRACTOR')}**",
            f"- Wrong answers: **{_count_category(metrics, 'WRONG_ANSWER')}**",
            f"- Calculation errors: **{_count_category(metrics, 'CALCULATION_ERROR')}**",
            f"- Assertion/Reason errors: **{_count_category(metrics, 'ASSERTION_REASON_ERROR')}**",
            f"- Duplicate risks: **{_count_category(metrics, 'DUPLICATE')}**",
            f"- Question-type issues: **{_count_category(metrics, 'QUESTION_TYPE_ERROR')}**",
            f"- NEET suitability issues: **{_count_category(metrics, 'NEET_SUITABILITY_ERROR')}**",
            "",
            "## Subject Breakdown",
            "| Subject | Reviewed | Agreement | Answer Agreement | False Pass | Human Accept |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for subj, data in sorted((metrics.get("subject_breakdown") or {}).items()):
        agr = (
            round(data["agreement"] / data["agreement_eligible"], 4)
            if data.get("agreement_eligible")
            else "LOW_SAMPLE_SIZE"
        )
        ans = (
            round(data["answer_agree"] / data["answer_compared"], 4)
            if data.get("answer_compared")
            else "—"
        )
        lines.append(
            f"| {subj} | {data.get('reviewed')} | {agr} | {ans} | {data.get('false_pass')} | {data.get('human_accept')} |"
        )

    lines.extend(["", "## Provider Breakdown", "| Provider | Reviewed | Agreement | False Pass | Human Accept |", "| --- | --- | --- | --- | --- |"])
    for prov, data in sorted((metrics.get("provider_breakdown") or {}).items()):
        agr = (
            round(data["agreement"] / data["agreement_eligible"], 4)
            if data.get("agreement_eligible")
            else "—"
        )
        lines.append(
            f"| {prov} | {data.get('reviewed')} | {agr} | {data.get('false_pass')} | {data.get('human_accept')} |"
        )

    lines.extend(["", "## Failure Taxonomy", "| Failure | Count | Critical | Major | Minor |", "| --- | --- | --- | --- | --- |"])
    taxonomy = _taxonomy_table(metrics.get("failure_records") or [])
    for cat, counts in sorted(taxonomy.items()):
        lines.append(f"| {cat} | {counts['total']} | {counts['CRITICAL']} | {counts['MAJOR']} | {counts['MINOR']} |")

    lines.extend(["", "## False-Pass Questions"])
    for fp in metrics.get("false_passes") or []:
        lines.append(f"- `{fp.get('question_id')}` — {fp.get('failure_category')} ({fp.get('failure_severity')})")

    incomplete = [r for r in metrics.get("_review_rows") or [] if human_review_status(r) != "HUMAN_REVIEW_COMPLETE"]
    if incomplete:
        lines.extend(["", "## Human Review Queue (incomplete)"])
        for row in incomplete[:50]:
            lines.append(f"- `{row.get('question_id')}` — {human_review_status(row)} — priority {row.get('preaudit_priority')}")

    lines.extend(
        [
            "",
            "## Pipeline Recommendations",
            _pipeline_recommendations(metrics),
            "",
            "## 10K Recommendation",
            f"**{gate.get('ten_k_recommendation')}**",
            "",
            f"Gate note: {gate.get('gate_reason')}",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(
    *,
    out_dir: Path,
    metrics: dict[str, Any],
    summary: dict[str, Any],
    gate: dict[str, Any],
    docs_dir: Path,
) -> dict[str, str]:
    paths = {
        "gate_results_jsonl": out_dir / "human_gold_gate_results.jsonl",
        "gate_summary_json": out_dir / "human_gold_gate_summary.json",
        "failure_taxonomy_csv": out_dir / "human_gold_failure_taxonomy.csv",
        "false_passes_csv": out_dir / "human_gold_false_passes.csv",
        "gate_report_md": out_dir / "human_gold_gate_report.md",
    }

    with paths["gate_results_jsonl"].open("w", encoding="utf-8") as fh:
        for rec in metrics.get("gate_results") or []:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    full_summary = {**summary, **gate, "metrics_snapshot": _public_metrics(metrics)}
    paths["gate_summary_json"].write_text(json.dumps(full_summary, indent=2), encoding="utf-8")

    _write_csv(
        paths["failure_taxonomy_csv"],
        metrics.get("failure_records") or [],
        [
            "question_id",
            "subject",
            "chapter",
            "ai_verdict",
            "human_verdict",
            "failure_category",
            "failure_severity",
            "failure_explanation",
        ],
    )
    _write_csv(
        paths["false_passes_csv"],
        metrics.get("false_passes") or [],
        [
            "question_id",
            "subject",
            "chapter",
            "ai_verdict",
            "human_verdict",
            "proposed_answer",
            "human_answer",
            "preaudit_priority",
            "failure_category",
            "failure_severity",
            "failure_explanation",
            "recommended_pipeline_fix",
        ],
    )

    write_gate_report_md(paths["gate_report_md"], summary, metrics, gate)

    docs_dir.mkdir(parents=True, exist_ok=True)
    for _, src in paths.items():
        docs_dir.joinpath(src.name).write_bytes(src.read_bytes())

    return {k: str(v) for k, v in paths.items()}


def write_review_queue(path: Path, rows: list[dict[str, Any]]) -> None:
    incomplete = [r for r in rows if human_review_status(r) != "HUMAN_REVIEW_COMPLETE"]
    from app.modules.cms.mcq.p2_3.human_gold_gate.loader import sort_review_rows

    ordered = sort_review_rows(incomplete)
    fields = [
        "question_id",
        "subject",
        "chapter",
        "preaudit_priority",
        "preaudit_verdict",
        "preaudit_reason",
        "preaudit_recommended_action",
        "human_review_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in ordered:
            w.writerow({**r, "human_review_status": human_review_status(r)})


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in fields})


def _fmt(value: Any) -> str:
    if value is None:
        return "null"
    return str(value)


def _count_category(metrics: dict[str, Any], category: str) -> int:
    return sum(1 for f in metrics.get("failure_records") or [] if f.get("failure_category") == category)


def _taxonomy_table(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for rec in records:
        cat = rec.get("failure_category") or "OTHER"
        bucket = out.setdefault(cat, {"total": 0, "CRITICAL": 0, "MAJOR": 0, "MINOR": 0})
        bucket["total"] += 1
        sev = rec.get("failure_severity") or "MINOR"
        if sev in bucket:
            bucket[sev] += 1
    return out


def _pipeline_recommendations(metrics: dict[str, Any]) -> str:
    fixes: Counter[str] = Counter()
    for fp in metrics.get("false_passes") or []:
        fixes[fp.get("recommended_pipeline_fix") or "NO_PIPELINE_CHANGE"] += 1
    if not fixes:
        return "No false-pass pipeline recommendations (review incomplete or no false-passes)."
    return "\n".join(f"- {fix}: {count}" for fix, count in fixes.most_common())


def _public_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in metrics.items() if not k.startswith("_") and k not in {"gate_results", "false_passes", "failure_records"}}
