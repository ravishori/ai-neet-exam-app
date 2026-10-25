"""Study Plan improvements: deterministic baseline, optional AI
personalization (independently configured from Content Factory / the
global ai_provider_default), strict schema validation, caching, and a
persistent daily spend cap -- see docs/ai/study-planner.md.

No live provider calls anywhere in this file -- every AI response is a
ScriptedProvider (same pattern as test_content_factory_p3.py)."""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.gateway.base import AIProvider, AIResponse
from app.modules.ai.gateway.registry import AVAILABLE, BLOCKED, ProviderRegistry, RegisteredProvider
from app.modules.ai.gateway.router import RoutingPolicy
from app.modules.ai.models import AIRequestLog
from app.modules.ai.schemas.ai import StudyPlanShape
from app.modules.ai.services.study_plan_deterministic import build_deterministic_plan
from app.modules.ai.services.study_planner_service import StudyPlannerService

pytestmark = pytest.mark.asyncio(loop_scope="session")


class ScriptedProvider(AIProvider):
    name = "scripted"

    def __init__(self, responses: list[AIResponse | Exception]):
        self._responses = list(responses)
        self.calls = 0

    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        self.calls += 1
        if not self._responses:
            raise RuntimeError("No scripted responses left")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


_VALID_PLAN_JSON = json.dumps(
    {
        "summary": "AI-personalized plan.",
        "weekly_focus": ["Organic chemistry", "Mock test"],
        "daily_schedule": [{"day": 1, "focus": "Organic chemistry deep dive", "duration_minutes": 180}],
    }
)


def _ai_response(text: str, *, is_fallback: bool = False) -> AIResponse:
    return AIResponse(text=text, model="scripted-model", prompt_tokens=50, completion_tokens=100, is_fallback=is_fallback)


def _registry_with(provider_name: str, instance: AIProvider | None, *, status: str = AVAILABLE) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(
        RegisteredProvider(name=provider_name, enabled=True, configured=True, model="scripted-model", instance=instance, status=status)
    )
    registry.register(
        RegisteredProvider(name="fallback", enabled=True, configured=True, model="fallback", instance=None, status="ENABLED")
    )
    return registry


def _gateway_for(session, provider: AIProvider, *, provider_name: str = "openai") -> AIGateway:
    registry = _registry_with(provider_name, provider)
    policy = RoutingPolicy(mode="fixed", primary=provider_name)
    return AIGateway(session, registry=registry, routing_policy=policy)


def _blocked_gateway(session, *, provider_name: str = "openai") -> AIGateway:
    registry = _registry_with(provider_name, None, status=BLOCKED)
    policy = RoutingPolicy(mode="fixed", primary=provider_name)
    return AIGateway(session, registry=registry, routing_policy=policy)


async def _register_user(client, email: str) -> uuid.UUID:
    import random

    mobile = str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "first_name": "StudyPlan",
            "last_name": "Test",
            "mobile": mobile,
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": "StudyPlanTestPass!42",
        },
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _email() -> str:
    return f"study-plan-{uuid.uuid4().hex[:12]}@example.com"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        self._store[key] = value


@pytest.fixture
def fake_redis(monkeypatch):
    from app.core import redis as redis_module

    redis = _FakeRedis()
    monkeypatch.setattr(redis_module, "get_redis", lambda: redis)
    return redis


