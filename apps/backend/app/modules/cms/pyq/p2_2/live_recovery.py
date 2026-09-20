"""Track A — live multi-provider PYQ source recovery."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.modules.cms.pyq.p2_2.budget import BudgetGuard
from app.modules.cms.pyq.p2_2.cache import RecoveryCache
from app.modules.cms.pyq.p2_2.consensus import compare_providers
from app.modules.cms.pyq.p2_2.deterministic import attempt_deterministic_recovery
from app.modules.cms.pyq.p2_2.evidence import build_evidence_package, canonical_hash
from app.modules.cms.pyq.p2_2.providers import AIRecoveryProvider, GatewayRecoveryProvider
from app.modules.cms.pyq.p2_2.schemas import AIRecoveryOutput, TriageResult
from app.modules.cms.pyq.p2_2.validation import validate_against_source

_VALIDATOR_ROTATION = ("anthropic", "openai", "gemini")


def _field_agreement(outputs: list[AIRecoveryOutput]) -> dict[str, Any]:
    if not outputs:
        return {}
    fields = ["stem"] + [f"option_{i}" for i in range(1, 5)]
    recovered = [o for o in outputs if o.status == "RECOVERED"]
    if len(recovered) < 2:
        return {"overall": "SINGLE_PROVIDER", "fields": {}}
    agreements: dict[str, float] = {}
    for field in fields:
        vals = []
        for o in recovered:
            if field == "stem":
                vals.append(o.stem.strip())
            else:
                vals.append(o.options.get(field.split("_")[1], "").strip())
        if not vals:
            continue
        matches = sum(1 for v in vals if v == vals[0])
        agreements[field] = round(matches / len(vals), 3)
    overall = sum(agreements.values()) / len(agreements) if agreements else 0.0
    return {"overall": round(overall, 3), "fields": agreements}


def _validator_provider(recovery_provider: str) -> str:
    for p in _VALIDATOR_ROTATION:
        if p != recovery_provider:
            return p
    return "anthropic"


async def _recover_with_cache(
    provider: AIRecoveryProvider,
    *,
    evidence: dict[str, Any],
    candidate_id: str,
    cache: RecoveryCache,
    attempt: int = 1,
) -> tuple[AIRecoveryOutput, dict[str, Any]]:
    source_hash = evidence.get("source_evidence_hash") or ""
    req_hash = canonical_hash({"provider": provider.name, "live": True})
    cached = cache.get(source_hash, req_hash, provider.name)
    if cached:
        output = AIRecoveryOutput(
            status=cached.get("status", "INCONCLUSIVE"),
            stem=cached.get("stem", ""),
            options=cached.get("options") or {},
            changed_fields=cached.get("changed_fields") or [],
            source_evidence_used=cached.get("source_evidence_used") or [],
            uncertainties=cached.get("uncertainties") or [],
            foreign_text_detected=bool(cached.get("foreign_text_detected")),
            confidence=float(cached.get("confidence") or 0.0),
        )
        return output, cached.get("attempt") or {"provider": provider.name, "cached": True}
    output, attempt_rec = await provider.recover(evidence=evidence, candidate_id=candidate_id, attempt=attempt)
    meta = {
        "provider": attempt_rec.provider,
        "model": attempt_rec.model,
        "status": attempt_rec.status,
        "request_id": attempt_rec.request_id,
        "latency_ms": attempt_rec.latency_ms,
        "prompt_tokens": attempt_rec.prompt_tokens,
        "completion_tokens": attempt_rec.completion_tokens,
        "cost_usd": attempt_rec.cost_usd,
        "error": attempt_rec.error,
    }
    cache.put(source_hash, req_hash, provider.name, {**output.to_dict(), "attempt": meta})
    return output, meta


async def process_live_recovery_candidate(
    *,
    record: dict[str, Any],
    triage: TriageResult,
    evidence: dict[str, Any],
    providers: dict[str, AIRecoveryProvider],
    budget: BudgetGuard,
    cache: RecoveryCache,
) -> dict[str, Any]:
    budget.check()
    qid = triage.question_id
    result: dict[str, Any] = {
        "question_id": qid,
        "original_status": triage.original_status,
        "triage": {"category": triage.category, "reason": triage.reason},
        "source_evidence_hash": evidence.get("source_evidence_hash"),
        "human_verdict": "PENDING",
        "providers": [],
        "validations": [],
    }

    if triage.category in ("SOURCE_INSUFFICIENT", "HUMAN_REVIEW"):
        result["recovery_status"] = "INCONCLUSIVE" if triage.category == "HUMAN_REVIEW" else "NOT_RECOVERABLE"
        result["verification_status"] = "HUMAN_REVIEW" if triage.category == "HUMAN_REVIEW" else "NOT_APPLICABLE"
        result["human_verdict"] = "HUMAN_INCONCLUSIVE"
        return result

    det = attempt_deterministic_recovery(record)
    if det and det.status == "RECOVERED":
        verdict, grade, reasons = validate_against_source(det, evidence, original=record)
        result["deterministic"] = det.to_dict()
        result["recovery_status"] = "DETERMINISTIC_RECOVERED"
        result["verification_status"] = "VERIFIED" if verdict == "PASS" else verdict
        result["source_fidelity"] = grade
        result["validation_reasons"] = reasons
        result["consensus"] = "SINGLE_PROVIDER"
        return result

    outputs: list[AIRecoveryOutput] = []
    provider_rows: list[dict[str, Any]] = []
    for name, prov in providers.items():
        try:
            out, meta = await _recover_with_cache(prov, evidence=evidence, candidate_id=qid, cache=cache)
            outputs.append(out)
            provider_rows.append({"provider": name, **meta, "recovery_status": out.status, "confidence": out.confidence})
            budget.record(
                track="A_recovery",
                provider=name,
                model=str(meta.get("model") or prov.model),
                candidate_id=qid,
                cost_usd=float(meta.get("cost_usd") or 0.0),
                status=out.status,
            )
        except Exception as exc:  # noqa: BLE001
            provider_rows.append({"provider": name, "status": "error", "error": str(exc)[:200]})

    result["providers"] = provider_rows
    result["consensus"] = compare_providers(outputs)
    result["field_agreement"] = _field_agreement(outputs)

    primary = next((o for o in outputs if o.status == "RECOVERED"), outputs[0] if outputs else None)
    if not primary:
        result["recovery_status"] = "NOT_RECOVERABLE"
        result["verification_status"] = "NOT_APPLICABLE"
        return result

    result["recovered"] = primary.to_dict()
    result["recovery_status"] = primary.status if primary.status != "RECOVERED" else "AI_RECOVERED"

    validations: list[dict[str, Any]] = []
    for prow in provider_rows:
        pname = prow.get("provider")
        if not pname or pname not in providers:
            continue
        out = next((o for i, o in enumerate(outputs) if provider_rows[i].get("provider") == pname), None)
        if not out:
            continue
        verdict, grade, reasons = validate_against_source(out, evidence, original=record)
        validations.append({"validator": "ocr_deterministic", "provider": pname, "verdict": verdict, "grade": grade, "reasons": reasons})
    result["validations"] = validations
    best = validations[0] if validations else {"verdict": "INCONCLUSIVE", "grade": "INCONCLUSIVE", "reasons": []}
    result["verification_status"] = "VERIFIED" if best["verdict"] == "PASS" else best["verdict"]
    result["source_fidelity"] = best.get("grade", "INCONCLUSIVE")
    result["validation_reasons"] = best.get("reasons", [])
    if result["consensus"] == "DISAGREEMENT":
        result["verification_status"] = "HUMAN_REVIEW"
    return result


async def run_recovery_track(
    *,
    cohort: list[TriageResult],
    records_by_id: dict[str, dict[str, Any]],
    evidence_builder,
    providers: dict[str, AIRecoveryProvider],
    budget: BudgetGuard,
    cache: RecoveryCache,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tr in cohort:
        rec = records_by_id[tr.question_id]
        evidence = evidence_builder(rec)
        row = await process_live_recovery_candidate(
            record=rec,
            triage=tr,
            evidence=evidence,
            providers=providers,
            budget=budget,
            cache=cache,
        )
        results.append(row)
        if budget.stopped:
            break

    by_provider: dict[str, dict[str, int]] = {}
    for row in results:
        for p in row.get("providers") or []:
            name = p.get("provider") or "unknown"
            by_provider.setdefault(name, {"processed": 0, "recovered": 0, "validated": 0, "failed": 0})
            by_provider[name]["processed"] += 1
            if p.get("recovery_status") == "RECOVERED":
                by_provider[name]["recovered"] += 1
        vs = row.get("verification_status")
        if vs == "VERIFIED":
            for name in by_provider:
                by_provider[name]["validated"] += 0
        if vs == "FAILED":
            pass

    stats = {
        "candidates": len(cohort),
        "processed": len(results),
        "ai_recovered": sum(1 for r in results if r.get("recovery_status") == "AI_RECOVERED"),
        "deterministic_recovered": sum(1 for r in results if r.get("recovery_status") == "DETERMINISTIC_RECOVERED"),
        "verified": sum(1 for r in results if r.get("verification_status") == "VERIFIED"),
        "failed": sum(1 for r in results if r.get("verification_status") == "FAILED"),
        "inconclusive": sum(1 for r in results if r.get("verification_status") == "INCONCLUSIVE"),
        "human_review": sum(1 for r in results if r.get("verification_status") == "HUMAN_REVIEW"),
        "provider_disagreement": sum(1 for r in results if r.get("consensus") == "DISAGREEMENT"),
        "by_provider": by_provider,
        "human_verdict_pending": sum(1 for r in results if r.get("human_verdict") == "PENDING"),
    }
    return results, stats
