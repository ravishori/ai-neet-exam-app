"""Independent MCQ validator for P2.2-R1."""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import Settings, get_settings
from app.modules.ai.gateway.base import AIProvider, GenerateRequest
from app.modules.ai.gateway.openai_provider import OpenAIProvider
from app.modules.ai.gateway.pricing import estimate_cost
from app.modules.ai.gateway.registry import build_registry_from_settings
from app.modules.cms.pyq.p2_2.r1_validation.schemas import VALIDATOR_SYSTEM_PROMPT


def resolve_validator_provider(settings: Settings | None = None) -> tuple[AIProvider, str, str] | None:
    """Return (provider_instance, provider_name, model) or None if unavailable."""
    settings = settings or get_settings()
    if settings.openai_api_key and settings.openai_enabled:
        model = "gpt-4o-mini"
        try:
            probe = OpenAIProvider(settings.openai_api_key, model)
            return probe, "openai", model
        except Exception:
            pass
    registry = build_registry_from_settings(settings)
    for name in ("openai", "anthropic"):
        entry = registry.get(name)
        if not entry or entry.status != "AVAILABLE" or not entry.instance:
            continue
        if name == "openai" and entry.model.startswith("gpt-5"):
            inst = OpenAIProvider(settings.openai_api_key, "gpt-4o-mini")
            return inst, "openai", "gpt-4o-mini"
        return entry.instance, name, entry.model
    return None


def parse_validator_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    for key in ("overall", "stem", "correct_answer", "explanation", "ncert_support", "ambiguity", "duplicate_risk", "difficulty"):
        if key in data and data[key] not in ("PASS", "FAIL", "INCONCLUSIVE"):
            data[key] = "INCONCLUSIVE"
    return data


def build_validator_user_prompt(row: dict[str, Any], *, ncert_excerpt: str) -> str:
    return json.dumps(
        {
            "mcq_to_validate": {
                "question_id": row.get("mcq_id"),
                "question": row.get("question"),
                "options": row.get("options"),
                "proposed_answer": row.get("correct_answer"),
                "explanation": row.get("explanation"),
                "difficulty": row.get("difficulty"),
                "topic": row.get("topic"),
                "subject": row.get("subject"),
                "class": row.get("class"),
                "chapter": row.get("chapter"),
            },
            "ncert_source": {
                "file": row.get("source_file"),
                "page": row.get("source_page"),
                "excerpt": ncert_excerpt[:4500],
            },
        },
        ensure_ascii=False,
        indent=2,
    )


async def validate_one(
    provider: AIProvider,
    *,
    provider_name: str,
    model: str,
    row: dict[str, Any],
    ncert_excerpt: str,
) -> tuple[dict[str, Any], float, dict[str, Any]]:
    req = GenerateRequest(
        system_prompt=VALIDATOR_SYSTEM_PROMPT,
        user_prompt=build_validator_user_prompt(row, ncert_excerpt=ncert_excerpt),
        max_tokens=1800,
        model=model,
        require_json=True,
        correlation_id=row.get("mcq_id"),
    )
    resp = await provider.generate_request(req)
    parsed = parse_validator_json(resp.text)
    cost_est = estimate_cost(provider_name, resp.model, resp.prompt_tokens, resp.completion_tokens)
    cost = float(resp.cost_usd or 0.0)
    if cost <= 0 and cost_est.cost_status == "ESTIMATED":
        cost = cost_est.cost_usd
    meta = {
        "provider": provider_name,
        "model": resp.model,
        "prompt_tokens": resp.prompt_tokens,
        "completion_tokens": resp.completion_tokens,
        "latency_ms": resp.latency_ms,
        "request_id": resp.provider_request_id,
        "cost_usd": cost,
    }
    return parsed, cost, meta
