"""FACTORY-P3.1 multi-provider AI Gateway — offline contract/routing/budget tests."""

from __future__ import annotations

import pytest

from app.modules.ai.gateway.base import (
    PROVIDER_AUTH_FAILED,
    PROVIDER_BLOCKED,
    PROVIDER_RATE_LIMITED,
    PROVIDER_TIMEOUT,
    GenerateRequest,
    ProviderError,
)
from app.modules.ai.gateway.capabilities import get_capability, register_capability, ProviderModelCapability
from app.modules.ai.gateway.fakes import (
    FakeAnthropicProvider,
    FakeGeminiProvider,
    FakeMistralProvider,
    FakeOpenAIProvider,
)
from app.modules.ai.gateway.pricing import PriceRate, estimate_cost, register_rate
from app.modules.ai.gateway.registry import (
    AVAILABLE,
    BLOCKED,
    DISABLED,
    ProviderRegistry,
    RegisteredProvider,
    build_registry_from_settings,
)
from app.modules.ai.gateway.router import MODE_FALLBACK_CHAIN, MODE_FIXED, ProviderRouter, parse_routing_policy

# Match factory suite event-loop scope when run together
pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _contract_success(provider_cls, name: str, model: str):
    p = provider_cls(behavior="success", model=model)
    resp = await p.generate_request(
        GenerateRequest(system_prompt="sys", user_prompt="user", max_tokens=100, model=model, require_json=True)
    )
    assert resp.provider == name
    assert resp.model == model
    assert resp.prompt_tokens > 0
    assert resp.completion_tokens > 0
    assert resp.provider_request_id
    assert resp.text
    cost = estimate_cost(name, model, resp.prompt_tokens, resp.completion_tokens)
    assert cost.cost_status == "ESTIMATED"
    assert cost.total_tokens == resp.prompt_tokens + resp.completion_tokens


@pytest.mark.parametrize(
    "cls,name,model",
    [
        (FakeAnthropicProvider, "anthropic", "claude-sonnet-4-6"),
        (FakeOpenAIProvider, "openai", "gpt-4o-mini"),
        (FakeGeminiProvider, "gemini", "gemini-2.0-flash"),
        (FakeMistralProvider, "mistral", "mistral-small-latest"),
    ],
)
async def test_provider_contract_success(cls, name, model):
    await _contract_success(cls, name, model)


@pytest.mark.parametrize(
    "behavior,code",
    [
        ("auth", PROVIDER_AUTH_FAILED),
        ("rate_limit", PROVIDER_RATE_LIMITED),
        ("timeout", PROVIDER_TIMEOUT),
        ("malformed", "PROVIDER_INVALID_RESPONSE"),
        ("unavailable", "PROVIDER_UNAVAILABLE"),
    ],
)
async def test_provider_contract_errors(behavior, code):
    p = FakeOpenAIProvider(behavior=behavior)
    with pytest.raises(ProviderError) as ei:
        await p.generate_request(GenerateRequest(system_prompt="s", user_prompt="u"))
    assert ei.value.code == code
    assert ei.value.provider == "openai"


@pytest.mark.asyncio(loop_scope="session")
async def test_capability_registry():
    cap = get_capability("openai", "gpt-4o-mini")
    assert cap is not None
    assert cap.supports_structured_output is True
    register_capability(
        ProviderModelCapability("openai", "gpt-test-local", supports_structured_output=True, enabled=True)
    )
    assert get_capability("openai", "gpt-test-local") is not None


@pytest.mark.parametrize(
    "provider,model",
    [
        ("anthropic", "claude-sonnet-4-6"),
        ("openai", "gpt-5-mini"),
        ("gemini", "gemini-2.5-flash"),
        ("gemini", "gemini-3.6-flash"),
        ("mistral", "mistral-small-2603"),
    ],
)
async def test_pilot_comparison_models_capability_and_pricing(provider, model):
    """FACTORY-P3.1 four-provider comparison models — registry tables only (no API calls)."""
    cap = get_capability(provider, model)
    assert cap is not None
    assert cap.enabled is True
    assert cap.supports_system_prompt is True
    assert cap.max_output >= 1200  # factory MCQ max_tokens
    cost = estimate_cost(provider, model, 500, 400)
    assert cost.cost_status == "ESTIMATED"
    assert cost.cost_usd > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_gemini_3_6_flash_capability_and_pricing():
    """FACTORY-P3.1 — gemini-3.6-flash capability/pricing from verified preflight (no API calls)."""
    from app.modules.ai.gateway.pricing import PriceRate, _RATES

    cap = get_capability("gemini", "gemini-3.6-flash")
    assert cap is not None
    assert cap.enabled is True
    assert cap.supports_structured_output is True
    assert cap.supports_system_prompt is True
    assert cap.max_context == 1_048_576
    assert cap.max_output == 65_536

    rate = _RATES[("gemini", "gemini-3.6-flash")]
    assert rate.input_per_million == 0.75
    assert rate.output_per_million == 3.75
    assert rate == PriceRate(0.75, 3.75)
    cost = estimate_cost("gemini", "gemini-3.6-flash", 500, 400)
    assert cost.cost_status == "ESTIMATED"
    assert cost.cost_usd > 0

    # Existing pilot models must remain registered (no regression).
    for provider, model in (
        ("anthropic", "claude-sonnet-4-6"),
        ("openai", "gpt-5-mini"),
        ("gemini", "gemini-2.5-flash"),
        ("mistral", "mistral-small-2603"),
    ):
        assert get_capability(provider, model) is not None
        assert estimate_cost(provider, model, 100, 100).cost_status == "ESTIMATED"