@pytest.fixture(autouse=True)
def _generous_spend_cap(monkeypatch):
    """Most tests aren't exercising the spend cap itself -- give them
    headroom so the cap's own (separately-tested) behavior doesn't
    interfere."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "study_planner_daily_spend_cap_usd", 10.0)


def _inputs() -> dict:
    return {
        "target_score": 650,
        "current_score": 450,
        "exam_date": date.today() + timedelta(days=90),
        "hours_per_day": 6,
    }


# ---------------------------------------------------------------------------
# Deterministic baseline
# ---------------------------------------------------------------------------


def test_deterministic_plan_is_pure_and_matches_strict_shape():
    kwargs = dict(target_score=650, current_score=450, days_remaining=90, hours_per_day=6, weak_concepts=["Genetics"])
    first = build_deterministic_plan(**kwargs)
    second = build_deterministic_plan(**kwargs)
    assert first == second  # pure function -- identical inputs, identical output

    validated = StudyPlanShape.model_validate(first)  # must satisfy the SAME strict schema as an AI response
    assert validated.summary


# ---------------------------------------------------------------------------
# AI personalization success / failure / fallback
# ---------------------------------------------------------------------------


async def test_ai_personalization_success_is_not_marked_fallback(client, db_session, fake_redis):
    user_id = await _register_user(client, _email())
    provider = ScriptedProvider([_ai_response(_VALID_PLAN_JSON)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    plan = await service.generate(user_id=user_id, **_inputs())

    assert plan.is_fallback is False
    assert plan.plan["summary"] == "AI-personalized plan."
    assert provider.calls == 1


async def test_malformed_json_falls_back_to_deterministic(client, db_session, fake_redis):
    user_id = await _register_user(client, _email())
    provider = ScriptedProvider([_ai_response("not valid json at all")])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    plan = await service.generate(user_id=user_id, **_inputs())

    assert plan.is_fallback is True
    assert plan.plan["summary"].startswith("Deterministic plan:")


async def test_schema_violation_falls_back_to_deterministic(client, db_session, fake_redis):
    """Valid JSON, but missing a required field -- must be rejected, not
    silently persisted with the gap."""
    user_id = await _register_user(client, _email())
    bad_shape = json.dumps({"summary": "ok", "weekly_focus": ["x"]})  # daily_schedule missing
    provider = ScriptedProvider([_ai_response(bad_shape)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    plan = await service.generate(user_id=user_id, **_inputs())

    assert plan.is_fallback is True


async def test_extra_fields_in_ai_response_are_rejected(client, db_session, fake_redis):
    user_id = await _register_user(client, _email())
    extra_field = json.dumps(
        {
            "summary": "ok",
            "weekly_focus": ["x"],
            "daily_schedule": [{"day": 1, "focus": "x", "duration_minutes": 60, "unexpected": "value"}],
        }
    )
    provider = ScriptedProvider([_ai_response(extra_field)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    plan = await service.generate(user_id=user_id, **_inputs())

    assert plan.is_fallback is True


async def test_providers_own_fallback_response_is_treated_as_unavailable(client, db_session, fake_redis):
    user_id = await _register_user(client, _email())
    provider = ScriptedProvider([_ai_response("ignored", is_fallback=True)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    plan = await service.generate(user_id=user_id, **_inputs())

    assert plan.is_fallback is True


async def test_provider_error_is_caught_and_falls_back_without_raising(client, db_session, fake_redis):
    """No provider configured/available at all -- the router raises
    ProviderError; the service must swallow it and use the deterministic
    plan, never surface a 502 to the caller for a routine "AI
    unavailable" reason."""
    user_id = await _register_user(client, _email())
    service = StudyPlannerService(db_session, gateway=_blocked_gateway(db_session))

    plan = await service.generate(user_id=user_id, **_inputs())

    assert plan.is_fallback is True
    assert plan.plan["summary"].startswith("Deterministic plan:")


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


