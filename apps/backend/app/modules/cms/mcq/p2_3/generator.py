"""P2.3 MCQ generation — reuses P2.2 provider patterns."""

from __future__ import annotations

import json
import uuid

from app.modules.ai.gateway.base import AIProvider, GenerateRequest, ProviderError
from app.modules.ai.gateway.pricing import estimate_cost
from app.modules.cms.mcq.p2_3.schemas import P2_3_GENERATION_PROMPT, GenerationSlot, McqRecord
from app.modules.cms.pyq.p2_2.budget import BudgetGuard
from app.modules.cms.pyq.p2_2.live_mcq import _parse_json


def build_generation_prompt(slot: GenerationSlot, source_text: str) -> str:
    return json.dumps(
        {
            "concept_blueprint": slot.to_dict(),
            "ncert_excerpt": source_text[:4500],
            "requirements": {
                "question_type": slot.question_type,
                "difficulty": slot.difficulty,
                "source_support": "NCERT-SUPPORTED only",
                "options": 4,
                "correct_answers": 1,
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def _record_from_slot(slot: GenerationSlot, *, run_id: str, batch_id: str) -> McqRecord:
    qid = f"p3-mcq-{slot.slot_index:04d}-{uuid.uuid4().hex[:8]}"
    c = slot.concept
    return McqRecord(
        question_id=qid,
        run_id=run_id,
        batch_id=batch_id,
        slot_index=slot.slot_index,
        concept_id=c.concept_id,
        subject=c.subject,
        class_level=c.class_level,
        chapter=c.chapter,
        topic=c.topic,
        question_type=slot.question_type,
        difficulty=slot.difficulty,
        source_id=c.source_id,
        source_locator=c.source_locator,
        source_file=c.source_file,
        source_page=c.source_page,
        source_excerpt_hash=c.source_excerpt_hash,
        generation_provider=slot.generation_provider,
        origin="p2_3_generation",
    )


async def generate_one(
    slot: GenerationSlot,
    *,
    run_id: str,
    batch_id: str,
    source_text: str,
    providers: dict[str, tuple[AIProvider, str]],
    budget: BudgetGuard,
    dry_run: bool = False,
) -> McqRecord:
    rec = _record_from_slot(slot, run_id=run_id, batch_id=batch_id)
    if dry_run:
        rec.question = f"[DRY-RUN] {slot.question_type} question on {rec.topic}?"
        rec.options = {"A": "opt A", "B": "opt B", "C": "opt C", "D": "opt D"}
        rec.correct_option = "A"
        rec.explanation = "Dry-run explanation placeholder for QA pipeline testing."
        rec.source_support = "NCERT-SUPPORTED"
        rec.generation_model = "dry-run"
        rec.generation_status = "GENERATED"
        rec.provenance["dry_run"] = True
        return rec

    prov_name = slot.generation_provider
    if prov_name not in providers:
        rec.generation_status = "FAILED"
        rec.errors.append(f"provider_unavailable:{prov_name}")
        return rec

    provider, model = providers[prov_name]
    rec.generation_model = model
    budget.check()
    req = GenerateRequest(
        system_prompt=P2_3_GENERATION_PROMPT,
        user_prompt=build_generation_prompt(slot, source_text),
        max_tokens=1800,
        model=model,
        require_json=True,
        correlation_id=rec.question_id,
    )
    try:
        resp = await provider.generate_request(req)
        body = _parse_json(resp.text)
        if body.get("status") == "REJECTED":
            rec.generation_status = "REJECTED"
            rec.errors.append(body.get("reason") or "model_rejected")
            return rec
        rec.question = body.get("question") or ""
        rec.options = {k: str(body["options"][k]) for k in "ABCD" if k in body.get("options", {})}
        rec.correct_option = (body.get("correct_answer") or "").upper()
        rec.explanation = body.get("explanation") or ""
        rec.topic = body.get("topic") or rec.topic
        rec.difficulty = (body.get("difficulty") or rec.difficulty).upper()
        rec.source_support = body.get("source_support") or "NCERT-SUPPORTED"
        rec.generation_status = "GENERATED"
        cost_est = estimate_cost(prov_name, resp.model, resp.prompt_tokens, resp.completion_tokens)
        cost = float(resp.cost_usd or 0.0)
        if cost <= 0 and cost_est.cost_status == "ESTIMATED":
            cost = cost_est.cost_usd
        rec.cost_usd += cost
        rec.provenance["generation"] = {
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
            "model": resp.model,
            "cost_usd": cost,
        }
        budget.record(
            track="P2.3_generation",
            provider=prov_name,
            model=resp.model,
            candidate_id=rec.question_id,
            cost_usd=cost,
            status=rec.generation_status,
        )
    except (ProviderError, json.JSONDecodeError, KeyError, TypeError) as exc:
        rec.generation_status = "FAILED"
        rec.errors.append(str(exc)[:200])
    return rec
