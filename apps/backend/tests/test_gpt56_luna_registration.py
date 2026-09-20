"""Unit tests: GPT-5.6 Luna capability + pricing + provider routing.

No live API calls. Verifies that the smallest reversible changes made for
the 100-MCQ Luna pilot land the model correctly in the gateway registries
so the Content Factory can select it via ``FACTORY_PROVIDER=openai`` +
``OPENAI_MODEL=gpt-5.6-luna``.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.modules.ai.gateway.capabilities import _CAPABILITIES
from app.modules.ai.gateway.openai_provider import uses_max_completion_tokens
from app.modules.ai.gateway.pricing import estimate_cost
from app.modules.ai.gateway.registry import build_registry_from_settings
from app.modules.cms.services.mcq_llm_provider import resolve_mcq_provider_selection

LUNA = "gpt-5.6-luna"


def test_capability_registered():
    cap = _CAPABILITIES.get(("openai", LUNA))
    assert cap is not None, "gpt-5.6-luna capability must be registered"
    assert cap.provider == "openai"
    assert cap.model == LUNA
    assert cap.supports_structured_output is True


def test_pricing_matches_operator_confirmed_rate():
    est = estimate_cost("openai", LUNA, 1_000_000, 1_000_000)
    assert est.cost_status == "ESTIMATED"
    # $0.20 per M input + $1.20 per M output = $1.40 for 1M+1M tokens.
    assert est.cost_usd == pytest.approx(1.40, rel=1e-6)


def test_pricing_scales_linearly_and_uses_declared_rates():
    # 500k input, 250k output → 500_000 * 0.20 / 1M + 250_000 * 1.20 / 1M
    est = estimate_cost("openai", LUNA, 500_000, 250_000)
    expected = (500_000 * 0.20 + 250_000 * 1.20) / 1_000_000
    assert est.cost_status == "ESTIMATED"
    assert est.cost_usd == pytest.approx(expected, rel=1e-6)


def test_uses_max_completion_tokens_for_luna():
    """GPT-5.6 family is a reasoning-family Chat Completions model. The
    provider adapter must send max_completion_tokens, not the legacy
    max_tokens; otherwise the API returns 400 unsupported_parameter."""
    assert uses_max_completion_tokens(LUNA) is True
    # Non-luna GPT-5 sibling stays covered by the existing gpt-5 prefix.
    assert uses_max_completion_tokens("gpt-5-mini") is True
    # A non-reasoning-family model still uses classic max_tokens.
    assert uses_max_completion_tokens("gpt-4o-mini") is False


def test_registry_selects_luna_when_env_configured(monkeypatch):
    """Setting OPENAI_ENABLED / OPENAI_API_KEY / OPENAI_MODEL for Luna
    yields an AVAILABLE provider with the exact model id — no fallback
    substitution."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-only")
    monkeypatch.setattr(settings, "openai_model", LUNA)
    monkeypatch.setattr(settings, "openai_base_url", "")

    registry = build_registry_from_settings(settings)
    entry = registry.get("openai")
    assert entry is not None
    assert entry.status == "AVAILABLE"
    assert entry.model == LUNA
    assert entry.instance is not None
    assert entry.instance.name == "openai"


def test_mcq_provider_selection_routes_to_openai_luna(monkeypatch):
    """resolve_mcq_provider_selection() honors FACTORY_PROVIDER=openai and
    reports gpt-5.6-luna. No silent fallback to another provider."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_enabled", True)
    monkeypatch.setattr(settings, "openai_model", LUNA)
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-only")
    monkeypatch.setattr(settings, "openai_base_url", "")
    monkeypatch.setattr(settings, "factory_provider", "openai")
    monkeypatch.setattr(settings, "factory_provider_mode", "fixed")
    monkeypatch.setattr(settings, "mcq_provider", "")
    monkeypatch.setattr(settings, "mcq_allow_fallback_chain", False)

    sel = resolve_mcq_provider_selection(settings)
    assert sel.registry_name == "openai"
    assert sel.model == LUNA
    assert sel.mode == "fixed"
    assert sel.routing_policy == "fixed:openai"
    assert sel.allow_fallback_chain is False


def test_fallback_chain_still_forbidden_without_explicit_opt_in(monkeypatch):
    """Sanity: even after adding Luna, the existing silent-fallback ban
    remains — no accidental Claude / Gemini invocation during this pilot."""
    from app.core.exceptions import AppError

    settings = get_settings()
    monkeypatch.setattr(settings, "openai_enabled", True)
    monkeypatch.setattr(settings, "openai_model", LUNA)
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-only")
    monkeypatch.setattr(settings, "openai_base_url", "")
    monkeypatch.setattr(settings, "factory_provider", "openai")
    monkeypatch.setattr(settings, "factory_provider_mode", "fallback_chain")
    monkeypatch.setattr(settings, "mcq_provider", "")
    monkeypatch.setattr(settings, "mcq_allow_fallback_chain", False)  # opt-in NOT given
    monkeypatch.setattr(settings, "factory_provider_fallback_chain", "anthropic,gemini")

    with pytest.raises(AppError) as exc:
        resolve_mcq_provider_selection(settings)
    assert exc.value.code == "MCQ_SILENT_FALLBACK_FORBIDDEN"
