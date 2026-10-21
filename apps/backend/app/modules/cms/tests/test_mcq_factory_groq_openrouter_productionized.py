"""Tests for NEET-MCQ-FACTORY-OPENROUTER-PRODUCTIONIZED-20261013.

Closes the gap the real, $0-cost live OpenRouter test run
(docs/quality/neet_mcq_factory_OPENROUTER_FIXED_MODEL_RESULT_20261013.md)
and its wiring report
(docs/quality/neet_mcq_factory_OPENROUTER_WIRING_20261013.md) left open:
the REAL CLI (``scripts/mcq_factory_groq_bulk_run.py``) was still
Groq-hardcoded, and the 900/700-token generation/verification caps (tuned
for Groq's non-reasoning model) were not genuinely configurable per
provider+model, so OpenRouter's reasoning model (which needs ~4000 tokens
to avoid truncation) could only be exercised via a one-off throwaway
script.

ZERO real network/API calls, ZERO real API keys, ZERO real database writes
anywhere in this file:

- Every ``Settings`` override below uses obviously-fake key/model strings
  (never a real OPENROUTER_API_KEY, never a value read from the real
  ``.env``).
- Generation/verification "providers" exercised through
  ``GroqFactoryOrchestrator`` are plain scripted async callables
  (``ScriptedCaller``), never an ``httpx`` client — same pattern as
  ``test_mcq_factory_groq_orchestrator.py``.
- The CLI section imports ``scripts/mcq_factory_groq_bulk_run.py`` as a
  module (same pattern as ``test_mcq_factory_groq_cli_live_run.py``) and
  only exercises its pure-config helpers (``_check_required_live_config``,
  ``_resolve_limits``) — never ``run_live``/``default_live_dependencies``,
  so no session/HTTP client is ever constructed.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import fitz
import pytest

from app.core.config import Settings
from app.modules.ai.gateway.base import AIResponse
from app.modules.ai.gateway.pricing import PriceRate, register_rate
from app.modules.ai.gateway.provider_capability_profiles import get_capability_profile
from app.modules.cms.mcq_factory_groq.orchestrator import (
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    STATUS_REVIEW_REQUIRED,
    FactSpec,
    GroqFactoryOrchestrator,
)
from app.modules.cms.mcq_factory_groq.pdf_text_index import index_pdf
from app.modules.cms.mcq_factory_groq.schemas import TaxonomyIds
from app.modules.cms.mcq_factory_groq.validators import InMemoryTaxonomyResolver
from app.modules.cms.services.mcq_factory_groq_controls import GroqFactoryCheckpoint, GroqFactoryLimits
from app.modules.cms.services.mcq_llm_provider import resolve_mcq_factory_stage_selection
from app.modules.cms.syllabus.neet_2026_parser import NeetSyllabusRegistry, NeetSyllabusTopic, NeetSyllabusUnit

pytestmark = pytest.mark.asyncio

NEMOTRON_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

# Fake, clearly-non-real (provider, model) pairs for the mechanics tests in
# section E (retries/budget/checkpoint) — these never collide with the real
# NEMOTRON_MODEL registered profile, and registering a rate for them is
# harmless/isolated (register_rate always overwrites its own exact key, so
# re-running this module never leaks a stale rate into another test file).
register_rate("groq", "fake-prod-gen-model", PriceRate(1_000_000.0, 0.0))
register_rate("groq", "fake-prod-verify-model", PriceRate(1_000_000.0, 0.0))
register_rate("openrouter", "fake-prod-openrouter-model", PriceRate(1_000_000.0, 0.0))

SUBJECT_ID = "s1"
CHAPTER_ID = "c1"
TOPIC_ID = "t1"

PAGE_TEXT = (
    "Newtons second law of motion states that the force acting on an object "
    "is equal to the mass of that object multiplied by its acceleration. "
    "This fundamental principle of classical mechanics explains how objects "
    "respond to applied forces and is written as force equals mass times "
    "acceleration in standard physics textbooks used for NEET preparation."
)
QUOTED_SNIPPET = "force acting on an object is equal to the mass of that object multiplied by its acceleration"


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/db",
        "jwt_secret": "x" * 40,
    }
    base.update(overrides)
    return Settings(**base)


def _write_pdf(path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(36, 36, page.rect.width - 36, page.rect.height - 36)
    page.insert_textbox(rect, PAGE_TEXT, fontsize=11)
    doc.save(str(path))
    doc.close()


def _document(tmp_path):
    pdf_path = tmp_path / "evidence.pdf"
    _write_pdf(pdf_path)
    return index_pdf(pdf_path)


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


def _taxonomy_resolver() -> InMemoryTaxonomyResolver:
    return InMemoryTaxonomyResolver(
        subjects={SUBJECT_ID: None}, chapters={CHAPTER_ID: SUBJECT_ID}, topics={TOPIC_ID: CHAPTER_ID}, concepts={}
    )


def _fact_spec(**overrides) -> FactSpec:
    base = dict(
        fact_id="fact-1",
        subject="PHYSICS",
        unit_number=1,
        chapter="Laws of Motion",
        topic="force and acceleration",
        class_level="11",
        taxonomy=TaxonomyIds(subject_id=SUBJECT_ID, chapter_id=CHAPTER_ID, topic_id=TOPIC_ID, concept_id=None),
        syllabus_registry=_syllabus_registry(),
    )
    base.update(overrides)
    return FactSpec(**base)


def _generated_candidate_json(*, doc_id: str, correct_option: str = "A") -> dict:
    return {
        "stem": "According to the evidence, what does Newton's second law equate force to?",
        "options": [
            {"label": "A", "text": "Mass times acceleration"},
            {"label": "B", "text": "Mass times velocity"},
            {"label": "C", "text": "Mass divided by acceleration"},
            {"label": "D", "text": "Velocity times time"},
        ],
        "correct_option": correct_option,
        "explanation": "Newton's second law states that force equals mass multiplied by acceleration, as given directly in the evidence chunk.",
        "source_evidence": {"doc_id": doc_id, "page": 1, "quoted_snippet": QUOTED_SNIPPET},
        "taxonomy": {"subject_id": SUBJECT_ID, "chapter_id": CHAPTER_ID, "topic_id": TOPIC_ID, "concept_id": None},
        "difficulty": "medium",
    }


def _ai_response(text: str, *, model: str, provider: str, prompt_tokens: int = 1, completion_tokens: int = 1) -> AIResponse:
    return AIResponse(
        text=text,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider=provider,
        provider_request_id="req-1",
        finish_reason="stop",
        is_fallback=False,
    )


def _verification_response(*, provider: str, model: str, answer_supported: bool = True, ambiguous: bool = False) -> AIResponse:
    payload = {"answer_supported": answer_supported, "ambiguous": ambiguous, "unsupported_claims": [], "notes": "ok"}
    return _ai_response(json.dumps(payload), model=model, provider=provider)


class ScriptedCaller:
    """Plain async callable standing in for a provider call site — never an
    httpx client, never a real OpenAIProvider. Same pattern already used by
    test_mcq_factory_groq_orchestrator.py."""

    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.call_count = 0

    async def __call__(self, *, system_prompt: str, user_prompt: str, max_tokens: int):
        self.call_count += 1
        idx = min(self.call_count - 1, len(self._outcomes) - 1)
        outcome = self._outcomes[idx]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


async def _noop_sleep(_seconds: float) -> None:
    return None


def _fake_pub_gate_session():
    return SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))


def _build_orchestrator(
    tmp_path,
    *,
    gen_caller,
    verify_caller=None,
    generation_provider_name: str = "groq",
    generation_model: str = "fake-prod-gen-model",
    verification_provider_name: str = "groq",
    verification_model: str = "fake-prod-verify-model",
    max_spend: float = 1000.0,
    max_retries: int = 2,
    gen_tokens_cap: int = 50,
    verify_tokens_cap: int = 50,
    checkpoint: GroqFactoryCheckpoint | None = None,
    writer_calls: list | None = None,
):
    limits = GroqFactoryLimits(
        max_total_spend_usd=max_spend,
        max_generation_tokens_per_question=gen_tokens_cap,
        max_verification_tokens_per_question=verify_tokens_cap,
        max_retries_per_call=max_retries,
        rate_limit_requests_per_minute=10_000,
        rate_limit_tokens_per_minute=10_000_000,
    )
    cp = checkpoint or GroqFactoryCheckpoint(tmp_path / "checkpoint.json", batch_id="batch-1")
    calls = writer_calls if writer_calls is not None else []

    async def writer(record) -> bool:
        calls.append(record)
        return True

    orch = GroqFactoryOrchestrator(
        batch_id="batch-1",
        limits=limits,
        checkpoint=cp,
        generation_caller=gen_caller,
        generation_provider_name=generation_provider_name,
        generation_model=generation_model,
        verification_caller=verify_caller,
        verification_provider_name=verification_provider_name,
        verification_model=verification_model,
        taxonomy_resolver=_taxonomy_resolver(),
        staging_writer=writer,
        publication_gate_session=_fake_pub_gate_session(),
        sleep_fn=_noop_sleep,
    )
    return orch, cp, calls


# ---------------------------------------------------------------------------
# A. Provider selection resolves to OpenRouter + nemotron when configured
# ---------------------------------------------------------------------------


def test_generation_selection_resolves_to_openrouter_nemotron_when_configured():
    s = _settings(
        mcq_factory_generation_provider="openrouter",
        openrouter_enabled=True,
        openrouter_api_key="fake-test-openrouter-key",
        openrouter_model=NEMOTRON_MODEL,
    )
    sel = resolve_mcq_factory_stage_selection("generation", settings=s)
    assert sel.registry_name == "openrouter"
    assert sel.model == NEMOTRON_MODEL
    assert sel.enabled is True
    assert sel.configured is True


def test_verification_selection_also_resolves_to_openrouter_nemotron_when_configured():
    """The real live test used the SAME nemotron model for both the
    generation and verification call sites — confirm the verification
    stage resolves identically when configured the same way."""
    s = _settings(
        mcq_factory_verification_provider="openrouter",
        openrouter_enabled=True,
        openrouter_api_key="fake-test-openrouter-key",
        openrouter_model=NEMOTRON_MODEL,
    )
    sel = resolve_mcq_factory_stage_selection("verification", settings=s)
    assert sel.registry_name == "openrouter"
    assert sel.model == NEMOTRON_MODEL
    assert sel.configured is True


# ---------------------------------------------------------------------------
# B. GroqFactoryLimits.from_stage_selections — per-(provider, model) token
#    caps: 4000 for the registered nemotron entry, unchanged 900/700
#    Groq-tuned defaults when no specific profile is registered.
# ---------------------------------------------------------------------------


def test_nemotron_profile_is_registered_at_exactly_4000_4000():
    """Confirms the fixed profile entry itself — matching the exact value
    the real, confirmed-working live test used (never a different/invented
    number)."""
    profile = get_capability_profile("openrouter", NEMOTRON_MODEL)
    assert profile is not None
    assert profile.max_tokens_per_call == 4000


def test_from_stage_selections_resolves_4000_for_openrouter_nemotron_both_stages():
    s = _settings()  # Groq-tuned defaults: 900/700 — must NOT leak in here
    limits = GroqFactoryLimits.from_stage_selections(
        generation_provider="openrouter",
        generation_model=NEMOTRON_MODEL,
        verification_provider="openrouter",
        verification_model=NEMOTRON_MODEL,
        settings=s,
    )
    assert limits.max_generation_tokens_per_question == 4000
    assert limits.max_verification_tokens_per_question == 4000
    # Spend ceiling / retries / rate limits are untouched by this method —
    # still exactly from_settings()'s values.
    assert limits.max_total_spend_usd == s.mcq_factory_groq_max_spend_usd
    assert limits.max_retries_per_call == s.mcq_factory_groq_max_retries


def test_from_stage_selections_falls_back_to_groq_defaults_900_700():
    """Regression check: Groq's own (provider, model) pair has no
    registered capability profile from this code path (seed_default_groq_profiles
    is deliberately never called by from_stage_selections — see its
    docstring), so Groq's real behavior is completely unchanged: the
    settings-driven 900/700 defaults win exactly as before this task."""
    s = _settings()
    assert s.mcq_factory_groq_max_generation_tokens == 900
    assert s.mcq_factory_groq_max_verification_tokens == 700

    limits = GroqFactoryLimits.from_stage_selections(
        generation_provider="groq",
        generation_model=s.groq_generation_model,
        verification_provider="groq",
        verification_model=s.groq_verification_model,
        settings=s,
    )
    assert limits.max_generation_tokens_per_question == 900
    assert limits.max_verification_tokens_per_question == 700


def test_from_stage_selections_respects_a_custom_groq_override_too():
    """A non-default settings override for Groq's own token caps must
    still win (no hardcoded profile silently shadows it) — proves the
    fallback genuinely reads live settings, not a frozen constant."""
    s = _settings(mcq_factory_groq_max_generation_tokens=123, mcq_factory_groq_max_verification_tokens=77)
    limits = GroqFactoryLimits.from_stage_selections(
        generation_provider="groq",
        generation_model=s.groq_generation_model,
        verification_provider="groq",
        verification_model=s.groq_verification_model,
        settings=s,
    )
    assert limits.max_generation_tokens_per_question == 123
    assert limits.max_verification_tokens_per_question == 77


def test_pilot_profile_for_stage_selections_uses_pilot_ceiling_with_nemotron_caps():
    s = _settings(mcq_factory_groq_pilot_max_spend_usd=3.5)
    limits = GroqFactoryLimits.pilot_profile_for_stage_selections(
        generation_provider="openrouter",
        generation_model=NEMOTRON_MODEL,
        verification_provider="openrouter",
        verification_model=NEMOTRON_MODEL,
        settings=s,
    )
    assert limits.max_total_spend_usd == 3.5  # pilot ceiling, not the general one
    assert limits.max_generation_tokens_per_question == 4000
    assert limits.max_verification_tokens_per_question == 4000


# ---------------------------------------------------------------------------
# C. Explicit truncation detection — distinguishable signal, never changes
#    the REJECTED/REVIEW_REQUIRED outcome.
# ---------------------------------------------------------------------------


async def test_generation_truncated_response_flagged_and_rejected_never_accepted(tmp_path):
    """completion_tokens == max_tokens (the cap actually requested) is a
    strong truncation signal — must be surfaced in the rejection reason
    AND must still never be accepted."""
    truncated = _ai_response("", model="fake-prod-gen-model", provider="groq", prompt_tokens=10, completion_tokens=50)
    gen = ScriptedCaller([truncated])
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, gen_tokens_cap=50)

    record = await orch.process_fact(_fact_spec(), _document(tmp_path))

    assert record.status == STATUS_REJECTED
    assert "GENERATION_MALFORMED_JSON" in record.reason
    assert "LIKELY_TRUNCATED" in record.reason
    assert "completion_tokens=50" in record.reason
    assert "max_tokens=50" in record.reason
    assert writer_calls[0].outcome == STATUS_REJECTED


async def test_generation_malformed_well_under_cap_is_not_flagged_as_truncated(tmp_path):
    """Regression guard: a genuinely malformed response produced well
    UNDER the token cap must NOT be mislabeled as truncated — the two
    causes stay distinguishable."""
    bad_but_not_truncated = _ai_response(
        "this is not json at all", model="fake-prod-gen-model", provider="groq", prompt_tokens=10, completion_tokens=5
    )
    gen = ScriptedCaller([bad_but_not_truncated])
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, gen_tokens_cap=50)

    record = await orch.process_fact(_fact_spec(), _document(tmp_path))

    assert record.status == STATUS_REJECTED
    assert "GENERATION_MALFORMED_JSON" in record.reason
    assert "LIKELY_TRUNCATED" not in record.reason
    assert writer_calls[0].outcome == STATUS_REJECTED


async def test_verification_truncated_response_flagged_and_review_required_never_accepted(tmp_path):
    """Same truncation-vs-malformed distinction on the VERIFICATION call
    site: a verification response that hit its own token cap must be
    flagged, must leave verification=None (never implicit agreement), and
    must still route to REVIEW_REQUIRED — never ACCEPTED."""
    document = _document(tmp_path)
    gen = ScriptedCaller([_ai_response(json.dumps(_generated_candidate_json(doc_id=document.doc_id)), model="fake-prod-gen-model", provider="groq")])
    truncated_verify = _ai_response(
        "", model="fake-prod-verify-model", provider="groq", prompt_tokens=10, completion_tokens=50
    )
    verify = ScriptedCaller([truncated_verify])
    orch, _cp, writer_calls = _build_orchestrator(
        tmp_path, gen_caller=gen, verify_caller=verify, gen_tokens_cap=50, verify_tokens_cap=50
    )

    record = await orch.process_fact(_fact_spec(), document)

    assert record.status == STATUS_REVIEW_REQUIRED
    assert record.verification is None
    assert "verification_parse_issue" in record.reason
    assert "LIKELY_TRUNCATED" in record.reason
    assert "completion_tokens=50" in record.reason
    assert writer_calls[0].outcome == STATUS_REVIEW_REQUIRED


# ---------------------------------------------------------------------------
# D. A valid, complete response well under a high (nemotron-sized) cap is
#    correctly accepted — mirrors the real live test's own observed
#    token usage (1015-2350 generation, 148-1093 verification, cap=4000).
# ---------------------------------------------------------------------------


async def test_high_cap_valid_complete_response_well_under_cap_is_accepted(tmp_path):
    document = _document(tmp_path)
    gen = ScriptedCaller(
        [
            _ai_response(
                json.dumps(_generated_candidate_json(doc_id=document.doc_id)),
                model=NEMOTRON_MODEL,
                provider="openrouter",
                prompt_tokens=400,
                completion_tokens=1800,  # well under the 4000 cap, like the real run
            )
        ]
    )
    verify = ScriptedCaller(
        [
            _ai_response(
                json.dumps({"answer_supported": True, "ambiguous": False, "unsupported_claims": [], "notes": "ok"}),
                model=NEMOTRON_MODEL,
                provider="openrouter",
                prompt_tokens=300,
                completion_tokens=500,  # well under the 4000 cap
            )
        ]
    )
    orch, _cp, writer_calls = _build_orchestrator(
        tmp_path,
        gen_caller=gen,
        verify_caller=verify,
        generation_provider_name="openrouter",
        generation_model=NEMOTRON_MODEL,
        verification_provider_name="openrouter",
        verification_model=NEMOTRON_MODEL,
        gen_tokens_cap=4000,
        verify_tokens_cap=4000,
    )

    record = await orch.process_fact(_fact_spec(), document)

    assert record.status == STATUS_ACCEPTED
    assert "LIKELY_TRUNCATED" not in record.reason
    assert writer_calls[0].outcome == STATUS_ACCEPTED


# ---------------------------------------------------------------------------
# E. Retries / budget-guard / checkpoint-resume parity for BOTH the Groq
#    path and the new OpenRouter path — the orchestrator's safety rails
#    must not silently depend on the provider identity being "groq".
# ---------------------------------------------------------------------------

_PROVIDER_IDENTITIES = [
    pytest.param(("groq", "fake-prod-gen-model", "groq", "fake-prod-verify-model"), id="groq"),
    pytest.param(
        ("openrouter", "fake-prod-openrouter-model", "openrouter", "fake-prod-openrouter-model"), id="openrouter"
    ),
]


@pytest.mark.parametrize("identity", _PROVIDER_IDENTITIES)
async def test_bounded_retries_are_actually_bounded_for_both_providers(tmp_path, identity):
    from app.modules.ai.gateway.base import PROVIDER_TIMEOUT, ProviderError

    gen_provider, gen_model, verify_provider, verify_model = identity
    err = ProviderError(PROVIDER_TIMEOUT, "timeout", provider=gen_provider, retryable=True)
    gen = ScriptedCaller([err, err, err])
    orch, _cp, writer_calls = _build_orchestrator(
        tmp_path,
        gen_caller=gen,
        generation_provider_name=gen_provider,
        generation_model=gen_model,
        verification_provider_name=verify_provider,
        verification_model=verify_model,
        max_retries=2,
    )

    record = await orch.process_fact(_fact_spec(), _document(tmp_path))

    assert record.status == STATUS_REJECTED
    assert gen.call_count == 3  # 1 initial + 2 retries, never a 3rd retry
    assert writer_calls[0].outcome == STATUS_REJECTED


@pytest.mark.parametrize("identity", _PROVIDER_IDENTITIES)
async def test_budget_ceiling_enforced_before_dispatch_for_both_providers(tmp_path, identity):
    from app.modules.cms.services.mcq_factory_groq_controls import SpendCeilingExceeded  # noqa: F401 (documents intent)

    gen_provider, gen_model, verify_provider, verify_model = identity
    document = _document(tmp_path)
    # $1/token (registered rate), gen+verify token cap = 1 each => $1 each.
    # Ceiling of $0.50 refuses BEFORE any dispatch (worst-case pre-check).
    gen = ScriptedCaller([_ai_response(json.dumps(_generated_candidate_json(doc_id=document.doc_id)), model=gen_model, provider=gen_provider)])
    orch, _cp, writer_calls = _build_orchestrator(
        tmp_path,
        gen_caller=gen,
        generation_provider_name=gen_provider,
        generation_model=gen_model,
        verification_provider_name=verify_provider,
        verification_model=verify_model,
        max_spend=0.5,
        gen_tokens_cap=1,
        verify_tokens_cap=1,
    )

    record = await orch.process_fact(_fact_spec(), document)

    assert record.status == STATUS_REJECTED
    assert "BUDGET_EXHAUSTED" in record.reason
    assert gen.call_count == 0  # refused before ANY dispatch
    assert writer_calls[0].outcome == STATUS_REJECTED


@pytest.mark.parametrize("identity", _PROVIDER_IDENTITIES)
async def test_checkpoint_resume_skips_without_double_spend_for_both_providers(tmp_path, identity):
    gen_provider, gen_model, verify_provider, verify_model = identity
    document = _document(tmp_path)
    checkpoint_path = tmp_path / "checkpoint.json"

    gen1 = ScriptedCaller([_ai_response(json.dumps(_generated_candidate_json(doc_id=document.doc_id)), model=gen_model, provider=gen_provider)])
    cp1 = GroqFactoryCheckpoint(checkpoint_path, batch_id="batch-resume")
    orch1, cp1, writer_calls_1 = _build_orchestrator(
        tmp_path,
        gen_caller=gen1,
        generation_provider_name=gen_provider,
        generation_model=gen_model,
        verification_provider_name=verify_provider,
        verification_model=verify_model,
        checkpoint=cp1,
    )
    record1 = await orch1.process_fact(_fact_spec(), document)
    assert record1.status in (STATUS_ACCEPTED, STATUS_REVIEW_REQUIRED)
    assert gen1.call_count == 1

    # A brand-new orchestrator/checkpoint instance reading the SAME file —
    # simulating a restarted process — must skip the already-done fact and
    # never dispatch a new call, for either provider identity.
    gen2 = ScriptedCaller([])
    cp2 = GroqFactoryCheckpoint(checkpoint_path, batch_id="batch-resume")
    orch2, _cp2, writer_calls_2 = _build_orchestrator(
        tmp_path,
        gen_caller=gen2,
        generation_provider_name=gen_provider,
        generation_model=gen_model,
        verification_provider_name=verify_provider,
        verification_model=verify_model,
        checkpoint=cp2,
    )
    record2 = await orch2.process_fact(_fact_spec(), document)

    assert record2.resumed_skip is True
    assert gen2.call_count == 0
    assert writer_calls_2 == []  # never re-persisted either


# ---------------------------------------------------------------------------
# F. CLI (scripts/mcq_factory_groq_bulk_run.py) — provider-agnostic
#    default_live_dependencies() / _check_required_live_config() /
#    _resolve_limits() genuinely support OpenRouter, not just Groq.
# ---------------------------------------------------------------------------


def test_cli_required_live_config_accepts_fully_configured_openrouter():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(
        mcq_factory_generation_provider="openrouter",
        openrouter_enabled=True,
        openrouter_api_key="fake-test-openrouter-key",
        openrouter_model=NEMOTRON_MODEL,
    )
    # Must NOT raise.
    cli._check_required_live_config(s)


def test_cli_required_live_config_still_refuses_unsupported_provider():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(mcq_factory_generation_provider="anthropic")
    with pytest.raises(cli.CliConfigError):
        cli._check_required_live_config(s)


def test_cli_required_live_config_refuses_openrouter_disabled():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(
        mcq_factory_generation_provider="openrouter",
        openrouter_enabled=False,
        openrouter_api_key="fake-test-openrouter-key",
        openrouter_model=NEMOTRON_MODEL,
    )
    with pytest.raises(cli.CliConfigError, match="OPENROUTER_ENABLED"):
        cli._check_required_live_config(s)


def test_cli_required_live_config_groq_default_still_works_unchanged():
    """Explicit confirmation that switching the CLI's config check to the
    provider-agnostic resolution did not change Groq's own default
    (mcq_factory_generation_provider unset) behavior."""
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(groq_enabled=True, groq_api_key="dummy-test-key-not-real")
    cli._check_required_live_config(s)  # must not raise


def test_cli_resolve_limits_uses_4000_cap_for_openrouter_nemotron():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(
        mcq_factory_generation_provider="openrouter",
        mcq_factory_verification_provider="openrouter",
        openrouter_enabled=True,
        openrouter_api_key="fake-test-openrouter-key",
        openrouter_model=NEMOTRON_MODEL,
    )
    args = cli.build_arg_parser().parse_args(["--batch-id", "t1", "--budget-profile", "general"])
    limits, gen_sel, verify_sel = cli._resolve_limits(args, s)

    assert gen_sel.registry_name == "openrouter"
    assert gen_sel.model == NEMOTRON_MODEL
    assert limits.max_generation_tokens_per_question == 4000
    assert limits.max_verification_tokens_per_question == 4000


def test_cli_resolve_limits_groq_default_is_900_700_unchanged():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings()
    args = cli.build_arg_parser().parse_args(["--batch-id", "t1", "--budget-profile", "general"])
    limits, gen_sel, verify_sel = cli._resolve_limits(args, s)

    assert gen_sel.registry_name == "groq"
    assert limits.max_generation_tokens_per_question == 900
    assert limits.max_verification_tokens_per_question == 700


# ---------------------------------------------------------------------------
# G. MCQ-FACTORY-KRUTRIM-001 — parallel extension of this file's existing
#    OpenRouter coverage. ZERO real network/API calls, ZERO real API keys.
#    KRUTRIM_MODEL below ("Krutrim-spectre-v2") is the REAL, confirmed API
#    model id (not a guess) — but every key/settings value here is a fake
#    test-only string and no live HTTP call is ever made.
# ---------------------------------------------------------------------------

KRUTRIM_MODEL = "Krutrim-spectre-v2"


def test_generation_selection_resolves_to_krutrim_when_configured():
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


def test_krutrim_profile_is_registered_at_precautionary_4000_4000():
    """Confirms the fixed profile entry for Krutrim-spectre-v2 — a
    PRECAUTIONARY default (no real observed Krutrim usage exists yet),
    deliberately matching the nemotron entry's safer/larger 4000 value
    rather than Groq's non-reasoning-tuned 900/700 default."""
    profile = get_capability_profile("krutrim", KRUTRIM_MODEL)
    assert profile is not None
    assert profile.max_tokens_per_call == 4000


