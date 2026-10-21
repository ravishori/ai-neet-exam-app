"""Tests for MCQ-FACTORY-PROVIDER-AGNOSTIC-001 — independent, settings-
driven provider+model selection for the two MCQ-factory orchestrator call
sites (generation vs verification), each defaulting to Groq.

ZERO real network calls, ZERO real API keys, ZERO real database writes:

- HTTP is mocked by monkeypatching ``httpx.AsyncClient`` with a fake
  client/response pair, exactly the pattern already used by
  ``tests/test_openai_adapter_fix_001.py`` — never a live connection.
- The "hypothetical second provider" used to prove the selection logic
  genuinely branches (rather than being hard-coded to Groq) is plain
  ``openai`` with a fake key — it is never actually called over the
  network; only its locally-stored config (base_url/model) is inspected,
  or its HTTP call is intercepted by the same fake client.
- The DB session used anywhere ``AIGateway`` needs one is a bare
  in-memory fake (``_FakeDbSession``) with no SQLAlchemy engine.
- Budget-enforcement tests reuse the exact harness pattern already
  proven by ``test_mcq_factory_groq_orchestrator.py`` (``ScriptedCaller``,
  a fake publication-gate session, an in-memory staging writer).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.modules.ai.gateway.base import AIResponse
from app.modules.ai.gateway.groq_provider import GroqProvider
from app.modules.ai.gateway.openai_provider import OpenAIProvider
from app.modules.ai.gateway.pricing import PriceRate, estimate_cost, register_rate
from app.modules.ai.gateway.provider_capability_profiles import (
    ProviderCapabilityProfile,
    get_capability_profile,
    register_capability_profile,
    seed_default_groq_profiles,
)
from app.modules.ai.gateway.registry import AVAILABLE, build_registry_from_settings
from app.modules.cms.mcq_factory_groq.orchestrator import (
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    FactSpec,
    GroqFactoryOrchestrator,
    build_mcq_factory_generation_caller,
    build_mcq_factory_verification_caller,
)
from app.modules.cms.mcq_factory_groq.pdf_text_index import index_pdf
from app.modules.cms.mcq_factory_groq.schemas import TaxonomyIds
from app.modules.cms.mcq_factory_groq.validators import InMemoryTaxonomyResolver
from app.modules.cms.services.mcq_factory_groq_controls import GroqFactoryCheckpoint, GroqFactoryLimits
from app.modules.cms.services.mcq_llm_provider import (
    build_mcq_factory_stage_caller,
    build_mcq_factory_stage_provider,
    resolve_mcq_factory_stage_selection,
)
from app.modules.cms.syllabus.neet_2026_parser import NeetSyllabusRegistry, NeetSyllabusTopic, NeetSyllabusUnit

def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/db",
        "jwt_secret": "x" * 40,
    }
    base.update(overrides)
    return Settings(**base)


class _FakeDbSession:
    """Bare in-memory stand-in for an AsyncSession — just enough surface
    for AIGateway._log() to run without a real SQLAlchemy engine."""

    def __init__(self) -> None:
        self.added: list = []
        self.info: dict = {}

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None

    async def flush(self) -> None:
        return None


class _FakeHttpClient:
    """Captures the request and returns a canned Chat-Completions-shaped
    response — mirrors tests/test_openai_adapter_fix_001.py exactly."""

    _captured: list[dict] = []

    def __init__(self, *a, **k) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None):
        self.__class__._captured.append({"url": url, "json": json})

        class _Resp:
            status_code = 200

            def json(self_inner):
                return {
                    "id": "chatcmpl-test",
                    "model": json.get("model") if json else "unknown",
                    "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 4},
                }

        return _Resp()


# ---------------------------------------------------------------------------
# A. Pure selection resolution — Groq default + hypothetical second provider
# ---------------------------------------------------------------------------


def test_generation_selection_defaults_to_groq_when_unset():
    s = _settings()
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "groq"
    assert sel.model == s.groq_generation_model


def test_verification_selection_defaults_to_groq_when_unset():
    s = _settings()
    sel = resolve_mcq_factory_stage_selection("verification", settings=s)
    assert sel.registry_name == "groq"
    assert sel.model == s.groq_verification_model


def test_generation_and_verification_selections_are_independent():
    """Setting the GENERATION provider must never affect the
    independently-configured VERIFICATION provider, and vice versa."""
    s = _settings(
        mcq_factory_generation_provider="openai",
        mcq_factory_generation_model="gpt-4o-mini",
        openai_enabled=True,
        openai_api_key="fake-test-key",
    )
    gen_sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    verify_sel = resolve_mcq_factory_stage_selection("verification", settings=s)

    assert gen_sel.registry_name == "openai"
    assert gen_sel.model == "gpt-4o-mini"
    # Verification was never touched — still the Groq default.
    assert verify_sel.registry_name == "groq"
    assert verify_sel.model == s.groq_verification_model


def test_selection_genuinely_branches_not_hardcoded():
    """The SAME resolver function, called with different settings, must
    resolve to genuinely different registry names/models — proving this
    is a real branch, not a constant disguised as a function."""
    groq_default = resolve_mcq_factory_stage_selection(
        "generation", settings=_settings()
    )
    second_provider = resolve_mcq_factory_stage_selection(
        "generation",
        settings=_settings(
            mcq_factory_generation_provider="openai",
            mcq_factory_generation_model="gpt-4o-mini",
            openai_enabled=True,
            openai_api_key="fake-test-key",
        ),
    )
    assert groq_default.registry_name != second_provider.registry_name
    assert groq_default.model != second_provider.model
    assert groq_default.registry_name == "groq"
    assert second_provider.registry_name == "openai"


def test_unsupported_provider_name_fails_closed_never_silently_groq():
    s = _settings(mcq_factory_generation_provider="not_a_real_vendor")
    with pytest.raises(AppError) as exc_info:
        resolve_mcq_factory_stage_selection("generation", settings=s)
    assert exc_info.value.code == "MCQ_PROVIDER_UNSUPPORTED"


def test_unsupported_verification_provider_name_also_fails_closed():
    s = _settings(mcq_factory_verification_provider="totally_made_up")
    with pytest.raises(AppError) as exc_info:
        resolve_mcq_factory_stage_selection("verification", settings=s)
    assert exc_info.value.code == "MCQ_PROVIDER_UNSUPPORTED"


def test_valid_but_unconfigured_provider_resolves_but_is_not_available():
    """A valid provider name with no key configured is NOT the same
    failure mode as an unsupported name — it resolves cleanly but reports
    itself unavailable, letting the caller decide (raise for generation,
    None for verification — see build_mcq_factory_stage_provider tests)."""
    s = _settings(mcq_factory_generation_provider="openai", openai_enabled=False, openai_api_key="")
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "openai"
    assert sel.enabled is False
    assert sel.configured is False


# ---------------------------------------------------------------------------
# B. build_mcq_factory_stage_provider / _caller — fail-closed semantics
# ---------------------------------------------------------------------------


def test_build_stage_provider_returns_none_for_unconfigured_openai():
    s = _settings(mcq_factory_generation_provider="openai", openai_enabled=False, openai_api_key="")
    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is None
    assert selection.registry_name == "openai"


def test_build_stage_provider_constructs_groq_default():
    s = _settings(groq_enabled=True, groq_api_key="fake-test-key")
    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is not None
    assert isinstance(provider, GroqProvider)
    assert selection.model == s.groq_generation_model


def test_build_stage_caller_generation_raises_when_unconfigured():
    s = _settings(mcq_factory_generation_provider="openai", openai_enabled=False, openai_api_key="")
    with pytest.raises(AppError) as exc_info:
        build_mcq_factory_stage_caller(_FakeDbSession(), stage="generation", settings=s)
    assert exc_info.value.code == "MCQ_FACTORY_GENERATION_PROVIDER_UNAVAILABLE"


def test_build_stage_caller_verification_returns_none_when_unconfigured():
    """Verification must fail closed to None (never raise, never silently
    substitute Groq) so the orchestrator's routing rule can force
    REVIEW_REQUIRED instead of crashing the whole batch."""
    s = _settings(mcq_factory_verification_provider="openai", openai_enabled=False, openai_api_key="")
    caller = build_mcq_factory_stage_caller(_FakeDbSession(), stage="verification", settings=s)
    assert caller is None


def test_build_stage_caller_unsupported_name_raises_for_both_stages():
    s_gen = _settings(mcq_factory_generation_provider="bogus_vendor")
    with pytest.raises(AppError):
        build_mcq_factory_stage_caller(_FakeDbSession(), stage="generation", settings=s_gen)

    s_verify = _settings(mcq_factory_verification_provider="bogus_vendor")
    with pytest.raises(AppError):
        build_mcq_factory_stage_caller(_FakeDbSession(), stage="verification", settings=s_verify)


# ---------------------------------------------------------------------------
# C. Real routing proof via mocked HTTP — generation vs verification hit
#    their OWN independently-configured provider/model, never each other's
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generation_caller_routes_to_groq_default(monkeypatch):
    _FakeHttpClient._captured = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeHttpClient)
    s = _settings(groq_enabled=True, groq_api_key="fake-test-key", groq_generation_model="openai/gpt-oss-20b")

    caller = build_mcq_factory_generation_caller(_FakeDbSession(), settings=s)
    resp = await caller(system_prompt="sys", user_prompt="user", max_tokens=50)

    assert isinstance(resp, AIResponse)
    assert len(_FakeHttpClient._captured) == 1
    call = _FakeHttpClient._captured[0]
    assert call["url"].startswith("https://api.groq.com/openai/v1")
    assert call["json"]["model"] == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_verification_caller_routes_to_groq_default_independently(monkeypatch):
    _FakeHttpClient._captured = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeHttpClient)
    s = _settings(groq_enabled=True, groq_api_key="fake-test-key", groq_verification_model="openai/gpt-oss-120b")

    caller = build_mcq_factory_verification_caller(_FakeDbSession(), settings=s)
    assert caller is not None
    resp = await caller(system_prompt="sys", user_prompt="user", max_tokens=50)

    assert isinstance(resp, AIResponse)
    call = _FakeHttpClient._captured[-1]
    assert call["url"].startswith("https://api.groq.com/openai/v1")
    assert call["json"]["model"] == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_generation_caller_routes_to_hypothetical_second_provider(monkeypatch):
    """Switching ONLY mcq_factory_generation_provider/_model must switch
    the ACTUAL HTTP destination away from Groq — proving the routing is
    a genuine branch on config, not a hard-coded Groq call underneath."""
    _FakeHttpClient._captured = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeHttpClient)
    s = _settings(
        mcq_factory_generation_provider="openai",
        mcq_factory_generation_model="gpt-4o-mini",
        openai_enabled=True,
        openai_api_key="fake-test-key",
    )

    caller = build_mcq_factory_generation_caller(_FakeDbSession(), settings=s)
    resp = await caller(system_prompt="sys", user_prompt="user", max_tokens=50)

    assert isinstance(resp, AIResponse)
    call = _FakeHttpClient._captured[-1]
    assert call["url"].startswith("https://api.openai.com/v1")
    assert "groq" not in call["url"]
    assert call["json"]["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_generation_and_verification_use_different_providers_simultaneously(monkeypatch):
    """Generation routed to the hypothetical second provider (openai)
    while verification stays on the Groq default — both built from the
    SAME settings object, neither call site leaks into the other."""
    _FakeHttpClient._captured = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeHttpClient)
    s = _settings(
        mcq_factory_generation_provider="openai",
        mcq_factory_generation_model="gpt-4o-mini",
        openai_enabled=True,
        openai_api_key="fake-test-key",
        groq_enabled=True,
        groq_api_key="fake-test-key",
    )

    gen_caller = build_mcq_factory_generation_caller(_FakeDbSession(), settings=s)
    verify_caller = build_mcq_factory_verification_caller(_FakeDbSession(), settings=s)
    assert verify_caller is not None

    await gen_caller(system_prompt="sys", user_prompt="user", max_tokens=50)
    await verify_caller(system_prompt="sys", user_prompt="user", max_tokens=50)

    assert len(_FakeHttpClient._captured) == 2
    gen_call, verify_call = _FakeHttpClient._captured
    assert gen_call["url"].startswith("https://api.openai.com/v1")
    assert gen_call["json"]["model"] == "gpt-4o-mini"
    assert verify_call["url"].startswith("https://api.groq.com/openai/v1")
    assert verify_call["json"]["model"] == s.groq_verification_model


# ---------------------------------------------------------------------------
# D. GroqProvider identity fix — correct lineage on the injected call path
# ---------------------------------------------------------------------------


def test_groq_provider_subclass_has_correct_name_and_is_openai_compatible():
    p = GroqProvider(api_key="fake-key", model="openai/gpt-oss-20b")
    assert p.name == "groq"
    assert isinstance(p, OpenAIProvider)


def test_registry_groq_entry_instance_has_groq_name_not_openai():
    s = _settings(groq_enabled=True, groq_api_key="fake-test-key")
    registry = build_registry_from_settings(s)
    entry = registry.get("groq")
    assert entry.status == AVAILABLE
    assert entry.instance.name == "groq"


# ---------------------------------------------------------------------------
# E. Pricing / capability-profile coexistence across provider+model pairs
# ---------------------------------------------------------------------------


def test_pricing_table_lets_groq_and_a_second_provider_coexist():
    s = _settings(groq_enabled=True, groq_api_key="fake-test-key")
    # Populates the real _RATES table with Groq's actual rates (same path
    # production code uses).
    build_registry_from_settings(s)
    groq_rate_before = estimate_cost("groq", s.groq_generation_model, 1_000_000, 0)

    register_rate("mock_vendor_x", "mock-model-x", PriceRate(9.99, 19.99))
    mock_cost = estimate_cost("mock_vendor_x", "mock-model-x", 1_000_000, 0)
    groq_rate_after = estimate_cost("groq", s.groq_generation_model, 1_000_000, 0)

    assert mock_cost.cost_status == "ESTIMATED"
    assert mock_cost.cost_usd == pytest.approx(9.99)
    # Registering the second provider's rate must not disturb Groq's.
    assert groq_rate_after.cost_usd == pytest.approx(groq_rate_before.cost_usd)
    assert groq_rate_after.cost_status == "ESTIMATED"


def test_capability_profiles_coexist_for_groq_and_second_provider():
    s = _settings()
    seed_default_groq_profiles(s)
    groq_gen_profile = get_capability_profile("groq", s.groq_generation_model)
    assert groq_gen_profile is not None
    assert groq_gen_profile.rate_limit_requests_per_minute == s.mcq_factory_groq_rate_limit_rpm
    assert groq_gen_profile.max_tokens_per_call == s.mcq_factory_groq_max_generation_tokens

    second_profile = ProviderCapabilityProfile(
        rate_limit_requests_per_minute=999,
        rate_limit_tokens_per_minute=123456,
        max_retries=7,
        max_tokens_per_call=4096,
    )
    register_capability_profile("mock_vendor_x", "mock-model-x", second_profile)

    # Both coexist with their own distinct numbers — neither overwrote the other.
    groq_gen_profile_again = get_capability_profile("groq", s.groq_generation_model)
    mock_profile_again = get_capability_profile("mock_vendor_x", "mock-model-x")
    assert groq_gen_profile_again.rate_limit_requests_per_minute == s.mcq_factory_groq_rate_limit_rpm
    assert mock_profile_again.rate_limit_requests_per_minute == 999
    assert mock_profile_again.max_retries == 7


# ---------------------------------------------------------------------------
# F. Budget enforcement is provider-agnostic — reuses the orchestrator's
#    own SpendTracker/GroqFactoryLimits with a NON-Groq provider identity
# ---------------------------------------------------------------------------


def _syllabus_registry() -> NeetSyllabusRegistry:
    topic = NeetSyllabusTopic(
        subject="PHYSICS",
        unit_number=1,
        unit_name="Laws of Motion",
        topic_index=1,
        topic="force and acceleration",
        subtopic=None,
        topic_id="PHYSICS:U01:T01",
        source_line=1,
    )
    unit = NeetSyllabusUnit(
        subject="PHYSICS", unit_number=1, unit_name="Laws of Motion", unit_id="PHYSICS:U01", source_line=1, topics=[topic]
    )
    return NeetSyllabusRegistry(
        source_path="fixture",
        source_sha256="0" * 64,
        units=[unit],
        topics_by_id={topic.topic_id: topic},
        units_by_id={unit.unit_id: unit},
    )


def _fact_spec(**overrides) -> FactSpec:
    base = dict(
        fact_id="fact-1",
        subject="PHYSICS",
        unit_number=1,
        chapter="Laws of Motion",
        topic="force and acceleration",
        class_level="11",
        taxonomy=TaxonomyIds(subject_id="s1", chapter_id="c1", topic_id="t1", concept_id=None),
        syllabus_registry=_syllabus_registry(),
    )
    base.update(overrides)
    return FactSpec(**base)


PAGE_TEXT = (
    "Newtons second law of motion states that the force acting on an object "
    "is equal to the mass of that object multiplied by its acceleration. "
    "This fundamental principle of classical mechanics explains how objects "
    "respond to applied forces and is written as force equals mass times "
    "acceleration in standard physics textbooks used for NEET preparation."
)


def _document(tmp_path):
    import fitz

    text = PAGE_TEXT
    pdf_path = tmp_path / "evidence.pdf"
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(36, 36, page.rect.width - 36, page.rect.height - 36)
    page.insert_textbox(rect, text, fontsize=11)
    doc.save(str(pdf_path))
    doc.close()
    return index_pdf(pdf_path)


def _fake_session():
    return SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))


class ScriptedCaller:
    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.call_count = 0

    async def __call__(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> AIResponse:
        self.call_count += 1
        idx = min(self.call_count - 1, len(self._outcomes) - 1)
        outcome = self._outcomes[idx]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


async def _noop_sleep(_seconds: float) -> None:
    return None


_write_calls: list = []


async def _record_writer(record) -> bool:
    _write_calls.append(record)
    return True


@pytest.mark.asyncio
async def test_budget_enforcement_identical_for_a_non_groq_provider_identity(tmp_path):
    """Exact same 'budget exhausted blocks before any dispatch' scenario
    as the existing Groq-specific orchestrator test, but with
    generation_provider_name/model set to a completely fictitious
    non-Groq vendor — proving SpendTracker/estimate_cost enforcement
    never special-cases "groq" anywhere."""
    register_rate("mock_vendor_budget_test", "mock-gen-model", PriceRate(1_000_000.0, 0.0))

    limits = GroqFactoryLimits(
        max_total_spend_usd=1.0,
        max_generation_tokens_per_question=10,
        max_verification_tokens_per_question=10,
        max_retries_per_call=2,
        rate_limit_requests_per_minute=10_000,
        rate_limit_tokens_per_minute=10_000_000,
    )
    checkpoint = GroqFactoryCheckpoint(tmp_path / "checkpoint.json", batch_id="batch-mock")
    gen = ScriptedCaller([AIResponse(text="{}", model="mock-gen-model", prompt_tokens=1, completion_tokens=1)])

    orch = GroqFactoryOrchestrator(
        batch_id="batch-mock",
        limits=limits,
        checkpoint=checkpoint,
        generation_caller=gen,
        generation_provider_name="mock_vendor_budget_test",
        generation_model="mock-gen-model",
        verification_caller=None,
        verification_provider_name="mock_vendor_budget_test",
        verification_model="mock-gen-model",
        taxonomy_resolver=InMemoryTaxonomyResolver(subjects={"s1": None}, chapters={"c1": "s1"}, topics={"t1": "c1"}, concepts={}),
        staging_writer=_record_writer,
        publication_gate_session=_fake_session(),
        sleep_fn=_noop_sleep,
    )

    record = await orch.process_fact(_fact_spec(), _document(tmp_path))

    # worst case = 10 tokens * $1/token = $10 > $1 ceiling -> never dispatched
    assert gen.call_count == 0
    assert record.status == STATUS_REJECTED
    assert "BUDGET_EXHAUSTED" in record.reason


# ---------------------------------------------------------------------------
# G. Provenance defect fix — "source" no longer hard-codes a "groq:" prefix
#    regardless of the actual configured generation provider.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provenance_source_reflects_actual_provider_not_hardcoded_groq(tmp_path, monkeypatch):
    """MCQ-FACTORY-PROVIDER-AGNOSTIC-001 defect fix: orchestrator.py used
    to build provenance_block["source"] as
    f"groq:{self.generation_provider_name}:{self.generation_model}" — a
    hard-coded "groq:" literal regardless of which provider actually ran.
    This proves the fix: with a non-Groq generation_provider_name, the
    captured provenance "source" must equal
    "<provider>:<model>" and must NOT contain a stray "groq:" prefix.
    """
    import app.modules.cms.mcq_factory_groq.orchestrator as orchestrator_module

    captured: dict = {}
    real_evaluate = orchestrator_module.evaluate_publication_readiness

    async def _capturing_evaluate(session, candidate, *, ncert_evidence, provenance, tags=None):
        captured["provenance"] = provenance
        return await real_evaluate(session, candidate, ncert_evidence=ncert_evidence, provenance=provenance, tags=tags)

    monkeypatch.setattr(orchestrator_module, "evaluate_publication_readiness", _capturing_evaluate)

    document = _document(tmp_path)
    candidate_json = {
        "stem": "According to the evidence, what does Newton's second law equate force to?",
        "options": [
            {"label": "A", "text": "Mass times acceleration"},
            {"label": "B", "text": "Mass times velocity"},
            {"label": "C", "text": "Mass divided by acceleration"},
            {"label": "D", "text": "Velocity times time"},
        ],
        "correct_option": "A",
        "explanation": "Newton's second law states that force equals mass multiplied by acceleration.",
        "source_evidence": {
            "doc_id": document.doc_id,
            "page": 1,
            "quoted_snippet": "force acting on an object is equal to the mass of that object multiplied by its acceleration",
        },
        "taxonomy": {"subject_id": "s1", "chapter_id": "c1", "topic_id": "t1", "concept_id": None},
        "difficulty": "medium",
    }
    import json

    gen = ScriptedCaller(
        [AIResponse(text=json.dumps(candidate_json), model="mock-gen-model", prompt_tokens=1, completion_tokens=1)]
    )
    verify = ScriptedCaller(
        [
            AIResponse(
                text=json.dumps({"answer_supported": True, "ambiguous": False, "unsupported_claims": [], "notes": "ok"}),
                model="mock-verify-model",
                prompt_tokens=1,
                completion_tokens=1,
            )
        ]
    )

    limits = GroqFactoryLimits(
        max_total_spend_usd=1000.0,
        max_generation_tokens_per_question=10,
        max_verification_tokens_per_question=10,
        max_retries_per_call=2,
        rate_limit_requests_per_minute=10_000,
        rate_limit_tokens_per_minute=10_000_000,
    )
    register_rate("mock_vendor_prov_test", "mock-gen-model", PriceRate(0.0, 0.0))
    register_rate("mock_vendor_prov_test", "mock-verify-model", PriceRate(0.0, 0.0))
    checkpoint = GroqFactoryCheckpoint(tmp_path / "checkpoint2.json", batch_id="batch-prov")
    orch = GroqFactoryOrchestrator(
        batch_id="batch-prov",
        limits=limits,
        checkpoint=checkpoint,
        generation_caller=gen,
        generation_provider_name="mock_vendor_prov_test",
        generation_model="mock-gen-model",
        verification_caller=verify,
        verification_provider_name="mock_vendor_prov_test",
        verification_model="mock-verify-model",
        taxonomy_resolver=InMemoryTaxonomyResolver(subjects={"s1": None}, chapters={"c1": "s1"}, topics={"t1": "c1"}, concepts={}),
        staging_writer=_record_writer,
        publication_gate_session=_fake_session(),
        sleep_fn=_noop_sleep,
    )

    record = await orch.process_fact(_fact_spec(), document)

    assert "provenance" in captured
    assert captured["provenance"]["source"] == "mock_vendor_prov_test:mock-gen-model"
    assert "groq:" not in captured["provenance"]["source"]
    assert record.status == STATUS_ACCEPTED


# ---------------------------------------------------------------------------
# H. OpenRouter wiring (MCQ-FACTORY-OPENROUTER-001) — ZERO real network
#    calls: all keys/models below are fake, test-only strings, never a
#    real OPENROUTER_API_KEY and never a model id confirmed as real
#    against OpenRouter's live /models listing (that confirmation is
#    explicitly out of scope for this change — see registry.py /
#    mcq_llm_provider.py docstrings). These tests only prove: (1) the
#    selection/registry/provider wiring resolves correctly when enabled +
#    a real-LOOKING key + a real-LOOKING model are all set, and (2) it
#    fails closed (never silently proceeds) when either the key or the
#    model is missing/empty — exactly the same fail-closed discipline
#    every other provider in this registry already has.
# ---------------------------------------------------------------------------


def test_openrouter_resolves_when_enabled_key_and_model_all_set():
    s = _settings(
        mcq_factory_generation_provider="openrouter",
        openrouter_enabled=True,
        openrouter_api_key="fake-test-openrouter-key",
        openrouter_model="fake-org/fake-model:free",
    )
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "openrouter"
    assert sel.model == "fake-org/fake-model:free"
    assert sel.enabled is True
    assert sel.configured is True

    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is not None
    assert provider.name == "openrouter"
    assert isinstance(provider, OpenAIProvider)
    assert selection.configured is True


def test_openrouter_fails_closed_when_model_is_empty_placeholder():
    """An empty/placeholder OPENROUTER_MODEL (the shipped .env.example
    default) must never be silently sent to the API. The selection still
    resolves to 'openrouter' (not an unsupported-provider error — the
    NAME is valid) but reports itself unconfigured, and
    build_mcq_factory_stage_provider refuses to construct a provider —
    same fail-closed shape a missing key already gets."""
    s = _settings(
        mcq_factory_generation_provider="openrouter",
        openrouter_enabled=True,
        openrouter_api_key="fake-test-openrouter-key",
        openrouter_model="",
    )
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "openrouter"
    assert sel.configured is False

    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is None
    assert selection.configured is False

    with pytest.raises(AppError) as exc_info:
        build_mcq_factory_stage_caller(_FakeDbSession(), stage="generation", settings=s)
    assert exc_info.value.code == "MCQ_FACTORY_GENERATION_PROVIDER_UNAVAILABLE"


def test_openrouter_fails_closed_when_key_missing():
    s = _settings(
        mcq_factory_generation_provider="openrouter",
        openrouter_enabled=True,
        openrouter_api_key="",
        openrouter_model="fake-org/fake-model:free",
    )
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "openrouter"
    assert sel.configured is False

    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is None


def test_openrouter_registry_entry_blocked_with_empty_model_even_with_real_looking_key():
    """Same fail-closed check at the registry layer (build_registry_from_settings),
    independent of the mcq_factory stage-selection layer tested above —
    both layers must refuse an empty model, never just one of them."""
    s = _settings(openrouter_enabled=True, openrouter_api_key="fake-test-openrouter-key", openrouter_model="")
    registry = build_registry_from_settings(s)
    entry = registry.get("openrouter")
    assert entry.status != AVAILABLE
    assert entry.instance is None


def test_openrouter_registry_entry_available_with_key_and_model_both_set():
    s = _settings(
        openrouter_enabled=True,
        openrouter_api_key="fake-test-openrouter-key",
        openrouter_model="fake-org/fake-model:free",
    )
    registry = build_registry_from_settings(s)
    entry = registry.get("openrouter")
    assert entry.status == AVAILABLE
    assert entry.instance is not None
    assert entry.instance.name == "openrouter"


def test_openrouter_never_enabled_by_default():
    """The Settings SCHEMA default for openrouter_enabled/openrouter_model
    must be False/"" (never auto-enabled, never a baked-in model
    assumption) — checked against Settings' field defaults directly
    rather than an instantiated Settings()/_settings(), since a real
    local .env on this machine may set OPENROUTER_MODEL/OPENROUTER_API_KEY
    for a future live check (that is expected and fine — it does not
    change the class's own default, and OPENROUTER_ENABLED is still
    absent from that .env so `enabled` stays False either way)."""
    assert Settings.model_fields["openrouter_enabled"].default is False
    assert Settings.model_fields["openrouter_model"].default == ""

    # With an explicit empty override (isolating from any local .env
    # value), the registry entry must be DISABLED, never AVAILABLE.
    s = _settings(openrouter_enabled=False, openrouter_api_key="", openrouter_model="")
    registry = build_registry_from_settings(s)
    entry = registry.get("openrouter")
    assert entry.enabled is False
    assert entry.status == "DISABLED"
    assert entry.instance is None


@pytest.mark.asyncio
async def test_openrouter_generation_caller_routes_to_openrouter_base_url(monkeypatch):
    """Mocked-HTTP proof (same _FakeHttpClient pattern as the Groq/openai
    routing tests above) that a fully-configured OpenRouter selection
    actually dispatches to https://openrouter.ai/api/v1 with the
    configured model — never a live network call."""
    _FakeHttpClient._captured = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeHttpClient)
    s = _settings(
        mcq_factory_generation_provider="openrouter",
        mcq_factory_generation_model="fake-org/fake-model:free",
        openrouter_enabled=True,
        openrouter_api_key="fake-test-openrouter-key",
    )

    caller = build_mcq_factory_generation_caller(_FakeDbSession(), settings=s)
    resp = await caller(system_prompt="sys", user_prompt="user", max_tokens=50)

    assert isinstance(resp, AIResponse)
    call = _FakeHttpClient._captured[-1]
    assert call["url"].startswith("https://openrouter.ai/api/v1")
    assert call["json"]["model"] == "fake-org/fake-model:free"


# ---------------------------------------------------------------------------
# I. Krutrim wiring (MCQ-FACTORY-KRUTRIM-001) — ZERO real network calls:
#    all keys/models below are fake, test-only strings, never a real
#    KRUTRIM_API_KEY. "Krutrim-spectre-v2" is used as the model id in
#    these tests because it is the REAL, confirmed API model id (from the
#    official krutrim-cloud-python client's api.md/completions.py source)
#    — not a guess — but no live call is ever made against it here. Mirrors
#    section H's OpenRouter tests exactly: (1) resolves correctly when
#    enabled + a real-looking key + a real-looking model are all set, and
#    (2) fails closed when either the key or the model is missing/empty —
#    same fail-closed discipline as OpenRouter and every other provider.
# ---------------------------------------------------------------------------

KRUTRIM_MODEL = "Krutrim-spectre-v2"


def test_krutrim_resolves_when_enabled_key_and_model_all_set():
    s = _settings(
        mcq_factory_generation_provider="krutrim",
        krutrim_enabled=True,
        krutrim_api_key="fake-test-krutrim-key",
        krutrim_model=KRUTRIM_MODEL,
    )
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "krutrim"
    assert sel.model == KRUTRIM_MODEL
    assert sel.enabled is True
    assert sel.configured is True

    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is not None
    assert provider.name == "krutrim"
    assert isinstance(provider, OpenAIProvider)
    assert selection.configured is True


def test_krutrim_fails_closed_when_model_is_empty_placeholder():
    """An empty/placeholder KRUTRIM_MODEL (the shipped .env.example
    default) must never be silently sent to the API — same fail-closed
    shape OpenRouter's empty-model test exercises."""
    s = _settings(
        mcq_factory_generation_provider="krutrim",
        krutrim_enabled=True,
        krutrim_api_key="fake-test-krutrim-key",
        krutrim_model="",
    )
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "krutrim"
    assert sel.configured is False

    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is None
    assert selection.configured is False

    with pytest.raises(AppError) as exc_info:
        build_mcq_factory_stage_caller(_FakeDbSession(), stage="generation", settings=s)
    assert exc_info.value.code == "MCQ_FACTORY_GENERATION_PROVIDER_UNAVAILABLE"


