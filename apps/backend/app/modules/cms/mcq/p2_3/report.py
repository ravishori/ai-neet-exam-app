"""P2.3 pilot report generation."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.cms.mcq.p2_3.schemas import McqRecord


def _count_field(records: list[McqRecord], field: str) -> dict[str, int]:
    c: Counter[str] = Counter()
    for r in records:
        val = getattr(r, field, None)
        c[str(val)] += 1
    return dict(c)


def _scale_decision(*, ready_rate: float, duplicate_rate: float, validation_blocked: bool) -> tuple[str, str]:
    if validation_blocked:
        return "RED", "Fix independent validation provider availability before scaling."
    if ready_rate >= 0.45 and duplicate_rate < 0.15:
        return "GREEN", "Proceed to 10K pilot with current pipeline settings."
    if ready_rate >= 0.25:
        return "YELLOW", "Refine generation prompts and validation thresholds; re-run pilot."
    return "RED", "Stop and redesign generation/validation approach."


def build_pilot_report(
    *,
    records: list[McqRecord],
    manifest: dict[str, Any],
    p2_2_info: dict[str, Any],
    usd_inr: float,
) -> dict[str, Any]:
    total = len(records)
    qa_pass = sum(1 for r in records if r.qa_status == "PASS")
    ncert_supported = sum(1 for r in records if r.source_support == "NCERT-SUPPORTED" and r.qa_status == "PASS")
    validated = sum(1 for r in records if r.validator_provider and r.validator_provider not in ("", "dry-run"))
    ready = sum(1 for r in records if r.validation_status == "READY")
    dup = sum(1 for r in records if r.duplicate_status != "NO_DUPLICATE")
    gen_cost = sum(float(r.provenance.get("generation", {}).get("cost_usd") or 0.0) for r in records)
    val_cost = sum(float(r.provenance.get("validation", {}).get("cost_usd") or 0.0) for r in records)
    if gen_cost == 0:
        gen_cost = sum(r.cost_usd for r in records if r.generation_status == "GENERATED") * 0.7
    total_cost_usd = gen_cost + val_cost
    total_cost_inr = total_cost_usd * usd_inr
    usable = ready
    cost_per_usable_inr = (total_cost_inr / usable) if usable else None
    validation_blocked = any("no_independent_provider" in (r.errors or []) for r in records)
    ready_rate = ready / total if total else 0.0
    dup_rate = dup / total if total else 0.0
    scale, next_action = _scale_decision(
        ready_rate=ready_rate,
        duplicate_rate=dup_rate,
        validation_blocked=validation_blocked,
    )

    return {
        "phase": "P2.3",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": manifest.get("run_id"),
        "executive_summary": {
            "new_mcqs_attempted": total,
            "structurally_valid": qa_pass,
            "ncert_supported": ncert_supported,
            "independently_validated": validated,
            "validation_ready": ready,
            "duplicate_count": dup,
            "p2_2_protected": p2_2_info.get("protected_count"),
            "production_db_writes": 0,
        },
        "distribution": {
            "subject": _count_field(records, "subject"),
            "class": _count_field(records, "class_level"),
            "chapter": _count_field(records, "chapter"),
            "topic": _count_field(records, "topic"),
            "difficulty": _count_field(records, "difficulty"),
            "question_type": _count_field(records, "question_type"),
            "generation_provider": _count_field(records, "generation_provider"),
            "validation_status": _count_field(records, "validation_status"),
        },
        "automated_qa": {
            "pass": qa_pass,
            "reject": total - qa_pass,
            "pass_rate": round(qa_pass / total, 4) if total else 0.0,
        },
        "independent_validation": {
            "processed": validated,
            "ready": ready,
            "minor": sum(1 for r in records if r.validation_status == "MINOR_REVISION"),
            "major": sum(1 for r in records if r.validation_status == "MAJOR_REVISION"),
            "reject": sum(1 for r in records if r.validation_status == "REJECT"),
            "inconclusive": sum(1 for r in records if r.validation_status == "INCONCLUSIVE"),
            "blocked": validation_blocked,
        },
        "human_gold": {
            "sample_size": 100,
            "status": "PENDING_HUMAN_REVIEW",
            "ready": 0,
            "minor": 0,
            "major": 0,
            "reject": 0,
            "inconclusive": 100,
            "ai_human_agreement": None,
            "false_pass_rate": None,
        },
        "duplicate_analysis": {
            "exact": sum(1 for r in records if r.duplicate_status == "EXACT_DUPLICATE"),
            "near": sum(1 for r in records if r.duplicate_status == "NEAR_DUPLICATE"),
            "semantic_p2_2": sum(1 for r in records if r.duplicate_status == "SEMANTIC_DUPLICATE"),
            "duplicate_rate": round(dup_rate, 4),
        },
        "cost_analysis": {
            "usd_inr_rate": usd_inr,
            "generation_cost_usd": round(gen_cost, 4),
            "validation_cost_usd": round(val_cost, 4),
            "total_cost_usd": round(total_cost_usd, 4),
            "total_cost_inr": round(total_cost_inr, 2),
            "cost_per_generated_mcq_usd": round(gen_cost / total, 6) if total else 0,
            "cost_per_valid_mcq_usd": round(gen_cost / qa_pass, 6) if qa_pass else 0,
            "cost_per_independently_validated_usd": round(total_cost_usd / validated, 6) if validated else 0,
            "cost_per_usable_mcq_inr": round(cost_per_usable_inr, 2) if cost_per_usable_inr else None,
        },
        "scale_decision": scale,
        "next_action": next_action,
        "production": {"db_writes": 0, "import_allowed": False},
    }


def write_pilot_report(root: Path, report: dict[str, Any], paths: dict[str, Path]) -> None:
    paths["base"].mkdir(parents=True, exist_ok=True)
    paths["quality"].write_text(json.dumps(report, indent=2), encoding="utf-8")
    paths["cost"].write_text(json.dumps(report["cost_analysis"], indent=2), encoding="utf-8")
    paths["provider"].write_text(
        json.dumps(report.get("distribution", {}).get("generation_provider", {}), indent=2),
        encoding="utf-8",
    )
    md = root / "docs/content-factory/P2_3_MCQ_PILOT_REPORT.md"
    json_out = root / "docs/content-factory/P2_3_MCQ_PILOT_REPORT.json"
    md.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    es = report["executive_summary"]
    cost = report["cost_analysis"]
    lines = [
        "# P2.3 NCERT MCQ Content Factory Pilot Report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Executive Summary",
        f"- New MCQs attempted: **{es['new_mcqs_attempted']}**",
        f"- Structurally valid: **{es['structurally_valid']}**",
        f"- NCERT-supported: **{es['ncert_supported']}**",
        f"- Independently validated: **{es['independently_validated']}**",
        f"- Validation READY: **{es['validation_ready']}**",
        f"- P2.2 protected (not regenerated): **{es['p2_2_protected']}**",
        f"- Production DB writes: **{es['production_db_writes']}**",
        "",
        "## Cost Analysis",
        f"- Total cost: **₹{cost['total_cost_inr']}** (${cost['total_cost_usd']} USD @ {cost['usd_inr_rate']})",
        f"- ₹/usable MCQ: **{cost.get('cost_per_usable_mcq_inr', 'N/A')}**",
        "",
        "## Scale Decision",
        f"**{report['scale_decision']}** — {report['next_action']}",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
