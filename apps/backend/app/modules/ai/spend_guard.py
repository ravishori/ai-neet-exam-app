"""Persistent, concurrency-safe daily USD spend cap for one AI agent_type,
backed by ``ai.ai_requests`` (AIRequestLog) — see docs/ai/study-planner.md.

Why a plain ``SELECT SUM(estimated_cost_usd) ... WHERE created_at >= today``
followed by "if under the cap, proceed" is NOT safe on its own: two
concurrent requests can both read the same (still-under-cap) sum before
either one's real cost is logged, and both proceed, overshooting the cap.
The real cost is only known AFTER the (slow, network-bound) AI call
returns, so the check has to happen before that -- there is no way to
check-and-log atomically around the call itself.

This closes that race with two things together:
1. A Postgres advisory transaction lock (``pg_advisory_xact_lock``), keyed
   per agent_type, held ONLY for the brief check-and-reserve step (never
   across the outbound HTTP call) -- serializes concurrent callers' reads
   of "today's spend so far" so they can't both act on the same stale sum.
2. Immediately committing a reservation row (an ordinary AIRequestLog row,
   ``success=False``, tagged with the WORST-CASE cost of the call about to
   be made) before releasing the lock -- so a second caller's own check,
   running after the first's lock is released but before the first's real
   call has returned, still sees the reservation and is correctly blocked
   if it would push the total over the cap.

Caller contract: call ``reserve_spend`` before the AI call; if it returns
``None``, do not call the provider (go straight to the deterministic
fallback). If it returns a reservation id, make the call, then ALWAYS call
``release_reservation`` afterward (success or failure) so the placeholder
never lingers once the real AIRequestLog row (written by
AIGateway._log) reflects the actual cost. A reservation that is never
released (process crash between reserve and release) inflates that day's
total until midnight UTC, when the window naturally resets -- an accepted,
documented, self-healing edge case, not treated as a bug worth a
background sweeper for a feature capped at $1-2/day by default.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.gateway.pricing import estimate_cost
from app.modules.ai.models import AIRequestLog

_RESERVATION_MODEL_TAG = "reserved"


def _utc_day_start():
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def worst_case_cost_usd(provider: str, model: str, max_tokens: int) -> float:
    """Conservative upper bound: prices BOTH prompt and completion tokens
    at ``max_tokens`` (the true prompt is far smaller in practice) using
    that (provider, model)'s registered rate. Falls back to a small fixed
    constant when no rate is registered at all, rather than treating an
    unknown rate as "free" -- an unregistered rate must never translate to
    an unbounded reservation-less budget."""
    estimate = estimate_cost(provider, model, max_tokens, max_tokens)
    if estimate.cost_status == "UNAVAILABLE":
        return 0.01
    return estimate.cost_usd


async def reserve_spend(
    session: AsyncSession, *, agent_type: str, limit_usd: float, cost_usd: float
) -> uuid.UUID | None:
    """Returns the reservation row's id if ``cost_usd`` fits within
    ``limit_usd`` given today's spend so far, else ``None`` (caller must
    not proceed to call the provider). ``limit_usd <= 0`` always returns
    ``None`` -- a non-positive cap means "no AI spend allowed", not
    "unlimited".

    Does not wrap its own body in an extra savepoint: StudyPlannerService
    treats any exception from this function as "spend check unavailable,
    fall back to the deterministic plan" without needing one (see its own
    docstring) -- a real mid-query DB failure here is the same class of
    problem as the database being unavailable for any other part of the
    request, and is left to surface as an ordinary request failure
    exactly like every other DB-backed endpoint in this app, rather than
    adding nested-transaction machinery whose only job would be papering
    over that one scenario."""
    if limit_usd <= 0:
        return None

    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"ai_spend:{agent_type}"})
    since = _utc_day_start()
    result = await session.execute(
        select(func.coalesce(func.sum(AIRequestLog.estimated_cost_usd), 0)).where(
            AIRequestLog.agent_type == agent_type, AIRequestLog.created_at >= since
        )
    )
    spent_so_far = float(result.scalar_one())
    if spent_so_far + cost_usd > limit_usd:
        await session.commit()  # release the advisory lock without leaving an open transaction
        return None

    reservation = AIRequestLog(
        agent_type=agent_type,
        user_id=None,
        model=_RESERVATION_MODEL_TAG,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost_usd=cost_usd,
        latency_ms=0,
        is_fallback=False,
        success=False,
        error_message="spend-cap reservation pending a real AI call",
    )
    session.add(reservation)
    await session.flush()
    await session.commit()
    return reservation.id


async def release_reservation(session: AsyncSession, reservation_id: uuid.UUID | None) -> None:
    """No-op if ``reservation_id`` is None (the cap was disabled, or the
    call never got a reservation in the first place)."""
    if reservation_id is None:
        return
    await session.execute(delete(AIRequestLog).where(AIRequestLog.id == reservation_id))
    await session.commit()
