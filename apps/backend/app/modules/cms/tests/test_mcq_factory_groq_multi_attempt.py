"""Tests for NEET-MCQ-FACTORY-MULTI-ATTEMPT-001 (multi-attempt generation +
cross-attempt/cross-batch duplicate detection + the deterministic four-angle
cycle) — see docs/quality/neet_mcq_factory_MULTI_ATTEMPT_PLAN_20261013.md.

ZERO real network calls, ZERO real database writes, ZERO real GROQ_API_KEY
anywhere in this file — same conventions as
``test_mcq_factory_groq_orchestrator.py``:

- Generation/verification "providers" are plain scripted async callables.
- The publication-gates session is a ``SimpleNamespace`` with an
  ``AsyncMock`` ``.execute``.
- The staging store is an in-memory list.
- The syllabus gate is checked against a tiny fixture registry.
- The cross-batch duplicate lookup is a plain Python async function
  returning a scripted list of ``CrossBatchDuplicateMatch`` — never a real
  SQL query, never a real session.
- A real local PDF IS written (via ``fitz``, to ``tmp_path``) and read back
  with the real ``pdf_text_index.index_pdf`` — local filesystem I/O only.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import fitz
import pytest

from app.modules.ai.gateway.base import AIResponse
from app.modules.ai.gateway.pricing import PriceRate, register_rate
from app.modules.cms.mcq_factory_groq.orchestrator import (
    REASON_SKIPPED_PRIOR_ATTEMPT_REJECTED,
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    STATUS_REVIEW_REQUIRED,
    CrossBatchDuplicateMatch,
    FactSpec,
    GroqFactoryOrchestrator,
)
from app.modules.cms.mcq_factory_groq.pdf_text_index import index_pdf
from app.modules.cms.mcq_factory_groq.prompt_templates import angle_for_attempt
from app.modules.cms.mcq_factory_groq.schemas import TaxonomyIds
from app.modules.cms.mcq_factory_groq.validators import InMemoryTaxonomyResolver
from app.modules.cms.services.mcq_factory_groq_controls import GroqFactoryCheckpoint, GroqFactoryLimits
from app.modules.cms.syllabus.neet_2026_parser import NeetSyllabusRegistry, NeetSyllabusTopic, NeetSyllabusUnit

pytestmark = pytest.mark.asyncio

register_rate("fake-groq-ma", "fake-gen-model-ma", PriceRate(1_000_000.0, 0.0))
register_rate("fake-groq-ma", "fake-verify-model-ma", PriceRate(1_000_000.0, 0.0))

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
QUOTED_SNIPPET = (
    "force acting on an object is equal to the mass of that object multiplied by its acceleration"
)


def _write_pdf(path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
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


def _candidate_json(*, doc_id: str, stem: str, correct_option: str = "A") -> dict:
    return {
        "stem": stem,
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


def _ai_response(payload, *, model: str = "fake-gen-model-ma", prompt_tokens: int = 1, completion_tokens: int = 1) -> AIResponse:
    import json

    return AIResponse(
        text=json.dumps(payload),
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider="fake-groq-ma",
        provider_request_id="req-1",
        finish_reason="stop",
        is_fallback=False,
    )


def _verification_response(*, answer_supported: bool = True, ambiguous: bool = False) -> AIResponse:
    return _ai_response(
        {"answer_supported": answer_supported, "ambiguous": ambiguous, "unsupported_claims": [], "notes": "ok"},
        model="fake-verify-model-ma",
    )


class ScriptedCaller:
    """Plain async callable standing in for a provider call site. Also
    records every ``user_prompt`` it was invoked with, so angle-cycle
    tests can assert the actual interpolated prompt text differs per
    attempt without needing to inspect orchestrator internals."""

    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.call_count = 0
        self.user_prompts: list[str] = []

    async def __call__(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> AIResponse:
        self.call_count += 1
        self.user_prompts.append(user_prompt)
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
    checkpoint: GroqFactoryCheckpoint | None = None,
    cross_batch_duplicate_lookup=None,
    batch_id: str = "batch-1",
):
    limits = GroqFactoryLimits(
        max_total_spend_usd=1000.0,
        max_generation_tokens_per_question=10,
        max_verification_tokens_per_question=10,
        max_retries_per_call=2,
        rate_limit_requests_per_minute=10_000,
        rate_limit_tokens_per_minute=10_000_000,
    )
    cp = checkpoint or GroqFactoryCheckpoint(tmp_path / "checkpoint.json", batch_id=batch_id)
    writer_calls: list = []

    async def default_writer(record) -> bool:
        writer_calls.append(record)
        return True

    orch = GroqFactoryOrchestrator(
        batch_id=batch_id,
        limits=limits,
        checkpoint=cp,
        generation_caller=gen_caller,
        generation_provider_name="fake-groq-ma",
        generation_model="fake-gen-model-ma",
        verification_caller=verify_caller,
        verification_provider_name="fake-groq-ma",
        verification_model="fake-verify-model-ma",
        taxonomy_resolver=_taxonomy_resolver(),
        staging_writer=default_writer,
        publication_gate_session=_fake_pub_gate_session(),
        cross_batch_duplicate_lookup=cross_batch_duplicate_lookup,
        sleep_fn=_noop_sleep,
    )
    return orch, cp, writer_calls


# ---------------------------------------------------------------------------
# (a) Angle-cycle prompt text genuinely differs per attempt_number
# ---------------------------------------------------------------------------


def test_angle_cycle_produces_four_distinct_instructions_and_wraps_deterministically():
    names_and_text = [angle_for_attempt(n) for n in range(1, 5)]
    names = [n for n, _ in names_and_text]
    texts = [t for _, t in names_and_text]

    assert names == ["DEFINE_IDENTIFY", "COMPARE_CONTRAST", "APPLY_SCENARIO", "CAUSAL_NUMERIC_STEP"]
    assert len(set(texts)) == 4  # all 4 instruction strings are genuinely different
    # Deterministic wrap-around: attempt 5 repeats attempt 1 exactly.
    assert angle_for_attempt(5) == angle_for_attempt(1)
    assert angle_for_attempt(8) == angle_for_attempt(4)
    with pytest.raises(ValueError):
        angle_for_attempt(0)


async def test_angle_instruction_text_actually_reaches_the_real_generation_prompt(tmp_path):
    """End-to-end: process_fact for attempt_number 1 and 2 on the SAME
    fact must send genuinely different user_prompt text to the generation
    caller (the angle instruction is interpolated, not just computed and
    discarded)."""
    document = _document(tmp_path)
    gen = ScriptedCaller(
        [
            _ai_response(_candidate_json(doc_id=document.doc_id, stem="Attempt one stem about force and mass.")),
            _ai_response(_candidate_json(doc_id=document.doc_id, stem="Attempt two stem about a different angle.")),
        ]
    )
    verify = ScriptedCaller([_verification_response(), _verification_response()])
    orch, _cp, _writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    await orch.process_fact(_fact_spec(), document, attempt_number=1)
    await orch.process_fact(_fact_spec(), document, attempt_number=2)

    assert len(gen.user_prompts) == 2
    assert gen.user_prompts[0] != gen.user_prompts[1]
    _name1, instruction1 = angle_for_attempt(1)
    _name2, instruction2 = angle_for_attempt(2)
    assert instruction1 in gen.user_prompts[0]
    assert instruction2 in gen.user_prompts[1]


# ---------------------------------------------------------------------------
# (b) Cross-attempt dedup: true positive (same normalized stem) -> REVIEW_REQUIRED + provenance
# ---------------------------------------------------------------------------


async def test_cross_attempt_duplicate_exact_match_forces_review_required_with_provenance(tmp_path):
    document = _document(tmp_path)
    same_stem = "According to the evidence, what does Newton's second law equate force to?"
    # Attempt 2's stem differs only in case/punctuation/whitespace —
    # normalize_stem() must treat these as IDENTICAL.
    cosmetically_different_stem = "  ACCORDING TO THE EVIDENCE, WHAT DOES NEWTON'S SECOND LAW EQUATE FORCE TO???  "
    gen = ScriptedCaller(
        [
            _ai_response(_candidate_json(doc_id=document.doc_id, stem=same_stem)),
            _ai_response(_candidate_json(doc_id=document.doc_id, stem=cosmetically_different_stem)),
        ]
    )
    verify = ScriptedCaller([_verification_response(), _verification_response()])
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    record1 = await orch.process_fact(_fact_spec(), document, attempt_number=1)
    assert record1.status == STATUS_ACCEPTED

    record2 = await orch.process_fact(_fact_spec(), document, attempt_number=2)

    assert record2.status == STATUS_REVIEW_REQUIRED
    gate = next(g for g in record2.validation_report.gates if g.code == "C_CROSS_ATTEMPT_DUPLICATE")
    assert gate.passed is False
    assert gate.warnings  # non-empty: the exact-match finding
    assert "fact-1" in gate.warnings[0]
    assert "attempt1" in gate.warnings[0]

    # Provenance correctly reaches the staging row too.
    staged = writer_calls[1]
    assert staged.is_duplicate is True
    assert "fact-1" in staged.duplicate_matched_source_file
    assert "attempt1" in staged.duplicate_matched_source_file


# ---------------------------------------------------------------------------
# (c) Cross-attempt dedup: true negative (genuinely different candidates)
# ---------------------------------------------------------------------------


async def test_cross_attempt_duplicate_does_not_flag_genuinely_different_candidates(tmp_path):
    document = _document(tmp_path)
    gen = ScriptedCaller(
        [
            _ai_response(_candidate_json(doc_id=document.doc_id, stem="What does Newton's second law equate force to?")),
            _ai_response(
                _candidate_json(
                    doc_id=document.doc_id,
                    stem="Which physical quantity multiplies mass to produce force in this relationship?",
                )
            ),
        ]
    )
    verify = ScriptedCaller([_verification_response(), _verification_response()])
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    record1 = await orch.process_fact(_fact_spec(), document, attempt_number=1)
    assert record1.status == STATUS_ACCEPTED

    record2 = await orch.process_fact(_fact_spec(), document, attempt_number=2)

    assert record2.status == STATUS_ACCEPTED
    gate = next(g for g in record2.validation_report.gates if g.code == "C_CROSS_ATTEMPT_DUPLICATE")
    assert gate.passed is True
    assert gate.warnings == []
    assert writer_calls[1].is_duplicate is False


# ---------------------------------------------------------------------------
# (d) Cross-BATCH dedup — a match from a DIFFERENT, earlier batch_id
# ---------------------------------------------------------------------------


async def test_cross_batch_duplicate_from_different_batch_forces_review_required(tmp_path):
    document = _document(tmp_path)
    gen = ScriptedCaller([_ai_response(_candidate_json(doc_id=document.doc_id, stem="A brand-new candidate stem."))])
    verify = ScriptedCaller([_verification_response()])

    async def fake_cross_batch_lookup(stem_hash_value: str):
        # Real wiring (generation_staging_store.find_staging_candidates_by_stem_hash)
        # would filter by stem_hash in SQL — this fake simulates exactly
        # one match found in an EARLIER, DIFFERENT batch.
        return [
            CrossBatchDuplicateMatch(
                staging_id="11111111-1111-1111-1111-111111111111",
                batch_id="earlier-batch-999",
                fact_id="fact-1",
                attempt_number=1,
            )
        ]

    orch, _cp, writer_calls = _build_orchestrator(
        tmp_path,
        gen_caller=gen,
        verify_caller=verify,
        cross_batch_duplicate_lookup=fake_cross_batch_lookup,
        batch_id="this-batch-new",
    )

    record = await orch.process_fact(_fact_spec(), document, attempt_number=1)

    assert record.status == STATUS_REVIEW_REQUIRED
    gate = next(g for g in record.validation_report.gates if g.code == "C_CROSS_ATTEMPT_DUPLICATE")
    assert gate.passed is False
    assert "earlier-batch-999" in gate.warnings[0]
    assert "fact-1" in gate.warnings[0]
    assert writer_calls[0].is_duplicate is True
    assert "earlier-batch-999" in writer_calls[0].duplicate_matched_source_file


async def test_no_cross_batch_lookup_configured_skips_the_check_cleanly(tmp_path):
    """Backward compatibility: cross_batch_duplicate_lookup=None (the
    default) must never attempt to call anything and must never flag a
    false positive."""
    document = _document(tmp_path)
    gen = ScriptedCaller([_ai_response(_candidate_json(doc_id=document.doc_id, stem="Some candidate stem."))])
    verify = ScriptedCaller([_verification_response()])
    orch, _cp, _writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)
    assert orch.cross_batch_duplicate_lookup is None

    record = await orch.process_fact(_fact_spec(), document, attempt_number=1)

    assert record.status == STATUS_ACCEPTED
    gate = next(g for g in record.validation_report.gates if g.code == "C_CROSS_ATTEMPT_DUPLICATE")
    assert gate.passed is True


# ---------------------------------------------------------------------------
# (e) Checkpoint/resume correctly skips an already-completed attempt
# ---------------------------------------------------------------------------


async def test_resume_mid_multi_attempt_skips_completed_attempts_dispatches_only_the_new_one(tmp_path):
    document = _document(tmp_path)
    checkpoint_path = tmp_path / "checkpoint.json"

    gen1 = ScriptedCaller(
        [
            _ai_response(_candidate_json(doc_id=document.doc_id, stem="First attempt stem, accepted cleanly.")),
            _ai_response(_candidate_json(doc_id=document.doc_id, stem="Second attempt stem, disputed by reviewer.")),
        ]
    )
    verify1 = ScriptedCaller([_verification_response(answer_supported=True), _verification_response(answer_supported=False)])
    checkpoint1 = GroqFactoryCheckpoint(checkpoint_path, batch_id="batch-resume")
    orch1, _cp1, _writer_calls1 = _build_orchestrator(
        tmp_path, gen_caller=gen1, verify_caller=verify1, checkpoint=checkpoint1, batch_id="batch-resume"
    )

    first_run_results = await orch1.run_batch([_fact_spec()], document, max_attempts_per_fact=2)
    assert len(first_run_results) == 2
    assert first_run_results[0].status == STATUS_ACCEPTED
    assert first_run_results[1].status == STATUS_REVIEW_REQUIRED
    assert gen1.call_count == 2

    # Fresh process: new orchestrator/checkpoint reloaded from the SAME file.
    gen2 = ScriptedCaller(
        [_ai_response(_candidate_json(doc_id=document.doc_id, stem="Third attempt stem, brand new content."))]
    )
    verify2 = ScriptedCaller([_verification_response()])
    checkpoint2 = GroqFactoryCheckpoint(checkpoint_path, batch_id="batch-resume")
    orch2, _cp2, _writer_calls2 = _build_orchestrator(
        tmp_path, gen_caller=gen2, verify_caller=verify2, checkpoint=checkpoint2, batch_id="batch-resume"
    )

    resumed_results = await orch2.run_batch([_fact_spec()], document, max_attempts_per_fact=3)

    assert len(resumed_results) == 3
    assert resumed_results[0].resumed_skip is True
    assert resumed_results[0].status == STATUS_ACCEPTED
    assert resumed_results[1].resumed_skip is True
    assert resumed_results[1].status == STATUS_REVIEW_REQUIRED
    assert resumed_results[2].resumed_skip is False
    assert resumed_results[2].status == STATUS_ACCEPTED
    # Only the NEW attempt (3) ever reached a provider — zero double-spend.
    assert gen2.call_count == 1
    assert verify2.call_count == 1


# ---------------------------------------------------------------------------
# (f) "Attempt 1 REJECTED -> later attempts skipped" policy
# ---------------------------------------------------------------------------


async def test_rejected_attempt_one_skips_all_later_attempts(tmp_path):
    document = _document(tmp_path)

    async def never_called(*, system_prompt, user_prompt, max_tokens):
        raise AssertionError("generation caller must never be dispatched for an out-of-syllabus fact")

    # A topic that does not match anything in the fixture syllabus registry
    # -> OUT_OF_SYLLABUS_SCOPE pipeline-level REJECTED before any provider
    # call is ever made.
    out_of_scope_spec = _fact_spec(topic="a topic that does not exist in the syllabus registry at all")
    orch, _cp, writer_calls = _build_orchestrator(tmp_path, gen_caller=never_called, verify_caller=None)

    results = await orch.run_batch([out_of_scope_spec], document, max_attempts_per_fact=3)

    assert len(results) == 3
    assert results[0].status == STATUS_REJECTED
    assert "OUT_OF_SYLLABUS_SCOPE" in results[0].reason
    assert results[1].status == STATUS_REJECTED
    assert results[1].reason == REASON_SKIPPED_PRIOR_ATTEMPT_REJECTED
    assert results[1].total_cost_usd == 0.0
    assert results[2].status == STATUS_REJECTED
    assert results[2].reason == REASON_SKIPPED_PRIOR_ATTEMPT_REJECTED
    assert results[2].total_cost_usd == 0.0
    # Skipped attempts are never checkpointed/staged — only the real
    # attempt-1 rejection is.
    assert len(writer_calls) == 1


# ---------------------------------------------------------------------------
# (g) "Attempt 1 REVIEW_REQUIRED -> attempt 2 still proceeds" policy
# ---------------------------------------------------------------------------


async def test_review_required_attempt_one_still_dispatches_attempt_two(tmp_path):
    document = _document(tmp_path)
    gen = ScriptedCaller(
        [
            _ai_response(_candidate_json(doc_id=document.doc_id, stem="First attempt, reviewer disagrees here.")),
            _ai_response(_candidate_json(doc_id=document.doc_id, stem="Second attempt, a totally distinct stem.")),
        ]
    )
    # Attempt 1: verification disagreement forces REVIEW_REQUIRED (NOT a
    # pipeline-level REJECTED). Attempt 2: clean agreement.
    verify = ScriptedCaller([_verification_response(answer_supported=False), _verification_response(answer_supported=True)])
    orch, _cp, _writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    results = await orch.run_batch([_fact_spec()], document, max_attempts_per_fact=2)

    assert len(results) == 2
    assert results[0].status == STATUS_REVIEW_REQUIRED
    assert results[1].resumed_skip is False
    assert results[1].reason != REASON_SKIPPED_PRIOR_ATTEMPT_REJECTED
    # A REAL provider call was dispatched for attempt 2 — never skipped.
    assert gen.call_count == 2
    assert verify.call_count == 2
    assert results[1].status == STATUS_ACCEPTED


# ---------------------------------------------------------------------------
# (h) Backward compatibility — no multi-attempt config
# ---------------------------------------------------------------------------


async def test_run_batch_default_produces_exactly_one_attempt_one_call_per_fact(tmp_path):
    document = _document(tmp_path)
    gen = ScriptedCaller(
        [
            _ai_response(_candidate_json(doc_id=document.doc_id, stem="Fact one's only candidate stem.")),
            _ai_response(_candidate_json(doc_id=document.doc_id, stem="Fact two's only candidate stem.")),
        ]
    )
    verify = ScriptedCaller([_verification_response(), _verification_response()])
    orch, _cp, _writer_calls = _build_orchestrator(tmp_path, gen_caller=gen, verify_caller=verify)

    specs = [_fact_spec(fact_id="fact-1"), _fact_spec(fact_id="fact-2")]
    # No max_attempts_per_fact passed at all — default must be 1.
    results = await orch.run_batch(specs, document)

    assert len(results) == 2
    assert all(r.attempt_number == 1 for r in results)
    assert gen.call_count == 2  # exactly one dispatch per fact, never more
    assert verify.call_count == 2