def test_krutrim_fails_closed_when_key_missing():
    s = _settings(
        mcq_factory_generation_provider="krutrim",
        krutrim_enabled=True,
        krutrim_api_key="",
        krutrim_model=KRUTRIM_MODEL,
    )
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "krutrim"
    assert sel.configured is False

    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is None


def test_krutrim_registry_entry_blocked_with_empty_model_even_with_real_looking_key():
    """Same fail-closed check at the registry layer (build_registry_from_settings),
    independent of the mcq_factory stage-selection layer tested above —
    both layers must refuse an empty model, never just one of them."""
    s = _settings(krutrim_enabled=True, krutrim_api_key="fake-test-krutrim-key", krutrim_model="")
    registry = build_registry_from_settings(s)
    entry = registry.get("krutrim")
    assert entry.status != AVAILABLE
    assert entry.instance is None


def test_krutrim_registry_entry_available_with_key_and_model_both_set():
    s = _settings(
        krutrim_enabled=True,
        krutrim_api_key="fake-test-krutrim-key",
        krutrim_model=KRUTRIM_MODEL,
    )
    registry = build_registry_from_settings(s)
    entry = registry.get("krutrim")
    assert entry.status == AVAILABLE
    assert entry.instance is not None
    assert entry.instance.name == "krutrim"


