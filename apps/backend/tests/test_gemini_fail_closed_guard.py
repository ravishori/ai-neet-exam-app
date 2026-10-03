"""Fail-closed Gemini guard (FACTORY-SEC-001 follow-up).

Proves that GeminiProvider construction -- and therefore every entry point
that constructs one -- is rejected whenever settings.gemini_enabled is
False, with no real network call ever attempted. All tests here mock
httpx.AsyncClient so that even if the guard regressed, no real HTTP request
would leave this process; the actual assertion in every test is that the
mocked client is NEVER invoked at all (construction fails before any call
is made).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.modules.ai.gateway.base import PROVIDER_DISABLED, ProviderError
from app.modules.ai.gateway.gemini_provider import GeminiProvider

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _NetworkCallMadeError(AssertionError):
    """Raised if any test manages to reach a real HTTP call -- a hard
    failure distinct from any expected ProviderError."""


def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _factory(*_args: Any, **_kwargs: Any) -> Any:
        raise _NetworkCallMadeError("httpx.AsyncClient was constructed -- a real network call was attempted")

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


def _patch_settings(monkeypatch: pytest.MonkeyPatch, *, gemini_enabled: bool, **extra: Any) -> None:
    fake_settings = SimpleNamespace(
        gemini_enabled=gemini_enabled,
        gemini_api_key="fake-key-never-used",
        gemini_model="gemini-3.6-flash",
        pyq_gemini_backfill_model="",
        pyq_gemini_backfill_preferred_model="gemini-2.5-flash-lite",
        **extra,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: fake_settings)


def test_gemini_provider_construction_rejected_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid_network(monkeypatch)
    _patch_settings(monkeypatch, gemini_enabled=False)

    with pytest.raises(ProviderError) as exc_info:
        GeminiProvider(api_key="fake-key", model="gemini-3.6-flash")

    assert exc_info.value.code == PROVIDER_DISABLED
    assert exc_info.value.provider == "gemini"
    assert exc_info.value.retryable is False


def test_gemini_provider_construction_allowed_when_enabled_but_still_no_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enabled construction must still succeed (no behavior regression for
    the normal case) -- but merely constructing the object must not itself
    make any network call (generate() is never invoked in this test)."""
    _forbid_network(monkeypatch)
    _patch_settings(monkeypatch, gemini_enabled=True)

    provider = GeminiProvider(api_key="fake-key", model="gemini-3.6-flash")
    assert provider is not None
    assert provider.name == "gemini"


async def test_resolve_pyq_answers_stage2_default_gateway_blocked_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The PYQ resolver's Stage-2 path builds a GeminiProvider directly
    (bypassing the AIGateway router's own gemini_enabled check) -- this is
    exactly the bypass the audit identified. Confirms the central guard in
    GeminiProvider now closes it too, with no DB session needed since the
    provider construction itself fails before anything else happens."""
    _forbid_network(monkeypatch)
    _patch_settings(monkeypatch, gemini_enabled=False)

    from scripts.resolve_pyq_answers import _stage2_default_gateway

    with pytest.raises(ProviderError) as exc_info:
        _stage2_default_gateway(session=None)  # session is unused before the provider construction raises

    assert exc_info.value.code == PROVIDER_DISABLED


async def test_pyq_gemini_backfill_model_probe_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The admin Gemini-backfill endpoint's model-availability probe also
    constructs GeminiProvider directly. Confirms it is blocked too, and
    that the existing except ProviderError handling in that function
    degrades safely rather than crashing or silently proceeding."""
    _forbid_network(monkeypatch)
    _patch_settings(monkeypatch, gemini_enabled=False)

    from app.modules.cms.pyq.pyq_gemini_backfill import select_backfill_model

    # select_backfill_model()'s own try/except ProviderError catches the
    # guard's exception and falls through to its documented fallback
    # (settings.gemini_model) -- it must never reach the point of
    # returning the "verified" candidate model, since no real call ever
    # succeeded (none was even attempted -- see _forbid_network above).
    result = await select_backfill_model()
    assert result == "gemini-3.6-flash"  # the fallback (settings.gemini_model), not the probed candidate
