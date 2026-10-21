"""Tests for Groq provider wiring added to the existing AI Gateway registry
and MCQ provider façade.

No network calls: ``build_registry_from_settings`` only constructs
provider objects (``OpenAIProvider.__init__`` does not touch the network —
it only stores api_key/model/base_url), and nothing here invokes
``.generate()``/``.generate_mcq()``.
"""

from __future__ import annotations

from app.core.config import Settings
from app.modules.ai.gateway.openai_provider import OpenAIProvider
from app.modules.ai.gateway.registry import AVAILABLE, BLOCKED, DISABLED, build_registry_from_settings
from app.modules.cms.services.mcq_llm_provider import (
    MCQ_SUPPORTED_PROVIDERS,
    normalize_mcq_provider_name,
    resolve_mcq_provider_selection,
)


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/db",
        "jwt_secret": "x" * 40,
    }
    base.update(overrides)
    return Settings(**base)


def test_groq_is_in_mcq_supported_providers():
    assert "groq" in MCQ_SUPPORTED_PROVIDERS


def test_normalize_mcq_provider_name_accepts_groq():
    assert normalize_mcq_provider_name("groq") == "groq"
    assert normalize_mcq_provider_name("GROQ") == "groq"


def test_registry_groq_disabled_by_default():
    settings = _settings()
    registry = build_registry_from_settings(settings)
    entry = registry.get("groq")
    assert entry is not None
    assert entry.enabled is False
    assert entry.status == DISABLED
    assert entry.instance is None


def test_registry_groq_blocked_without_api_key():
    settings = _settings(groq_enabled=True, groq_api_key="")
    registry = build_registry_from_settings(settings)
    entry = registry.get("groq")
    assert entry.status == BLOCKED
    assert entry.instance is None


def test_registry_groq_available_constructs_openai_compatible_provider():
    settings = _settings(
        groq_enabled=True,
        groq_api_key="fake-test-key-not-real",
        groq_generation_model="openai/gpt-oss-20b",
        groq_base_url="https://api.groq.com/openai/v1",
    )
    registry = build_registry_from_settings(settings)
    entry = registry.get("groq")
    assert entry.status == AVAILABLE
    assert isinstance(entry.instance, OpenAIProvider)
    assert entry.model == "openai/gpt-oss-20b"
    # No network call was made constructing this — OpenAIProvider.__init__
    # only stores config; verify no unexpected attribute leaked a live client.
    assert entry.instance._base_url == "https://api.groq.com/openai/v1"


def test_registry_groq_base_url_alone_does_not_configure_it():
    """Unlike the 'local' OpenAI override, Groq always needs a real key —
    a bare base_url must never be treated as 'configured'."""
    settings = _settings(groq_enabled=True, groq_api_key="", groq_base_url="https://api.groq.com/openai/v1")
    registry = build_registry_from_settings(settings)
    entry = registry.get("groq")
    assert entry.configured is False
    assert entry.status == BLOCKED


def test_resolve_mcq_provider_selection_for_groq():
    settings = _settings(
        mcq_provider="groq",
        groq_generation_model="openai/gpt-oss-20b",
    )
    selection = resolve_mcq_provider_selection(settings)
    assert selection.registry_name == "groq"
    assert selection.model == "openai/gpt-oss-20b"


def test_verification_model_is_distinct_setting_from_generation_model():
    """Hard requirement: generation and verification must be two separate
    settings, never one shared model string."""
    settings = _settings()
    assert settings.groq_generation_model != settings.groq_verification_model
    assert settings.groq_generation_model == "openai/gpt-oss-20b"
    assert settings.groq_verification_model == "openai/gpt-oss-120b"
