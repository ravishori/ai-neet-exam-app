"""FACTORY-PYQ-P5 — one-time full backfill of ANSWER_PENDING PYQs via
Gemini, explicitly bypassing the global AIGateway router (FACTORY_PROVIDER
is never touched or relied on — see scripts.resolve_pyq_answers._stage2_default_gateway,
reused here for the ongoing worker; this module builds its own gateway
using the backfill's own selected model instead, see select_backfill_model()).

EXECUTION PATH NOTE: Google's Gemini Batch API (app.modules.ai.gateway.
gemini_batch) was implemented per this feature's original design, but a
live connectivity test against it (2 trivial, non-PYQ requests) returned
`FAILED_PRECONDITION` on submission with the currently configured API key.
This is unresolved (likely a Vertex-AI-vs-AI-Studio-key mismatch, not
necessarily a wire-format bug) and is explicitly NOT blocking this
release: the backfill instead runs as bounded-concurrency synchronous
Gemini calls, which are the same, already-verified call path Stage 2's
ongoing worker uses. gemini_batch.py is kept for later diagnosis.

Idempotency / resumability: every question this job touches gets a
pyq.gemini_batch_items row up front (status=SUBMITTED). run_backfill() only
processes items still in SUBMITTED state, so re-running after an
interruption picks up exactly where it left off — never reprocesses an
item already RESULT_RECEIVED/APPLIED/FAILED/SKIPPED, and never re-derives
an assertion for a question that (from Stage 1, the ongoing worker, or a
previous run of this same job) has already left ANSWER_PENDING.

Concurrency model: the network-bound Gemini calls (the slow, parallelizable
part) run concurrently under a bounded semaphore, entirely independent of
the database — a single AsyncSession is not safe for concurrent use, so no
DB read/write happens during that phase. Results are collected in memory,
then applied to the database one at a time in a second, strictly
sequential phase, reusing the exact same never-overwrite / idempotent
write logic either way.
"""

from __future__ import annotations

import asyncio
import json
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from scripts.resolve_pyq_answers import (
    OPTION_LABELS,
    RESOLVER_VERSION_STAGE2,
    _build_explanation,
    _load_ku_index,
    _option_text,
    _significant_words,
)

logger = get_logger("pyq.gemini_backfill")

JOB_TYPE_FULL_BACKFILL = "FULL_BACKFILL"

# Provider error codes worth retrying with backoff — rate limits, timeouts,
# transient unavailability. Anything else (auth failure, invalid/unsupported
# model, malformed response) fails the item immediately — never retried
# indefinitely, per requirement.
_RETRYABLE_CODES = frozenset({"PROVIDER_RATE_LIMITED", "PROVIDER_TIMEOUT", "PROVIDER_UNAVAILABLE"})
_BACKOFF_BASE_SECONDS = 1.0


class BackfillAlreadyRunning(Exception):
    """Raised by start_full_backfill() when a non-terminal FULL_BACKFILL
    job already exists — the hard duplicate-launch guard."""


async def select_backfill_model() -> str:
    """Exactly one minimal, non-PYQ call to verify the cheaper preferred
    model is actually available on this API project; falls back to the
    already-verified gemini_model otherwise. Never sends question/option/
    evidence data — only a trivial "reply OK" probe."""
    from app.core.config import get_settings
    from app.modules.ai.gateway.base import ProviderError
    from app.modules.ai.gateway.gemini_provider import GeminiProvider

    settings = get_settings()
    if settings.pyq_gemini_backfill_model:
        return settings.pyq_gemini_backfill_model

    candidate = settings.pyq_gemini_backfill_preferred_model
    try:
        provider = GeminiProvider(api_key=settings.gemini_api_key, model=candidate)
        resp = await provider.generate(
            system_prompt="Reply with only the single word: OK", user_prompt="Respond now.", max_tokens=10
        )
        if not resp.is_fallback:
            logger.info("pyq_gemini_backfill_model_selected", model=candidate, verified=True)
            return candidate
    except ProviderError as exc:
        logger.info("pyq_gemini_backfill_preferred_model_unavailable", model=candidate, error_code=exc.code)

    logger.info("pyq_gemini_backfill_model_selected", model=settings.gemini_model, verified=True, fallback=True)
    return settings.gemini_model


