"""P2.2-R1 validation pipeline orchestrator."""

from __future__ import annotations

import asyncio
import csv
import json
import random
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz

from app.modules.cms.pyq.p2_2.budget import BudgetGuard
from app.modules.cms.pyq.p2_2.cache import RecoveryCache
from app.modules.cms.pyq.p2_2.pipeline import load_jsonl
from app.modules.cms.pyq.p2_2.r1_validation.duplicates import classify_duplicates
from app.modules.cms.pyq.p2_2.r1_validation.loader import EXPECTED_STRUCTURAL, load_gemini_structural_candidates
from app.modules.cms.pyq.p2_2.r1_validation.schemas import FailureCategory, QualityGrade
from app.modules.cms.pyq.p2_2.r1_validation.validator import resolve_validator_provider, validate_one

HUMAN_SAMPLE_SIZE = 100
R1_SEED = 20260902


def _load_ncert_excerpt(study_root: Path, relative_path: str, page: int) -> str:
    pdf = study_root / relative_path.replace("/", "\\").replace("\\", "/")
    if not pdf.exists():
        pdf = study_root / Path(relative_path)
    if not pdf.exists():
        return ""
    doc = fitz.open(pdf)
    try:
        idx = max(0, int(page) - 1)
        if idx >= doc.page_count:
            return ""
        return (doc.load_page(idx).get_text("text") or "").strip()[:6000]
    finally:
        doc.close()


