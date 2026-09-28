"""P2.2 live AI pilot orchestrator — no production DB writes."""

from __future__ import annotations

import asyncio
import csv
import json
import random
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.modules.ai.gateway.registry import build_registry_from_settings
from app.modules.cms.pyq.p2_2.budget import BudgetGuard
from app.modules.cms.pyq.p2_2.cache import RecoveryCache
from app.modules.cms.pyq.p2_2.evidence import build_evidence_package, check_source_availability, neighbor_summaries
from app.modules.cms.pyq.p2_2.live_mcq import run_mcq_track
from app.modules.cms.pyq.p2_2.live_recovery import run_recovery_track
from app.modules.cms.pyq.p2_2.live_schemas import LiveMcqRecord, PilotVerdict
from app.modules.cms.pyq.p2_2.ncert_sources import assign_sources_for_mcq, build_ncert_source_pool
from app.modules.cms.pyq.p2_2.pipeline import (
    build_neighbors_index,
    index_by_qid,
    load_c_grade_ids,
    load_jsonl,
    select_pilot_cohort,
)
from app.modules.cms.pyq.p2_2.providers import GatewayRecoveryProvider
from app.modules.cms.pyq.p2_2.triage import question_id, triage_population

RECOVERY_TARGET = 40
MCQ_TARGET = 1000
HUMAN_MCQ_SAMPLE = 100
LIVE_SEED = 20260901
USD_INR_DEFAULT = 83.0


def _inr(usd: float, rate: float) -> float:
    return round(usd * rate, 2)


def build_live_providers() -> dict[str, Any]:
    settings = get_settings()
    registry = build_registry_from_settings(settings)
    out: dict[str, Any] = {}
    for name in ("gemini", "openai", "anthropic"):
        entry = registry.get(name)
        if entry and entry.status == "AVAILABLE" and entry.instance:
            out[name] = (entry.instance, entry.model)
    recovery: dict[str, GatewayRecoveryProvider] = {}
    for name, (inst, model) in out.items():
        recovery[name] = GatewayRecoveryProvider(inst, name=name, model=model)
    return {"generation": out, "recovery": recovery, "settings": settings}


def estimate_preflight_cost(
    *,
    recovery_count: int,
    mcq_count: int,
    providers_available: int,
) -> dict[str, Any]:
    settings = get_settings()
    per_recovery = 0.015 * min(providers_available, 3)
    per_mcq = 0.012 * 2  # generation + review
    est = recovery_count * per_recovery + mcq_count * per_mcq
    budget = float(getattr(settings, "factory_max_pilot_cost_usd", 30.0))
    live_budget = float(getattr(settings, "p2_2_live_max_cost_usd", 75.0))
    return {
        "estimated_max_api_cost_usd": round(est, 2),
        "budget_configured_usd": live_budget,
        "factory_budget_usd": budget,
        "pilot_limits": {
            "recovery_candidates": recovery_count,
            "mcq_target": mcq_count,
            "providers": providers_available,
        },
    }


def _track_a_verdict(stats: dict[str, Any], *, false_recovery: int) -> PilotVerdict:
    processed = stats.get("processed") or 0
    if processed == 0:
        return "RED"
    verified = stats.get("verified") or 0
    rate = verified / processed
    if false_recovery > 0:
        return "RED"
    if rate >= 0.45 and (stats.get("provider_disagreement") or 0) <= processed * 0.35:
        return "GREEN"
    if rate >= 0.25:
        return "YELLOW"
    return "RED"


def _track_b_verdict(stats: dict[str, Any]) -> PilotVerdict:
    generated = stats.get("generated") or 0
    if generated < MCQ_TARGET * 0.9:
        return "RED"
    struct = stats.get("structurally_valid") or 0
    validated = stats.get("validated") or 0
    pending = stats.get("generated_pending_review") or 0
    rate = (validated + pending * 0.5) / generated if generated else 0
    dup = (stats.get("exact_duplicate_count") or 0) + (stats.get("near_duplicate_count") or 0)
    if validated / generated >= 0.55 and dup <= generated * 0.05:
        return "GREEN"
    if struct / generated >= 0.3 and rate >= 0.25:
        return "YELLOW"
    if rate >= 0.35:
        return "YELLOW"
    return "RED"


