"""P2.3 NCERT MCQ content factory pipeline."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz

from app.core.config import get_settings
from app.modules.cms.mcq.p2_3.duplicates import classify_duplicates
from app.modules.cms.mcq.p2_3.generator import generate_one
from app.modules.cms.mcq.p2_3.plan import build_generation_plan, inventory_from_study_dir
from app.modules.cms.mcq.p2_3.provider_routing import resolve_generation_providers
from app.modules.cms.mcq.p2_3.qa import automated_qa
from app.modules.cms.mcq.p2_3.report import build_pilot_report, write_pilot_report
from app.modules.cms.mcq.p2_3.safeguard import (
    assert_p2_2_not_regenerated,
    load_p2_2_protected_ids,
    load_p2_2_protected_stems,
    verify_p2_2_population,
)
from app.modules.cms.mcq.p2_3.sampling import GOLD_SAMPLE_SIZE, GOLD_SEED, select_gold_sample, write_human_gold_csv
from app.modules.cms.mcq.p2_3.schemas import RUN_PHASE, McqRecord
from app.modules.cms.mcq.p2_3.validator import resolve_independent_validator_for, validate_record
from app.modules.cms.pyq.p2_2.budget import BudgetExceededError, BudgetGuard
from app.modules.cms.pyq.p2_2.cache import RecoveryCache
from app.modules.cms.pyq.p2_2.ncert_sources import build_ncert_source_pool

P2_3_SEED = 20260903
DEFAULT_USD_INR = 83.0


def _load_ncert_excerpt(study_root: Path, relative_path: str, page: int) -> str:
    from app.modules.ingestion.services.ncert_canonical_source import (
        NcertSourceError,
        assert_ncert_generation_root,
        validate_ncert_generation_source,
    )

    root = assert_ncert_generation_root(study_root)
    try:
        validated = validate_ncert_generation_source(root / relative_path.replace("\\", "/"), root=root)
    except NcertSourceError:
        return ""
    pdf = validated.resolved_path
    doc = fitz.open(pdf)
    try:
        idx = max(0, int(page) - 1)
        if idx >= doc.page_count:
            return ""
        return (doc.load_page(idx).get_text("text") or "").strip()[:6000]
    finally:
        doc.close()


def _source_text_map(study_dir: Path) -> dict[str, str]:
    pool = build_ncert_source_pool(study_dir)
    return {s.source_id: s.text for s in pool}


def staging_paths(root: Path, *, dry_run: bool = False) -> dict[str, Path]:
    base = root / "data/staging/mcq/p2_3"
    if dry_run:
        base = base / "dry_run"
    return {
        "base": base,
        "generation": base / "generation_results.jsonl",
        "validation": base / "validation_results.jsonl",
        "manifest": base / "run_manifest.json",
        "cost": base / "cost_report.json",
        "quality": base / "quality_report.json",
        "provider": base / "provider_report.json",
        "human_gold": base / "human_gold_sample.csv",
    }


def p2_2_mcq_path(root: Path) -> Path:
    return root / "docs/content-factory/PYQ_P2_2_MCQ_RESULTS.jsonl"


def load_records(path: Path) -> list[McqRecord]:
    if not path.exists():
        return []
    out: list[McqRecord] = []
    for line in path.open(encoding="utf-8"):
        if not line.strip():
            continue
        d = json.loads(line)
        out.append(
            McqRecord(
                question_id=d["question_id"],
                run_id=d["run_id"],
                batch_id=d["batch_id"],
                slot_index=d["slot_index"],
                concept_id=d["concept_id"],
                subject=d["subject"],
                class_level=d["class"],
                chapter=d.get("chapter"),
                topic=d["topic"],
                question_type=d["question_type"],
                difficulty=d["difficulty"],
                source_id=d["source_id"],
                source_locator=d["source_locator"],
                source_file=d["source_file"],
                source_page=d["source_page"],
                source_excerpt_hash=d["source_excerpt_hash"],
                question=d.get("question", ""),
                options=d.get("options") or {},
                correct_option=d.get("correct_option") or d.get("correct_answer", ""),
                explanation=d.get("explanation", ""),
                source_support=d.get("source_support", ""),
                generation_provider=d.get("generation_provider", ""),
                generation_model=d.get("generation_model", ""),
                generation_prompt_version=d.get("generation_prompt_version", ""),
                generation_status=d.get("generation_status", "PENDING"),
                qa_status=d.get("qa_status", "PENDING"),
                validation_status=d.get("validation_status", "INCONCLUSIVE"),
                validator_provider=d.get("validator_provider", ""),
                validator_model=d.get("validator_model", ""),
                validator_reason=d.get("validator_reason", ""),
                validator_confidence=float(d.get("validator_confidence") or 0.0),
                duplicate_status=d.get("duplicate_status", "NO_DUPLICATE"),
                duplicate_of=d.get("duplicate_of"),
                similarity_score=float(d.get("similarity_score") or 0.0),
                human_review_status=d.get("human_review_status", "NOT_SAMPLED"),
                human_grade=d.get("human_grade"),
                final_status=d.get("final_status", "INCONCLUSIVE"),
                cost_usd=float(d.get("cost_usd") or 0.0),
                errors=d.get("errors") or [],
                provenance=d.get("provenance") or {},
                origin=d.get("origin", "p2_3_generation"),
            )
        )
    return out


def save_records(path: Path, records: list[McqRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")


def load_or_create_manifest(path: Path, *, run_id: str | None = None) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    rid = run_id or f"p2_3-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    return {
        "phase": RUN_PHASE,
        "run_id": rid,
        "batch_id": f"{rid}-batch-1",
        "created_at": datetime.now(UTC).isoformat(),
        "seed": P2_3_SEED,
        "production_db_writes": 0,
    }


def dry_run_preflight(root: Path) -> dict[str, Any]:
    settings = get_settings()
    study_dir = Path(settings.ncert_source_root)
    paths = staging_paths(root)
    p2_2_path = p2_2_mcq_path(root)
    p2_2_info = verify_p2_2_population(p2_2_path)
    concepts = inventory_from_study_dir(study_dir)
    slots, plan_meta = build_generation_plan(concepts, total=settings.p2_3_mcq_count, seed=P2_3_SEED)
    return {
        "phase": RUN_PHASE,
        "mode": "dry_run",
        "p2_2_protected": p2_2_info,
        "ncert_concepts": len(concepts),
        "generation_plan": plan_meta,
        "staging": {k: str(v) for k, v in paths.items()},
        "production_db_writes": 0,
    }


async def run_generation_async(
    *,
    root: Path,
    count: int | None = None,
    dry_run: bool = False,
    resume: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    study_dir = Path(settings.ncert_source_root)
    paths = staging_paths(root, dry_run=dry_run)
    p2_2_path = p2_2_mcq_path(root)
    protected_ids = load_p2_2_protected_ids(p2_2_path)
    verify_p2_2_population(p2_2_path)

    manifest = load_or_create_manifest(paths["manifest"])
    run_id = manifest["run_id"]
    batch_id = manifest["batch_id"]
    target = count or settings.p2_3_mcq_count

    existing = load_records(paths["generation"]) if resume else []
    done_slots = {r.slot_index for r in existing if r.generation_status == "GENERATED"}
    if existing and not resume:
        return {
            "status": "already_generated",
            "count": len(existing),
            "message": "Use --resume to continue or delete staging to start fresh.",
        }

    concepts = inventory_from_study_dir(study_dir)
    slots, plan_meta = build_generation_plan(concepts, total=target, seed=P2_3_SEED)
    source_map = _source_text_map(study_dir)
    budget = BudgetGuard(max_cost_usd=settings.p2_3_max_cost_usd)
    providers = resolve_generation_providers()
    records: list[McqRecord] = list(existing)

    for slot in slots:
        if slot.slot_index in done_slots:
            continue
        src_text = source_map.get(slot.concept.source_id, slot.concept.excerpt_preview)
        try:
            rec = await generate_one(
                slot,
                run_id=run_id,
                batch_id=batch_id,
                source_text=src_text,
                providers=providers,
                budget=budget,
                dry_run=dry_run,
            )
            qa_status, qa_errors = automated_qa(rec)
            rec.qa_status = qa_status
            rec.errors.extend(qa_errors)
            if qa_status == "PASS" and rec.generation_status == "GENERATED":
                rec.final_status = "INCONCLUSIVE"
            records.append(rec)
            save_records(paths["generation"], records)
        except BudgetExceededError as exc:
            manifest["stopped_reason"] = str(exc)
            break

    new_ids = [r.question_id for r in records if r.origin == "p2_3_generation"]
    assert_p2_2_not_regenerated(question_ids=new_ids, protected=protected_ids)

    manifest.update(
        {
            "generation_plan": plan_meta,
            "generated_count": len(records),
            "dry_run": dry_run,
            "budget": budget.summary(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    paths["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "run_id": run_id,
        "generated": len(records),
        "structurally_valid": sum(1 for r in records if r.qa_status == "PASS"),
        "dry_run": dry_run,
        "budget": budget.summary(),
    }


async def run_validation_async(*, root: Path, resume: bool = False, dry_run: bool = False) -> dict[str, Any]:
    settings = get_settings()
    study_dir = Path(settings.ncert_source_root)
    paths = staging_paths(root, dry_run=dry_run)
    p2_2_path = p2_2_mcq_path(root)
    protected_stems = load_p2_2_protected_stems(p2_2_path)

    records = load_records(paths["generation"])
    if not records:
        return {"status": "no_generation_records"}

    existing_val = load_records(paths["validation"]) if resume and paths["validation"].exists() else []
    validated_ids = {r.question_id for r in existing_val if r.validator_provider}
    if existing_val and resume:
        by_id = {r.question_id: r for r in records}
        for vr in existing_val:
            if vr.question_id in by_id:
                by_id[vr.question_id] = vr
        records = list(by_id.values())

    classify_duplicates(records, protected_stems=protected_stems)

    budget = BudgetGuard(max_cost_usd=settings.p2_3_max_cost_usd)
    cache = RecoveryCache(paths["base"] / "cache")

    if dry_run:
        for rec in records:
            if rec.qa_status != "PASS" or rec.question_id in validated_ids:
                continue
            bundle = resolve_independent_validator_for(rec.generation_provider)
            rec.validation_status = "INCONCLUSIVE"
            rec.validator_provider = bundle[1] if bundle else "dry-run"
            rec.validator_reason = "dry_run_skip"
        save_records(paths["validation"], records)
        return {"status": "dry_run_validation", "count": len(records)}

    semaphore = asyncio.Semaphore(6)

    async def _one(rec: McqRecord) -> McqRecord:
        if rec.qa_status != "PASS":
            return rec
        if rec.question_id in validated_ids and rec.validator_provider and not any(
            "same_provider" in str(e) for e in rec.errors
        ):
            return rec
        bundle = resolve_independent_validator_for(rec.generation_provider)
        if not bundle:
            rec.validation_status = "INCONCLUSIVE"
            rec.validator_reason = "INDEPENDENT VALIDATION BLOCKED"
            if "no_independent_provider" not in rec.errors:
                rec.errors.append("no_independent_provider")
            return rec
        provider_inst, provider_name, model = bundle
        async with semaphore:
            excerpt = _load_ncert_excerpt(study_dir, rec.source_file, rec.source_page)
            cache_key = f"p2_3:{rec.question_id}:{rec.source_excerpt_hash}:{provider_name}"
            cached = cache.get(rec.source_excerpt_hash, cache_key, provider_name)
            if cached and cached.get("status"):
                rec.validator_provider = provider_name
                rec.validation_status = cached.get("status") or "INCONCLUSIVE"  # type: ignore[assignment]
                rec.final_status = rec.validation_status
                rec.provenance["validation"] = cached
                return rec
            try:
                rec = await validate_record(
                    rec,
                    provider_inst=provider_inst,
                    provider_name=provider_name,
                    model=model,
                    ncert_excerpt=excerpt,
                    budget=budget,
                )
                cache.put(
                    rec.source_excerpt_hash,
                    cache_key,
                    provider_name,
                    {
                        "validator": rec.provenance.get("validation", {}),
                        "status": rec.validation_status,
                    },
                )
            except BudgetExceededError:
                rec.validation_status = "INCONCLUSIVE"
                rec.errors.append("budget_exceeded")
            return rec

    records = await asyncio.gather(*[_one(r) for r in records])
    records = list(records)
    save_records(paths["validation"], records)

    ready = sum(1 for r in records if r.validation_status == "READY")
    return {
        "status": "validated",
        "count": len(records),
        "ready": ready,
        "routing": "cross_provider",
        "budget": budget.summary(),
    }


def run_gold_sample(*, root: Path, count: int = GOLD_SAMPLE_SIZE, dry_run: bool = False) -> dict[str, Any]:
    paths = staging_paths(root, dry_run=dry_run)
    records = load_records(paths["validation"]) or load_records(paths["generation"])
    sample = select_gold_sample(records, seed=GOLD_SEED, target=count)
    write_human_gold_csv(paths["human_gold"], sample)
    docs_csv = root / "docs/content-factory/P2_3_HUMAN_GOLD_SAMPLE.csv"
    write_human_gold_csv(docs_csv, sample)
    return {"sample_size": len(sample), "path": str(paths["human_gold"])}


def run_report(*, root: Path) -> dict[str, Any]:
    settings = get_settings()
    paths = staging_paths(root)
    p2_2_path = p2_2_mcq_path(root)
    records = load_records(paths["validation"]) or load_records(paths["generation"])
    manifest = load_or_create_manifest(paths["manifest"])
    report = build_pilot_report(
        records=records,
        manifest=manifest,
        p2_2_info=verify_p2_2_population(p2_2_path),
        usd_inr=settings.p2_3_usd_inr,
    )
    write_pilot_report(root, report, paths)
    return report


def run_generation(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_generation_async(**kwargs))


def run_validation(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_validation_async(**kwargs))
