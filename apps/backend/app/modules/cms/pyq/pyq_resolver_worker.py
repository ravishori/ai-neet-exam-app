"""FACTORY-PYQ-P5 — background scheduler for the deterministic NCERT-grounded
PYQ answer resolver (scripts/resolve_pyq_answers.py). No new resolution
algorithm here: this module only adds scheduling, batching, and a
cross-restart/cross-instance lock around the existing, already-idempotent
resolve_up_to()/resolve_batch() functions.

Behavior:
  - Every tick, process at most settings.pyq_resolver_batch_size oldest
    ANSWER_PENDING questions (created_at ASC) — a strict per-window cap,
    not a floor: even with a large backlog, this tick never processes more
    than the cap, and the next tick never starts early. There is no
    catch-up behavior — a full batch does NOT trigger an immediate retick;
    the worker always waits the full settings.pyq_resolver_interval_hours
    before its next tick, full batch or not.
  - A Redis lock (SET NX with a TTL) ensures at most one worker instance is
    resolving at a time, and survives an ungraceful restart (the lock simply
    expires) — "safe to restart; no duplicate/concurrent processing".
  - Never touches ANSWER_VERIFIED/ANSWER_CONFLICT rows — resolve_batch()
    only ever selects state='ANSWER_PENDING', so existing verified/disputed
    answers are never revisited or overwritten by this worker.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger("pyq.resolver.worker")

_LOCK_KEY = "pyq_resolver_worker:lock"
_LOCK_TTL_SECONDS = 900  # generous vs. a single batch's expected runtime; expires on crash


async def _try_acquire_lock() -> bool:
    redis_client = get_redis()
    if redis_client is None:
        # No Redis configured/available — fail closed (skip this tick) rather
        # than risk two instances resolving concurrently with no coordination.
        logger.warning("pyq_resolver_lock_unavailable")
        return False
    acquired = await redis_client.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL_SECONDS)
    return bool(acquired)


async def _release_lock() -> None:
    redis_client = get_redis()
    if redis_client is not None:
        await redis_client.delete(_LOCK_KEY)


async def run_one_tick() -> int:
    """Resolve up to one batch. Returns the number of ANSWER_PENDING rows
    actually scanned this tick (0 means either nothing pending, or the lock
    was held elsewhere / Redis unavailable)."""
    from scripts.resolve_pyq_answers import _load_ku_index, resolve_up_to

    settings = get_settings()
    if not await _try_acquire_lock():
        logger.info("pyq_resolver_tick_skipped_locked")
        return 0

    try:
        async with AsyncSessionLocal() as session:
            idx = await _load_ku_index(session)
            report = await resolve_up_to(
                session, idx, max_total=settings.pyq_resolver_batch_size, apply=True
            )
            logger.info(
                "pyq_resolver_tick_complete",
                total_scanned=report.total_scanned,
                answered=report.answered,
                conflicts=report.conflicts,
                unresolved_no_source_match=report.unresolved_no_source_match,
                unresolved_no_option_grounded=report.unresolved_no_option_grounded,
            )
            return report.total_scanned
    except Exception:
        logger.exception("pyq_resolver_tick_failed")
        return 0
    finally:
        await _release_lock()


async def run_worker_loop() -> None:
    settings = get_settings()
    interval_seconds = settings.pyq_resolver_interval_hours * 3600
    while True:
        try:
            await run_one_tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("pyq_resolver_loop_tick_error")
        # Strict cadence: always wait the full interval before the next
        # tick, regardless of how many rows this tick processed or how
        # large the remaining backlog is. A large backlog is drained at
        # settings.pyq_resolver_batch_size per settings.pyq_resolver_interval_hours,
        # never faster — this is a deliberate rate limit, not a bug.
        await asyncio.sleep(interval_seconds)