async def test_identical_inputs_hit_the_cache_and_skip_a_second_ai_call(client, db_session, fake_redis):
    user_id = await _register_user(client, _email())
    provider = ScriptedProvider([_ai_response(_VALID_PLAN_JSON)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    first = await service.generate(user_id=user_id, **_inputs())
    second = await service.generate(user_id=user_id, **_inputs())

    assert first.is_fallback is False
    assert second.is_fallback is False
    assert second.plan["summary"] == "AI-personalized plan."
    assert provider.calls == 1, "second call with identical inputs must be served from cache, not a new AI call"


async def test_different_inputs_do_not_share_a_cache_entry(client, db_session, fake_redis):
    user_id = await _register_user(client, _email())
    provider = ScriptedProvider([_ai_response(_VALID_PLAN_JSON), _ai_response(_VALID_PLAN_JSON)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    await service.generate(user_id=user_id, **_inputs())
    different_inputs = _inputs()
    different_inputs["hours_per_day"] = 8
    await service.generate(user_id=user_id, **different_inputs)

    assert provider.calls == 2


async def test_different_users_with_identical_inputs_do_not_share_a_cache_entry(client, db_session, fake_redis):
    """Same target/current score, exam date, hours/day -- but two
    different students. The cache key must include user_id, not just the
    plan parameters, or one student's AI-personalized plan (which also
    factors in THEIR weak concepts) would leak to another."""
    user_a = await _register_user(client, _email())
    user_b = await _register_user(client, _email())
    provider = ScriptedProvider([_ai_response(_VALID_PLAN_JSON), _ai_response(_VALID_PLAN_JSON)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    await service.generate(user_id=user_a, **_inputs())
    await service.generate(user_id=user_b, **_inputs())

    assert provider.calls == 2, "two different users must never share one cache entry, even with identical inputs"


async def test_cache_backend_unavailable_still_generates_a_plan(client, db_session, monkeypatch):
    """Redis down must never block plan generation -- falls through to a
    real AI call (or deterministic) instead of erroring."""
    from app.core import redis as redis_module

    monkeypatch.setattr(redis_module, "get_redis", lambda: None)
    user_id = await _register_user(client, _email())
    provider = ScriptedProvider([_ai_response(_VALID_PLAN_JSON)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    plan = await service.generate(user_id=user_id, **_inputs())
    assert plan.is_fallback is False


# ---------------------------------------------------------------------------
# Persistent daily spend cap
# ---------------------------------------------------------------------------


async def test_spend_cap_at_zero_blocks_the_ai_call_entirely(client, db_session, fake_redis, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "study_planner_daily_spend_cap_usd", 0.0)
    user_id = await _register_user(client, _email())
    provider = ScriptedProvider([_ai_response(_VALID_PLAN_JSON)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    plan = await service.generate(user_id=user_id, **_inputs())

    assert plan.is_fallback is True
    assert provider.calls == 0, "a zero spend cap must prevent the provider from ever being called"


async def test_reservation_is_released_after_a_successful_call(client, db_session, fake_redis):
    """No reservation row (model='reserved') should remain once a
    successful call's real AIRequestLog row has been written."""
    user_id = await _register_user(client, _email())
    provider = ScriptedProvider([_ai_response(_VALID_PLAN_JSON)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    await service.generate(user_id=user_id, **_inputs())

    reservations = (
        await db_session.execute(select(AIRequestLog).where(AIRequestLog.model == "reserved"))
    ).scalars().all()
    assert reservations == []


async def test_spend_cap_is_isolated_from_other_agent_types(client, db_session, fake_redis):
    """A different feature's (TUTOR) heavy spend must never count against
    Study Planner's own daily cap -- they're isolated by agent_type."""
    from app.core.config import get_settings

    monkeypatch_cap = 0.05  # comfortably covers one call's worst-case reservation on its own
    from unittest.mock import patch

    db_session.add(
        AIRequestLog(
            agent_type="TUTOR",
            user_id=None,
            model="other-feature-model",
            prompt_tokens=100000,
            completion_tokens=100000,
            estimated_cost_usd=500.0,  # a huge TUTOR spend
            latency_ms=10,
            is_fallback=False,
            success=True,
        )
    )
    await db_session.commit()

    with patch.object(get_settings(), "study_planner_daily_spend_cap_usd", monkeypatch_cap):
        user_id = await _register_user(client, _email())
        provider = ScriptedProvider([_ai_response(_VALID_PLAN_JSON)])
        service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))
        plan = await service.generate(user_id=user_id, **_inputs())

    # TUTOR's $500 spend must not have blocked STUDY_PLANNER's own, separate budget.
    assert plan.is_fallback is False, "an unrelated agent_type's spend must never count against this one's cap"


async def test_spend_guard_db_failure_fails_safely_to_deterministic(client, db_session, fake_redis, monkeypatch):
    """If the spend-cap's own check can't run (DB hiccup specific to that
    query), the service must fail CLOSED toward "no AI spend" and still
    return a usable (deterministic) plan -- never a 500, and never
    silently skip the cap to let the AI call through anyway."""
    import app.modules.ai.services.study_planner_service as study_planner_service_module

    async def _broken_reserve_spend(*_args, **_kwargs):
        raise RuntimeError("simulated DB hiccup during the spend-cap check")

    # Patch the name as imported into study_planner_service -- a direct
    # `from ... import reserve_spend` binds it there too, so patching the
    # original spend_guard module wouldn't affect the already-bound
    # reference the service actually calls.
    monkeypatch.setattr(study_planner_service_module, "reserve_spend", _broken_reserve_spend)

    user_id = await _register_user(client, _email())
    provider = ScriptedProvider([_ai_response(_VALID_PLAN_JSON)])
    service = StudyPlannerService(db_session, gateway=_gateway_for(db_session, provider))

    plan = await service.generate(user_id=user_id, **_inputs())

    assert plan.is_fallback is True
    assert provider.calls == 0, "the AI provider must never be called when the spend-cap check itself fails"

    # The session must still be usable afterward -- this generate() call's
    # own StudyPlan insert+commit already proves that (it succeeded above),
    # but assert directly too since that's the specific risk being guarded.
    await db_session.execute(select(AIRequestLog).limit(1))


# NOTE on true cross-connection concurrency: a standalone script (outside
# pytest, run manually during this feature's verification) confirmed
# reserve_spend() works correctly end-to-end against a fresh engine/
# connection/session constructed exactly as a real request's would be --
# it returned a valid reservation id against the real test database. A
# pytest-based version of that same two-connection scenario, run inside
# this suite's pytest-asyncio session-scoped event loop, hit a
# SQLAlchemy "MissingGreenlet" error from constructing a second ad-hoc
# engine mid-test -- a harness/event-loop-scoping interaction specific to
# this test runner, not a defect in reserve_spend's own logic (which does
# not change behavior based on how its caller's session/engine was
# constructed). Documented here as a residual verification gap: the
# pg_advisory_xact_lock + committed-reservation-row design is covered by
# the isolated-agent-type and reservation-release tests above against a
# real Postgres instance, and by that manual standalone run, but not by
# an automated two-connection race test in THIS suite. See
# docs/ai/study-planner.md's "Known limitations" section.


# ---------------------------------------------------------------------------
# Routing policy independence (Content Factory / global default isolation)
# ---------------------------------------------------------------------------


def test_routing_policy_inherits_ai_provider_default_when_unset(monkeypatch):
    from app.core.config import get_settings
    from app.modules.ai.services.study_planner_service import _build_routing_policy

    settings = get_settings()
    monkeypatch.setattr(settings, "study_planner_provider", "")
    monkeypatch.setattr(settings, "study_planner_provider_fallback_chain", "")
    monkeypatch.setattr(settings, "ai_provider_default", "anthropic")
    monkeypatch.setattr(settings, "factory_provider", "mistral")  # deliberately different -- must be ignored

    policy = _build_routing_policy()
    assert policy.primary == "anthropic"


def test_routing_policy_uses_its_own_setting_independent_of_factory_provider(monkeypatch):
    from app.core.config import get_settings
    from app.modules.ai.services.study_planner_service import _build_routing_policy

    settings = get_settings()
    monkeypatch.setattr(settings, "study_planner_provider", "gemini")
    monkeypatch.setattr(settings, "study_planner_provider_fallback_chain", "openai")
    monkeypatch.setattr(settings, "factory_provider", "anthropic")  # Content Factory's own choice -- must be ignored
    monkeypatch.setattr(settings, "factory_provider_mode", "fixed")

    policy = _build_routing_policy()
    assert policy.primary == "gemini"
    assert policy.chain == ["gemini", "openai"]
    assert policy.mode == "fallback_chain"