def test_krutrim_never_enabled_by_default():
    """The Settings SCHEMA default for krutrim_enabled/krutrim_model must
    be False/"" (never auto-enabled, never a baked-in model assumption) —
    checked against Settings' field defaults directly, same pattern as
    the OpenRouter equivalent test."""
    assert Settings.model_fields["krutrim_enabled"].default is False
    assert Settings.model_fields["krutrim_model"].default == ""

    s = _settings(krutrim_enabled=False, krutrim_api_key="", krutrim_model="")
    registry = build_registry_from_settings(s)
    entry = registry.get("krutrim")
    assert entry.enabled is False
    assert entry.status == "DISABLED"
    assert entry.instance is None


@pytest.mark.asyncio
async def test_krutrim_generation_caller_routes_to_krutrim_base_url_with_bearer_auth(monkeypatch):
    """Mocked-HTTP proof (same _FakeHttpClient pattern as the Groq/openai/
    openrouter routing tests above) that a fully-configured Krutrim
    selection actually dispatches to https://cloud.olakrutrim.com/v1 with
    the configured model AND a correctly-formed 'Authorization: Bearer
    <key>' header — reusing OpenAIProvider's own existing header-
    construction code (KrutrimProvider adds no new logic), never a
    duplicated/bespoke implementation. Never a live network call."""
    _FakeHttpClient._captured = []
    captured_headers: list[dict] = []

    class _HeaderCapturingHttpClient(_FakeHttpClient):
        async def post(self, url, json=None, headers=None):
            captured_headers.append(dict(headers or {}))
            return await super().post(url, json=json, headers=headers)

    monkeypatch.setattr(httpx, "AsyncClient", _HeaderCapturingHttpClient)
    s = _settings(
        mcq_factory_generation_provider="krutrim",
        mcq_factory_generation_model=KRUTRIM_MODEL,
        krutrim_enabled=True,
        krutrim_api_key="fake-test-krutrim-key",
        krutrim_model=KRUTRIM_MODEL,
    )

    caller = build_mcq_factory_generation_caller(_FakeDbSession(), settings=s)
    resp = await caller(system_prompt="sys", user_prompt="user", max_tokens=50)

    assert isinstance(resp, AIResponse)
    call = _FakeHttpClient._captured[-1]
    assert call["url"].startswith("https://cloud.olakrutrim.com/v1")
    # Standard OpenAI chat-completions request shape: model + messages only
    # — no Krutrim-specific fields invented.
    assert call["json"]["model"] == KRUTRIM_MODEL
    assert set(call["json"].keys()) <= {"model", "messages", "max_tokens", "temperature", "response_format"}
    assert "messages" in call["json"]
    assert captured_headers[-1].get("Authorization") == "Bearer fake-test-krutrim-key"


