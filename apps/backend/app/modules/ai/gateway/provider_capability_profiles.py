"""Provider+model-keyed capability profiles (rate limits, token caps,
default retries) — MCQ-FACTORY-PROVIDER-AGNOSTIC-001.

Mirrors ``pricing.py``'s ``(provider, model) -> PriceRate`` dict pattern
exactly, for the same reason: Groq's two models (openai/gpt-oss-20b
generation, openai/gpt-oss-120b verification) and a second provider's
model must be able to carry DIFFERENT rate-limit/token-cap/retry numbers
without one overwriting the other, the same way ``pricing.py`` already
lets Groq's and a second provider's per-token prices coexist.

This module is intentionally NOT wired into
``mcq_factory_groq_controls.GroqFactoryLimits`` — that dataclass still
reads the existing, unchanged ``mcq_factory_groq_*`` Settings fields via
``GroqFactoryLimits.from_settings`` / ``.pilot_profile``, and this task's
constraint is "keep all actual numeric values exactly as they are for
Groq (don't change real behavior)". ``seed_default_groq_profiles`` below
copies those exact numbers into this generalized structure so Groq's
real behavior is represented here too, but nothing currently reads this
module at runtime for Groq's own calls — it exists so a second
provider/model's rate-limit/token-cap numbers have somewhere to live
that cannot collide with Groq's, which is the structural gap this task
asked to close. A future caller that wants a SECOND provider's own rate
limiter (distinct from the orchestrator's single, shared
``SlidingWindowRateLimiter``) can call ``get_capability_profile`` instead
of reading ``mcq_factory_groq_rate_limit_rpm`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapabilityProfile:
    rate_limit_requests_per_minute: int
    rate_limit_tokens_per_minute: int
    max_retries: int
    max_tokens_per_call: int

    def __post_init__(self) -> None:
        if self.rate_limit_requests_per_minute <= 0 or self.rate_limit_tokens_per_minute <= 0:
            raise ValueError("rate limits must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.max_tokens_per_call <= 0:
            raise ValueError("max_tokens_per_call must be positive")


_PROFILES: dict[tuple[str, str], ProviderCapabilityProfile] = {}


def register_capability_profile(provider: str, model: str, profile: ProviderCapabilityProfile) -> None:
    """Register (or overwrite) one (provider, model)'s capability
    profile. Distinct keys never collide — this is the whole point: a
    second provider/model pair's numbers coexist with Groq's."""
    _PROFILES[(provider, model)] = profile


def get_capability_profile(provider: str, model: str) -> ProviderCapabilityProfile | None:
    """Return the registered profile for (provider, model), or ``None``
    if nothing was ever registered for that exact pair — callers must
    decide their own fallback (e.g. a conservative default), never
    silently borrow a different provider's numbers."""
    return _PROFILES.get((provider, model))


# ---------------------------------------------------------------------------
# NEET-MCQ-FACTORY-OPENROUTER-PRODUCTIONIZED-20261013 — hardcoded, KNOWN-GOOD
# (provider, model) profiles this codebase ships with. Unlike
# ``seed_default_groq_profiles`` below (which reads live ``Settings`` and
# therefore must never be relied on for a fixed numeric fact, since a
# different test/process could construct ``Settings`` differently and the
# "never overwrite" rule would then freeze in whichever value happened to
# seed first), the entries here are PURE CONSTANTS with no settings
# dependency at all — safe to seed unconditionally, in any order, from any
# number of call sites, with zero cross-test leakage risk.
# ---------------------------------------------------------------------------

