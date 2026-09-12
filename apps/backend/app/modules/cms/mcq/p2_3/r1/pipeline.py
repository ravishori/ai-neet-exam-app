"""P2.3-R1 provider repair revalidation pipeline."""

from __future__ import annotations

import asyncio
import csv
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz

from app.core.config import get_settings
from app.modules.cms.mcq.p2_3.pipeline import _load_ncert_excerpt, load_records, p2_2_mcq_path
from app.modules.cms.mcq.p2_3.provider_routing import (
    cross_validator_for,
    is_same_provider_validation,
    resolve_validator_bundle,
)
from app.modules.cms.mcq.p2_3.r1.ncert_analysis import build_ncert_failure_analysis
from app.modules.cms.mcq.p2_3.r1.taxonomy import build_qa_failure_taxonomy
from app.modules.cms.mcq.p2_3.schemas import McqRecord
from app.modules.cms.mcq.p2_3.validator import validate_record, validation_cost_usd
from app.modules.cms.pyq.p2_2.budget import BudgetExceededError, BudgetGuard
from app.modules.cms.pyq.p2_2.cache import RecoveryCache

R1_REASON = "same_provider_routing_blocked"
R1_PHASE = "P2.3-R1"


def r1_staging_paths(root: Path) -> dict[str, Path]:
    base = root / "data/staging/mcq/p2_3_r1"
    return {
        "base": base,
        "original_validation_snapshot": base / "original_validation_snapshot.jsonl",
        "revalidation_results": base / "r1_revalidation_results.jsonl",
        "merged_validation": base / "r1_merged_validation.jsonl",
        "manifest": base / "run_manifest.json",
        "gold_annotated": base / "human_gold_sample_r1_annotated.csv",
        "cost": base / "r1_cost_report.json",
    }


def p2_3_paths(root: Path) -> dict[str, Path]:
    base = root / "data/staging/mcq/p2_3"
    return {
        "generation": base / "generation_results.jsonl",
        "validation": base / "validation_results.jsonl",
        "human_gold": base / "human_gold_sample.csv",
    }


def load_jsonl_dicts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def save_jsonl_dicts(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def record_to_dict(rec: McqRecord) -> dict[str, Any]:
    return rec.to_dict()


def dict_to_record(d: dict[str, Any]) -> McqRecord:
    from app.modules.cms.mcq.p2_3.pipeline import load_records
    import tempfile

    tmp = Path(tempfile.mkdtemp()) / "one.jsonl"
    tmp.write_text(json.dumps(d) + "\n", encoding="utf-8")
    return load_records(tmp)[0]


def is_same_provider_blocked(rec: dict[str, Any]) -> bool:
    return any("same_provider" in str(e) for e in (rec.get("errors") or []))


def effective_validation_status(row: dict[str, Any]) -> str:
    if row.get("r1_validation_status"):
        return row["r1_validation_status"]
    return row.get("validation_status") or row.get("original_validation_status") or "INCONCLUSIVE"


def build_r1_row(original: dict[str, Any]) -> dict[str, Any]:
    """Merge original record with R1 audit fields (generation content unchanged)."""
    row = dict(original)
    row["original_validation_status"] = original.get("validation_status")
    row["original_validator_provider"] = original.get("validator_provider") or ""
    row["original_validator_model"] = original.get("validator_model") or ""
    row["original_validator_reason"] = original.get("validator_reason") or ""
    row["r1_validation_status"] = None
    row["r1_validator_provider"] = None
    row["r1_validator_model"] = None
    row["r1_validator_reason"] = None
    row["r1_validation_cost_usd"] = 0.0
    row["reason_for_revalidation"] = None
    row["validation_status_after_r1"] = original.get("validation_status")
    return row


def compute_metrics(merged: list[dict[str, Any]], *, qa_pass_base: int) -> dict[str, Any]:
    qa_pass = sum(1 for r in merged if r.get("qa_status") == "PASS")
    qa_fail = len(merged) - qa_pass
    ncert_supported = sum(
        1 for r in merged if r.get("qa_status") == "PASS" and r.get("source_support") == "NCERT-SUPPORTED"
    )
    same_blocked = sum(1 for r in merged if is_same_provider_blocked(r) and not r.get("r1_validation_status"))
    provider_failures = sum(1 for r in merged if r.get("generation_status") == "FAILED")

    statuses = Counter(effective_validation_status(r) for r in merged if r.get("qa_status") == "PASS")
    independently_validated = sum(
        1
        for r in merged
        if r.get("qa_status") == "PASS"
        and (
            (r.get("r1_validator_provider") and r.get("r1_validation_status"))
            or (
                r.get("validator_provider")
                and not is_same_provider_validation(r.get("generation_provider", ""), r.get("validator_provider", ""))
            )
        )
    )
    base = qa_pass or 1
    return {
        "total_generated": len(merged),
        "qa_pass": qa_pass,
        "qa_fail": qa_fail,
        "ncert_supported": ncert_supported,
        "independently_validated": independently_validated,
        "independent_validation_rate": round(independently_validated / base, 4),
        "ready": statuses.get("READY", 0),
        "minor_revision": statuses.get("MINOR_REVISION", 0),
        "major_revision": statuses.get("MAJOR_REVISION", 0),
        "reject": statuses.get("REJECT", 0),
        "inconclusive": statuses.get("INCONCLUSIVE", 0),
        "ai_ready_rate": round(statuses.get("READY", 0) / base, 4),
        "same_provider_blocked_remaining": same_blocked,
        "provider_failures": provider_failures,
    }


def annotate_gold_sample(
    *,
    root: Path,
    merged_by_id: dict[str, dict[str, Any]],
    out_path: Path,
) -> dict[str, Any]:
    src = p2_3_paths(root)["human_gold"]
    if not src.exists():
        return {"status": "no_original_gold_sample"}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows_out: list[dict[str, str]] = []
    with src.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or []) + [
            "validation_status_before_R1",
            "validation_status_after_R1",
            "r1_validator_provider",
        ]
        for row in reader:
            qid = row.get("question_id") or ""
            rec = merged_by_id.get(qid, {})
            row["validation_status_before_R1"] = rec.get("original_validation_status") or rec.get("validation_status") or ""
            row["validation_status_after_R1"] = effective_validation_status(rec)
            row["r1_validator_provider"] = rec.get("r1_validator_provider") or rec.get("validator_provider") or ""
            rows_out.append(row)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)
    docs_out = root / "docs/content-factory/P2_3_R1_HUMAN_GOLD_ANNOTATED.csv"
    shutil.copy(out_path, docs_out)
    return {"status": "annotated", "count": len(rows_out), "path": str(out_path)}


