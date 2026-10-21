"""Unit tests for MCQ-FACTORY-GROQ-CONTROLS-001 safety rails.

No network calls, no database, no live Groq client anywhere in this file.
"""

from __future__ import annotations

import pytest

from app.modules.cms.services.mcq_factory_groq_controls import (
    CheckpointEntry,
    GroqFactoryCheckpoint,
    GroqFactoryLimits,
    RetryBudget,
    RetryBudgetExceeded,
    SlidingWindowRateLimiter,
    SpendCeilingExceeded,
    SpendTracker,
    enforce_token_cap,
)

# --- GroqFactoryLimits -------------------------------------------------------


def test_limits_reject_non_positive_values():
    with pytest.raises(ValueError):
        GroqFactoryLimits(
            max_total_spend_usd=0,
            max_generation_tokens_per_question=100,
            max_verification_tokens_per_question=100,
            max_retries_per_call=1,
            rate_limit_requests_per_minute=10,
            rate_limit_tokens_per_minute=1000,
        )


def test_limits_from_settings_uses_configured_defaults():
    from app.core.config import Settings

    settings = Settings(
        database_url="postgresql+asyncpg://u:p@localhost:5432/db",
        jwt_secret="x" * 40,
    )
    limits = GroqFactoryLimits.from_settings(settings)
    assert limits.max_total_spend_usd == settings.mcq_factory_groq_max_spend_usd
    assert limits.max_generation_tokens_per_question == settings.mcq_factory_groq_max_generation_tokens
    assert limits.max_verification_tokens_per_question == settings.mcq_factory_groq_max_verification_tokens
    assert limits.max_retries_per_call == settings.mcq_factory_groq_max_retries


# --- SpendTracker -------------------------------------------------------


def test_spend_tracker_accumulates_within_ceiling():
    tracker = SpendTracker(limit_usd=10.0)
    tracker.record(3.0)
    tracker.record(4.0)
    assert tracker.spent_usd == pytest.approx(7.0)
    assert tracker.remaining_usd() == pytest.approx(3.0)


def test_spend_tracker_raises_before_exceeding_ceiling():
    tracker = SpendTracker(limit_usd=10.0)
    tracker.record(9.0)
    with pytest.raises(SpendCeilingExceeded):
        tracker.record(2.0)
    # State must not have been mutated by the rejected call.
    assert tracker.spent_usd == pytest.approx(9.0)


def test_spend_tracker_would_exceed_is_side_effect_free():
    tracker = SpendTracker(limit_usd=5.0)
    assert tracker.would_exceed(6.0) is True
    assert tracker.spent_usd == 0.0


def test_spend_tracker_rejects_negative_cost():
    tracker = SpendTracker(limit_usd=5.0)
    with pytest.raises(ValueError):
        tracker.record(-1.0)


# --- per-question token caps -------------------------------------------------


def test_enforce_token_cap_clamps_to_cap():
    assert enforce_token_cap(requested_max_tokens=5000, cap=900, stage="generation") == 900


def test_enforce_token_cap_allows_under_cap():
    assert enforce_token_cap(requested_max_tokens=500, cap=900, stage="generation") == 500


def test_enforce_token_cap_rejects_non_positive_request():
    with pytest.raises(ValueError):
        enforce_token_cap(requested_max_tokens=0, cap=900, stage="verification")


# --- RetryBudget --------------------------------------------------------


def test_retry_budget_consumes_up_to_max():
    budget = RetryBudget(max_retries=2)
    assert budget.consume() == 1
    assert budget.consume() == 2
    assert budget.exhausted is True


def test_retry_budget_raises_past_max():
    budget = RetryBudget(max_retries=1)
    budget.consume()
    with pytest.raises(RetryBudgetExceeded):
        budget.consume()


def test_retry_budget_zero_retries_is_immediately_exhausted():
    budget = RetryBudget(max_retries=0)
    assert budget.exhausted is True
    with pytest.raises(RetryBudgetExceeded):
        budget.consume()