async def start_full_backfill(session: AsyncSession) -> uuid.UUID:
    """Creates the job row and one gemini_batch_items row per currently
    ANSWER_PENDING question, then returns the job id. Does not itself
    process any item — call run_backfill() (resumable) for that. Raises
    BackfillAlreadyRunning if one is already SUBMITTED/PROCESSING —
    enforced by both an application-level check here and a partial unique
    index in the schema (uq_pyq_gemini_batch_jobs_active_by_type), so a
    race between two callers still can't create two active jobs.
    """
    existing = (
        await session.execute(
            text(
                "SELECT id FROM pyq.gemini_batch_jobs "
                "WHERE job_type = :jt AND status IN ('SUBMITTED', 'PROCESSING') LIMIT 1"
            ),
            {"jt": JOB_TYPE_FULL_BACKFILL},
        )
    ).first()
    if existing:
        raise BackfillAlreadyRunning(f"Active FULL_BACKFILL job already exists: {existing[0]}")

    question_ids = [
        row[0]
        for row in (
            await session.execute(text("SELECT id FROM pyq.questions WHERE state = 'ANSWER_PENDING' ORDER BY id"))
        ).all()
    ]

    model = await select_backfill_model()
    job_id = (
        await session.execute(
            text(
                "INSERT INTO pyq.gemini_batch_jobs (job_type, status, gemini_model, question_count, submitted_at) "
                "VALUES (:jt, 'SUBMITTED', :model, :count, :now) RETURNING id"
            ),
            {"jt": JOB_TYPE_FULL_BACKFILL, "model": model, "count": len(question_ids), "now": datetime.now(UTC)},
        )
    ).scalar_one()

    for qid in question_ids:
        await session.execute(
            text(
                "INSERT INTO pyq.gemini_batch_items (id, batch_job_id, question_id, custom_id, status) "
                "VALUES (:id, :job_id, :qid, :custom_id, 'SUBMITTED') "
                "ON CONFLICT (batch_job_id, question_id) DO NOTHING"
            ),
            {"id": uuid.uuid4(), "job_id": job_id, "qid": qid, "custom_id": str(qid)},
        )
    await session.commit()
    logger.info("pyq_gemini_backfill_started", job_id=str(job_id), question_count=len(question_ids), model=model)
    return job_id


@dataclass
class _ItemOutcome:
    item_id: uuid.UUID
    question_id: uuid.UUID
    kind: str  # "no_evidence" | "success" | "provider_error" | "fallback" | "bad_response"
    candidate_units: list[str] | None = None
    supported_options: list[str] | None = None
    reasoning: str = ""
    confidence: float | None = None
    supporting_ku_ids: list | None = None
    model: str | None = None
    error: str | None = None
    option_texts: dict[str, str] | None = None


async def _call_with_backoff(gateway, *, agent_type, system_prompt, user_prompt, max_tokens, max_retries: int):
    from app.modules.ai.gateway.base import ProviderError

    attempt = 0
    while True:
        attempt += 1
        try:
            return await gateway.generate(
                agent_type=agent_type, system_prompt=system_prompt, user_prompt=user_prompt,
                max_tokens=max_tokens, require_json=True,
            )
        except ProviderError as exc:
            if exc.code not in _RETRYABLE_CODES or attempt >= max_retries:
                raise
            delay = _BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            logger.warning(
                "pyq_gemini_backfill_retry", error_code=exc.code, attempt=attempt, delay_seconds=round(delay, 2)
            )
            await asyncio.sleep(delay)