_KNOWN_FIXED_PROFILES: dict[tuple[str, str], ProviderCapabilityProfile] = {
    # nvidia/nemotron-3-super-120b-a12b:free (via OpenRouter) is a
    # REASONING model — it spends tokens on invisible chain-of-thought
    # before emitting visible output. Groq's 900/700 generation/
    # verification caps (tuned for a non-reasoning model) intermittently
    # produced empty/truncated output at this cap, causing
    # GENERATION_MALFORMED_JSON rejections (see
    # docs/quality/neet_mcq_factory_OPENROUTER_FIXED_MODEL_RESULT_20261013.md).
    # 4000 is the EXACT value a real, $0-cost live test run confirmed
    # reliably fixes this: real completion-token usage observed was
    # 1015-2350 for generation, 148-1093 for verification — comfortably
    # under 4000 every time across 10/10 real facts processed. This model
    # is used for BOTH the generation and verification call sites in that
    # real run, so one (provider, model) entry covers both stages (see
    # ``GroqFactoryLimits.from_stage_selections``, which looks this profile
    # up independently per stage by that stage's own resolved
    # (provider, model) pair).
    #
    # rate_limit_requests_per_minute / rate_limit_tokens_per_minute below
    # are conservative, UNMEASURED placeholders (same convention as
    # SlidingWindowRateLimiter's own module docstring) — NOT the real
    # OpenRouter per-minute limit (the real, confirmed constraint observed
    # live was a 50-requests/DAY free-tier cap, a different axis this
    # per-minute profile does not model). They are inert today: nothing
    # currently reads them for OpenRouter's rate limiting (the
    # orchestrator's shared SlidingWindowRateLimiter is still built from
    # GroqFactoryLimits' settings-driven rpm/tpm, unchanged by this
    # profile) — only max_tokens_per_call is consumed by
    # GroqFactoryLimits.from_stage_selections today. Update before any
    # future caller starts reading the rate fields for real.
    ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free"): ProviderCapabilityProfile(
        rate_limit_requests_per_minute=20,
        rate_limit_tokens_per_minute=100_000,
        max_retries=3,
        max_tokens_per_call=4000,
    ),
    # MCQ-FACTORY-KRUTRIM-001 — ("krutrim", "Krutrim-spectre-v2"). Unlike
    # the nemotron entry above, this 4000/4000 cap is NOT backed by any
    # real observed completion-token usage for this model (zero live
    # Krutrim calls have been made anywhere in this codebase/task) — it is
    # a PRECAUTIONARY default, deliberately the safer/larger of the two
    # existing conventions (Groq's non-reasoning-tuned 900/700 default vs.
    # nemotron's reasoning-model-tuned 4000/4000), chosen because nothing
    # is yet known about whether Krutrim-spectre-v2 behaves like a
    # reasoning model that burns invisible chain-of-thought tokens before
    # emitting visible output. Replace with a real, observed-usage-backed
    # value (same discipline as the nemotron entry) before relying on this
    # number for anything beyond a small, capped pilot run.
    #
    # rate_limit_requests_per_minute / rate_limit_tokens_per_minute are
    # likewise conservative, UNMEASURED placeholders (same caveat as the
    # nemotron entry's own rate fields) — no real Krutrim per-minute rate
    # limit has been confirmed. Only max_tokens_per_call is consumed by
    # GroqFactoryLimits.from_stage_selections today.
    ("krutrim", "Krutrim-spectre-v2"): ProviderCapabilityProfile(
        rate_limit_requests_per_minute=20,
        rate_limit_tokens_per_minute=100_000,
        max_retries=3,
        max_tokens_per_call=4000,
    ),
    # MCQ-FACTORY-DEEPSEEK-001 — ("deepseek", "deepseek-flash"). Same
    # PRECAUTIONARY-default reasoning as the Krutrim entry above: zero
    # live DeepSeek calls have been made anywhere in this codebase/task,
    # so there is no real observed completion-token usage to tune this
    # cap from. Deliberately reuses the same safer/larger 4000/4000
    # convention (rather than Groq's non-reasoning-tuned 900/700 default)
    # since nothing is yet known about deepseek-flash's actual visible-
    # output token usage for this factory's prompts. Replace with a real,
    # observed-usage-backed value before relying on this number for
    # anything beyond a small, capped pilot run.
    #
    # rate_limit_requests_per_minute / rate_limit_tokens_per_minute are
    # likewise conservative, UNMEASURED placeholders — no real DeepSeek
    # per-minute rate limit has been confirmed. Only max_tokens_per_call
    # is consumed by GroqFactoryLimits.from_stage_selections today.
    ("deepseek", "deepseek-flash"): ProviderCapabilityProfile(
        rate_limit_requests_per_minute=20,
        rate_limit_tokens_per_minute=100_000,
        max_retries=3,
        max_tokens_per_call=4000,
    ),
}


def seed_known_fixed_profiles() -> None:
    """Idempotently register every hardcoded, known-good (provider, model)
    profile this codebase ships with (currently just the OpenRouter
    nemotron entry above). Safe to call from any code path, any number of
    times, in any order — these are constants, not settings-derived, so
    "never overwrite an existing registration" can never freeze in a
    wrong/stale value the way it could for a settings-driven seed. Never
    overwrites a profile some caller/test already explicitly registered
    for that exact key (e.g. a test that wants to exercise a DIFFERENT
    numeric profile for this same (provider, model) pair on purpose)."""
    for key, profile in _KNOWN_FIXED_PROFILES.items():
        if key not in _PROFILES:
            _PROFILES[key] = profile


# Seed eagerly at import time too, so any caller that only imports
# get_capability_profile (without ever calling seed_known_fixed_profiles
# itself) still sees the known-good entries above.
seed_known_fixed_profiles()


def seed_default_groq_profiles(settings) -> None:
    """Idempotently register Groq's two existing models' profiles,
    copied verbatim from the Settings fields
    ``mcq_factory_groq_rate_limit_rpm`` / ``_tpm`` / ``_max_retries`` and
    the stage-specific token caps (``mcq_factory_groq_max_generation_tokens``
    / ``_max_verification_tokens``) — i.e. the SAME numbers
    ``GroqFactoryLimits.from_settings`` already uses, just represented
    per (provider, model) here. Never overwrites a profile some caller
    (or a test simulating a second provider) already registered for that
    exact (provider, model) key.
    """
    gen_key = ("groq", settings.groq_generation_model)
    if gen_key not in _PROFILES:
        _PROFILES[gen_key] = ProviderCapabilityProfile(
            rate_limit_requests_per_minute=settings.mcq_factory_groq_rate_limit_rpm,
            rate_limit_tokens_per_minute=settings.mcq_factory_groq_rate_limit_tpm,
            max_retries=settings.mcq_factory_groq_max_retries,
            max_tokens_per_call=settings.mcq_factory_groq_max_generation_tokens,
        )
    verify_key = ("groq", settings.groq_verification_model)
    if verify_key not in _PROFILES:
        _PROFILES[verify_key] = ProviderCapabilityProfile(
            rate_limit_requests_per_minute=settings.mcq_factory_groq_rate_limit_rpm,
            rate_limit_tokens_per_minute=settings.mcq_factory_groq_rate_limit_tpm,
            max_retries=settings.mcq_factory_groq_max_retries,
            max_tokens_per_call=settings.mcq_factory_groq_max_verification_tokens,
        )


__all__ = [
    "ProviderCapabilityProfile",
    "register_capability_profile",
    "get_capability_profile",
    "seed_default_groq_profiles",
    "seed_known_fixed_profiles",
]