# ---------------------------------------------------------------------------
# J. DeepSeek wiring (MCQ-FACTORY-DEEPSEEK-001) — ZERO real network calls:
#    all keys/models below are fake, test-only strings, never a real
#    DEEPSEEK_API_KEY. "deepseek-flash" is used as the model id in these
#    tests because it is the REAL, current, confirmed API model id (from
#    DeepSeek's official docs at api-docs.deepseek.com) — not a guess —
#    but no live call is ever made against it here. Mirrors section I's
#    Krutrim tests exactly, PLUS one DeepSeek-specific dedicated
#    assertion: the constructed request URL must be exactly
#    "https://api.deepseek.com/chat/completions" (NOT
#    ".../v1/chat/completions") — the one place DeepSeek genuinely
#    differs from Groq/OpenRouter/Krutrim, whose base_urls all end in
#    "/v1".
# ---------------------------------------------------------------------------

DEEPSEEK_MODEL = "deepseek-flash"


def test_deepseek_resolves_when_enabled_key_and_model_all_set():
    s = _settings(
        mcq_factory_generation_provider="deepseek",
        deepseek_enabled=True,
        deepseek_api_key="fake-test-deepseek-key",
        deepseek_model=DEEPSEEK_MODEL,
    )
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "deepseek"
    assert sel.model == DEEPSEEK_MODEL
    assert sel.enabled is True
    assert sel.configured is True

    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is not None
    assert provider.name == "deepseek"
    assert isinstance(provider, OpenAIProvider)
    assert selection.configured is True