async def _fetch_one_outcome(
    *, gateway, idx, semaphore: asyncio.Semaphore, max_retries: int,
    item_id: uuid.UUID, question_id: uuid.UUID, raw_stem, raw_options,
) -> _ItemOutcome:
    """Pure network/CPU — no database access at all, safe to run
    concurrently with many siblings under the semaphore."""
    from app.modules.ai.gateway.base import ProviderError
    from app.modules.ai.prompts import pyq_resolver_batch as prompts
    from app.modules.ai.services.json_utils import parse_json_response

    options = raw_options if isinstance(raw_options, dict) else (json.loads(raw_options) if raw_options else {})
    stem = raw_stem or ""
    option_texts = {label: _option_text(options, label) for label in OPTION_LABELS if _option_text(options, label).strip()}
    option_words: set[str] = set()
    for opt_text in option_texts.values():
        option_words |= _significant_words(opt_text)
    candidate_units = sorted(idx.candidates_for(_significant_words(stem) | option_words))[:8]

    if not candidate_units or not option_texts:
        return _ItemOutcome(item_id=item_id, question_id=question_id, kind="no_evidence")

    evidence_by_id = {uid[:8]: idx.unit_text[uid] for uid in candidate_units}
    user_prompt = prompts.build_user_prompt(stem=stem, options=option_texts, evidence_by_id=evidence_by_id)

    async with semaphore:
        try:
            response = await _call_with_backoff(
                gateway, agent_type="PYQ_ANSWER_RESOLVER_BACKFILL", system_prompt=prompts.SYSTEM_PROMPT,
                user_prompt=user_prompt, max_tokens=500, max_retries=max_retries,
            )
        except ProviderError as exc:
            return _ItemOutcome(
                item_id=item_id, question_id=question_id, kind="provider_error", error=f"{exc.code}: provider error"
            )

    if response.is_fallback:
        return _ItemOutcome(item_id=item_id, question_id=question_id, kind="fallback", error="fallback_response")

    try:
        parsed = parse_json_response(response.text)
        raw_supported = parsed.get("supported_options", [])
        if not isinstance(raw_supported, list):
            raise ValueError("supported_options must be a list")
        supported_options = sorted({label for label in raw_supported if label in option_texts})
        reasoning = str(parsed.get("reasoning") or "").strip()
        confidence = parsed.get("confidence")
        supporting_ku_ids = parsed.get("supporting_knowledge_unit_ids") or []
    except (ValueError, AttributeError, TypeError, KeyError):
        return _ItemOutcome(item_id=item_id, question_id=question_id, kind="bad_response", error="unparseable_response")

    return _ItemOutcome(
        item_id=item_id, question_id=question_id, kind="success", candidate_units=candidate_units,
        supported_options=supported_options, reasoning=reasoning, confidence=confidence,
        supporting_ku_ids=supporting_ku_ids, model=response.model, option_texts=option_texts,
    )


async def _apply_one_outcome(session: AsyncSession, outcome: _ItemOutcome) -> None:
    """Strictly sequential DB write — never runs concurrently with another
    call of itself. Re-checks live question state immediately before
    writing, so a question resolved by anything else since the job started
    is skipped rather than overwritten."""
    if outcome.kind in ("no_evidence",):
        await session.execute(
            text(
                "UPDATE pyq.gemini_batch_items SET status = 'APPLIED', applied_at = now(), "
                "raw_result = :r, updated_at = now() WHERE id = :id"
            ),
            {"id": outcome.item_id, "r": json.dumps({"outcome": "no_evidence"})},
        )
        return

    if outcome.kind == "provider_error":
        await session.execute(
            text(
                "UPDATE pyq.gemini_batch_items SET status = 'FAILED', last_error = :err, updated_at = now() "
                "WHERE id = :id"
            ),
            {"id": outcome.item_id, "err": outcome.error},
        )
        return

    if outcome.kind == "fallback":
        await session.execute(
            text(
                "UPDATE pyq.gemini_batch_items SET status = 'FAILED', last_error = 'fallback_response', "
                "updated_at = now() WHERE id = :id"
            ),
            {"id": outcome.item_id},
        )
        return

    if outcome.kind == "bad_response":
        await session.execute(
            text(
                "UPDATE pyq.gemini_batch_items SET status = 'FAILED', last_error = 'unparseable_response', "
                "updated_at = now() WHERE id = :id"
            ),
            {"id": outcome.item_id},
        )
        return

    # outcome.kind == "success"
    current_state = (
        await session.execute(text("SELECT state FROM pyq.questions WHERE id = :id"), {"id": outcome.question_id})
    ).scalar_one()
    if current_state != "ANSWER_PENDING":
        await session.execute(
            text("UPDATE pyq.gemini_batch_items SET status = 'SKIPPED', updated_at = now() WHERE id = :id"),
            {"id": outcome.item_id},
        )
        return

    if not outcome.supported_options:
        await session.execute(
            text("UPDATE pyq.gemini_batch_items SET status = 'APPLIED', applied_at = now() WHERE id = :id"),
            {"id": outcome.item_id},
        )
        return  # insufficient evidence — leave ANSWER_PENDING

    option_texts = outcome.option_texts or {}
    explanation = outcome.reasoning or _build_explanation(
        option_label=outcome.supported_options[0],
        option_text=option_texts.get(outcome.supported_options[0], ""),
        best_summary="",
    )
    evidence_note = (
        f"gemini_backfill_knowledge_units={','.join(outcome.candidate_units or [])}; "
        f"model={outcome.model}; confidence={outcome.confidence}; supporting_ids={outcome.supporting_ku_ids}"
    )
    new_state = "ANSWER_VERIFIED" if len(outcome.supported_options) == 1 else "ANSWER_CONFLICT"
    verification_status = "VERIFIED" if len(outcome.supported_options) == 1 else "DISPUTED"

    for label in outcome.supported_options:
        await session.execute(
            text(
                "INSERT INTO pyq.answer_assertions "
                "(id, question_id, asserted_option, assertion_source, verification_status, "
                "evidence_note, resolver_version, explanation) "
                "VALUES (:id, :qid, :opt, :src, :vstatus, :note, :rver, :expl) "
                "ON CONFLICT (question_id, assertion_source) DO NOTHING"
            ),
            {
                "id": uuid.uuid4(), "qid": outcome.question_id, "opt": label,
                "src": f"knowledge_units_gemini_backfill:{outcome.item_id}:option_{label}",
                "vstatus": verification_status, "note": evidence_note,
                "rver": RESOLVER_VERSION_STAGE2, "expl": explanation,
            },
        )
    await session.execute(
        text("UPDATE pyq.questions SET state = :s, updated_at = now() WHERE id = :id AND state = 'ANSWER_PENDING'"),
        {"s": new_state, "id": outcome.question_id},
    )
    await session.execute(
        text("UPDATE pyq.gemini_batch_items SET status = 'APPLIED', applied_at = now() WHERE id = :id"),
        {"id": outcome.item_id},
    )