def test_from_stage_selections_resolves_4000_for_krutrim_both_stages():
    s = _settings()  # Groq-tuned defaults: 900/700 — must NOT leak in here
    limits = GroqFactoryLimits.from_stage_selections(
        generation_provider="krutrim",
        generation_model=KRUTRIM_MODEL,
        verification_provider="krutrim",
        verification_model=KRUTRIM_MODEL,
        settings=s,
    )
    assert limits.max_generation_tokens_per_question == 4000
    assert limits.max_verification_tokens_per_question == 4000


def test_cli_required_live_config_accepts_fully_configured_krutrim():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(
        mcq_factory_generation_provider="krutrim",
        krutrim_enabled=True,
        krutrim_api_key="fake-test-krutrim-key",
        krutrim_model=KRUTRIM_MODEL,
    )
    # Must NOT raise.
    cli._check_required_live_config(s)


def test_cli_required_live_config_refuses_krutrim_disabled():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(
        mcq_factory_generation_provider="krutrim",
        krutrim_enabled=False,
        krutrim_api_key="fake-test-krutrim-key",
        krutrim_model=KRUTRIM_MODEL,
    )
    with pytest.raises(cli.CliConfigError, match="KRUTRIM_ENABLED"):
        cli._check_required_live_config(s)


def test_cli_resolve_limits_uses_4000_cap_for_krutrim():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(
        mcq_factory_generation_provider="krutrim",
        mcq_factory_verification_provider="krutrim",
        krutrim_enabled=True,
        krutrim_api_key="fake-test-krutrim-key",
        krutrim_model=KRUTRIM_MODEL,
    )
    args = cli.build_arg_parser().parse_args(["--batch-id", "t1", "--budget-profile", "general"])
    limits, gen_sel, verify_sel = cli._resolve_limits(args, s)

    assert gen_sel.registry_name == "krutrim"
    assert gen_sel.model == KRUTRIM_MODEL
    assert limits.max_generation_tokens_per_question == 4000
    assert limits.max_verification_tokens_per_question == 4000


