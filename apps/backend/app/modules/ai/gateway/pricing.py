"""Configuration-driven token pricing — not hard-coded inside generation loops.

cost_status:
  ESTIMATED — known rate table applied
  UNAVAILABLE — no rate configured (factory budget must fail closed)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PriceRate:
    input_per_million: float
    output_per_million: float


# Approximate public list prices (USD / 1M tokens) — observability, not billing-grade.
_RATES: dict[tuple[str, str], PriceRate] = {
    ("anthropic", "claude-sonnet-4-6"): PriceRate(3.0, 15.0),
    ("anthropic", "claude-3-5-sonnet-latest"): PriceRate(3.0, 15.0),
    ("openai", "gpt-4o-mini"): PriceRate(0.15, 0.60),
    ("openai", "gpt-4o"): PriceRate(2.50, 10.0),
    # OpenAI API pricing — GPT-5 mini (text); observability only, not billing-grade.
    ("openai", "gpt-5-mini"): PriceRate(0.25, 2.0),
    ("gemini", "gemini-2.0-flash"): PriceRate(0.10, 0.40),
    ("gemini", "gemini-1.5-flash"): PriceRate(0.075, 0.30),
    # Google Gemini API pricing — gemini-2.5-flash text/image/video tier (ai.google.dev).
    ("gemini", "gemini-2.5-flash"): PriceRate(0.30, 2.50),
    # Google Gemini API Standard paid pricing — gemini-3.6-flash text (ai.google.dev); observability only.
    ("gemini", "gemini-3.6-flash"): PriceRate(0.75, 3.75),
    ("mistral", "mistral-small-latest"): PriceRate(0.10, 0.30),
    ("mistral", "mistral-large-latest"): PriceRate(2.0, 6.0),
    # Mistral docs — Mistral Small 4 API id mistral-small-2603.
    ("mistral", "mistral-small-2603"): PriceRate(0.15, 0.60),
}


@dataclass
class CostEstimate:
    cost_usd: float
    cost_status: str  # ESTIMATED | UNAVAILABLE
    input_tokens: int
    output_tokens: int
    total_tokens: int


def estimate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> CostEstimate:
    rate = _RATES.get((provider, model))
    total = int(prompt_tokens or 0) + int(completion_tokens or 0)
    if rate is None:
        return CostEstimate(
            cost_usd=0.0,
            cost_status="UNAVAILABLE",
            input_tokens=int(prompt_tokens or 0),
            output_tokens=int(completion_tokens or 0),
            total_tokens=total,
        )
    cost = (prompt_tokens * rate.input_per_million + completion_tokens * rate.output_per_million) / 1_000_000
    return CostEstimate(
        cost_usd=cost,
        cost_status="ESTIMATED",
        input_tokens=int(prompt_tokens or 0),
        output_tokens=int(completion_tokens or 0),
        total_tokens=total,
    )


def register_rate(provider: str, model: str, rate: PriceRate) -> None:
    _RATES[(provider, model)] = rate
