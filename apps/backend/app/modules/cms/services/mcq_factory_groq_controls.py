"""MCQ-FACTORY-GROQ-CONTROLS-001 — cost, rate, retry and checkpoint safety
rails for the Groq-backed NEW QUESTION GENERATION pipeline
(app/modules/cms/mcq_factory_groq/).

Everything in this module is pure Python: no HTTP, no provider SDK, no
database access. It is designed so the bulk-generation CLI (see
scripts/mcq_factory_groq_bulk_run.py) and any future live-call site can
import and exercise these rails without ever constructing a network
client — every class here can be fully unit tested offline.

Design notes (mirrors the discipline documented in
docs/quality/neet_ai_assisted_recovery_pilot_proposal_20261011.md, adapted
for NEW QUESTION GENERATION rather than PYQ answer recovery):

- Hard total USD spend ceiling (``SpendTracker``) — a caller reports the
  ``cost_usd`` from each ``AIResponse`` *after* a call; the tracker raises
  before the running total would exceed the configured ceiling, so a
  caller checks it before issuing the *next* call.
- Separate, explicit per-question token caps for generation vs
  verification (``GroqFactoryLimits``) — the two stages use different
  models (openai/gpt-oss-20b vs openai/gpt-oss-120b per
  settings.groq_generation_model / groq_verification_model) and must
  never share one budget number.
- Bounded retries (``RetryBudget``) — a call that keeps failing stops
  being retried once the budget is exhausted; it does not loop forever
  and does not silently fall back to a different provider (silent
  cross-provider fallback is forbidden project-wide — see
  mcq_llm_provider.py's module docstring).
- A generic, provider-agnostic sliding-window rate limiter
  (``SlidingWindowRateLimiter``) for requests/minute and tokens/minute.
  Real Groq limits for openai/gpt-oss-20b / openai/gpt-oss-120b must be
  read from console.groq.com/docs/rate-limits and the
  ``mcq_factory_groq_rate_limit_*`` settings updated before any live run —
  the shipped defaults are conservative placeholders, not measured Groq
  limits.
- Resumable checkpointing (``GroqFactoryCheckpoint``) keyed by exactly the
  same identity triple the existing local staging table enforces
  uniqueness on — ``(batch_id, fact_id, attempt_number)``, see
  ``generation_staging_store.py``'s
  ``uq_generation_staging_candidates_batch_fact_attempt`` constraint. A
  stopped run resumes by skipping any key already recorded, and folds the
  recorded spend back into a fresh ``SpendTracker`` so a resume can never
  under-count prior spend and blow through the ceiling.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings


class SpendCeilingExceeded(RuntimeError):
    """Raised instead of ever issuing a call that would exceed the ceiling."""


class RetryBudgetExceeded(RuntimeError):
    """Raised when a caller tries to consume more retries than configured."""


# ---------------------------------------------------------------------------
# Limits (one object describing every numeric safety rail for one run)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroqFactoryLimits:
    max_total_spend_usd: float
    max_generation_tokens_per_question: int
    max_verification_tokens_per_question: int
    max_retries_per_call: int
    rate_limit_requests_per_minute: int
    rate_limit_tokens_per_minute: int

    def __post_init__(self) -> None:
        if self.max_total_spend_usd <= 0:
            raise ValueError("max_total_spend_usd must be positive")
        if self.max_generation_tokens_per_question <= 0 or self.max_verification_tokens_per_question <= 0:
            raise ValueError("per-question token caps must be positive")
        if self.max_retries_per_call < 0:
            raise ValueError("max_retries_per_call must be >= 0")
        if self.rate_limit_requests_per_minute <= 0 or self.rate_limit_tokens_per_minute <= 0:
            raise ValueError("rate limits must be positive")

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> GroqFactoryLimits:
        s = settings or get_settings()
        return cls(
            max_total_spend_usd=s.mcq_factory_groq_max_spend_usd,
            max_generation_tokens_per_question=s.mcq_factory_groq_max_generation_tokens,
            max_verification_tokens_per_question=s.mcq_factory_groq_max_verification_tokens,
            max_retries_per_call=s.mcq_factory_groq_max_retries,
            rate_limit_requests_per_minute=s.mcq_factory_groq_rate_limit_rpm,
            rate_limit_tokens_per_minute=s.mcq_factory_groq_rate_limit_tpm,
        )

    @classmethod
    def pilot_profile(cls, settings: Settings | None = None) -> GroqFactoryLimits:
        """Named pilot-profile limits for the human-authorized 100-question
        pilot run — identical to ``from_settings`` except the spend ceiling
        uses the dedicated, stricter ``settings.mcq_factory_groq_pilot_max_spend_usd``
        (default $5) instead of the general ``settings.mcq_factory_groq_max_spend_usd``
        (default $20). ``scripts/mcq_factory_groq_bulk_run.py`` defaults to
        this profile; pass ``--budget-profile general`` to opt into the
        wider ceiling instead. Rate-limit numbers are unchanged — they stay
        configurable placeholders either way (see module docstring)."""
        import dataclasses as _dc

        s = settings or get_settings()
        base = cls.from_settings(s)
        return _dc.replace(base, max_total_spend_usd=s.mcq_factory_groq_pilot_max_spend_usd)

    @classmethod
    def from_stage_selections(
        cls,
        *,
        generation_provider: str,
        generation_model: str,
        verification_provider: str,
        verification_model: str,
        settings: Settings | None = None,
    ) -> GroqFactoryLimits:
        """NEET-MCQ-FACTORY-OPENROUTER-PRODUCTIONIZED-20261013 — genuinely
        per-(provider, model) token-cap resolution, instead of always
        reading the Groq-specific ``mcq_factory_groq_max_generation_tokens``
        / ``_max_verification_tokens`` Settings fields regardless of which
        provider is actually selected.

        Reuses ``app.modules.ai.gateway.provider_capability_profiles``'s
        existing ``(provider, model) -> ProviderCapabilityProfile`` registry
        (the structure the MCQ-FACTORY-PROVIDER-AGNOSTIC-001 refactor built
        for exactly this gap) rather than a parallel mechanism: when a
        specific (provider, model) entry is registered (e.g. OpenRouter's
        ``nvidia/nemotron-3-super-120b-a12b:free``, a reasoning model that
        needs a much higher cap — see
        ``provider_capability_profiles._KNOWN_FIXED_PROFILES``), its
        ``max_tokens_per_call`` wins for that stage. When no entry exists
        for a (provider, model) pair (the case for Groq's own models today
        — deliberately NOT auto-seeded here, see note below), this falls
        back to exactly ``from_settings(s)``'s existing
        ``mcq_factory_groq_max_generation_tokens`` /
        ``_max_verification_tokens`` values — i.e. Groq's real behavior is
        completely unchanged by this method existing.

        Deliberately does NOT call ``seed_default_groq_profiles`` here:
        that helper reads LIVE ``Settings`` and "never overwrites an
        existing registration," so if it were called from this
        per-call-site classmethod, whichever test/process happened to
        seed a given (groq, model) key FIRST would silently freeze that
        token cap for every later caller using a DIFFERENT Settings
        override for the same model string — a real cross-test leakage
        hazard in a module-level mutable registry. Only the hardcoded,
        settings-independent constants in ``_KNOWN_FIXED_PROFILES`` (seeded
        unconditionally, with no leakage risk since they never vary) are
        consulted automatically here.

        For the SAME reason, a ``generation_provider``/``verification_provider``
        of exactly ``"groq"`` NEVER consults the profile registry at all —
        it always falls back to ``from_settings(s)`` directly. Some OTHER
        test file in the same process may have already called
        ``seed_default_groq_profiles`` (a test-only demonstration helper,
        never called by production code) with a DIFFERENT ``Settings``
        instance, which would otherwise leave a stale, frozen entry for
        Groq's default model string in the shared global registry — this
        explicit bypass guarantees Groq's real behavior is governed by
        live settings alone, exactly as before this method existed,
        regardless of what any other test/process seeded.
        """
        import dataclasses as _dc

        from app.modules.ai.gateway.provider_capability_profiles import get_capability_profile

        s = settings or get_settings()
        base = cls.from_settings(s)

        gen_profile = None if generation_provider == "groq" else get_capability_profile(
            generation_provider, generation_model
        )
        verify_profile = None if verification_provider == "groq" else get_capability_profile(
            verification_provider, verification_model
        )

        return _dc.replace(
            base,
            max_generation_tokens_per_question=(
                gen_profile.max_tokens_per_call
                if gen_profile is not None
                else base.max_generation_tokens_per_question
            ),
            max_verification_tokens_per_question=(
                verify_profile.max_tokens_per_call
                if verify_profile is not None
                else base.max_verification_tokens_per_question
            ),
        )

    @classmethod
    def pilot_profile_for_stage_selections(
        cls,
        *,
        generation_provider: str,
        generation_model: str,
        verification_provider: str,
        verification_model: str,
        settings: Settings | None = None,
    ) -> GroqFactoryLimits:
        """Same per-(provider, model) token-cap resolution as
        ``from_stage_selections``, but using the dedicated, stricter pilot
        spend ceiling — mirrors ``pilot_profile`` vs ``from_settings``
        exactly."""
        import dataclasses as _dc

        s = settings or get_settings()
        base = cls.from_stage_selections(
            generation_provider=generation_provider,
            generation_model=generation_model,
            verification_provider=verification_provider,
            verification_model=verification_model,
            settings=s,
        )
        return _dc.replace(base, max_total_spend_usd=s.mcq_factory_groq_pilot_max_spend_usd)


# ---------------------------------------------------------------------------
# Spend ceiling
# ---------------------------------------------------------------------------


@dataclass
class SpendTracker:
    """In-memory running-total USD spend guard.

    Never calls a provider itself — the caller reports ``cost_usd`` (taken
    from ``AIResponse.cost_usd``) after each real call via ``record()``.
    ``record()`` raises *before* mutating state when the ceiling would be
    exceeded, so the running total never silently goes over.
    """

    limit_usd: float
    spent_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.limit_usd <= 0:
            raise ValueError("limit_usd must be positive")
        if self.spent_usd < 0:
            raise ValueError("spent_usd must be >= 0")

    def would_exceed(self, cost_usd: float) -> bool:
        return (self.spent_usd + cost_usd) > self.limit_usd

    def record(self, cost_usd: float) -> None:
        if cost_usd < 0:
            raise ValueError("cost_usd must be >= 0")
        if self.would_exceed(cost_usd):
            raise SpendCeilingExceeded(
                f"Recording ${cost_usd:.4f} would bring total spend to "
                f"${self.spent_usd + cost_usd:.4f}, exceeding the "
                f"${self.limit_usd:.4f} ceiling. STOP — no further Groq "
                "calls may be made in this run."
            )
        self.spent_usd += cost_usd

    def remaining_usd(self) -> float:
        return max(0.0, self.limit_usd - self.spent_usd)


# ---------------------------------------------------------------------------
# Per-question token caps
# ---------------------------------------------------------------------------


def enforce_token_cap(*, requested_max_tokens: int, cap: int, stage: str) -> int:
    """Clamp ``requested_max_tokens`` to ``cap``. Returns the (possibly
    smaller) value a caller must actually pass to the provider. ``stage``
    is only used for error messages ('generation' | 'verification')."""
    if requested_max_tokens <= 0:
        raise ValueError(f"requested_max_tokens must be positive for stage={stage!r}")
    if cap <= 0:
        raise ValueError(f"cap must be positive for stage={stage!r}")
    return min(requested_max_tokens, cap)


# ---------------------------------------------------------------------------
# Bounded retries
# ---------------------------------------------------------------------------


@dataclass
class RetryBudget:
    max_retries: int
    attempts_used: int = 0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")

    @property
    def exhausted(self) -> bool:
        return self.attempts_used >= self.max_retries

    def consume(self) -> int:
        """Record one retry attempt. Returns the new attempt count.
        Raises ``RetryBudgetExceeded`` instead of allowing a caller to
        retry past the configured bound."""
        if self.exhausted:
            raise RetryBudgetExceeded(
                f"Retry budget of {self.max_retries} attempts is exhausted."
            )
        self.attempts_used += 1
        return self.attempts_used


# ---------------------------------------------------------------------------
# Rate limiting (generic sliding window — provider-agnostic)
# ---------------------------------------------------------------------------


class SlidingWindowRateLimiter:
    """Sliding-window limiter over both requests/window and tokens/window.

    No network calls and no sleeping on its own — ``wait_time_s()`` tells
    the caller how long it *would* need to wait; the caller decides whether
    to actually sleep (production code) or fail fast (tests). This keeps
    the limiter itself free of any blocking behaviour for unit tests.

    Real Groq per-model rate limits are NOT hardcoded here — they must be
    read from console.groq.com/docs/rate-limits for openai/gpt-oss-20b and
    openai/gpt-oss-120b and the ``mcq_factory_groq_rate_limit_rpm`` /
    ``mcq_factory_groq_rate_limit_tpm`` settings updated accordingly before
    any live run. The constructor only validates that *some* positive
    limit was supplied.
    """

    def __init__(
        self,
        *,
        requests_per_minute: int,
        tokens_per_minute: int,
        window_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if requests_per_minute <= 0 or tokens_per_minute <= 0:
            raise ValueError("rate limits must be positive")
        if window_s <= 0:
            raise ValueError("window_s must be positive")
        self._rpm = requests_per_minute
        self._tpm = tokens_per_minute
        self._window_s = window_s
        self._clock = clock
        self._lock = threading.Lock()
        self._events: list[tuple[float, int]] = []  # (timestamp, tokens)

    def _prune_locked(self, now: float) -> None:
        cutoff = now - self._window_s
        self._events = [(t, tok) for t, tok in self._events if t >= cutoff]

    def wait_time_s(self, *, tokens: int) -> float:
        """Seconds to wait before a call of ``tokens`` size would be within
        budget. ``0.0`` means the call may proceed immediately."""
        if tokens < 0:
            raise ValueError("tokens must be >= 0")
        with self._lock:
            now = self._clock()
            self._prune_locked(now)
            current_tokens = sum(tok for _, tok in self._events)
            if len(self._events) < self._rpm and current_tokens + tokens <= self._tpm:
                return 0.0
            if not self._events:
                return 0.0
            oldest_ts = self._events[0][0]
            return max(0.0, (oldest_ts + self._window_s) - now)

    def record(self, *, tokens: int) -> None:
        """Record that a call of ``tokens`` size was just made. Callers
        should call this immediately after a real request completes (or
        right before issuing one, if they prefer to budget pessimistically)."""
        if tokens < 0:
            raise ValueError("tokens must be >= 0")
        with self._lock:
            now = self._clock()
            self._prune_locked(now)
            self._events.append((now, tokens))

    def in_flight_requests(self) -> int:
        with self._lock:
            self._prune_locked(self._clock())
            return len(self._events)


# ---------------------------------------------------------------------------
# Resumable checkpointing
# ---------------------------------------------------------------------------


@dataclass
class CheckpointEntry:
    fact_id: str
    attempt_number: int
    status: str  # "GENERATED" | "VERIFIED" | "REJECTED" | "REVIEW_REQUIRED"
    cost_usd: float = 0.0


class GroqFactoryCheckpoint:
    """Resumable checkpoint file keyed by ``(batch_id, fact_id,
    attempt_number)`` — the exact identity triple
    ``generation_staging.candidates`` enforces uniqueness on (see
    ``uq_generation_staging_candidates_batch_fact_attempt`` in
    generation_staging_store.py). A key already present when a run resumes
    is never reprocessed and never re-spent.

    This is additive, local-filesystem bookkeeping (JSON, same convention
    as ``deterministic_batch_runner.write_checkpoint`` /
    ``load_checkpoint``) — it does not read or write any database.
    """

    def __init__(self, path: Path, batch_id: str) -> None:
        self._path = Path(path)
        self.batch_id = batch_id
        self._entries: dict[tuple[str, int], CheckpointEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if payload.get("batch_id") != self.batch_id:
            # Different batch_id at this path — never silently merge two
            # batches' spend/progress into one tracker.
            return
        for row in payload.get("entries", []):
            try:
                entry = CheckpointEntry(
                    fact_id=str(row["fact_id"]),
                    attempt_number=int(row["attempt_number"]),
                    status=str(row["status"]),
                    cost_usd=float(row.get("cost_usd", 0.0)),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._entries[(entry.fact_id, entry.attempt_number)] = entry

    def is_done(self, fact_id: str, attempt_number: int = 1) -> bool:
        return (fact_id, attempt_number) in self._entries

    def get(self, fact_id: str, attempt_number: int = 1) -> CheckpointEntry | None:
        return self._entries.get((fact_id, attempt_number))

    def record(self, entry: CheckpointEntry) -> None:
        self._entries[(entry.fact_id, entry.attempt_number)] = entry
        self._flush()

    def total_spent_usd(self) -> float:
        return sum(e.cost_usd for e in self._entries.values())

    def entries(self) -> list[CheckpointEntry]:
        return list(self._entries.values())

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "batch_id": self.batch_id,
            "entries": [
                {
                    "fact_id": e.fact_id,
                    "attempt_number": e.attempt_number,
                    "status": e.status,
                    "cost_usd": e.cost_usd,
                }
                for e in self._entries.values()
            ],
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def rehydrated_spend_tracker(self, limit_usd: float) -> SpendTracker:
        """Build a fresh ``SpendTracker`` for a resumed run whose starting
        ``spent_usd`` already reflects everything this checkpoint recorded
        — so resuming a stopped run can never under-count prior spend."""
        spent = self.total_spent_usd()
        return SpendTracker(limit_usd=limit_usd, spent_usd=min(spent, limit_usd))


__all__ = [
    "SpendCeilingExceeded",
    "RetryBudgetExceeded",
    "GroqFactoryLimits",
    "SpendTracker",
    "enforce_token_cap",
    "RetryBudget",
    "SlidingWindowRateLimiter",
    "CheckpointEntry",
    "GroqFactoryCheckpoint",
]
