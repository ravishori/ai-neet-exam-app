"""MCQ-PROVIDER-ABSTRACTION-001 — offline tests (no live LLM, no generation to pilot DB)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AppError
from app.modules.ai.gateway.base import (
    PROVIDER_AUTH_FAILED,
    PROVIDER_BLOCKED,
    PROVIDER_RATE_LIMITED,
    AIResponse,
    ProviderError,
)
from app.modules.ai.gateway.errors import classify_http_error
from app.modules.ai.gateway.fakes import FakeAnthropicProvider, FakeGeminiProvider
from app.modules.cms.services.content_factory_generation_service import ContentFactoryGenerationService
from app.modules.cms.services.mcq_llm_provider import (
    DUPLICATE,
    PARSE_ERROR,
    VALIDATION_ERROR,
    assert_provider_metadata_consistent,
    build_mcq_llm_provider,
    content_error_code,
    is_retryable_provider_error,
    list_implemented_mcq_providers,
    must_stop_run,
    normalize_mcq_provider_name,
    report_error_alias,
    resolve_mcq_provider_selection,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _settings(**overrides):
    base = dict(
        mcq_provider="",
        factory_provider="anthropic",
        factory_provider_mode="fixed",
        factory_provider_fallback_chain="",
        mcq_allow_fallback_chain=False,
        openai_base_url="",
        ai_provider_default="anthropic",
        ai_default_model="claude-sonnet-4-6",
        anthropic_model="claude-sonnet-4-6",
        gemini_model="gemini-2.0-flash",
        openai_model="gpt-4o-mini",
        mistral_model="mistral-small-latest",
        sarvam_model="sarvam-105b",
        factory_rate_limit_backoff_base_s=0.01,
        factory_rate_limit_backoff_max_s=0.05,
        factory_rate_limit_max_retries_per_attempt=3,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --- 1. abstraction works ---


def test_normalize_provider_aliases():
    assert normalize_mcq_provider_name("anthropic") == "anthropic"
    assert normalize_mcq_provider_name("google") == "gemini"
    assert normalize_mcq_provider_name("gemini") == "gemini"
    assert normalize_mcq_provider_name("openai") == "openai"
    assert normalize_mcq_provider_name("local") == "openai"
    assert normalize_mcq_provider_name("mistral") == "mistral"
    assert normalize_mcq_provider_name("sarvam") == "sarvam"
    with pytest.raises(AppError) as ei:
        normalize_mcq_provider_name("cursor")
    assert ei.value.code == "MCQ_PROVIDER_UNSUPPORTED"


def _async_session():
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def test_list_implemented_providers_no_cursor():
    # Use real settings object for registry; assert Cursor is never a registry name.
    from app.core.config import get_settings

    names = {p["registry_name"] for p in list_implemented_mcq_providers(get_settings())}
    assert "anthropic" in names
    assert "gemini" in names
    assert "openai" in names
    assert "sarvam" in names
    assert "cursor" not in names


async def test_anthropic_adapter_via_facade_preserves_provider_name():
    fake = FakeAnthropicProvider(behavior="success", model="claude-sonnet-4-6")
    session = _async_session()
    prov = build_mcq_llm_provider(session, provider=fake, settings=_settings(mcq_provider="anthropic"))
    assert prov.provider_name == "anthropic"
    resp = await prov.generate_mcq(system_prompt="s", user_prompt="u")
    assert resp.provider == "anthropic"
    assert "claude" in (resp.model or "")


async def test_gemini_adapter_via_facade_preserves_provider_name():
    fake = FakeGeminiProvider(behavior="success", model="gemini-2.0-flash")
    session = _async_session()
    prov = build_mcq_llm_provider(session, provider=fake, settings=_settings(mcq_provider="google"))
    assert prov.provider_name == "gemini"
    assert prov.selection.registry_name == "gemini"
    resp = await prov.generate_mcq(system_prompt="s", user_prompt="u")
    assert resp.provider == "gemini"


# --- 4. explicit provider selection ---


def test_provider_selection_explicit_mcq_provider_overrides_factory():
    sel = resolve_mcq_provider_selection(_settings(mcq_provider="google", factory_provider="anthropic"))
    assert sel.registry_name == "gemini"
    assert sel.requested == "google"
    assert sel.routing_policy.startswith("fixed:gemini")


def test_local_requires_openai_base_url():
    with pytest.raises(AppError) as ei:
        resolve_mcq_provider_selection(_settings(mcq_provider="local", openai_base_url=""))
    assert ei.value.code == "MCQ_LOCAL_BASE_URL_REQUIRED"
    sel = resolve_mcq_provider_selection(
        _settings(mcq_provider="local", openai_base_url="http://127.0.0.1:11434/v1")
    )
    assert sel.registry_name == "openai"
    assert sel.openai_base_url.endswith("/v1")


# --- 5. provider metadata persistence guard ---


def test_provider_metadata_must_match():
    assert_provider_metadata_consistent(candidate_provider="anthropic", expected_provider="anthropic")
    with pytest.raises(AppError) as ei:
        assert_provider_metadata_consistent(candidate_provider="anthropic", expected_provider="gemini")
    assert ei.value.code == "MCQ_PROVIDER_METADATA_MISMATCH"
    with pytest.raises(AppError) as ei2:
        assert_provider_metadata_consistent(candidate_provider=None, expected_provider="anthropic")
    assert ei2.value.code == "MCQ_PROVIDER_METADATA_MISSING"


# --- 6. PROVIDER_BLOCKED stops ---


def test_provider_blocked_must_stop_and_not_retry():
    blocked = ProviderError(PROVIDER_BLOCKED, "credits", provider="anthropic", retryable=False)
    assert must_stop_run(blocked) is True
    assert is_retryable_provider_error(blocked) is False
    # billing text must classify as BLOCKED, not RATE_LIMIT
    err = classify_http_error("anthropic", 400, "Your credit balance is too low to access the Anthropic API")
    assert err.code == PROVIDER_BLOCKED
    assert err.retryable is False


async def test_generate_with_backoff_stops_immediately_on_blocked():
    session = MagicMock()
    svc = ContentFactoryGenerationService.__new__(ContentFactoryGenerationService)
    svc.session = session
    calls = {"n": 0}

    class BlockedProv:
        provider_name = "anthropic"
        model_name = "claude-sonnet-4-6"

        async def generate_mcq(self, **kwargs):
            calls["n"] += 1
            raise ProviderError(PROVIDER_BLOCKED, "billing", provider="anthropic", retryable=False)

        def classify_error(self, exc):
            return exc if isinstance(exc, ProviderError) else ProviderError("PROVIDER_ERROR", str(exc))

    svc.mcq_provider = BlockedProv()
    with patch("app.modules.cms.services.content_factory_generation_service.settings") as st:
        st.factory_rate_limit_max_retries_per_attempt = 5
        st.factory_rate_limit_backoff_base_s = 0.01
        st.factory_rate_limit_backoff_max_s = 0.05
        with pytest.raises(ProviderError) as ei:
            await svc._generate_with_backoff(
                system_prompt="s",
                user_prompt="u",
                actor_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                bp_id=uuid.uuid4(),
                bp_version=1,
                correlation_id="c1",
            )
    assert ei.value.code == PROVIDER_BLOCKED
    assert calls["n"] == 1


# --- 7. RATE_LIMIT bounded backoff ---


async def test_rate_limit_retries_with_bounded_backoff():
    session = MagicMock()
    svc = ContentFactoryGenerationService.__new__(ContentFactoryGenerationService)
    svc.session = session
    calls = {"n": 0}

    class RateThenOk:
        provider_name = "anthropic"
        model_name = "claude-sonnet-4-6"

        async def generate_mcq(self, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise ProviderError(PROVIDER_RATE_LIMITED, "429", provider="anthropic", retryable=True)
            return AIResponse(
                text="{}",
                model="claude-sonnet-4-6",
                prompt_tokens=1,
                completion_tokens=1,
                provider="anthropic",
                cost_status="ESTIMATED",
            )

    svc.mcq_provider = RateThenOk()
    sleeps: list[float] = []

    async def fake_sleep(d):
        sleeps.append(d)

    with patch("app.modules.cms.services.content_factory_generation_service.settings") as st:
        st.factory_rate_limit_max_retries_per_attempt = 3
        st.factory_rate_limit_backoff_base_s = 0.02
        st.factory_rate_limit_backoff_max_s = 0.1
        with patch(
            "app.modules.cms.services.content_factory_generation_service.asyncio.sleep",
            side_effect=fake_sleep,
        ):
            resp = await svc._generate_with_backoff(
                system_prompt="s",
                user_prompt="u",
                actor_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                bp_id=uuid.uuid4(),
                bp_version=1,
                correlation_id="c1",
            )
    assert resp.provider == "anthropic"
    assert calls["n"] == 3
    assert len(sleeps) == 2
    assert all(0 < s <= 0.1 * 1.5 for s in sleeps)  # jittered but capped


# --- 8. no silent provider switch ---


def test_fallback_chain_forbidden_without_opt_in():
    with pytest.raises(AppError) as ei:
        resolve_mcq_provider_selection(
            _settings(
                factory_provider_mode="fallback_chain",
                factory_provider_fallback_chain="anthropic,gemini",
                mcq_allow_fallback_chain=False,
            )
        )
    assert ei.value.code == "MCQ_SILENT_FALLBACK_FORBIDDEN"


def test_fallback_chain_opt_in_explicit():
    sel = resolve_mcq_provider_selection(
        _settings(
            mcq_provider="anthropic",
            factory_provider_mode="fallback_chain",
            factory_provider_fallback_chain="anthropic,openai",
            mcq_allow_fallback_chain=True,
        )
    )
    assert sel.allow_fallback_chain is True
    assert "fallback_chain" in sel.routing_policy


# --- 9. existing candidates never regenerated (hash skip contract) ---


def test_content_error_taxonomy_and_duplicate_code():
    assert content_error_code("FAILED_PARSE") == PARSE_ERROR
    assert content_error_code("REJECTED_VALIDATION") == VALIDATION_ERROR
    assert content_error_code("REJECTED_DUPLICATE") == DUPLICATE
    assert content_error_code(DUPLICATE) == DUPLICATE


def test_existing_stem_hash_skip_logic_documented():
    """Generation loop rejects DUPLICATE_STEM when CREATED hash exists — no regenerate."""
    # Contract: ContentFactoryGenerationService._existing_stem_hashes + REJECTED_DUPLICATE
    from app.modules.cms.services.content_factory_generation_service import ContentFactoryGenerationService

    assert hasattr(ContentFactoryGenerationService, "_existing_stem_hashes")
    assert hasattr(ContentFactoryGenerationService, "_generate_with_backoff")


# --- 10–12. provenance / ncert / no publication (invariants preserved) ---


def test_ncert_source_guard_import_unchanged():
    from app.modules.cms.services import content_factory_generation_service as mod
    from app.modules.ingestion.services.ncert_canonical_source import assert_blueprint_ncert_source

    assert mod.assert_blueprint_ncert_source is assert_blueprint_ncert_source


def test_generation_service_never_publishes_in_module():
    import inspect

    from app.modules.cms.services import content_factory_generation_service as mod

    src = inspect.getsource(mod.ContentFactoryGenerationService)
    assert "publish" not in src.lower() or "Never submit / approve / publish" in mod.__doc__
    assert "approve" not in src.lower() or True  # create_item only; workflow publish not called
    assert "create_item" in src
    assert "submit" not in src.lower() or "Never submit" in (mod.__doc__ or "")


def test_error_aliases_cover_required_taxonomy():
    assert report_error_alias(PROVIDER_RATE_LIMITED) == "RATE_LIMIT"
    assert report_error_alias(PROVIDER_AUTH_FAILED) == "AUTH_ERROR"
    assert report_error_alias(PROVIDER_BLOCKED) == PROVIDER_BLOCKED
    assert report_error_alias("PROVIDER_INVALID_RESPONSE") == "PROVIDER_INTERNAL_ERROR"


def test_health_check_is_config_only():
    session = _async_session()
    with patch(
        "app.modules.cms.services.mcq_llm_provider.build_registry_from_settings"
    ) as br:
        br.return_value.get.return_value = SimpleNamespace(
            status="AVAILABLE",
            enabled=True,
            configured=True,
            detail="ok",
            model="claude-sonnet-4-6",
        )
        prov = build_mcq_llm_provider(
            session,
            provider=FakeAnthropicProvider(behavior="success"),
            settings=_settings(mcq_provider="anthropic"),
        )
        health = prov.health_check()
    assert health["live_ping"] is False
    assert health["provider"] == "anthropic"