def test_deepseek_fails_closed_when_model_is_empty_placeholder():
    """An empty/placeholder DEEPSEEK_MODEL (the shipped .env.example
    default) must never be silently sent to the API — same fail-closed
    shape OpenRouter's/Krutrim's empty-model tests exercise."""
    s = _settings(
        mcq_factory_generation_provider="deepseek",
        deepseek_enabled=True,
        deepseek_api_key="fake-test-deepseek-key",
        deepseek_model="",
    )
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "deepseek"
    assert sel.configured is False

    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is None
    assert selection.configured is False

    with pytest.raises(AppError) as exc_info:
        build_mcq_factory_stage_caller(_FakeDbSession(), stage="generation", settings=s)
    assert exc_info.value.code == "MCQ_FACTORY_GENERATION_PROVIDER_UNAVAILABLE"


def test_deepseek_fails_closed_when_key_missing():
    s = _settings(
        mcq_factory_generation_provider="deepseek",
        deepseek_enabled=True,
        deepseek_api_key="",
        deepseek_model=DEEPSEEK_MODEL,
    )
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "deepseek"
    assert sel.configured is False

    provider, selection = build_mcq_factory_stage_provider("generation", settings=s)
    assert provider is None


def test_deepseek_registry_entry_blocked_with_empty_model_even_with_real_looking_key():
    """Same fail-closed check at the registry layer (build_registry_from_settings),
    independent of the mcq_factory stage-selection layer tested above —
    both layers must refuse an empty model, never just one of them."""
    s = _settings(deepseek_enabled=True, deepseek_api_key="fake-test-deepseek-key", deepseek_model="")
    registry = build_registry_from_settings(s)
    entry = registry.get("deepseek")
    assert entry.status != AVAILABLE
    assert entry.instance is None


