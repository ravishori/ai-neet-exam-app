"""Track B — NCERT-grounded MCQ generation (file-only, no DB)."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from difflib import SequenceMatcher
from typing import Any

from app.modules.ai.gateway.base import AIProvider, GenerateRequest, ProviderError
from app.modules.ai.gateway.pricing import estimate_cost
from app.modules.cms.pyq.p2_2.budget import BudgetGuard
from app.modules.cms.pyq.p2_2.live_schemas import (
    MCQ_REVIEW_SYSTEM_PROMPT,
    NCERT_MCQ_SYSTEM_PROMPT,
    LiveMcqRecord,
)
from app.modules.cms.pyq.p2_2.ncert_sources import NcertPageSource
from app.modules.cms.services.factory_candidate_validation import stem_hash

_PROVIDER_ORDER = ("gemini", "openai", "anthropic")
_REVIEW_ROTATION = ("anthropic", "openai", "gemini")


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _provider_for_index(index: int) -> str:
    return _PROVIDER_ORDER[index % len(_PROVIDER_ORDER)]


def _review_provider_for_generator(generator: str) -> str:
    for p in _REVIEW_ROTATION:
        if p != generator:
            return p
    return "anthropic"


def structural_validate(body: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if body.get("status") == "REJECTED":
        return errors
    q = (body.get("question") or "").strip()
    if len(q) < 15:
        errors.append("QUESTION_TOO_SHORT")
    opts = body.get("options") or {}
    if set(opts.keys()) != {"A", "B", "C", "D"}:
        errors.append("OPTION_COUNT")
    texts = [str(opts.get(k) or "").strip() for k in "ABCD"]
    if any(not t for t in texts):
        errors.append("EMPTY_OPTION")
    if len(set(texts)) != 4:
        errors.append("DUPLICATE_OPTIONS")
    ans = (body.get("correct_answer") or "").strip().upper()
    if ans not in {"A", "B", "C", "D"}:
        errors.append("INVALID_ANSWER")
    expl = (body.get("explanation") or "").strip()
    if len(expl) < 20:
        errors.append("EXPLANATION_TOO_SHORT")
    if body.get("source_support") != "NCERT-SUPPORTED":
        errors.append("NOT_NCERT_SUPPORTED")
    diff = (body.get("difficulty") or "").upper()
    if diff not in {"EASY", "MEDIUM", "HARD"}:
        errors.append("INVALID_DIFFICULTY")
    return errors


def near_duplicate(a: str, b: str, threshold: float = 0.92) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold


def build_mcq_user_prompt(source: NcertPageSource) -> str:
    return json.dumps(
        {
            "ncert_source": {
                "file": source.relative_path,
                "subject": source.subject,
                "class": source.class_level,
                "chapter": source.chapter,
                "page": source.page,
                "excerpt": source.text[:4500],
            },
            "requirements": {
                "source_support": "NCERT-SUPPORTED only",
                "options": 4,
                "correct_answers": 1,
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def build_review_user_prompt(source: NcertPageSource, mcq: dict[str, Any]) -> str:
    return json.dumps(
        {
            "ncert_excerpt": source.text[:3500],
            "candidate_mcq": mcq,
        },
        ensure_ascii=False,
        indent=2,
    )


async def _call_provider(
    provider: AIProvider,
    *,
    provider_name: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    budget: BudgetGuard,
    track: str,
    candidate_id: str,
    max_tokens: int = 1800,
) -> tuple[str, float, dict[str, Any]]:
    budget.check()
    req = GenerateRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        model=model,
        require_json=True,
        correlation_id=candidate_id,
    )
    try:
        resp = await provider.generate_request(req)
    except ProviderError as exc:
        budget.record(
            track=track,
            provider=provider_name,
            model=model,
            candidate_id=candidate_id,
            cost_usd=0.0,
            status="error",
            error=str(exc)[:200],
        )
        raise
    cost_est = estimate_cost(provider_name, resp.model, resp.prompt_tokens, resp.completion_tokens)
    cost = float(resp.cost_usd or cost_est.cost_usd or 0.0)
    budget.record(
        track=track,
        provider=provider_name,
        model=resp.model,
        candidate_id=candidate_id,
        cost_usd=cost,
        status="ok",
    )
    meta = {
        "prompt_tokens": resp.prompt_tokens,
        "completion_tokens": resp.completion_tokens,
        "latency_ms": resp.latency_ms,
        "request_id": resp.provider_request_id,
    }
    return resp.text, cost, meta


async def generate_one_mcq(
    *,
    index: int,
    source: NcertPageSource,
    providers: dict[str, tuple[AIProvider, str]],
    budget: BudgetGuard,
    semaphore: asyncio.Semaphore,
) -> LiveMcqRecord:
    async with semaphore:
        gen_name = _provider_for_index(index)
        provider, model = providers[gen_name]
        mcq_id = f"mcq-{index:04d}-{uuid.uuid4().hex[:8]}"
        rec = LiveMcqRecord(
            mcq_id=mcq_id,
            provider=gen_name,
            model=model,
            status="REJECTED",
            subject=source.subject,
            class_level=source.class_level,
            chapter=source.chapter,
            topic="",
            source_file=source.relative_path,
            source_page=source.page,
            source_hash=source.text_hash,
        )
        try:
            raw, cost, meta = await _call_provider(
                provider,
                provider_name=gen_name,
                model=model,
                system_prompt=NCERT_MCQ_SYSTEM_PROMPT,
                user_prompt=build_mcq_user_prompt(source),
                budget=budget,
                track="B_generation",
                candidate_id=mcq_id,
            )
            rec.cost_usd += cost
            rec.provenance["generation"] = meta
            body = _parse_json(raw)
            if body.get("status") == "REJECTED":
                rec.errors.append(body.get("reason") or "model_rejected")
                rec.status = "REJECTED"
                return rec
            errors = structural_validate(body)
            if errors:
                rec.errors.extend(errors)
                rec.status = "REJECTED"
                return rec
            rec.question = body["question"]
            rec.options = {k: str(body["options"][k]) for k in "ABCD"}
            rec.correct_answer = body["correct_answer"].upper()
            rec.explanation = body["explanation"]
            rec.topic = body.get("topic") or f"chapter-{source.chapter or 'unknown'}"
            rec.difficulty = body.get("difficulty", "MEDIUM").upper()
            rec.question_type = body.get("question_type") or "conceptual"
            rec.source_support = body.get("source_support") or "NCERT-SUPPORTED"
            rec.status = "GENERATED"

            rev_name = _review_provider_for_generator(gen_name)
            rev_provider, rev_model = providers[rev_name]
            try:
                review_raw, rev_cost, rev_meta = await _call_provider(
                    rev_provider,
                    provider_name=rev_name,
                    model=rev_model,
                    system_prompt=MCQ_REVIEW_SYSTEM_PROMPT,
                    user_prompt=build_review_user_prompt(
                        source,
                        {
                            "question": rec.question,
                            "options": rec.options,
                            "correct_answer": rec.correct_answer,
                            "explanation": rec.explanation,
                        },
                    ),
                    budget=budget,
                    track="B_review",
                    candidate_id=f"{mcq_id}-review",
                )
                rec.cost_usd += rev_cost
                rec.review_provider = rev_name
                rec.provenance["review"] = rev_meta
                review = _parse_json(review_raw)
                rec.review_verdict = review.get("verdict", "INCONCLUSIVE")
                if review.get("verdict") == "PASS" and review.get("ncert_supported") is True:
                    rec.status = "VALIDATED"
                elif review.get("verdict") == "FAIL":
                    rec.status = "REJECTED"
                    rec.errors.extend(review.get("issues") or ["review_fail"])
                else:
                    rec.status = "INCONCLUSIVE"
                if review.get("ambiguous"):
                    rec.status = "HUMAN_REVIEW"
            except Exception as rev_exc:  # noqa: BLE001
                rec.review_verdict = "INCONCLUSIVE"
                rec.status = "GENERATED"
                rec.errors.append(f"review_unavailable:{str(rev_exc)[:120]}")
            return rec
        except Exception as exc:  # noqa: BLE001
            rec.errors.append(str(exc)[:200])
            rec.status = "REJECTED"
            return rec


async def run_mcq_track(
    *,
    sources: list[NcertPageSource],
    providers: dict[str, tuple[AIProvider, str]],
    budget: BudgetGuard,
    concurrency: int = 6,
) -> tuple[list[LiveMcqRecord], dict[str, Any]]:
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        generate_one_mcq(index=i, source=s, providers=providers, budget=budget, semaphore=semaphore)
        for i, s in enumerate(sources)
    ]
    records = await asyncio.gather(*tasks)
    stem_hashes: dict[str, str] = {}
    exact_dup = near_dup = semantic_dup = 0
    for rec in records:
        if not rec.question:
            continue
        h = stem_hash(rec.question)
        if h in stem_hashes:
            exact_dup += 1
            rec.errors.append("exact_duplicate")
            if rec.status == "VALIDATED":
                rec.status = "REJECTED"
            continue
        for _, other_q in stem_hashes.items():
            if near_duplicate(rec.question, other_q):
                near_dup += 1
                rec.errors.append("near_duplicate")
                if rec.status == "VALIDATED":
                    rec.status = "REJECTED"
                break
        stem_hashes[h] = rec.question

    stats = {
        "generated": len(records),
        "structurally_valid": sum(1 for r in records if r.question and len(r.options) == 4),
        "validated": sum(1 for r in records if r.status == "VALIDATED"),
        "rejected": sum(1 for r in records if r.status == "REJECTED"),
        "inconclusive": sum(1 for r in records if r.status == "INCONCLUSIVE"),
        "generated_pending_review": sum(1 for r in records if r.status == "GENERATED"),
        "human_review": sum(1 for r in records if r.status == "HUMAN_REVIEW"),
        "exact_duplicate_count": exact_dup,
        "near_duplicate_count": near_dup,
        "semantic_duplicate_count": semantic_dup,
        "cost_usd": round(sum(r.cost_usd for r in records), 6),
    }
    return list(records), stats