@pytest.mark.asyncio(loop_scope="session")
async def test_registry_enablement():
    class S:
        anthropic_enabled = True
        anthropic_api_key = "sk-ant"
        anthropic_model = "claude-sonnet-4-6"
        ai_default_model = "claude-sonnet-4-6"
        openai_enabled = False
        openai_api_key = "sk-oai"
        openai_model = "gpt-4o-mini"
        gemini_enabled = True
        gemini_api_key = ""
        gemini_model = "gemini-2.0-flash"
        mistral_enabled = True
        mistral_api_key = "sk-mis"
        mistral_model = "mistral-small-latest"

    reg = build_registry_from_settings(S())  # type: ignore[arg-type]
    assert reg.get("anthropic").status == AVAILABLE
    assert reg.get("openai").status == DISABLED
    assert reg.get("gemini").status == BLOCKED  # enabled but missing key
    assert reg.get("mistral").status == AVAILABLE
    assert "openai" not in [p.name for p in reg.list_available()]


@pytest.mark.asyncio(loop_scope="session")
async def test_registry_rejects_duplicate_and_unknown():
    reg = ProviderRegistry()
    reg.register(
        RegisteredProvider(
            name="openai",
            enabled=True,
            configured=True,
            model="gpt-4o-mini",
            instance=FakeOpenAIProvider(),
            status=AVAILABLE,
        )
    )
    with pytest.raises(ValueError, match="Duplicate"):
        reg.register(
            RegisteredProvider(
                name="openai",
                enabled=True,
                configured=True,
                model="x",
                instance=None,
                status=DISABLED,
            )
        )
    with pytest.raises(ValueError, match="Unknown"):
        reg.register(
            RegisteredProvider(
                name="acme",
                enabled=True,
                configured=True,
                model="x",
                instance=None,
                status=AVAILABLE,
            )
        )


async def test_fixed_provider_no_silent_fallback():
    reg = ProviderRegistry()
    openai = FakeOpenAIProvider(behavior="rate_limit")
    gemini = FakeGeminiProvider(behavior="success")
    reg.register(RegisteredProvider("openai", True, True, "gpt-4o-mini", openai, AVAILABLE))
    reg.register(RegisteredProvider("gemini", True, True, "gemini-2.0-flash", gemini, AVAILABLE))
    policy = parse_routing_policy(mode=MODE_FIXED, provider="openai")
    router = ProviderRouter(reg, policy)
    result = await router.execute(GenerateRequest(system_prompt="s", user_prompt="u"))
    assert result.response is None
    assert result.error is not None
    assert result.error.code == PROVIDER_RATE_LIMITED
    assert len(result.attempts) == 1
    assert result.attempts[0].provider == "openai"
    assert gemini.calls == 0  # no silent switch


async def test_fixed_provider_blocked_when_unavailable():
    reg = ProviderRegistry()
    reg.register(RegisteredProvider("openai", True, False, "gpt-4o-mini", None, BLOCKED, detail="no key"))
    router = ProviderRouter(reg, parse_routing_policy(mode=MODE_FIXED, provider="openai"))
    result = await router.execute(GenerateRequest(system_prompt="s", user_prompt="u"))
    assert result.response is None
    assert result.error.code == PROVIDER_BLOCKED
    assert result.attempts[0].status == PROVIDER_BLOCKED


async def test_explicit_fallback_chain_records_attempts():
    reg = ProviderRegistry()
    openai = FakeOpenAIProvider(behavior="rate_limit")
    gemini = FakeGeminiProvider(behavior="success")
    reg.register(RegisteredProvider("openai", True, True, "gpt-4o-mini", openai, AVAILABLE))
    reg.register(RegisteredProvider("gemini", True, True, "gemini-2.0-flash", gemini, AVAILABLE))
    policy = parse_routing_policy(
        mode=MODE_FALLBACK_CHAIN,
        provider="openai",
        fallback_chain="openai,gemini",
    )
    result = await ProviderRouter(reg, policy).execute(GenerateRequest(system_prompt="s", user_prompt="u"))
    assert result.response is not None
    assert result.response.provider == "gemini"
    assert len(result.attempts) == 2
    assert result.attempts[0].status == PROVIDER_RATE_LIMITED
    assert result.attempts[0].provider == "openai"
    assert result.attempts[1].status == "SUCCESS"
    assert result.attempts[1].provider == "gemini"


@pytest.mark.asyncio(loop_scope="session")
async def test_budget_cost_known_and_unknown():
    ok = estimate_cost("openai", "gpt-4o-mini", 1000, 500)
    assert ok.cost_status == "ESTIMATED"
    assert ok.cost_usd > 0
    bad = estimate_cost("openai", "totally-unknown-model-xyz", 1000, 500)
    assert bad.cost_status == "UNAVAILABLE"
    assert bad.cost_usd == 0.0
    register_rate("openai", "totally-unknown-model-xyz", PriceRate(1.0, 2.0))
    fixed = estimate_cost("openai", "totally-unknown-model-xyz", 1_000_000, 1_000_000)
    assert fixed.cost_status == "ESTIMATED"
    assert fixed.cost_usd == 3.0


async def test_budget_estimate_exceeds_cap_semantics():
    """Unknown cost must not be treated as free ($0) for budget bypass."""
    est = estimate_cost("acme", "nope", 10, 10)
    assert est.cost_status == "UNAVAILABLE"
    assert est.cost_usd == 0.0
