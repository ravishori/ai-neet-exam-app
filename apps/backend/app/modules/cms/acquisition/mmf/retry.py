"""Bounded slot retry for empty/retryable provider responses.

Retries fill the original allocation slot only — never inflate caps or
cross-substitute providers.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from app.modules.cms.acquisition.mmf.contract_v2 import PROVIDER_CAPS, TOTAL_CAP
from app.modules.cms.acquisition.mmf.reliability import (
    FailureClass,
    ProviderReliabilityMetrics,
    classify_provider_error,
    is_retryable,
)

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 8.0
    retry_empty: bool = True

    def backoff_for(self, attempt: int) -> float:
        # attempt is 1-indexed after a failure
        return min(self.base_backoff_seconds * (2 ** (attempt - 1)), self.max_backoff_seconds)


class AllocationCapError(ValueError):
    pass


def assert_allocation_caps(
    *,
    provider: str,
    requested: int,
    already_generated: int = 0,
    additional: int = 0,
) -> None:
    cap = PROVIDER_CAPS.get(provider)
    if cap is None:
        raise AllocationCapError(f"unknown_provider:{provider}")
    if requested > cap:
        raise AllocationCapError(f"requested_{requested}_exceeds_provider_cap_{cap}")
    if already_generated + additional > cap:
        raise AllocationCapError(
            f"would_exceed_provider_cap:{provider}:{already_generated}+{additional}>{cap}"
        )
    if already_generated + additional > TOTAL_CAP:
        raise AllocationCapError("would_exceed_total_cap_1000")


def assert_no_cross_provider_fill(provider: str, slot_provider: str) -> None:
    if provider != slot_provider:
        raise AllocationCapError(
            f"cross_provider_fill_forbidden:{slot_provider}_slot_with_{provider}"
        )


async def execute_with_retry(
    *,
    call: Callable[[], Awaitable[T]],
    is_empty: Callable[[T], bool],
    metrics: ProviderReliabilityMetrics,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> tuple[T | None, FailureClass | None]:
    """Retry only retryable empty/provider failures. Does not create extra slots."""
    policy = policy or RetryPolicy()
    sleeper = sleep or asyncio.sleep
    last_kind: FailureClass | None = None
    last_result: T | None = None

    for attempt in range(1, policy.max_attempts + 1):
        metrics.record_attempt()
        try:
            result = await call()
            last_result = result
            if is_empty(result):
                last_kind = "EMPTY_RESPONSE"
                metrics.record_failure("EMPTY_RESPONSE", "empty_response")
                if not policy.retry_empty or attempt >= policy.max_attempts:
                    break
                await sleeper(policy.backoff_for(attempt))
                continue
            metrics.record_success(1)
            return result, None
        except Exception as exc:  # noqa: BLE001 — classified below
            kind = classify_provider_error(exc)
            last_kind = kind
            metrics.record_failure(kind, str(exc))
            if not is_retryable(kind) or attempt >= policy.max_attempts:
                break
            await sleeper(policy.backoff_for(attempt))

    metrics.record_terminal(1)
    return last_result, last_kind


def empty_text_response(text: str | None) -> bool:
    return not (text or "").strip()


__all__ = [
    "AllocationCapError",
    "RetryPolicy",
    "assert_allocation_caps",
    "assert_no_cross_provider_fill",
    "empty_text_response",
    "execute_with_retry",
]