def write_r1_reports(
    *,
    root: Path,
    report: dict[str, Any],
    taxonomy: dict[str, Any],
    ncert_analysis: dict[str, Any],
    cost: dict[str, Any],
) -> None:
    docs = root / "docs/content-factory"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "P2_3_R1_PROVIDER_REPAIR_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (docs / "P2_3_R1_QA_FAILURE_TAXONOMY.json").write_text(json.dumps(taxonomy, indent=2), encoding="utf-8")
    (docs / "P2_3_R1_NCERT_FAILURE_ANALYSIS.json").write_text(json.dumps(ncert_analysis, indent=2), encoding="utf-8")
    (docs / "P2_3_R1_COST_ANALYSIS.json").write_text(json.dumps(cost, indent=2), encoding="utf-8")

    es = report.get("metrics") or {}
    cost_a = report.get("cost") or {}
    md_lines = [
        "# P2.3-R1 Provider Routing Repair Report",
        "",
        f"Generated: {report.get('generated_at')}",
        "",
        "## Summary",
        f"- QA PASS: **{es.get('qa_pass')}/{es.get('total_generated')}**",
        f"- Independent validation: **{es.get('independently_validated')}/{es.get('qa_pass')}** ({es.get('independent_validation_rate')})",
        f"- AI READY: **{es.get('ready')}** (rate {es.get('ai_ready_rate')} of QA PASS)",
        f"- Previously blocked revalidated: **{report.get('revalidated_count', 0)}**",
        f"- Production DB writes: **0**",
        "",
        "## Cost",
        f"- R1 validation: **₹{cost_a.get('r1_validation_cost_inr')}**",
        f"- Cumulative P2.3: **₹{cost_a.get('cumulative_cost_inr')}**",
        f"- ₹/AI-READY: **{cost_a.get('cost_per_ai_ready_inr')}**",
        "",
        f"## Scale Decision: **{report.get('scale_decision')}**",
        "",
        report.get("scale_reason", ""),
    ]
    (docs / "P2_3_R1_PROVIDER_REPAIR_REPORT.md").write_text("\n".join(md_lines), encoding="utf-8")


def scale_decision(metrics: dict[str, Any], *, validation_blocked: int) -> tuple[str, str]:
    if validation_blocked > 0:
        return "RED", "Independent validation still blocked for some QA-pass records."
    ready_rate = metrics.get("ai_ready_rate") or 0.0
    indep_rate = metrics.get("independent_validation_rate") or 0.0
    if indep_rate >= 0.95 and ready_rate >= 0.15:
        return "GREEN", "Proceed to human gold review — independent validation yield restored."
    if indep_rate >= 0.80 and ready_rate >= 0.08:
        return "YELLOW", "Fix generation/source planning before scaling; human review still required."
    return "RED", "Provider/quality architecture still unsuitable for scale."


