"""Study Plan generation: a deterministic, rule-based baseline is always
computed first; AI personalization (independently configured from
Content Factory / the global ai_provider_default -- see
study_planner_provider* settings) is an optional improvement applied on
top of it, never a dependency the feature needs to function. See
docs/ai/study-planner.md for the full design writeup, provider
comparison, and configuration reference.

Fail-safe order, each step degrading gracefully to the next on any
failure (never raising past this service for a routine "AI unavailable"
reason -- only a genuine infrastructure failure, e.g. the database itself
being down, propagates, exactly as every other DB-backed endpoint in this
app already does):
1. Deterministic plan (always computed, zero I/O beyond the weak-concepts
   read already needed for the prompt either way).
2. Cache lookup (Redis; a cache miss or Redis being unavailable both fall
   through to step 3 silently).
3. Spend-cap reservation (ai.ai_requests-backed, concurrency-safe -- see
   app.modules.ai.spend_guard). No budget left -> skip straight to using
   the deterministic plan.
4. AI call via an independently-configured routing policy, requesting
   native JSON mode.
5. Strict schema validation (StudyPlanShape) of the AI's JSON. Anything
   that fails validation is discarded -- the deterministic plan is used
   instead, never a half-trusted AI response.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.gateway.base import ProviderError
from app.modules.ai.gateway.router import parse_routing_policy
from app.modules.ai.models import StudyPlan
from app.modules.ai.prompts import study_planner as planner_prompts
from app.modules.ai.repositories.ai_repository import AIRepository
from app.modules.ai.schemas.ai import StudyPlanShape
from app.modules.ai.services.json_utils import parse_json_response
from app.modules.ai.services.study_plan_deterministic import build_deterministic_plan
from app.modules.ai.spend_guard import release_reservation, reserve_spend, worst_case_cost_usd

logger = get_logger("ai")

AGENT_TYPE = "STUDY_PLANNER"
_MAX_TOKENS = 1200
_CACHE_PREFIX = "study_plan_cache"


def _build_routing_policy():
    settings = get_settings()
    provider = (settings.study_planner_provider or settings.ai_provider_default or "anthropic").strip().lower()
    chain = (settings.study_planner_provider_fallback_chain or "").strip()
    if chain:
        return parse_routing_policy(mode="fallback_chain", provider=provider, fallback_chain=chain)
    return parse_routing_policy(mode="fixed", provider=provider)


def _cache_key(
    *,
    user_id: uuid.UUID,
    target_score: int,
    current_score: int,
    exam_date: date,
    hours_per_day: int,
    weak_concepts: list[str],
) -> str:
    raw = "|".join(
        [
            str(user_id),
            str(target_score),
            str(current_score),
            exam_date.isoformat(),
            str(hours_per_day),
            ",".join(sorted(weak_concepts)),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{_CACHE_PREFIX}:{digest}"


class StudyPlannerService:
    def __init__(self, session: AsyncSession, *, gateway: AIGateway | None = None):
        self.session = session
        self.repo = AIRepository(session)
        # Independently-configured policy (study_planner_provider*) unless
        # a gateway was injected (tests) -- never reads
        # factory_provider*/ai_provider_default's EFFECT on any other
        # feature, and changing those settings never changes this one's
        # resolved policy except through the explicit inherit-when-unset
        # fallback in _build_routing_policy.
        self.gateway = gateway or AIGateway(session, routing_policy=_build_routing_policy())

    async def _try_cache_get(self, key: str) -> dict | None:
        try:
            from app.core.redis import get_redis

            redis_client = get_redis()
            if redis_client is None:
                return None
            cached = await redis_client.get(key)
            if cached is None:
                return None
            return StudyPlanShape.model_validate_json(cached).model_dump()
        except Exception:  # noqa: BLE001 -- cache is a pure optimization, never fail generation over it
            logger.warning("study_planner_cache_read_failed", exc_info=True)
            return None

    async def _try_cache_set(self, key: str, plan_data: dict) -> None:
        try:
            from app.core.redis import get_redis

            redis_client = get_redis()
            if redis_client is None:
                return
            settings = get_settings()
            await redis_client.set(
                key, StudyPlanShape.model_validate(plan_data).model_dump_json(), ex=settings.study_planner_cache_ttl_seconds
            )
        except Exception:  # noqa: BLE001
            logger.warning("study_planner_cache_write_failed", exc_info=True)

    async def _personalize_with_ai(
        self, *, user_prompt: str, user_id: uuid.UUID, policy_provider: str
    ) -> dict | None:
        """Returns a validated plan dict on success, or None on ANY
        failure (provider unavailable, over spend cap, bad/invalid JSON)
        -- callers must treat None as "use the deterministic plan",
        never as an error to surface to the caller."""
        settings = get_settings()
        entry = self.gateway.registry.get(policy_provider)
        model_hint = entry.model if entry else ""
        cost_cap_usd = worst_case_cost_usd(policy_provider, model_hint, _MAX_TOKENS)

        try:
            reservation_id = await reserve_spend(
                self.session,
                agent_type=AGENT_TYPE,
                limit_usd=settings.study_planner_daily_spend_cap_usd,
                cost_usd=cost_cap_usd,
            )
        except Exception:  # noqa: BLE001 -- spend-cap infra itself failing must never
            # turn into a 500: fail closed toward "no AI spend", not toward
            # losing the whole request. reserve_spend runs its own body in
            # a SAVEPOINT (see spend_guard.py), so a failure there has
            # already been contained to that savepoint alone -- no
            # explicit rollback needed here, and a session-wide rollback()
            # would be actively wrong: it would also undo any earlier,
            # already-committed work in this same request's transaction.
            logger.warning("study_planner_spend_guard_unavailable", exc_info=True)
            return None
        if reservation_id is None:
            logger.info("study_planner_spend_cap_reached", agent_type=AGENT_TYPE)
            return None

        try:
            response = await self.gateway.generate(
                agent_type=AGENT_TYPE,
                system_prompt=planner_prompts.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                user_id=user_id,
                max_tokens=_MAX_TOKENS,
                require_json=True,
            )
        except ProviderError as exc:
            logger.info("study_planner_provider_unavailable", error=str(exc)[:200])
            return None
        finally:
            try:
                await release_reservation(self.session, reservation_id)
            except Exception:  # noqa: BLE001 -- best-effort cleanup; a failure here
                # just means the reservation lingers until the daily window
                # resets (same accepted edge case as a process crash -- see
                # spend_guard.py's own docstring), never a reason to mask
                # whatever the AI call actually returned. release_reservation
                # also runs its own body in a SAVEPOINT, so no explicit
                # session-wide rollback is needed (same reasoning as the
                # reserve_spend except block above).
                logger.warning("study_planner_spend_release_failed", exc_info=True)

        if response.is_fallback:
            return None

        try:
            parsed = parse_json_response(response.text)
            validated = StudyPlanShape.model_validate(parsed)
        except (ValueError, ValidationError) as exc:
            logger.warning("study_planner_bad_ai_response", error=str(exc)[:300])
            return None

        return validated.model_dump()

    async def generate(
        self, *, user_id: uuid.UUID, target_score: int, current_score: int, exam_date: date, hours_per_day: int
    ) -> StudyPlan:
        days_remaining = max(1, (exam_date - date.today()).days)
        weak_concepts = await self.repo.get_weak_concept_names(user_id)

        deterministic_plan = build_deterministic_plan(
            target_score=target_score,
            current_score=current_score,
            days_remaining=days_remaining,
            hours_per_day=hours_per_day,
            weak_concepts=weak_concepts,
        )

        cache_key = _cache_key(
            user_id=user_id,
            target_score=target_score,
            current_score=current_score,
            exam_date=exam_date,
            hours_per_day=hours_per_day,
            weak_concepts=weak_concepts,
        )

        plan_data = await self._try_cache_get(cache_key)
        is_fallback = plan_data is None
        if plan_data is None:
            user_prompt = planner_prompts.build_prompt(
                target_score=target_score,
                current_score=current_score,
                days_remaining=days_remaining,
                hours_per_day=hours_per_day,
                weak_concepts=weak_concepts,
            )
            policy_provider = self.gateway.routing_policy.primary
            plan_data = await self._personalize_with_ai(
                user_prompt=user_prompt, user_id=user_id, policy_provider=policy_provider
            )
            if plan_data is not None:
                is_fallback = False
                await self._try_cache_set(cache_key, plan_data)
            else:
                plan_data = deterministic_plan
                is_fallback = True

        plan = StudyPlan(
            user_id=user_id,
            target_score=target_score,
            current_score=current_score,
            exam_date=exam_date,
            hours_per_day=hours_per_day,
            plan=plan_data,
            is_fallback=is_fallback,
        )
        self.repo.add_study_plan(plan)
        await self.repo.commit()
        return plan