# --- SlidingWindowRateLimiter --------------------------------------------


def test_rate_limiter_allows_calls_within_budget():
    clock = {"t": 0.0}
    limiter = SlidingWindowRateLimiter(
        requests_per_minute=5, tokens_per_minute=1000, clock=lambda: clock["t"]
    )
    assert limiter.wait_time_s(tokens=100) == 0.0
    limiter.record(tokens=100)
    assert limiter.in_flight_requests() == 1


def test_rate_limiter_blocks_when_request_count_exceeded():
    clock = {"t": 0.0}
    limiter = SlidingWindowRateLimiter(
        requests_per_minute=2, tokens_per_minute=100000, clock=lambda: clock["t"]
    )
    limiter.record(tokens=1)
    limiter.record(tokens=1)
    # Third request within the same window must wait.
    wait = limiter.wait_time_s(tokens=1)
    assert wait > 0.0


def test_rate_limiter_blocks_when_token_budget_exceeded():
    clock = {"t": 0.0}
    limiter = SlidingWindowRateLimiter(
        requests_per_minute=1000, tokens_per_minute=100, clock=lambda: clock["t"]
    )
    limiter.record(tokens=90)
    wait = limiter.wait_time_s(tokens=50)
    assert wait > 0.0


def test_rate_limiter_window_expires_old_events():
    clock = {"t": 0.0}
    limiter = SlidingWindowRateLimiter(
        requests_per_minute=1, tokens_per_minute=100000, window_s=60.0, clock=lambda: clock["t"]
    )
    limiter.record(tokens=1)
    assert limiter.wait_time_s(tokens=1) > 0.0
    clock["t"] = 61.0  # advance past the window
    assert limiter.wait_time_s(tokens=1) == 0.0


def test_rate_limiter_rejects_non_positive_limits():
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(requests_per_minute=0, tokens_per_minute=100)


# --- GroqFactoryCheckpoint ------------------------------------------------


def test_checkpoint_round_trips_and_resumes(tmp_path):
    path = tmp_path / "checkpoint.json"
    cp = GroqFactoryCheckpoint(path, batch_id="batch-1")
    assert cp.is_done("fact-1") is False

    cp.record(CheckpointEntry(fact_id="fact-1", attempt_number=1, status="GENERATED", cost_usd=0.01))
    assert cp.is_done("fact-1") is True
    assert cp.total_spent_usd() == pytest.approx(0.01)

    # Simulate a fresh process resuming from the same file.
    resumed = GroqFactoryCheckpoint(path, batch_id="batch-1")
    assert resumed.is_done("fact-1") is True
    assert resumed.total_spent_usd() == pytest.approx(0.01)
    entry = resumed.get("fact-1")
    assert entry is not None
    assert entry.status == "GENERATED"


def test_checkpoint_different_batch_id_at_same_path_is_ignored(tmp_path):
    path = tmp_path / "checkpoint.json"
    cp1 = GroqFactoryCheckpoint(path, batch_id="batch-1")
    cp1.record(CheckpointEntry(fact_id="fact-1", attempt_number=1, status="GENERATED", cost_usd=1.0))

    cp2 = GroqFactoryCheckpoint(path, batch_id="batch-2")
    assert cp2.is_done("fact-1") is False
    assert cp2.total_spent_usd() == 0.0


def test_checkpoint_rehydrated_spend_tracker_prevents_double_spend(tmp_path):
    path = tmp_path / "checkpoint.json"
    cp = GroqFactoryCheckpoint(path, batch_id="batch-1")
    cp.record(CheckpointEntry(fact_id="fact-1", attempt_number=1, status="GENERATED", cost_usd=8.0))

    resumed = GroqFactoryCheckpoint(path, batch_id="batch-1")
    tracker = resumed.rehydrated_spend_tracker(limit_usd=10.0)
    assert tracker.spent_usd == pytest.approx(8.0)
    with pytest.raises(SpendCeilingExceeded):
        tracker.record(3.0)  # 8 + 3 > 10
