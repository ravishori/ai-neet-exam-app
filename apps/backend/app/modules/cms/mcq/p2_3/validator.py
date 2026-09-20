"""P2.3 independent validation with cross-provider routing."""

from __future__ import annotations

from typing import Any

from app.modules.ai.gateway.pricing import estimate_cost
from app.modules.cms.mcq.p2_3.provider_routing import (
    assert_cross_provider,
    is_same_provider_validation,
    resolve_validator_bundle,
)
from app.modules.cms.mcq.p2_3.qa import map_validator_to_status
from app.modules.cms.mcq.p2_3.schemas import McqRecord
from app.modules.cms.pyq.p2_2.r1_validation.validator import validate_one


def record_to_validator_row(rec: McqRecord) -> dict[str, Any]:
    return {
        "mcq_id": rec.question_id,
        "question": rec.question,
        "options": rec.options,
        "correct_answer": rec.correct_option,
        "explanation": rec.explanation,
        "difficulty": rec.difficulty,
        "topic": rec.topic,
        "subject": rec.subject,
        "class": rec.class_level,
        "chapter": rec.chapter,
        "source_file": rec.source_file,
        "source_page": rec.source_page,
        "source_hash": rec.source_excerpt_hash,
        "generation_provider": rec.generation_provider,
    }


def validation_cost_usd(meta: dict[str, Any], *, provider_name: str, model: str) -> float:
    """Extract validation cost from meta; estimate when API returns zero."""
    cost = float(meta.get("cost_usd") or 0.0)
    if cost > 0:
        return cost
    pt = int(meta.get("prompt_tokens") or 0)
    ct = int(meta.get("completion_tokens") or 0)
    if pt or ct:
        est = estimate_cost(provider_name, model, pt, ct)
        if est.cost_status == "ESTIMATED":
            return est.cost_usd
    return 0.0


async def validate_record(
    rec: McqRecord,
    *,
    provider_inst: Any,
    provider_name: str,
    model: str,
    ncert_excerpt: str,
    budget: Any,
    track_validation_cost: bool = True,
) -> McqRecord:
    if rec.qa_status != "PASS":
        rec.validation_status = "REJECT"
        rec.final_status = "REJECT"
        rec.validator_reason = "skipped_qa_fail"
        return rec

    if is_same_provider_validation(rec.generation_provider, provider_name):
        rec.validation_status = "INCONCLUSIVE"
        rec.final_status = "INCONCLUSIVE"
        rec.validator_reason = "same_provider_as_generator"
        if "independent_validation_blocked:same_provider" not in rec.errors:
            rec.errors.append("independent_validation_blocked:same_provider")
        return rec

    assert_cross_provider(rec.generation_provider, provider_name)

    row = record_to_validator_row(rec)
    budget.check()
    parsed, _raw_cost, meta = await validate_one(
        provider_inst,
        provider_name=provider_name,
        model=model,
        row=row,
        ncert_excerpt=ncert_excerpt,
    )
    cost = validation_cost_usd(meta, provider_name=provider_name, model=meta.get("model") or model)
    rec.validator_provider = provider_name
    rec.validator_model = meta.get("model") or model
    rec.validator_confidence = float(parsed.get("confidence") or 0.0)
    rec.validator_reason = "; ".join(str(i) for i in (parsed.get("issues") or [])[:3])
    rec.validation_status = map_validator_to_status(parsed)  # type: ignore[assignment]
    rec.final_status = rec.validation_status
    if track_validation_cost:
        rec.cost_usd += cost
    rec.provenance["validation"] = {"validator": parsed, "meta": meta, "cost_usd": cost}
    budget.record(
        track="P2.3_validation",
        provider=provider_name,
        model=model,
        candidate_id=rec.question_id,
        cost_usd=cost,
        status=rec.validation_status,
    )
    return rec


def resolve_independent_validator_for(generator_provider: str) -> tuple[Any, str, str] | None:
    return resolve_validator_bundle(generator_provider)


def resolve_independent_validator() -> tuple[Any, str, str] | None:
    """Legacy: OpenAI-only resolver (prefer resolve_independent_validator_for)."""
    return resolve_validator_bundle("gemini")
