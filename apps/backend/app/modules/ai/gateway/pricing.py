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
    # OpenAI API pricing — GPT-5.6 Luna (operator-confirmed from
    # https://developers.openai.com/api/docs/models/gpt-5.6-luna).
    # Cached input at $0.02 / MTok is not modeled here — factory cost is
    # computed from prompt_tokens / completion_tokens only; a future rate
    # extension can add a cached_input_per_million field if OpenAI starts
    # returning cached_input_tokens in the response body.
    ("openai", "gpt-5.6-luna"): PriceRate(0.20, 1.20),
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
    # Sarvam public INR rates converted at the project's ₹83/USD
    # observability rate. Cached-input pricing is not represented here.
    ("sarvam", "sarvam-105b"): PriceRate(29.28 / 83.0, 73.20 / 83.0),
    ("sarvam", "sarvam-105b-conversations"): PriceRate(29.28 / 83.0, 73.20 / 83.0),
    # MCQ-FACTORY-KRUTRIM-001 — Krutrim's real, confirmed published rate
    # (Krutrim AI Studio billing docs) is ₹6.6 per 1,000,000 tokens, for
    # BOTH input and output. Converted to USD/1M here at the project's
    # existing ₹83/USD observability rate (the same rate already used for
    # the Sarvam rows above and for settings.p2_3_usd_inr) — i.e.
    # 6.6 / 83.0 ≈ $0.0795 per 1M tokens, both directions. Observability
    # estimate only, not billing-grade.
    ("krutrim", "Krutrim-spectre-v2"): PriceRate(6.6 / 83.0, 6.6 / 83.0),
    # MCQ-FACTORY-DEEPSEEK-001 — DeepSeek's real, confirmed published rate
    # (api-docs.deepseek.com) per 1,000,000 tokens is time-of-day
    # dependent: cache-miss input $0.15 off-peak / $0.30 peak, output
    # $0.60 off-peak / $1.20 peak (peak = 01:00-04:00 and 06:00-10:00 UTC
    # Mon-Fri). PriceRate has no time-of-day axis, so the PEAK (higher,
    # more conservative) cache-miss rate is stored here as the single safe
    # default — off-peak is cheaper but every one of this project's
    # prompts includes a different evidence chunk, so a cache hit is never
    # guaranteed. Observability estimate only, not billing-grade.
    ("deepseek", "deepseek-flash"): PriceRate(0.30, 1.20),
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