def test_deepseek_registry_entry_available_with_key_and_model_both_set():
    s = _settings(
        deepseek_enabled=True,
        deepseek_api_key="fake-test-deepseek-key",
        deepseek_model=DEEPSEEK_MODEL,
    )
    registry = build_registry_from_settings(s)
    entry = registry.get("deepseek")
    assert entry.status == AVAILABLE
    assert entry.instance is not None
    assert entry.instance.name == "deepseek"


def test_deepseek_never_enabled_by_default():
    """The Settings SCHEMA default for deepseek_enabled/deepseek_model must
    be False/"" (never auto-enabled, never a baked-in model assumption) —
    checked against Settings' field defaults directly, same pattern as
    the OpenRouter/Krutrim equivalent tests."""
    assert Settings.model_fields["deepseek_enabled"].default is False
    assert Settings.model_fields["deepseek_model"].default == ""

    s = _settings(deepseek_enabled=False, deepseek_api_key="", deepseek_model="")
    registry = build_registry_from_settings(s)
    entry = registry.get("deepseek")
    assert entry.enabled is False
    assert entry.status == "DISABLED"
    assert entry.instance is None


@pytest.mark.asyncio
async def test_deepseek_generation_caller_routes_to_exact_base_url_no_v1_with_bearer_auth(monkeypatch):
    """Mocked-HTTP proof (same _FakeHttpClient pattern as the Groq/openai/
    openrouter/krutrim routing tests above) that a fully-configured
    DeepSeek selection dispatches to EXACTLY
    'https://api.deepseek.com/chat/completions' — NOT
    '.../v1/chat/completions' — with the configured model AND a
    correctly-formed 'Authorization: Bearer <key>' header. This is the
    one DeepSeek-specific behavior worth a dedicated assertion: every
    other provider in this family (Groq/OpenRouter/Krutrim) has a
    base_url ending in '/v1'; DeepSeek's real, documented endpoint does
    not. Reuses OpenAIProvider's own existing URL-construction and
    header-construction code (DeepSeekProvider adds no new logic), never
    a duplicated/bespoke implementation. Never a live network call."""
    _FakeHttpClient._captured = []
    captured_headers: list[dict] = []

    class _HeaderCapturingHttpClient(_FakeHttpClient):
        async def post(self, url, json=None, headers=None):
            captured_headers.append(dict(headers or {}))
            return await super().post(url, json=json, headers=headers)

    monkeypatch.setattr(httpx, "AsyncClient", _HeaderCapturingHttpClient)
    s = _settings(
        mcq_factory_generation_provider="deepseek",
        mcq_factory_generation_model=DEEPSEEK_MODEL,
        deepseek_enabled=True,
        deepseek_api_key="fake-test-deepseek-key",
        deepseek_model=DEEPSEEK_MODEL,
    )

    caller = build_mcq_factory_generation_caller(_FakeDbSession(), settings=s)
    resp = await caller(system_prompt="sys", user_prompt="user", max_tokens=50)

    assert isinstance(resp, AIResponse)
    call = _FakeHttpClient._captured[-1]
    # The one dedicated DeepSeek-specific assertion: EXACT URL, no "/v1".
    assert call["url"] == "https://api.deepseek.com/chat/completions"
    # Standard OpenAI chat-completions request shape: model + messages only
    # — no DeepSeek-specific fields invented.
    assert call["json"]["model"] == DEEPSEEK_MODEL
    assert set(call["json"].keys()) <= {"model", "messages", "max_tokens", "temperature", "response_format"}
    assert "messages" in call["json"]
    assert captured_headers[-1].get("Authorization") == "Bearer fake-test-deepseek-key"


def test_existing_groq_default_selection_unaffected_by_openrouter_addition():
    """Explicit confirmation (not an assumption) that adding OpenRouter
    left Groq's own default (unset) stage-selection behavior unchanged —
    this is the same assertion test_generation_selection_defaults_to_groq_when_unset
    makes, re-asserted here as the task's required 'existing Groq-path
    tests still pass unmodified' confirmation."""
    s = _settings()
    gen_sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    verify_sel = resolve_mcq_factory_stage_selection("verification", settings=s)
    assert gen_sel.registry_name == "groq"
    assert gen_sel.model == s.groq_generation_model
    assert verify_sel.registry_name == "groq"
    assert verify_sel.model == s.groq_verification_model
