"""Tests for MCQ-FACTORY-GROQ-ORCHESTRATOR-001
(app/modules/cms/mcq_factory_groq/orchestrator.py).

ZERO real network calls, ZERO real database writes, ZERO real GROQ_API_KEY
anywhere in this file:

- Generation/verification "providers" are plain scripted async callables
  (``ScriptedCaller`` below) — never an ``httpx`` client, never a real
  ``OpenAIProvider``.
- The publication-gates session is a ``SimpleNamespace`` with an
  ``AsyncMock`` ``.execute`` (the exact pattern already used by
  ``test_mcq_factory_groq_validators.py::test_evaluate_publication_readiness_calls_real_publication_gates``)
  — never a live Postgres connection.
- The staging store is a plain in-memory list appended to by a fake async
  writer — never ``generation_staging_store.insert_staging_candidate``.
- The syllabus gate is checked against a tiny fixture ``NeetSyllabusRegistry``
  — never the real on-disk ``NEETSyllabus.txt``.
- A real local PDF IS written (via ``fitz``, to ``tmp_path``) and read back
  with the real ``pdf_text_index.index_pdf`` — this is local filesystem
  I/O only, the same pattern ``test_mcq_factory_groq_validators.py`` and
  ``test_mcq_factory_groq_pdf_and_evidence.py`` already use; it is not a
  network or database call.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import fitz
import pytest

from app.modules.ai.gateway.base import (
    PROVIDER_AUTH_FAILED,
    PROVIDER_RATE_LIMITED,
    PROVIDER_TIMEOUT,
    AIResponse,
    ProviderError,
)
from app.modules.ai.gateway.pricing import PriceRate, register_rate
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
from app.modules.cms.services.mcq_factory_groq_controls import (
    GroqFactoryCheckpoint,
    GroqFactoryLimits,
    RetryBudgetExceeded,
    SpendCeilingExceeded,
)
from app.modules.cms.syllabus.neet_2026_parser import NeetSyllabusRegistry, NeetSyllabusTopic, NeetSyllabusUnit

pytestmark = pytest.mark.asyncio

# Deterministic, made-up pricing so cost math in tests is exact and
# readable: with output_per_million=0, cost == prompt_tokens dollars
# exactly (never a real Groq/OpenAI rate — these provider/model strings
# ("fake-groq"/"fake-gen-model") never appear in the real registry).
register_rate("fake-groq", "fake-gen-model", PriceRate(1_000_000.0, 0.0))
register_rate("fake-groq", "fake-verify-model", PriceRate(1_000_000.0, 0.0))

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


def _write_pdf(path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    # insert_textbox (not insert_text) so a multi-sentence paragraph wraps
    # across lines and is fully captured by extraction instead of being
    # clipped at the page edge on one unwrapped line.
    rect = fitz.Rect(36, 36, page.rect.width - 36, page.rect.height - 36)
    page.insert_textbox(rect, text, fontsize=11)
    doc.save(str(path))
    doc.close()


def _document(tmp_path):
    pdf_path = tmp_path / "evidence.pdf"
    _write_pdf(pdf_path, PAGE_TEXT)
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


def _generated_candidate_json(*, doc_id: str, page: int = 1, correct_option: str = "A", quoted_snippet: str = QUOTED_SNIPPET) -> dict:
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
        "source_evidence": {"doc_id": doc_id, "page": page, "quoted_snippet": quoted_snippet},
        "taxonomy": {"subject_id": SUBJECT_ID, "chapter_id": CHAPTER_ID, "topic_id": TOPIC_ID, "concept_id": None},
        "difficulty": "medium",
    }


def _ai_response(payload, *, model: str = "fake-gen-model", prompt_tokens: int = 1, completion_tokens: int = 1) -> AIResponse:
    import json

    return AIResponse(
        text=json.dumps(payload),
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider="fake-groq",
        provider_request_id="req-1",
        finish_reason="stop",
        is_fallback=False,
    )


def _verification_response(*, answer_supported: bool = True, ambiguous: bool = False, prompt_tokens: int = 1) -> AIResponse:
    return _ai_response(
        {"answer_supported": answer_supported, "ambiguous": ambiguous, "unsupported_claims": [], "notes": "ok"},
        model="fake-verify-model",
        prompt_tokens=prompt_tokens,
    )


class ScriptedCaller:
    """A plain async callable standing in for a provider call site.
    ``outcomes`` is a list of AIResponse objects and/or Exception
    instances, consumed one per invocation; the last entry repeats once
    the list is exhausted. No network, no SDK — just a Python list."""

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


def _fake_session():
    return SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))


def _build_orchestrator(
    tmp_path,
    *,
    gen_caller,
    verify_caller=None,
    max_spend: float = 1000.0,
    max_retries: int = 2,
    gen_tokens_cap: int = 10,
    verify_tokens_cap: int = 10,
    checkpoint: GroqFactoryCheckpoint | None = None,
    staging_writer=None,
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

    async def default_writer(record) -> bool:
        calls.append(record)
        return True

    orch = GroqFactoryOrchestrator(
        batch_id="batch-1",
        limits=limits,
        checkpoint=cp,
        generation_caller=gen_caller,
        generation_provider_name="fake-groq",
        generation_model="fake-gen-model",
        verification_caller=verify_caller,
        verification_provider_name="fake-groq",
        verification_model="fake-verify-model",
        taxonomy_resolver=_taxonomy_resolver(),
        staging_writer=staging_writer or default_writer,
        publication_gate_session=_fake_session(),
        sleep_fn=_noop_sleep,
    )
    return orch, cp, calls


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


async def test_success_path_both_models_called_and_accepted(tmp_path):
    document = _document(tmp_path)
    gen = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=document.doc_id))])
    verify = ScriptedCaller([_verification_response(answer_supported=True, ambiguous=False)])
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    record = await orch.process_fact(_fact_spec(), document)

    assert record.status == STATUS_ACCEPTED
    assert gen.call_count == 1
    assert verify.call_count == 1
    assert record.validation_report is not None
    assert record.validation_report.classification == "GREEN"
    assert record.publication_content_ready is True
    assert record.staging_write_ok is True
    assert len(writer_calls) == 1
    assert writer_calls[0].outcome == STATUS_ACCEPTED


# ---------------------------------------------------------------------------
# Invalid-answer rejection (generation output fails schema validation)
# ---------------------------------------------------------------------------


async def test_invalid_answer_rejection(tmp_path):
    document = _document(tmp_path)
    bad_payload = _generated_candidate_json(doc_id=document.doc_id, correct_option="Z")  # not a real label
    gen = ScriptedCaller([_ai_response(bad_payload)])
    verify = ScriptedCaller([_verification_response()])
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    record = await orch.process_fact(_fact_spec(), document)

    assert record.status == STATUS_REJECTED
    assert "GENERATION_SCHEMA_INVALID" in record.reason
    # Verification must never be called for a candidate that never parsed.
    assert verify.call_count == 0
    assert writer_calls[0].outcome == STATUS_REJECTED


# ---------------------------------------------------------------------------
# Unsupported / unmatchable evidence (fabricated citation) -> REVIEW_REQUIRED
# ---------------------------------------------------------------------------


async def test_unmatchable_evidence_forces_review_required(tmp_path):
    document = _document(tmp_path)
    fabricated = _generated_candidate_json(
        doc_id=document.doc_id, quoted_snippet="a sentence that was never actually written on this page at all"
    )
    gen = ScriptedCaller([_ai_response(fabricated)])
    verify = ScriptedCaller([_verification_response(answer_supported=True, ambiguous=False)])
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    record = await orch.process_fact(_fact_spec(), document)

    assert record.status == STATUS_REVIEW_REQUIRED
    assert record.validation_report.classification == "RED"
    assert "P_PROVENANCE" in record.validation_report.failing_gate_codes
    assert writer_calls[0].outcome == STATUS_REVIEW_REQUIRED
    assert writer_calls[0].evidence_relocation_confirmed is False


async def test_verification_disagreement_forces_review_required_even_when_deterministic_checks_pass(tmp_path):
    document = _document(tmp_path)
    gen = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=document.doc_id))])
    verify = ScriptedCaller([_verification_response(answer_supported=False, ambiguous=False)])
    orch, _cp, _writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    record = await orch.process_fact(_fact_spec(), document)

    assert record.status == STATUS_REVIEW_REQUIRED
    assert record.verification is not None
    assert record.verification.answer_supported is False


async def test_missing_verification_caller_forces_review_required_never_implicit_accept(tmp_path):
    """No verification_caller configured (e.g. Groq verification disabled/
    unconfigured) must NEVER be silently treated as agreement."""
    document = _document(tmp_path)
    gen = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=document.doc_id))])
    orch, _cp, _writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=None)

    record = await orch.process_fact(_fact_spec(), document)

    assert record.status == STATUS_REVIEW_REQUIRED
    assert record.verification is None


# ---------------------------------------------------------------------------
# Provider failure handling — timeout / malformed JSON / 429
# ---------------------------------------------------------------------------


async def test_generation_timeout_retries_then_fails_safely(tmp_path):
    err = ProviderError(PROVIDER_TIMEOUT, "timed out", provider="fake-groq", retryable=True)
    gen = ScriptedCaller([err, err, err])  # always fails
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, max_retries=2)

    record = await orch.process_fact(_fact_spec(), _document(tmp_path))

    assert record.status == STATUS_REJECTED
    assert "GENERATION_PROVIDER_FAILED" in record.reason
    assert gen.call_count == 3  # 1 initial attempt + 2 bounded retries, never more
    assert writer_calls[0].outcome == STATUS_REJECTED


async def test_generation_rate_limited_429_retries_then_succeeds(tmp_path):
    document = _document(tmp_path)
    err = ProviderError(PROVIDER_RATE_LIMITED, "rate limited", provider="fake-groq", retryable=True)
    good = _ai_response(_generated_candidate_json(doc_id=document.doc_id))
    gen = ScriptedCaller([err, good])
    verify = ScriptedCaller([_verification_response()])
    orch, _cp, _writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify, max_retries=2)

    record = await orch.process_fact(_fact_spec(), document)

    assert gen.call_count == 2
    assert record.status == STATUS_ACCEPTED


async def test_generation_malformed_json_handled_safely(tmp_path):
    bad_text_response = AIResponse(
        text="this is not json", model="fake-gen-model", prompt_tokens=1, completion_tokens=1, provider="fake-groq"
    )
    gen = ScriptedCaller([bad_text_response])
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen)

    record = await orch.process_fact(_fact_spec(), _document(tmp_path))

    assert record.status == STATUS_REJECTED
    assert "GENERATION_MALFORMED_JSON" in record.reason
    assert writer_calls[0].outcome == STATUS_REJECTED


async def test_verification_malformed_json_treated_as_insufficient_not_crash(tmp_path):
    document = _document(tmp_path)
    gen = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=document.doc_id))])
    bad_verify = AIResponse(
        text="{not valid json", model="fake-verify-model", prompt_tokens=1, completion_tokens=1, provider="fake-groq"
    )
    verify = ScriptedCaller([bad_verify])
    orch, _cp, _writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    record = await orch.process_fact(_fact_spec(), document)

    assert record.status == STATUS_REVIEW_REQUIRED
    assert record.verification is None


async def test_generation_auth_failure_is_not_retried(tmp_path):
    err = ProviderError(PROVIDER_AUTH_FAILED, "bad key", provider="fake-groq", retryable=False)
    gen = ScriptedCaller([err])
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, max_retries=3)

    record = await orch.process_fact(_fact_spec(), _document(tmp_path))

    assert record.status == STATUS_REJECTED
    assert gen.call_count == 1  # non-retryable: never retried even though retries are available
    assert writer_calls[0].outcome == STATUS_REJECTED


# ---------------------------------------------------------------------------
# Bounded retries actually bounded
# ---------------------------------------------------------------------------


async def test_bounded_retries_are_actually_bounded(tmp_path):
    err = ProviderError(PROVIDER_TIMEOUT, "always failing", provider="fake-groq", retryable=True)
    gen = ScriptedCaller([err] * 10)
    orch, _cp, _writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, max_retries=3)

    record = await orch.process_fact(_fact_spec(), _document(tmp_path))

    assert record.status == STATUS_REJECTED
    assert gen.call_count == 4  # 1 + 3 retries, never a 5th call
    assert isinstance(record.reason, str) and "RetryBudgetExceeded" in record.reason


# ---------------------------------------------------------------------------
# Budget exhaustion — pre-dispatch, mid-batch, and on a retry attempt
# ---------------------------------------------------------------------------


async def test_budget_exhausted_blocks_before_any_dispatch(tmp_path):
    """Ceiling is already too small for even the first worst-case call —
    the provider callable must never be invoked at all."""
    gen = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id="irrelevant"))])
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, max_spend=1.0, gen_tokens_cap=10)
    # worst case for a generation call = 10 tokens * $1/token = $10 > $1 ceiling

    record = await orch.process_fact(_fact_spec(), _document(tmp_path))

    assert gen.call_count == 0
    assert record.status == STATUS_REJECTED
    assert "BUDGET_EXHAUSTED" in record.reason
    assert writer_calls[0].outcome == STATUS_REJECTED


async def test_budget_exhaustion_mid_batch_stops_cleanly(tmp_path):
    document = _document(tmp_path)
    # Ceiling allows exactly one fact's generation+verification (1 token
    # each, $1 each => $2 total) but not a second fact's.
    gen = ScriptedCaller(
        [
            _ai_response(_generated_candidate_json(doc_id=document.doc_id), prompt_tokens=1),
            _ai_response(_generated_candidate_json(doc_id=document.doc_id), prompt_tokens=1),
        ]
    )
    verify = ScriptedCaller([_verification_response(prompt_tokens=1), _verification_response(prompt_tokens=1)])
    orch, _cp, writer_calls = _build_orchestrator(
        tmp_path, gen_caller=gen, verify_caller=verify, max_spend=2.0, gen_tokens_cap=1, verify_tokens_cap=1
    )

    specs = [_fact_spec(fact_id="fact-1"), _fact_spec(fact_id="fact-2"), _fact_spec(fact_id="fact-3")]
    results = await orch.run_batch(specs, document)

    assert len(results) == 2  # third fact never attempted once the ceiling was hit
    assert results[0].status == STATUS_ACCEPTED
    assert results[1].status == STATUS_REJECTED
    assert "BUDGET_EXHAUSTED" in results[1].reason
    assert len(writer_calls) == 2  # both outcomes persisted, batch stopped cleanly (no crash)


async def test_budget_exhausted_blocks_a_retry_attempt_specifically(tmp_path):
    """Simulates a provider that is billed for tokens it already streamed
    before erroring out (a real possibility for some providers on a
    mid-stream failure) — the spend tracker is updated by the FIRST
    attempt even though it failed, so the pre-dispatch check correctly
    blocks the SECOND (retry) attempt before it is ever dispatched."""
    orch, _cp, writer_calls = _build_orchestrator(
        tmp_path, gen_caller=None, max_spend=5.0, gen_tokens_cap=1, max_retries=2
    )

    attempt_log: list[int] = []

    async def billed_then_fails(*, system_prompt, user_prompt, max_tokens):
        attempt_log.append(len(attempt_log) + 1)
        if len(attempt_log) == 1:
            # First attempt: provider billed $5 worth of streamed tokens
            # before timing out — record that spend, then raise.
            orch.spend_tracker.record(5.0)
            raise ProviderError(PROVIDER_TIMEOUT, "timed out mid-stream", provider="fake-groq", retryable=True)
        raise AssertionError("must never be dispatched — budget already exhausted by attempt 1")

    orch.generation_caller = billed_then_fails

    record = await orch.process_fact(_fact_spec(), _document(tmp_path))

    assert len(attempt_log) == 1  # the retry attempt was blocked BEFORE dispatch
    assert record.status == STATUS_REJECTED
    assert "BUDGET_EXHAUSTED" in record.reason
    assert writer_calls[0].outcome == STATUS_REJECTED


# ---------------------------------------------------------------------------
# Resume after interruption — checkpoint correctness, no double-spend
# ---------------------------------------------------------------------------


async def test_resume_after_interruption_skips_already_processed_fact_without_double_spend(tmp_path):
    document = _document(tmp_path)
    checkpoint_path = tmp_path / "checkpoint.json"

    gen1 = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=document.doc_id))])
    verify1 = ScriptedCaller([_verification_response()])
    checkpoint1 = GroqFactoryCheckpoint(checkpoint_path, batch_id="batch-1")
    orch1, _cp1, writer_calls1 = _build_orchestrator(
        tmp_path, gen_caller=gen1, verify_caller=verify1, checkpoint=checkpoint1
    )
    first_record = await orch1.process_fact(_fact_spec(), document)
    assert first_record.status == STATUS_ACCEPTED
    spent_after_first_run = checkpoint1.total_spent_usd()
    assert spent_after_first_run > 0

    # Simulate a fresh process: new orchestrator, checkpoint reloaded from
    # the SAME file path.
    gen2 = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=document.doc_id))])
    verify2 = ScriptedCaller([_verification_response()])
    checkpoint2 = GroqFactoryCheckpoint(checkpoint_path, batch_id="batch-1")
    orch2, _cp2, writer_calls2 = _build_orchestrator(
        tmp_path, gen_caller=gen2, verify_caller=verify2, checkpoint=checkpoint2
    )
    resumed_record = await orch2.process_fact(_fact_spec(), document)

    assert resumed_record.resumed_skip is True
    assert resumed_record.status == STATUS_ACCEPTED
    # Neither provider was ever called on resume — no double spend.
    assert gen2.call_count == 0
    assert verify2.call_count == 0
    # Nothing new written to staging on a resumed skip.
    assert writer_calls2 == []
    # Cumulative spend read back after "restart" matches the first run's —
    # it was persisted to disk, not lost.
    assert checkpoint2.total_spent_usd() == pytest.approx(spent_after_first_run)
    # The rehydrated tracker used by a new orchestrator instance correctly
    # starts from that same persisted total.
    assert orch2.spend_tracker.spent_usd == pytest.approx(spent_after_first_run)


# ---------------------------------------------------------------------------
# Staging-store write failure handled safely
# ---------------------------------------------------------------------------


async def test_staging_write_failure_handled_safely_checkpoint_still_recorded(tmp_path):
    document = _document(tmp_path)
    gen = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=document.doc_id))])
    verify = ScriptedCaller([_verification_response()])

    async def failing_writer(_record):
        raise RuntimeError("staging store unreachable")

    orch, cp, _writer_calls = _build_orchestrator(
        tmp_path, gen_caller=gen, verify_caller=verify, staging_writer=failing_writer
    )

    record = await orch.process_fact(_fact_spec(), document)

    assert record.status == STATUS_ACCEPTED  # validation outcome unaffected by persistence failure
    assert record.staging_write_ok is False
    assert "staging store unreachable" in record.staging_write_error
    # Checkpoint is still recorded so a resume never re-spends on this fact,
    # even though the staging write failed — the caller must reconcile
    # staging persistence manually using the returned audit record.
    assert cp.is_done("fact-1") is True


# ---------------------------------------------------------------------------
# No real DB writes by default — the fakes are the only persistence path
# ---------------------------------------------------------------------------


async def test_no_real_database_or_network_objects_are_ever_constructed(tmp_path):
    """Sanity check that this whole test file's success path never
    constructs a real SQLAlchemy engine/session or a real httpx client —
    the publication-gates session is a bare SimpleNamespace and the
    generation/verification callers are plain Python objects."""
    document = _document(tmp_path)
    gen = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=document.doc_id))])
    verify = ScriptedCaller([_verification_response()])
    orch, _cp, _writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    assert type(orch.publication_gate_session).__name__ == "SimpleNamespace"
    assert not hasattr(orch.publication_gate_session, "bind")
    assert not hasattr(orch.generation_caller, "_base_url")  # not a real OpenAIProvider

    record = await orch.process_fact(_fact_spec(), document)
    assert record.status == STATUS_ACCEPTED