def _overall_verdict(a: PilotVerdict, b: PilotVerdict) -> PilotVerdict:
    if a == "RED" or b == "RED":
        if a == "GREEN" or b == "GREEN":
            return "YELLOW"
        return "RED"
    if a == "YELLOW" or b == "YELLOW":
        return "YELLOW"
    return "GREEN"


def select_human_mcq_sample(records: list[LiveMcqRecord], *, target: int, seed: int) -> list[LiveMcqRecord]:
    rng = random.Random(seed)
    buckets: dict[str, list[LiveMcqRecord]] = {}
    for rec in records:
        key = f"{rec.subject}:{rec.difficulty}:{rec.provider}:{rec.status}"
        buckets.setdefault(key, []).append(rec)
    selected: list[LiveMcqRecord] = []
    keys = list(buckets.keys())
    rng.shuffle(keys)
    per = max(1, target // max(len(keys), 1))
    for key in keys:
        pool = buckets[key][:]
        rng.shuffle(pool)
        selected.extend(pool[:per])
    remaining = [r for r in records if r not in selected]
    rng.shuffle(remaining)
    while len(selected) < target and remaining:
        selected.append(remaining.pop())
    return selected[:target]


def write_human_review_csv(path: Path, recovery_rows: list[dict[str, Any]], mcq_sample: list[LiveMcqRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "track",
                "record_id",
                "subject_or_paper",
                "provider",
                "auto_verdict",
                "human_verdict",
                "notes",
            ]
        )
        for row in recovery_rows:
            w.writerow(
                [
                    "A_recovery",
                    row.get("question_id"),
                    row.get("question_id", "").split(":")[0],
                    ",".join(p.get("provider", "") for p in row.get("providers") or []),
                    row.get("verification_status"),
                    "PENDING",
                    "",
                ]
            )
        for rec in mcq_sample:
            w.writerow(
                [
                    "B_mcq",
                    rec.mcq_id,
                    rec.subject,
                    rec.provider,
                    rec.review_verdict,
                    "PENDING",
                    "",
                ]
            )


def provider_comparison_recovery(rows: list[dict[str, Any]]) -> dict[str, Any]:
    agreements: list[float] = []
    for row in rows:
        fa = row.get("field_agreement") or {}
        overall = fa.get("overall")
        if isinstance(overall, int | float):
            agreements.append(float(overall))
    return {
        "mean_field_agreement": round(sum(agreements) / len(agreements), 3) if agreements else 0.0,
        "disagreement_count": sum(1 for r in rows if r.get("consensus") == "DISAGREEMENT"),
        "unanimous_count": sum(1 for r in rows if r.get("consensus") == "UNANIMOUS"),
    }


def provider_comparison_mcq(records: list[LiveMcqRecord]) -> dict[str, Any]:
    by_provider: dict[str, Counter] = {}
    for rec in records:
        c = by_provider.setdefault(rec.provider, Counter())
        c["total"] += 1
        c[rec.status] += 1
        c["cost_usd"] += int(rec.cost_usd * 1_000_000)
    return {
        name: {
            "total": cnt["total"],
            "validated": cnt.get("VALIDATED", 0),
            "rejected": cnt.get("REJECTED", 0),
            "inconclusive": cnt.get("INCONCLUSIVE", 0),
            "human_review": cnt.get("HUMAN_REVIEW", 0),
            "cost_usd": cnt["cost_usd"] / 1_000_000,
        }
        for name, cnt in by_provider.items()
    }


async def run_live_pilot_async(
    *,
    root: Path,
    output_dir: Path,
    docs_dir: Path,
    recovery_count: int = RECOVERY_TARGET,
    mcq_count: int = MCQ_TARGET,
    seed: int = LIVE_SEED,
    max_cost_usd: float | None = None,
    usd_inr: float = USD_INR_DEFAULT,
    mcq_concurrency: int = 6,
    skip_recovery: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    live_budget = max_cost_usd or float(getattr(settings, "p2_2_live_max_cost_usd", 75.0))
    budget = BudgetGuard(max_cost_usd=live_budget)

    r3_dir = root / "data/staging/pyq/2020-2025/p2_1e_full_r3"
    triage_path = docs_dir / "PYQ_P2_2_TRIAGE.json"
    audit_json = docs_dir / "PYQ_P2_1G_R3_HUMAN_FIDELITY_AUDIT.json"
    zip_path = root / "data/staging/pyq/NEET_PYQ_OFFICIAL.zip"
    study_dir = Path(settings.study_material_dir)

    provider_bundle = build_live_providers()
    gen_providers = provider_bundle["generation"]
    rec_providers = provider_bundle["recovery"]
    if len(rec_providers) < 1:
        raise RuntimeError("No live AI providers available")

    preflight = estimate_preflight_cost(
        recovery_count=recovery_count,
        mcq_count=mcq_count,
        providers_available=len(rec_providers),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    cache = RecoveryCache(output_dir / "cache")

    # --- Track A ---
    records = load_jsonl(r3_dir / "questions.p2_1e_full.jsonl")
    records_by_id = index_by_qid(records)
    neighbors_index = build_neighbors_index(records)
    c_grade_ids = load_c_grade_ids(audit_json)
    triage_data = json.loads(triage_path.read_text(encoding="utf-8")) if triage_path.exists() else None
    if triage_data:
        from app.modules.cms.pyq.p2_2.schemas import TriageResult

        triage_results = [
            TriageResult(
                r["question_id"],
                r["category"],
                r["reason"],
                r["original_status"],
                r.get("missing_fields") or [],
                r.get("known_defects") or [],
            )
            for r in triage_data.get("records") or []
        ]
    else:
        source_availability: dict[str, dict[str, bool]] = {}
        words_path = r3_dir / "ocr.words.p2_1e_full.jsonl"
        for rec in records:
            qid = question_id(rec)
            source_availability[qid] = check_source_availability(rec, zip_path=zip_path if zip_path.exists() else None, words_path=words_path)
        triage_results = triage_population(records, c_grade_ids=c_grade_ids, source_availability=source_availability)

    recovery_jsonl = docs_dir / "PYQ_P2_2_RECOVERY_RESULTS.jsonl"
    recovery_rows: list[dict[str, Any]] = []
    recovery_stats: dict[str, Any] = {}
    if skip_recovery and recovery_jsonl.exists():
        recovery_rows = [json.loads(line) for line in recovery_jsonl.open(encoding="utf-8") if line.strip()]
        recovery_stats = {
            "candidates": len(recovery_rows),
            "processed": len(recovery_rows),
            "ai_recovered": sum(1 for r in recovery_rows if r.get("recovery_status") == "AI_RECOVERED"),
            "deterministic_recovered": sum(1 for r in recovery_rows if r.get("recovery_status") == "DETERMINISTIC_RECOVERED"),
            "verified": sum(1 for r in recovery_rows if r.get("verification_status") == "VERIFIED"),
            "failed": sum(1 for r in recovery_rows if r.get("verification_status") == "FAILED"),
            "inconclusive": sum(1 for r in recovery_rows if r.get("verification_status") == "INCONCLUSIVE"),
            "human_review": sum(1 for r in recovery_rows if r.get("verification_status") == "HUMAN_REVIEW"),
            "provider_disagreement": sum(1 for r in recovery_rows if r.get("consensus") == "DISAGREEMENT"),
            "skipped_rerun": True,
        }
        cohort = []
    else:
        cohort = select_pilot_cohort(triage_results, records_by_id, target=recovery_count, seed=seed)
        words_path = r3_dir / "ocr.words.p2_1e_full.jsonl"

        def evidence_builder(rec: dict[str, Any]) -> dict[str, Any]:
            page = int(rec.get("source_page") or 0)
            qnum = int(rec.get("question_number") or 0)
            avail = check_source_availability(rec, zip_path=zip_path if zip_path.exists() else None, words_path=words_path)
            return build_evidence_package(
                rec,
                words_path=words_path,
                neighbors=neighbor_summaries(neighbors_index, page=page, qnum=qnum),
                source_image_available=avail.get("has_pdf", False),
            )

        recovery_rows, recovery_stats = await run_recovery_track(
            cohort=cohort,
            records_by_id=records_by_id,
            evidence_builder=evidence_builder,
            providers=rec_providers,
            budget=budget,
            cache=cache,
        )

        with recovery_jsonl.open("w", encoding="utf-8") as fh:
            for row in recovery_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # --- Track B ---
    ncert_pool = build_ncert_source_pool(study_dir)
    mcq_sources = assign_sources_for_mcq(ncert_pool, mcq_count, seed=seed)
    mcq_records, mcq_stats = await run_mcq_track(
        sources=mcq_sources,
        providers=gen_providers,
        budget=budget,
        concurrency=mcq_concurrency,
    )

    mcq_jsonl = docs_dir / "PYQ_P2_2_MCQ_RESULTS.jsonl"
    with mcq_jsonl.open("w", encoding="utf-8") as fh:
        for rec in mcq_records:
            fh.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

    human_mcq_sample = select_human_mcq_sample(mcq_records, target=HUMAN_MCQ_SAMPLE, seed=seed)
    human_csv = docs_dir / "PYQ_P2_2_HUMAN_REVIEW.csv"
    write_human_review_csv(human_csv, recovery_rows, human_mcq_sample)

    provider_cmp = {
        "recovery": provider_comparison_recovery(recovery_rows),
        "mcq": provider_comparison_mcq(mcq_records),
    }
    (docs_dir / "PYQ_P2_2_PROVIDER_COMPARISON.json").write_text(
        json.dumps(provider_cmp, indent=2), encoding="utf-8"
    )

    false_recovery = sum(1 for r in recovery_rows if r.get("verification_status") == "FAILED")
    track_a_verdict = _track_a_verdict(recovery_stats, false_recovery=false_recovery)
    track_b_verdict = _track_b_verdict(mcq_stats)
    overall = _overall_verdict(track_a_verdict, track_b_verdict)

    subject_dist = Counter(r.subject for r in mcq_records)
    chapter_dist = Counter(f"{r.subject}:{r.chapter}" for r in mcq_records)

    report = {
        "phase": "P2.2_LIVE",
        "generated_at": datetime.now(UTC).isoformat(),
        "seed": seed,
        "preflight": preflight,
        "budget": budget.summary(),
        "track_a": {
            **recovery_stats,
            "false_recovery": false_recovery,
            "human_verdict_pending": len(recovery_rows),
            "cohort_ids": [c.question_id for c in cohort] if cohort else [r.get("question_id") for r in recovery_rows],
            "verdict": track_a_verdict,
        },
        "track_b": {
            **mcq_stats,
            "subject_distribution": dict(subject_dist),
            "chapter_distribution_sample": dict(list(chapter_dist.items())[:30]),
            "human_sample_size": len(human_mcq_sample),
            "human_verdict_pending": len(human_mcq_sample),
            "generation_success_rate": round((mcq_stats.get("generated") or 0) / mcq_count, 3),
            "source_support_rate": round(
                sum(1 for r in mcq_records if r.source_support == "NCERT-SUPPORTED") / max(len(mcq_records), 1),
                3,
            ),
            "verdict": track_b_verdict,
        },
        "provider_comparison": provider_cmp,
        "verdicts": {
            "track_a": track_a_verdict,
            "track_b": track_b_verdict,
            "overall": overall,
        },
        "production_db_writes": 0,
        "r3_modified": False,
        "usd_inr": usd_inr,
    }
    report["next_action"] = "SCALE" if overall == "GREEN" else ("REFINE" if overall == "YELLOW" else "ABANDON")

    (output_dir / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (docs_dir / "PYQ_P2_2_LIVE_PILOT_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def run_live_pilot(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_live_pilot_async(**kwargs))