def test_existing_openrouter_and_groq_cli_behavior_unaffected_by_krutrim_addition():
    """Explicit confirmation (not an assumption) that adding Krutrim left
    the existing Groq-default and OpenRouter CLI config checks unchanged."""
    import scripts.mcq_factory_groq_bulk_run as cli

    s_groq = _settings(groq_enabled=True, groq_api_key="dummy-test-key-not-real")
    cli._check_required_live_config(s_groq)  # must not raise

    s_or = _settings(
        mcq_factory_generation_provider="openrouter",
        openrouter_enabled=True,
        openrouter_api_key="fake-test-openrouter-key",
        openrouter_model=NEMOTRON_MODEL,
    )
    cli._check_required_live_config(s_or)  # must not raise


# ---------------------------------------------------------------------------
# H. MCQ-FACTORY-DEEPSEEK-001 — parallel extension of this file's existing
#    Krutrim/OpenRouter coverage. ZERO real network/API calls, ZERO real
#    API keys. DEEPSEEK_MODEL below ("deepseek-flash") is the REAL,
#    current, confirmed API model id (not a guess — from DeepSeek's
#    official docs at api-docs.deepseek.com) — but every key/settings
#    value here is a fake test-only string and no live HTTP call is ever
#    made.
# ---------------------------------------------------------------------------

