"""Pre-human audit summary report."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.cms.mcq.p2_3.pre_human_audit.schemas import PRIORITY_RANK, QUEUE_COLUMNS


def build_summary(records: list[dict[str, Any]], *, gold_checksum: str) -> dict[str, Any]:
    priorities = Counter(r.get("preaudit_priority") for r in records)
    verdicts = Counter(r.get("preaudit_verdict") for r in records)
    answer_checks = Counter(r.get("preaudit_answer_check") for r in records)
    calc = Counter(r.get("preaudit_calculation_check") for r in records)
    ncert = Counter(r.get("preaudit_ncert_support") for r in records)
    options = Counter(r.get("preaudit_option_quality") for r in records)
    neet = Counter(r.get("preaudit_neet_suitability") for r in records)
    dups = Counter(r.get("preaudit_duplicate_status") for r in records)
    qtypes = Counter(r.get("preaudit_question_type_check") for r in records)

    ar_failures = sum(
        1
        for r in records
        if "proposed_option_correct=FALSE" in (r.get("preaudit_assertion_reason_check") or "")
        or "proposed_option_correct=QUESTIONABLE" in (r.get("preaudit_assertion_reason_check") or "")
    )

    queue = sorted(
        records,
        key=lambda r: (
            PRIORITY_RANK.get(r.get("preaudit_priority") or "LOW", 9),
            -(float(r.get("preaudit_answer_confidence") or 0.0)),
            r.get("question_id") or "",
        ),
    )

    human_queue = [
        {
            "question_id": r["question_id"],
            "subject": r.get("subject"),
            "chapter": r.get("chapter"),
            "problem": r.get("preaudit_reason"),
            "recommended_action": r.get("preaudit_recommended_action"),
            "preaudit_priority": r.get("preaudit_priority"),
        }
        for r in queue
        if r.get("preaudit_priority") in ("CRITICAL", "HIGH", "MEDIUM")
    ]

    return {
        "phase": "P2.3-R1-PreHumanAudit",
        "generated_at": datetime.now(UTC).isoformat(),
        "gold_sample_checksum": gold_checksum,
        "production_db_writes": 0,
        "executive_summary": {
            "total_audited": len(records),
            "critical": priorities.get("CRITICAL", 0),
            "high": priorities.get("HIGH", 0),
            "medium": priorities.get("MEDIUM", 0),
            "low": priorities.get("LOW", 0),
            "likely_pass": verdicts.get("PREAUDIT_LIKELY_PASS", 0),
            "flagged": verdicts.get("PREAUDIT_FLAGGED", 0),
            "review": verdicts.get("PREAUDIT_REVIEW", 0),
        },
        "answer_integrity": {
            "correct_proposed_answers": answer_checks.get("CORRECT", 0),
            "potential_wrong_answers": answer_checks.get("WRONG", 0),
            "multiple_answer_risks": answer_checks.get("MULTIPLE_CORRECT", 0),
            "calculation_failures": calc.get("FAIL", 0),
            "assertion_reason_failures": ar_failures,
            "inconclusive": answer_checks.get("INCONCLUSIVE", 0),
        },
        "ncert_integrity": dict(ncert),
        "option_quality": dict(options),
        "neet_suitability": dict(neet),
        "duplicate_analysis": dict(dups),
        "question_type_analysis": dict(qtypes),
        "human_review_queue": human_queue,
        "terminology_note": "pre-human audit / automated screening — human review pending; not human verified",
    }


def write_report_md(path: Path, summary: dict[str, Any]) -> None:
    es = summary["executive_summary"]
    ai = summary["answer_integrity"]
    lines = [
        "# P2.3 Pre-Human Gold Sample Audit Report",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "> Automated pre-human screening only. **Not human verified.**",
        "",
        "## Executive Summary",
        f"- Total audited: **{es['total_audited']}**",
        f"- CRITICAL: **{es['critical']}**",
        f"- HIGH: **{es['high']}**",
        f"- MEDIUM: **{es['medium']}**",
        f"- LOW: **{es['low']}**",
        f"- Likely pass (screening): **{es['likely_pass']}**",
        f"- Flagged: **{es['flagged']}**",
        f"- Review: **{es['review']}**",
        "",
        "## Answer Integrity",
        f"- Correct (deterministic): **{ai['correct_proposed_answers']}**",
        f"- Potential wrong: **{ai['potential_wrong_answers']}**",
        f"- Calculation failures: **{ai['calculation_failures']}**",
        f"- Assertion/Reason concerns: **{ai['assertion_reason_failures']}**",
        f"- Inconclusive: **{ai['inconclusive']}**",
        "",
        "## Human Review Queue (ranked)",
    ]
    for i, item in enumerate(summary.get("human_review_queue") or [], 1):
        lines.append(
            f"{i}. **{item['preaudit_priority']}** `{item['question_id']}` — {item.get('problem')} → {item.get('recommended_action')}"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(
    *,
    out_dir: Path,
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    docs_dir: Path,
) -> dict[str, str]:
    import csv

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "jsonl": out_dir / "pre_human_audit.jsonl",
        "csv": out_dir / "pre_human_audit.csv",
        "summary": out_dir / "pre_human_audit_summary.json",
        "report_md": out_dir / "pre_human_audit_report.md",
        "queue": out_dir / "pre_human_review_queue.csv",
    }

    with paths["jsonl"].open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    fieldnames = list(records[0].keys()) if records else []
    with paths["csv"].open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

    paths["summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report_md(paths["report_md"], summary)

    queue_rows = sorted(
        records,
        key=lambda r: (
            PRIORITY_RANK.get(r.get("preaudit_priority") or "LOW", 9),
            -(float(r.get("preaudit_answer_confidence") or 0.0)),
            r.get("question_id") or "",
        ),
    )
    with paths["queue"].open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=QUEUE_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in queue_rows:
            w.writerow(
                {
                    "question_id": r.get("question_id"),
                    "subject": r.get("subject"),
                    "chapter": r.get("chapter"),
                    "question": (r.get("question") or "")[:200],
                    "proposed_answer": r.get("proposed_answer"),
                    "validator_verdict": r.get("validator_verdict"),
                    "preaudit_priority": r.get("preaudit_priority"),
                    "preaudit_verdict": r.get("preaudit_verdict"),
                    "main_issue": r.get("preaudit_reason"),
                    "reason": r.get("preaudit_reason"),
                    "recommended_action": r.get("preaudit_recommended_action"),
                    "preaudit_answer_confidence": r.get("preaudit_answer_confidence"),
                }
            )

    docs_dir.mkdir(parents=True, exist_ok=True)
    for name, src in paths.items():
        docs_dir.joinpath(src.name).write_bytes(src.read_bytes())

    return {k: str(v) for k, v in paths.items()}