async def run_backfill(session: AsyncSession, job_id: uuid.UUID, *, ai_gateway=None) -> dict:
    """Resumable: processes only gemini_batch_items still in status
    SUBMITTED for this job. Safe to call repeatedly (e.g. after a crash) —
    each item is only ever processed once."""
    from app.core.config import get_settings

    job = (
        await session.execute(
            text("SELECT id, status, gemini_model FROM pyq.gemini_batch_jobs WHERE id = :id"), {"id": job_id}
        )
    ).one_or_none()
    if job is None:
        raise ValueError(f"No such backfill job: {job_id}")
    if job.status not in ("SUBMITTED", "PROCESSING"):
        return await get_backfill_status(session, job_id)  # already terminal — idempotent no-op

    await session.execute(
        text("UPDATE pyq.gemini_batch_jobs SET status = 'PROCESSING', updated_at = now() WHERE id = :id"),
        {"id": job_id},
    )
    await session.commit()

    settings = get_settings()
    if ai_gateway is not None:
        gateway = ai_gateway
    else:
        from app.modules.ai.gateway.ai_gateway import AIGateway
        from app.modules.ai.gateway.gemini_provider import GeminiProvider

        gateway = AIGateway(session, provider=GeminiProvider(api_key=settings.gemini_api_key, model=job.gemini_model))

    idx = await _load_ku_index(session)

    # The q.state filter is a one-time, non-concurrent efficiency check —
    # it avoids spending an AI call on a question something else already
    # resolved before this run started. It is NOT the safety boundary
    # against overwriting VERIFIED/CONFLICT; _apply_one_outcome's own
    # re-check immediately before writing is (a question resolved in the
    # split second after this SELECT is still caught there, just after an
    # otherwise-wasted call — never after an overwrite).
    pending_items = (
        await session.execute(
            text(
                "SELECT bi.id, bi.question_id, q.raw_stem, q.raw_options "
                "FROM pyq.gemini_batch_items bi "
                "JOIN pyq.questions q ON q.id = bi.question_id "
                "WHERE bi.batch_job_id = :job_id AND bi.status = 'SUBMITTED' AND q.state = 'ANSWER_PENDING' "
                "ORDER BY bi.id"
            ),
            {"job_id": job_id},
        )
    ).all()

    # Items whose question was already resolved before this run started
    # never even get a fetch attempt — mark them SKIPPED directly so
    # completion accounting is accurate without spending a call.
    already_resolved_item_ids = [
        row[0]
        for row in (
            await session.execute(
                text(
                    "SELECT bi.id FROM pyq.gemini_batch_items bi "
                    "JOIN pyq.questions q ON q.id = bi.question_id "
                    "WHERE bi.batch_job_id = :job_id AND bi.status = 'SUBMITTED' AND q.state != 'ANSWER_PENDING'"
                ),
                {"job_id": job_id},
            )
        ).all()
    ]
    for skip_id in already_resolved_item_ids:
        await session.execute(
            text("UPDATE pyq.gemini_batch_items SET status = 'SKIPPED', updated_at = now() WHERE id = :id"),
            {"id": skip_id},
        )
    if already_resolved_item_ids:
        await session.commit()

    # Phase 1: bounded-concurrency network calls — no DB access here at all.
    semaphore = asyncio.Semaphore(max(1, settings.pyq_gemini_backfill_concurrency))
    outcomes = await asyncio.gather(
        *[
            _fetch_one_outcome(
                gateway=gateway, idx=idx, semaphore=semaphore, max_retries=settings.pyq_gemini_backfill_max_retries,
                item_id=item_id, question_id=question_id, raw_stem=raw_stem, raw_options=raw_options,
            )
            for item_id, question_id, raw_stem, raw_options in pending_items
        ]
    )

    # Phase 2: strictly sequential DB writes.
    for outcome in outcomes:
        try:
            await _apply_one_outcome(session, outcome)
            await session.commit()
        except Exception:
            logger.exception("pyq_gemini_backfill_item_apply_failed", item_id=str(outcome.item_id))
            await session.rollback()
            await session.execute(
                text(
                    "UPDATE pyq.gemini_batch_items SET status = 'FAILED', last_error = :err, updated_at = now() "
                    "WHERE id = :id"
                ),
                {"id": outcome.item_id, "err": "unhandled exception applying result — see server logs"},
            )
            await session.commit()

    remaining = (
        await session.execute(
            text("SELECT count(*) FROM pyq.gemini_batch_items WHERE batch_job_id = :id AND status = 'SUBMITTED'"),
            {"id": job_id},
        )
    ).scalar_one()
    failed = (
        await session.execute(
            text("SELECT count(*) FROM pyq.gemini_batch_items WHERE batch_job_id = :id AND status = 'FAILED'"),
            {"id": job_id},
        )
    ).scalar_one()
    if remaining == 0:
        final_status = "PARTIAL" if failed > 0 else "COMPLETED"
        await session.execute(
            text(
                "UPDATE pyq.gemini_batch_jobs SET status = :s, completed_at = :now, updated_at = now() WHERE id = :id"
            ),
            {"s": final_status, "now": datetime.now(UTC), "id": job_id},
        )
        await session.commit()

    return await get_backfill_status(session, job_id)