async def run_r1_revalidation_async(*, root: Path, resume: bool = False) -> dict[str, Any]:
    settings = get_settings()
    study_dir = Path(settings.study_material_dir)
    usd_inr = settings.p2_3_usd_inr
    p3 = p2_3_paths(root)
    r1 = r1_staging_paths(root)
    r1["base"].mkdir(parents=True, exist_ok=True)

    # Snapshot original validation (never overwrite p2_3 source files)
    original_rows = load_jsonl_dicts(p3["validation"])
    if not original_rows:
        return {"status": "error", "message": "No P2.3 validation_results.jsonl found"}

    if not r1["original_validation_snapshot"].exists():
        save_jsonl_dicts(r1["original_validation_snapshot"], original_rows)

    gen_rows = load_jsonl_dicts(p3["generation"])
    gen_by_id = {r["question_id"]: r for r in gen_rows}

    # Build merged R1 rows from original validation
    merged: list[dict[str, Any]] = []
    for orig in original_rows:
        row = build_r1_row(orig)
        # Ensure generation fields preserved from generation_results if needed
        g = gen_by_id.get(row["question_id"], {})
        for key in ("question", "options", "correct_option", "explanation", "generation_provider", "generation_model"):
            if g.get(key) is not None and g.get(key) != "":
                row[key] = g.get(key) if key != "correct_option" else g.get("correct_option") or g.get("correct_answer")
        merged.append(row)

    blocked = [r for r in merged if r.get("qa_status") == "PASS" and is_same_provider_blocked(r)]
    expected_blocked = 298

    # Load prior R1 revalidation if resuming
    prior_r1 = {r["question_id"]: r for r in load_jsonl_dicts(r1["revalidation_results"])} if resume else {}
    done_ids = {qid for qid, r in prior_r1.items() if r.get("r1_validation_status")}

    budget = BudgetGuard(max_cost_usd=settings.p2_3_max_cost_usd)
    cache = RecoveryCache(r1["base"] / "cache")
    semaphore = asyncio.Semaphore(6)
    r1_cost_usd = 0.0
    r1_calls = 0
    revalidated = 0

    async def _revalidate_one(row: dict[str, Any]) -> dict[str, Any]:
        nonlocal r1_cost_usd, r1_calls, revalidated
        qid = row["question_id"]
        if qid in done_ids:
            pr = prior_r1[qid]
            row.update({k: pr.get(k) for k in pr if k.startswith("r1_") or k == "validation_status_after_r1"})
            return row
        if row.get("qa_status") != "PASS" or not is_same_provider_blocked(row):
            return row

        gen_prov = row.get("generation_provider") or ""
        bundle = resolve_validator_bundle(gen_prov)
        if not bundle:
            row["reason_for_revalidation"] = R1_REASON
            row["r1_validator_reason"] = "INDEPENDENT VALIDATION BLOCKED — no cross-provider validator"
            row["validation_status_after_r1"] = "INCONCLUSIVE"
            return row

        provider_inst, validator_name, model = bundle
        assert cross_validator_for(gen_prov) == validator_name

        rec = dict_to_record(row)
        async with semaphore:
            excerpt = _load_ncert_excerpt(study_dir, rec.source_file, rec.source_page)
            cache_key = f"r1:{qid}:{rec.source_excerpt_hash}:{validator_name}"
            cached = cache.get(rec.source_excerpt_hash, cache_key, validator_name)
            if cached and cached.get("r1_validation_status"):
                row.update(cached)
                return row
            try:
                gen_cost = float(row.get("cost_usd") or 0.0)
                rec = await validate_record(
                    rec,
                    provider_inst=provider_inst,
                    provider_name=validator_name,
                    model=model,
                    ncert_excerpt=excerpt,
                    budget=budget,
                    track_validation_cost=False,
                )
                val_cost = float((rec.provenance.get("validation") or {}).get("cost_usd") or 0.0)
                meta = (rec.provenance.get("validation") or {}).get("meta") or {}
                if val_cost <= 0:
                    val_cost = validation_cost_usd(meta, provider_name=validator_name, model=model)
                r1_cost_usd += val_cost
                r1_calls += 1
                revalidated += 1
                row["reason_for_revalidation"] = R1_REASON
                row["r1_validation_status"] = rec.validation_status
                row["r1_validator_provider"] = validator_name
                row["r1_validator_model"] = rec.validator_model
                row["r1_validator_reason"] = rec.validator_reason
                row["r1_validation_cost_usd"] = val_cost
                row["validation_status_after_r1"] = rec.validation_status
                row["r1_provenance"] = rec.provenance.get("validation")
                # Preserve original generation cost only
                row["cost_usd"] = gen_cost
                cache.put(rec.source_excerpt_hash, cache_key, validator_name, row)
            except BudgetExceededError:
                row["r1_validator_reason"] = "budget_exceeded"
                row["validation_status_after_r1"] = row.get("original_validation_status")
        return row

    merged = await asyncio.gather(*[_revalidate_one(r) for r in merged])
    merged = list(merged)

    # For records already independently validated (gemini→openai), set after_r1 = original
    for row in merged:
        if row.get("qa_status") != "PASS":
            continue
        if not is_same_provider_blocked(row) and row.get("validator_provider"):
            if not is_same_provider_validation(row.get("generation_provider", ""), row.get("validator_provider", "")):
                row["validation_status_after_r1"] = row.get("validation_status")
                row.setdefault("original_validation_status", row.get("validation_status"))

    save_jsonl_dicts(r1["revalidation_results"], [r for r in merged if r.get("r1_validation_status")])
    save_jsonl_dicts(r1["merged_validation"], merged)

    metrics = compute_metrics(merged, qa_pass_base=614)
    taxonomy = build_qa_failure_taxonomy(merged)
    ncert_analysis = build_ncert_failure_analysis(merged, study_root=study_dir)

    gen_cost = sum(float(r.get("cost_usd") or 0.0) for r in merged)
    orig_val_cost = sum(
        float((r.get("provenance") or {}).get("validation", {}).get("cost_usd") or 0.0) for r in merged
    )
    r1_val_cost = sum(float(r.get("r1_validation_cost_usd") or 0.0) for r in merged)
    cumulative_usd = gen_cost + orig_val_cost + r1_val_cost
    ready_count = metrics["ready"]
    cost_analysis = {
        "usd_inr_rate": usd_inr,
        "r1_validation_cost_usd": round(r1_val_cost, 6),
        "r1_validation_cost_inr": round(r1_val_cost * usd_inr, 2),
        "r1_validation_calls": r1_calls,
        "generation_cost_usd": round(gen_cost, 6),
        "original_validation_cost_usd": round(orig_val_cost, 6),
        "cumulative_cost_usd": round(cumulative_usd, 6),
        "cumulative_cost_inr": round(cumulative_usd * usd_inr, 2),
        "cost_per_independently_validated_usd": round(cumulative_usd / max(metrics["independently_validated"], 1), 6),
        "cost_per_ai_ready_usd": round(cumulative_usd / max(ready_count, 1), 6),
        "cost_per_ai_ready_inr": round((cumulative_usd * usd_inr) / max(ready_count, 1), 2),
        "pricing_note": "R1 uses estimate_cost when API returns zero cost_usd",
    }
    r1["cost"].write_text(json.dumps(cost_analysis, indent=2), encoding="utf-8")

    merged_by_id = {r["question_id"]: r for r in merged}
    gold_info = annotate_gold_sample(root=root, merged_by_id=merged_by_id, out_path=r1["gold_annotated"])

    validation_blocked = metrics["same_provider_blocked_remaining"]
    decision, reason = scale_decision(metrics, validation_blocked=validation_blocked)

    report = {
        "phase": R1_PHASE,
        "generated_at": datetime.now(UTC).isoformat(),
        "no_new_generation": True,
        "production_db_writes": 0,
        "p2_2_protected_unchanged": True,
        "expected_same_provider_blocked": expected_blocked,
        "revalidated_count": revalidated,
        "metrics": metrics,
        "cost": cost_analysis,
        "gold_sample": gold_info,
        "scale_decision": decision,
        "scale_reason": reason,
        "quality_layers": {
            "generation_quality": {
                "qa_pass_rate": round(metrics["qa_pass"] / max(metrics["total_generated"], 1), 4),
                "provider_failures": metrics["provider_failures"],
            },
            "qa_yield": metrics["qa_pass"],
            "provider_availability": {
                "anthropic_generation_disabled": True,
                "cross_provider_routing": "gemini→openai, openai→gemini",
            },
            "independent_validation_yield": metrics["independent_validation_rate"],
            "ai_ready_yield": metrics["ai_ready_rate"],
            "human_verified_yield": None,
        },
        "budget": budget.summary(),
    }

    r1["manifest"].write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_r1_reports(root=root, report=report, taxonomy=taxonomy, ncert_analysis=ncert_analysis, cost=cost_analysis)
    return report


def run_r1_revalidation(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_r1_revalidation_async(**kwargs))