def select_human_sample(candidates: list[dict[str, Any]], *, seed: int = R1_SEED, target: int = HUMAN_SAMPLE_SIZE) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        key = f"{row.get('subject')}:{row.get('chapter')}:{row.get('difficulty')}:{row.get('question_type') or 'conceptual'}"
        buckets.setdefault(key, []).append(row)
    selected: list[dict[str, Any]] = []
    keys = list(buckets.keys())
    rng.shuffle(keys)
    per = max(1, target // max(len(keys), 1))
    for key in keys:
        pool = buckets[key][:]
        rng.shuffle(pool)
        selected.extend(pool[:per])
    remaining = [r for r in candidates if r not in selected]
    rng.shuffle(remaining)
    while len(selected) < target and remaining:
        selected.append(remaining.pop())
    return selected[:target]


def classify_quality(
    *,
    validator: dict[str, Any] | None,
    duplicate_class: str,
    validator_available: bool,
) -> tuple[QualityGrade, FailureCategory | None]:
    if not validator_available or not validator:
        return "I", None
    if duplicate_class in ("EXACT_DUPLICATE", "NEAR_DUPLICATE"):
        return "D", "DUPLICATE"
    overall = validator.get("overall")
    ncert = validator.get("ncert_support_class") or validator.get("ncert_support")
    if overall == "INCONCLUSIVE" or ncert == "INCONCLUSIVE":
        return "I", "OTHER"
    if overall == "FAIL":
        issues = [str(i).lower() for i in validator.get("issues") or []]
        if validator.get("correct_answer") == "FAIL" or any("multiple" in i for i in issues):
            return "D", "MULTIPLE_CORRECT" if any("multiple" in i for i in issues) else "WRONG_ANSWER"
        if validator.get("ambiguity") == "FAIL":
            return "D", "AMBIGUOUS"
        if validator.get("ncert_support") == "FAIL" or ncert in ("NO_SUPPORT", "WEAK_SUPPORT"):
            return "D", "NCERT_UNSUPPORTED"
        if validator.get("explanation") == "FAIL":
            return "D", "EXPLANATION_ERROR"
        return "D", "OTHER"
    if overall == "PASS":
        if ncert in ("DIRECT_NCERT_SUPPORT", "SUPPORTED_WITHIN_NCERT_CONTEXT", "PASS"):
            if validator.get("stem") == "PASS" and validator.get("difficulty") == "PASS":
                return "A", None
            return "B", None
        return "C", "NCERT_UNSUPPORTED"
    return "I", None


def failure_taxonomy(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for rec in records:
        cat = rec.get("primary_failure")
        if cat:
            counts[cat] += 1
        elif rec.get("quality_grade") in ("D", "C"):
            counts["OTHER"] += 1
    total = len(records) or 1
    return {
        "counts": dict(counts),
        "percentages": {k: round(100.0 * v / total, 2) for k, v in counts.items()},
    }


def write_human_gold_csv(path: Path, sample: list[dict[str, Any]], validation_by_id: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "question_id",
                "subject",
                "class",
                "chapter",
                "topic",
                "provider",
                "difficulty",
                "question",
                "option_A",
                "option_B",
                "option_C",
                "option_D",
                "proposed_answer",
                "NCERT_source",
                "validator_verdict",
                "human_stem",
                "human_option_A",
                "human_option_B",
                "human_option_C",
                "human_option_D",
                "human_answer",
                "human_explanation",
                "human_ncert_support",
                "human_ambiguity",
                "human_duplicate",
                "human_difficulty",
                "human_overall",
                "reviewer_notes",
            ]
        )
        for row in sample:
            opts = row.get("options") or {}
            val = validation_by_id.get(row["mcq_id"]) or {}
            w.writerow(
                [
                    row.get("mcq_id"),
                    row.get("subject"),
                    row.get("class"),
                    row.get("chapter"),
                    row.get("topic"),
                    row.get("provider"),
                    row.get("difficulty"),
                    row.get("question"),
                    opts.get("A", ""),
                    opts.get("B", ""),
                    opts.get("C", ""),
                    opts.get("D", ""),
                    row.get("correct_answer"),
                    row.get("source_file"),
                    val.get("overall", "PENDING"),
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "",
                ]
            )


async def run_r1_validation_async(
    *,
    root: Path,
    mcq_path: Path,
    output_dir: Path,
    docs_dir: Path,
    study_material_dir: Path,
    r3_questions_path: Path | None = None,
    seed: int = R1_SEED,
    max_cost_usd: float = 25.0,
    concurrency: int = 6,
) -> dict[str, Any]:
    candidates = load_gemini_structural_candidates(mcq_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache = RecoveryCache(output_dir / "cache")
    budget = BudgetGuard(max_cost_usd=max_cost_usd)

    r3_stems: list[str] = []
    if r3_questions_path and r3_questions_path.exists():
        r3_stems = [(r.get("stem") or "") for r in load_jsonl(r3_questions_path)]

    dup_map = classify_duplicates(candidates, r3_stems=r3_stems)
    validator_bundle = resolve_validator_provider()
    validator_available = validator_bundle is not None
    provider_name = "NO_INDEPENDENT_PROVIDER_AVAILABLE"
    model = ""
    provider_inst = None
    if validator_bundle:
        provider_inst, provider_name, model = validator_bundle

    semaphore = asyncio.Semaphore(concurrency)
    validation_records: list[dict[str, Any]] = []
    validation_by_id: dict[str, dict[str, Any]] = {}

    async def _validate_row(row: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            mcq_id = row["mcq_id"]
            excerpt = _load_ncert_excerpt(study_material_dir, row.get("source_file") or "", int(row.get("source_page") or 1))
            rec: dict[str, Any] = {
                "mcq_id": mcq_id,
                "input": {
                    "subject": row.get("subject"),
                    "class": row.get("class"),
                    "chapter": row.get("chapter"),
                    "topic": row.get("topic"),
                    "source_file": row.get("source_file"),
                    "source_page": row.get("source_page"),
                },
                "duplicate_class": dup_map.get(mcq_id, "NO_DUPLICATE"),
                "generation_cost_usd": float(row.get("cost_usd") or 0.0),
            }
            if not validator_available or not provider_inst:
                rec["validator"] = None
                rec["validation_status"] = "SKIPPED_NO_PROVIDER"
                rec["quality_grade"], rec["primary_failure"] = classify_quality(
                    validator=None, duplicate_class=rec["duplicate_class"], validator_available=False
                )
                return rec

            cache_key = f"r1:{mcq_id}:{row.get('source_hash')}"
            cached = cache.get(row.get("source_hash") or mcq_id, cache_key, provider_name)
            if cached:
                rec["validator"] = cached.get("validator")
                rec["validation_meta"] = cached.get("meta")
                rec["validation_cost_usd"] = cached.get("cost_usd", 0.0)
            else:
                try:
                    budget.check()
                    parsed, cost, meta = await validate_one(
                        provider_inst,
                        provider_name=provider_name,
                        model=model,
                        row=row,
                        ncert_excerpt=excerpt,
                    )
                    budget.record(
                        track="R1_validation",
                        provider=provider_name,
                        model=model,
                        candidate_id=mcq_id,
                        cost_usd=cost,
                        status=parsed.get("overall", "INCONCLUSIVE"),
                    )
                    rec["validator"] = parsed
                    rec["validation_meta"] = meta
                    rec["validation_cost_usd"] = cost
                    cache.put(
                        row.get("source_hash") or mcq_id,
                        cache_key,
                        provider_name,
                        {"validator": parsed, "meta": meta, "cost_usd": cost},
                    )
                except Exception as exc:  # noqa: BLE001
                    rec["validator"] = {"overall": "INCONCLUSIVE", "issues": [str(exc)[:200]]}
                    rec["validation_status"] = "ERROR"
                    rec["validation_cost_usd"] = 0.0

            grade, failure = classify_quality(
                validator=rec.get("validator"),
                duplicate_class=rec["duplicate_class"],
                validator_available=True,
            )
            rec["quality_grade"] = grade
            rec["primary_failure"] = failure
            rec["validation_status"] = (rec.get("validator") or {}).get("overall", "INCONCLUSIVE")
            return rec

    validation_records = await asyncio.gather(*[_validate_row(r) for r in candidates])
    validation_by_id = {r["mcq_id"]: r.get("validator") or {} for r in validation_records}

    human_sample = select_human_sample(candidates, seed=seed)
    human_csv = docs_dir / "PYQ_P2_2_R1_HUMAN_GOLD_REVIEW.csv"
    write_human_gold_csv(human_csv, human_sample, validation_by_id)

    pass_n = sum(1 for r in validation_records if (r.get("validator") or {}).get("overall") == "PASS")
    fail_n = sum(1 for r in validation_records if (r.get("validator") or {}).get("overall") == "FAIL")
    inc_n = sum(1 for r in validation_records if (r.get("validator") or {}).get("overall") == "INCONCLUSIVE" or r.get("validation_status") == "SKIPPED_NO_PROVIDER")

    gen_cost = sum(float(r.get("generation_cost_usd") or 0.0) for r in validation_records)
    val_cost = sum(float(r.get("validation_cost_usd") or 0.0) for r in validation_records)
    production_ready = sum(1 for r in validation_records if r.get("quality_grade") == "A")
    minor = sum(1 for r in validation_records if r.get("quality_grade") == "B")

    taxonomy = failure_taxonomy(validation_records)
    dup_counts = Counter(r.get("duplicate_class") for r in validation_records)

    summary = {
        "phase": "P2.2-R1",
        "generated_at": datetime.now(UTC).isoformat(),
        "seed": seed,
        "input": {"generated_candidates": 1000, "structurally_valid": EXPECTED_STRUCTURAL},
        "independent_validation": {
            "provider": provider_name,
            "model": model,
            "processed": len(validation_records) if validator_available else 0,
            "pass": pass_n,
            "fail": fail_n,
            "inconclusive": inc_n,
            "available": validator_available,
        },
        "human_gold": {
            "sample_size": len(human_sample),
            "sampling_method": "stratified_deterministic",
            "population_size": len(candidates),
            "strata": "subject/chapter/difficulty/question_type",
            "pass": 0,
            "minor_revision": 0,
            "major_revision": 0,
            "reject": 0,
            "inconclusive": len(human_sample),
            "status": "PENDING_HUMAN_REVIEW",
        },
        "quality": {
            "true_acceptance_rate": round(pass_n / EXPECTED_STRUCTURAL, 4) if validator_available else 0.0,
            "production_ready_rate": round(production_ready / EXPECTED_STRUCTURAL, 4),
            "minor_revision_rate": round(minor / EXPECTED_STRUCTURAL, 4),
            "false_pass_rate": 0.0,
            "ambiguity_rate": round(
                sum(1 for r in validation_records if (r.get("validator") or {}).get("ambiguity") == "FAIL") / EXPECTED_STRUCTURAL,
                4,
            ),
            "duplicate_rate": round(
                sum(1 for d in dup_map.values() if d != "NO_DUPLICATE") / EXPECTED_STRUCTURAL,
                4,
            ),
            "answer_accuracy_proxy": round(
                sum(1 for r in validation_records if (r.get("validator") or {}).get("correct_answer") == "PASS") / EXPECTED_STRUCTURAL,
                4,
            )
            if validator_available
            else 0.0,
            "grades": dict(Counter(r.get("quality_grade") for r in validation_records)),
        },
        "economics": {
            "generation_cost_usd": round(gen_cost, 6),
            "validation_cost_usd": round(val_cost, 6),
            "total_cost_usd": round(gen_cost + val_cost, 6),
            "cost_per_generated_question_usd": round(gen_cost / 1000, 6),
            "cost_per_structurally_valid_usd": round(gen_cost / EXPECTED_STRUCTURAL, 6),
            "cost_per_independently_validated_usd": round((gen_cost + val_cost) / max(pass_n, 1), 6),
            "cost_per_human_accepted_usd": None,
            "cost_per_human_accepted_inr": None,
            "inr_note": "INR conversion omitted — no recorded exchange-rate basis in P2.2 artifacts",
        },
        "provider": {
            "generator": "gemini",
            "generator_model": "gemini-3.6-flash",
            "validator": provider_name,
            "validator_model": model,
            "provider_agreement": None,
            "agreement_note": "Human gold review pending — AI vs human agreement not yet computable",
        },
        "duplicate_summary": dict(dup_counts),
        "failure_taxonomy": taxonomy,
        "production": {"db_writes": 0, "import_allowed": False},
    }

    if not validator_available:
        summary["final_verdict"] = "RED"
        summary["next_action"] = "STOP"
    elif pass_n / EXPECTED_STRUCTURAL >= 0.55 and production_ready / EXPECTED_STRUCTURAL >= 0.35:
        summary["final_verdict"] = "GREEN"
        summary["next_action"] = "SCALE"
    elif pass_n / EXPECTED_STRUCTURAL >= 0.30:
        summary["final_verdict"] = "YELLOW"
        summary["next_action"] = "REFINE"
    else:
        summary["final_verdict"] = "RED"
        summary["next_action"] = "STOP"

    results_path = output_dir / "validation_records.jsonl"
    with results_path.open("w", encoding="utf-8") as fh:
        for rec in validation_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    (output_dir / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (docs_dir / "PYQ_P2_2_R1_VALIDATION_REPORT.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (docs_dir / "PYQ_P2_2_R1_PROVIDER_VALIDATION.json").write_text(
        json.dumps(
            {
                "validator": provider_name,
                "model": model,
                "pass": pass_n,
                "fail": fail_n,
                "inconclusive": inc_n,
                "budget": budget.summary(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (docs_dir / "PYQ_P2_2_R1_FAILURE_TAXONOMY.json").write_text(json.dumps(taxonomy, indent=2), encoding="utf-8")
    (docs_dir / "PYQ_P2_2_R1_COST_ANALYSIS.json").write_text(json.dumps(summary["economics"], indent=2), encoding="utf-8")
    return summary


def run_r1_validation(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_r1_validation_async(**kwargs))