async def get_backfill_status(session: AsyncSession, job_id: uuid.UUID) -> dict:
    job = (
        await session.execute(
            text(
                "SELECT id, status, gemini_batch_name, gemini_model, question_count, submitted_at, "
                "completed_at, last_error FROM pyq.gemini_batch_jobs WHERE id = :id"
            ),
            {"id": job_id},
        )
    ).one_or_none()
    if job is None:
        raise ValueError(f"No such backfill job: {job_id}")

    item_stmt = text(
        "SELECT bi.status, q.state FROM pyq.gemini_batch_items bi "
        "JOIN pyq.questions q ON q.id = bi.question_id WHERE bi.batch_job_id = :id"
    )
    rows = (await session.execute(item_stmt, {"id": job_id})).all()

    total = len(rows)
    outcome_counts = {"ANSWER_VERIFIED": 0, "ANSWER_CONFLICT": 0, "ANSWER_PENDING": 0}
    submitted = processing = completed_items = failed_items = 0
    for item_status, question_state in rows:
        outcome_counts[question_state] = outcome_counts.get(question_state, 0) + 1
        if item_status == "SUBMITTED":
            submitted += 1
        elif item_status in ("RESULT_RECEIVED",):
            processing += 1
        elif item_status in ("APPLIED", "SKIPPED"):
            completed_items += 1
        elif item_status == "FAILED":
            failed_items += 1

    completion_pct = round(100.0 * (completed_items + failed_items) / total, 2) if total else 0.0

    return {
        "batch_id": str(job.id),
        "job_status": job.status,
        "gemini_batch_name": job.gemini_batch_name,
        "model": job.gemini_model,
        "question_count": job.question_count,
        "submitted_at": job.submitted_at,
        "completed_at": job.completed_at,
        "last_error": job.last_error,
        "submitted": submitted,
        "processing": processing,
        "completed": completed_items,
        "failed": failed_items,
        "verified": outcome_counts["ANSWER_VERIFIED"],
        "conflict": outcome_counts["ANSWER_CONFLICT"],
        "pending": outcome_counts["ANSWER_PENDING"],
        "completion_pct": completion_pct,
    }