DEEPSEEK_MODEL = "deepseek-flash"


def test_generation_selection_resolves_to_deepseek_when_configured():
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


def test_deepseek_profile_is_registered_at_precautionary_4000_4000():
    """Confirms the fixed profile entry for deepseek-flash — a
    PRECAUTIONARY default (no real observed DeepSeek usage exists yet),
    deliberately matching the nemotron/Krutrim entries' safer/larger 4000
    value rather than Groq's non-reasoning-tuned 900/700 default."""
    profile = get_capability_profile("deepseek", DEEPSEEK_MODEL)
    assert profile is not None
    assert profile.max_tokens_per_call == 4000


def test_from_stage_selections_resolves_4000_for_deepseek_both_stages():
    s = _settings()  # Groq-tuned defaults: 900/700 — must NOT leak in here
    limits = GroqFactoryLimits.from_stage_selections(
        generation_provider="deepseek",
        generation_model=DEEPSEEK_MODEL,
        verification_provider="deepseek",
        verification_model=DEEPSEEK_MODEL,
        settings=s,
    )
    assert limits.max_generation_tokens_per_question == 4000
    assert limits.max_verification_tokens_per_question == 4000


def test_cli_required_live_config_accepts_fully_configured_deepseek():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(
        mcq_factory_generation_provider="deepseek",
        deepseek_enabled=True,
        deepseek_api_key="fake-test-deepseek-key",
        deepseek_model=DEEPSEEK_MODEL,
    )
    # Must NOT raise.
    cli._check_required_live_config(s)


