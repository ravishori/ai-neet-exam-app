"""P2.2 AI-assisted source recovery pipeline."""

from __future__ import annotations

import asyncio
import json
import random
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.cms.pyq.p2_2.cache import RecoveryCache
from app.modules.cms.pyq.p2_2.consensus import compare_providers
from app.modules.cms.pyq.p2_2.deterministic import attempt_deterministic_recovery
from app.modules.cms.pyq.p2_2.evidence import (
    build_evidence_package,
    canonical_hash,
    check_source_availability,
    neighbor_summaries,
)
from app.modules.cms.pyq.p2_2.providers import AIRecoveryProvider, DryRunRecoveryProvider
from app.modules.cms.pyq.p2_2.schemas import AIRecoveryOutput, RecoveryRecord, TriageResult
from app.modules.cms.pyq.p2_2.triage import question_id, triage_population
from app.modules.cms.pyq.p2_2.validation import validate_against_source

PILOT_TARGET = 75
PILOT_MIN = 50
PILOT_MAX = 100
CONFIDENCE_ESCALATION_THRESHOLD = 0.55


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def index_by_qid(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {question_id(r): r for r in records}


def build_neighbors_index(records: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        by_page[int(rec.get("source_page") or 0)].append(rec)
    return by_page


def load_c_grade_ids(audit_json: Path) -> set[str]:
    if not audit_json.exists():
        return set()
    data = json.loads(audit_json.read_text(encoding="utf-8"))
    cases = data.get("fidelity_sample", {}).get("cases") or []
    return {c["question_id"] for c in cases if c.get("grade") == "C"}


def triage_summary(results: list[TriageResult]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for r in results:
        counts[r.category] += 1
    return dict(counts)


def select_pilot_cohort(
    triage_results: list[TriageResult],
    records_by_id: dict[str, dict[str, Any]],
    *,
    target: int = PILOT_TARGET,
    seed: int = 42,
) -> list[TriageResult]:
    """Stratified pilot selection across triage categories and defect types."""
    rng = random.Random(seed)
    buckets: dict[str, list[TriageResult]] = defaultdict(list)
    for tr in triage_results:
        if tr.category == "SOURCE_INSUFFICIENT":
            continue
        rec = records_by_id.get(tr.question_id, {})
        key = tr.category
        if "diagram_dependent" in tr.known_defects:
            key = f"{key}:diagram"
        elif any(m.startswith("option_") for m in tr.missing_fields):
            key = f"{key}:missing_options"
        elif "mathematical" in tr.reason:
            key = f"{key}:math"
        elif "layout" in tr.reason or "boundary" in tr.reason:
            key = f"{key}:layout"
        elif "chemistry" in tr.reason:
            key = f"{key}:chem"
        year = str(rec.get("exam_year") or "unknown")
        key = f"{key}:y{year}"
        buckets[key].append(tr)

    selected: list[TriageResult] = []
    bucket_keys = list(buckets.keys())
    rng.shuffle(bucket_keys)
    per_bucket = max(1, target // max(len(bucket_keys), 1))
    for key in bucket_keys:
        pool = buckets[key][:]
        rng.shuffle(pool)
        selected.extend(pool[:per_bucket])

    seen = {s.question_id for s in selected}
    remaining = [t for t in triage_results if t.category != "SOURCE_INSUFFICIENT" and t.question_id not in seen]
    rng.shuffle(remaining)
    while len(selected) < target and remaining:
        selected.append(remaining.pop())
    if len(selected) > target:
        rng.shuffle(selected)
        selected = selected[:target]
    if len(selected) > PILOT_MAX:
        rng.shuffle(selected)
        selected = selected[:PILOT_MAX]
    if len(selected) < PILOT_MIN:
        extra = [t for t in triage_results if t.category != "SOURCE_INSUFFICIENT" and t.question_id not in seen]
        rng.shuffle(extra)
        for t in extra:
            if len(selected) >= PILOT_MIN:
                break
            if t.question_id not in seen:
                selected.append(t)
                seen.add(t.question_id)
    return selected


def _request_hash(evidence: dict[str, Any], provider_name: str) -> str:
    return canonical_hash({"provider": provider_name, "evidence_hash": evidence.get("source_evidence_hash")})


def _route_verification(
    *,
    recovery_status: str,
    validation_verdict: str,
    confidence: float,
    consensus: str | None,
    triage_category: str,
) -> str:
    if recovery_status in ("NOT_RECOVERABLE",):
        return "NOT_APPLICABLE"
    if triage_category == "HUMAN_REVIEW":
        return "HUMAN_REVIEW"
    if consensus == "DISAGREEMENT":
        return "HUMAN_REVIEW"
    if validation_verdict == "FAIL":
        return "FAILED"
    if validation_verdict == "PASS" and confidence >= CONFIDENCE_ESCALATION_THRESHOLD:
        return "VERIFIED"
    if validation_verdict == "INCONCLUSIVE" or recovery_status == "INCONCLUSIVE":
        return "INCONCLUSIVE"
    return "PENDING"


async def process_candidate(
    record: dict[str, Any],
    triage: TriageResult,
    *,
    evidence: dict[str, Any],
    primary: AIRecoveryProvider,
    secondary: AIRecoveryProvider | None,
    cache: RecoveryCache,
) -> RecoveryRecord:
    source_hash = evidence.get("source_evidence_hash") or ""
    req_hash = _request_hash(evidence, primary.name)
    rec = RecoveryRecord(
        question_id=triage.question_id,
        source_evidence_hash=source_hash,
        recovery_request_hash=req_hash,
        original_status=triage.original_status,
        triage={"category": triage.category, "reason": triage.reason, "missing_fields": triage.missing_fields},
        evidence_package={"question_id": evidence.get("question_id"), "page": evidence.get("page"), "known_defects": evidence.get("known_defects")},
    )

    if triage.category == "SOURCE_INSUFFICIENT":
        rec.recovery_status = "NOT_RECOVERABLE"
        rec.verification_status = "NOT_APPLICABLE"
        rec.uncertainties = [triage.reason]
        return rec

    if triage.category == "HUMAN_REVIEW":
        rec.recovery_status = "INCONCLUSIVE"
        rec.verification_status = "HUMAN_REVIEW"
        rec.uncertainties = [triage.reason]
        return rec

    outputs: list[AIRecoveryOutput] = []
    provider_entries: list[dict[str, Any]] = []

    if triage.category == "DETERMINISTIC_RECOVERABLE":
        det = attempt_deterministic_recovery(record)
        if det and det.status == "RECOVERED":
            rec.recovery_status = "DETERMINISTIC_RECOVERED"
            rec.recovered_fields = {"stem": det.stem, "options": det.options}
            rec.changes = det.changed_fields
            verdict, grade, reasons = validate_against_source(det, evidence, original=record)
            rec.source_fidelity = grade
            rec.verification_status = _route_verification(
                recovery_status="DETERMINISTIC_RECOVERED",
                validation_verdict=verdict,
                confidence=det.confidence,
                consensus="SINGLE_PROVIDER",
                triage_category=triage.category,
            )
            rec.uncertainties = det.uncertainties + reasons
            provider_entries.append(
                {
                    "provider": "deterministic",
                    "model": "reparse-v1",
                    "status": det.status,
                    "confidence": det.confidence,
                }
            )
            rec.providers = provider_entries
            rec.consensus = "SINGLE_PROVIDER"
            return rec

    cached = cache.get(source_hash, req_hash, primary.name)
    if cached:
        output = AIRecoveryOutput(**{k: cached[k] for k in ("status", "stem", "options", "changed_fields", "source_evidence_used", "uncertainties", "foreign_text_detected", "confidence") if k in cached})
        attempt_meta = cached.get("attempt") or {}
    else:
        output, attempt = await primary.recover(evidence=evidence, candidate_id=triage.question_id)
        attempt_meta = {
            "provider": attempt.provider,
            "model": attempt.model,
            "candidate_id": attempt.candidate_id,
            "attempt": attempt.attempt,
            "timestamp": attempt.timestamp,
            "status": attempt.status,
            "request_id": attempt.request_id,
            "latency_ms": attempt.latency_ms,
        }
        cache.put(
            source_hash,
            req_hash,
            primary.name,
            {**output.to_dict(), "attempt": attempt_meta},
        )
    outputs.append(output)
    provider_entries.append(
        {
            "provider": attempt_meta.get("provider", primary.name),
            "model": attempt_meta.get("model", primary.model),
            "status": output.status,
            "confidence": output.confidence,
        }
    )

    if (
        secondary
        and output.status == "RECOVERED"
        and output.confidence < CONFIDENCE_ESCALATION_THRESHOLD
    ):
        sec_hash = _request_hash(evidence, secondary.name)
        sec_cached = cache.get(source_hash, sec_hash, secondary.name)
        if sec_cached:
            sec_out = AIRecoveryOutput(**{k: sec_cached[k] for k in ("status", "stem", "options", "changed_fields", "source_evidence_used", "uncertainties", "foreign_text_detected", "confidence") if k in sec_cached})
            sec_meta = sec_cached.get("attempt") or {}
        else:
            sec_out, sec_attempt = await secondary.recover(evidence=evidence, candidate_id=triage.question_id, attempt=2)
            sec_meta = {
                "provider": sec_attempt.provider,
                "model": sec_attempt.model,
                "status": sec_attempt.status,
                "request_id": sec_attempt.request_id,
                "latency_ms": sec_attempt.latency_ms,
            }
            cache.put(source_hash, sec_hash, secondary.name, {**sec_out.to_dict(), "attempt": sec_meta})
        outputs.append(sec_out)
        provider_entries.append(
            {
                "provider": sec_meta.get("provider", secondary.name),
                "model": sec_meta.get("model", secondary.model),
                "status": sec_out.status,
                "confidence": sec_out.confidence,
            }
        )

    consensus = compare_providers(outputs)
    rec.consensus = consensus
    rec.providers = provider_entries

    primary_out = outputs[0]
    if primary_out.status == "RECOVERED":
        rec.recovery_status = "AI_RECOVERED"
        rec.recovered_fields = {"stem": primary_out.stem, "options": primary_out.options}
        rec.changes = primary_out.changed_fields
        rec.foreign_text_detected = primary_out.foreign_text_detected
    elif primary_out.status == "NOT_RECOVERABLE":
        rec.recovery_status = "NOT_RECOVERABLE"
    else:
        rec.recovery_status = "INCONCLUSIVE"

    verdict, grade, reasons = validate_against_source(primary_out, evidence, original=record)
    rec.source_fidelity = grade
    rec.uncertainties = list(primary_out.uncertainties) + reasons
    rec.verification_status = _route_verification(
        recovery_status=rec.recovery_status,
        validation_verdict=verdict,
        confidence=primary_out.confidence,
        consensus=consensus,
        triage_category=triage.category,
    )
    return rec


async def run_pilot_async(
    *,
    r3_dir: Path,
    output_dir: Path,
    audit_json: Path,
    zip_path: Path | None = None,
    primary: AIRecoveryProvider | None = None,
    secondary: AIRecoveryProvider | None = None,
    pilot_size: int = PILOT_TARGET,
    seed: int = 42,
) -> dict[str, Any]:
    questions_path = r3_dir / "questions.p2_1e_full.jsonl"
    words_path = r3_dir / "ocr.words.p2_1e_full.jsonl"
    records = load_jsonl(questions_path)
    records_by_id = index_by_qid(records)
    neighbors_index = build_neighbors_index(records)
    c_grade_ids = load_c_grade_ids(audit_json)

    source_availability: dict[str, dict[str, bool]] = {}
    for rec in records:
        qid = question_id(rec)
        source_availability[qid] = check_source_availability(rec, zip_path=zip_path, words_path=words_path)

    triage_results = triage_population(records, c_grade_ids=c_grade_ids, source_availability=source_availability)
    pilot_cohort = select_pilot_cohort(triage_results, records_by_id, target=pilot_size, seed=seed)

    output_dir.mkdir(parents=True, exist_ok=True)
    cache = RecoveryCache(output_dir / "cache")
    primary = primary or DryRunRecoveryProvider()
    secondary = secondary or DryRunRecoveryProvider()

    recovery_records: list[RecoveryRecord] = []
    for tr in pilot_cohort:
        rec = records_by_id[tr.question_id]
        page = int(rec.get("source_page") or 0)
        qnum = int(rec.get("question_number") or 0)
        avail = source_availability.get(tr.question_id, {})
        evidence = build_evidence_package(
            rec,
            words_path=words_path,
            neighbors=neighbor_summaries(neighbors_index, page=page, qnum=qnum),
            source_image_available=avail.get("has_pdf", False),
        )
        recovery_records.append(
            await process_candidate(
                rec,
                tr,
                evidence=evidence,
                primary=primary,
                secondary=secondary if primary.name != secondary.name else None,
                cache=cache,
            )
        )

    records_path = output_dir / "recovery_records.jsonl"
    with records_path.open("w", encoding="utf-8") as fh:
        for rr in recovery_records:
            fh.write(json.dumps(rr.to_dict(), ensure_ascii=False) + "\n")

    quality_counts = Counter(r.get("p2_1e_quality_status") for r in records)
    triage_counts = triage_summary(triage_results)
    pilot_stats = _pilot_stats(recovery_records)

    report = {
        "phase": "P2.2",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "dry_run" if isinstance(primary, DryRunRecoveryProvider) else "live",
        "r3_input": {
            "questions": len(records),
            "VALID": quality_counts.get("VALID", 0),
            "PARTIAL": quality_counts.get("PARTIAL", 0),
        },
        "triage": triage_counts,
        "pilot": pilot_stats,
        "c_grade_population": len(c_grade_ids),
        "triage_population": len(triage_results),
        "pilot_candidates": [r.question_id for r in pilot_cohort],
        "production_db_writes": 0,
        "r3_modified": False,
    }

    manifest = {
        **report,
        "artifacts": {
            "recovery_records": str(records_path),
            "cache_dir": str(output_dir / "cache"),
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return report


def _pilot_stats(records: list[RecoveryRecord]) -> dict[str, Any]:
    stats: Counter[str] = Counter()
    fidelity: Counter[str] = Counter()
    for r in records:
        stats[r.recovery_status] += 1
        stats[f"verification:{r.verification_status}"] += 1
        fidelity[r.source_fidelity] += 1
        if r.consensus == "DISAGREEMENT":
            stats["provider_disagreement"] += 1
        if r.verification_status == "HUMAN_REVIEW":
            stats["human_review"] += 1
        if r.verification_status == "FAILED":
            stats["false_recovery"] += 1
    unanimous = sum(1 for r in records if r.consensus == "UNANIMOUS")
    with_consensus = sum(1 for r in records if r.consensus in ("UNANIMOUS", "MAJORITY", "DISAGREEMENT"))
    agreement_pct = round(100.0 * unanimous / with_consensus, 1) if with_consensus else 0.0
    return {
        "candidates": len(records),
        "processed": len(records),
        "deterministic_recovered": stats.get("DETERMINISTIC_RECOVERED", 0),
        "ai_recovered": stats.get("AI_RECOVERED", 0),
        "verified": stats.get("verification:VERIFIED", 0),
        "inconclusive": stats.get("INCONCLUSIVE", 0) + stats.get("verification:INCONCLUSIVE", 0),
        "not_recoverable": stats.get("NOT_RECOVERABLE", 0),
        "human_review": stats.get("human_review", 0),
        "provider_disagreement": stats.get("provider_disagreement", 0),
        "false_recovery": stats.get("false_recovery", 0),
        "source_fidelity": dict(fidelity),
        "provider_agreement_pct": agreement_pct,
        "cost_usd": 0.0,
    }


def run_pilot(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_pilot_async(**kwargs))


def build_triage_artifact(
    *,
    r3_dir: Path,
    audit_json: Path,
    zip_path: Path | None = None,
) -> dict[str, Any]:
    questions_path = r3_dir / "questions.p2_1e_full.jsonl"
    words_path = r3_dir / "ocr.words.p2_1e_full.jsonl"
    records = load_jsonl(questions_path)
    c_grade_ids = load_c_grade_ids(audit_json)
    source_availability: dict[str, dict[str, bool]] = {}
    for rec in records:
        qid = question_id(rec)
        source_availability[qid] = check_source_availability(rec, zip_path=zip_path, words_path=words_path)
    results = triage_population(records, c_grade_ids=c_grade_ids, source_availability=source_availability)
    return {
        "phase": "P2.2",
        "generated_at": datetime.now(UTC).isoformat(),
        "population": {
            "partial_and_c_grade": len(results),
            "c_grade_ids": len(c_grade_ids),
        },
        "summary": triage_summary(results),
        "records": [
            {
                "question_id": r.question_id,
                "category": r.category,
                "reason": r.reason,
                "original_status": r.original_status,
                "missing_fields": r.missing_fields,
                "known_defects": r.known_defects,
            }
            for r in results
        ],
    }