def test_cli_required_live_config_refuses_deepseek_disabled():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(
        mcq_factory_generation_provider="deepseek",
        deepseek_enabled=False,
        deepseek_api_key="fake-test-deepseek-key",
        deepseek_model=DEEPSEEK_MODEL,
    )
    with pytest.raises(cli.CliConfigError, match="DEEPSEEK_ENABLED"):
        cli._check_required_live_config(s)


def test_cli_resolve_limits_uses_4000_cap_for_deepseek():
    import scripts.mcq_factory_groq_bulk_run as cli

    s = _settings(
        mcq_factory_generation_provider="deepseek",
        mcq_factory_verification_provider="deepseek",
        deepseek_enabled=True,
        deepseek_api_key="fake-test-deepseek-key",
        deepseek_model=DEEPSEEK_MODEL,
    )
    args = cli.build_arg_parser().parse_args(["--batch-id", "t1", "--budget-profile", "general"])
    limits, gen_sel, verify_sel = cli._resolve_limits(args, s)

    assert gen_sel.registry_name == "deepseek"
    assert gen_sel.model == DEEPSEEK_MODEL
    assert limits.max_generation_tokens_per_question == 4000
    assert limits.max_verification_tokens_per_question == 4000


def test_existing_openrouter_krutrim_and_groq_cli_behavior_unaffected_by_deepseek_addition():
    """Explicit confirmation (not an assumption) that adding DeepSeek left
    the existing Groq-default, OpenRouter, and Krutrim CLI config checks
    unchanged."""
    import scripts.mcq_factory_groq_bulk_run as cli

    s_groq = _settings(groq_enabled=True, groq_api_key="dummy-test-key-not-real")
    cli._check_required_live_config(s_groq)  # must not raise

    s_or = _settings(
        mcq_factory_generation_provider="openrouter",
        openrouter_enabled=True,
        openrouter_api_key="fake-test-openrouter-key",
        openrouter_model=NEMOTRON_MODEL,
    )
    cli._check_required_live_config(s_or)  # must not raise

    s_kr = _settings(
        mcq_factory_generation_provider="krutrim",
        krutrim_enabled=True,
        krutrim_api_key="fake-test-krutrim-key",
        krutrim_model="Krutrim-spectre-v2",
    )
    cli._check_required_live_config(s_kr)  # must not raise
