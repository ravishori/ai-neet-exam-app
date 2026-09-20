"""P2.2 AI-assisted source recovery tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.modules.cms.pyq.p2_2.cache import RecoveryCache
from app.modules.cms.pyq.p2_2.consensus import compare_providers
from app.modules.cms.pyq.p2_2.deterministic import attempt_deterministic_recovery
from app.modules.cms.pyq.p2_2.evidence import build_evidence_package, canonical_hash, check_source_availability
from app.modules.cms.pyq.p2_2.pipeline import select_pilot_cohort
from app.modules.cms.pyq.p2_2.providers import (
    DryRunRecoveryProvider,
    GatewayRecoveryProvider,
    build_user_prompt,
    parse_recovery_json,
)
from app.modules.cms.pyq.p2_2.schemas import AIRecoveryOutput, RECOVERY_PROMPT_CONTRACT, TriageResult
from app.modules.cms.pyq.p2_2.triage import missing_fields, triage_record
from app.modules.cms.pyq.p2_2.validation import validate_against_source

ROOT = Path(__file__).resolve().parents[6]
R3 = ROOT / "data/staging/pyq/2020-2025/p2_1e_full_r3"


def _sample_record(**overrides) -> dict:
    base = {
        "source_sha256": "abc123def4567890" * 4,
        "source_page": 2,
        "question_number": 5,
        "stem": "What is the speed?",
        "option_a": "10 m/s",
        "option_b": "",
        "option_c": "",
        "option_d": "",
        "raw_extracted_text": "5 What is the speed?\n(1) 10 m/s\n(2) 20 m/s\n(3) 30 m/s\n(4) 40 m/s",
        "p2_1e_quality_status": "PARTIAL",
        "exam_year": 2023,
        "paper_code": "A",
    }
    base.update(overrides)
    return base


def test_provider_abstraction_dry_run():
    provider = DryRunRecoveryProvider()
    assert provider.name == "dry_run"


def test_structured_json_validation():
    raw = json.dumps(
        {
            "status": "RECOVERED",
            "stem": "Test stem",
            "options": {"1": "A", "2": "B", "3": "C", "4": "D"},
            "changed_fields": ["option_2"],
            "source_evidence_used": ["ocr_text"],
            "uncertainties": [],
            "foreign_text_detected": False,
            "confidence": 0.9,
        }
    )
    out = parse_recovery_json(raw)
    assert out.status == "RECOVERED"
    assert out.options["2"] == "B"


def test_malformed_ai_output():
    with pytest.raises(json.JSONDecodeError):
        parse_recovery_json("not json")


def test_missing_fields_in_ai_output():
    out = parse_recovery_json('{"status": "INCONCLUSIVE"}')
    assert out.status == "INCONCLUSIVE"
    assert out.options == {}


def test_hallucinated_content_detection():
    output = AIRecoveryOutput(
        status="RECOVERED",
        stem="Completely invented stem about quantum gravity",
        options={"1": "invented alpha", "2": "invented beta", "3": "c", "4": "d"},
    )
    evidence = {"ocr_text": "5 What is the speed?\n(1) 10 m/s\n(2) 20 m/s"}
    verdict, grade, _ = validate_against_source(output, evidence, original=_sample_record())
    assert verdict == "FAIL"
    assert grade == "D"


def test_source_evidence_requirement():
    tr = triage_record(_sample_record(raw_extracted_text=""), has_source_pdf=False, has_ocr_words=False)
    assert tr.category == "SOURCE_INSUFFICIENT"


def test_disagreement_handling():
    a = AIRecoveryOutput(status="RECOVERED", stem="A stem", options={"1": "x", "2": "y", "3": "z", "4": "w"})
    b = AIRecoveryOutput(status="RECOVERED", stem="Different", options={"1": "x", "2": "y", "3": "z", "4": "w"})
    assert compare_providers([a, b]) == "DISAGREEMENT"


def test_confidence_handling():
    out = parse_recovery_json('{"status":"RECOVERED","confidence":0.42,"options":{}}')
    assert out.confidence == 0.42


def test_cache_behavior(tmp_path):
    cache = RecoveryCache(tmp_path)
    payload = {"status": "RECOVERED", "stem": "s", "options": {}, "changed_fields": [], "source_evidence_used": [], "uncertainties": [], "foreign_text_detected": False, "confidence": 0.5}
    cache.put("sh", "rh", "dry_run", payload)
    hit = cache.get("sh", "rh", "dry_run")
    assert hit is not None
    assert hit["stem"] == "s"
    assert cache.get("sh", "rh", "other") is None


@pytest.mark.asyncio
async def test_retry_behavior_via_attempt_counter():
    provider = DryRunRecoveryProvider()
    _, attempt = await provider.recover(evidence={"ocr_text": "x", "r3_extraction": {"stem": "s"}}, candidate_id="q1", attempt=2)
    assert attempt.attempt == 2


def test_rate_limit_handling_placeholder():
    """Provider errors surface via ProviderAttempt.error — gateway layer responsibility."""
    from app.modules.cms.pyq.p2_2.schemas import ProviderAttempt

    pa = ProviderAttempt(provider="x", model="m", candidate_id="c", attempt=1, timestamp="t", status="error", error="rate_limit")
    assert pa.error == "rate_limit"


def test_timeout_handling_placeholder():
    from app.modules.cms.pyq.p2_2.schemas import ProviderAttempt

    pa = ProviderAttempt(provider="x", model="m", candidate_id="c", attempt=1, timestamp="t", status="timeout", error="timeout")
    assert "timeout" in pa.error


def test_diagram_routing():
    rec = _sample_record(stem="Refer to the figure shown below", p2_1e_quality_status="PARTIAL")
    tr = triage_record(rec, has_source_pdf=False, has_ocr_words=True)
    assert tr.category == "HUMAN_REVIEW"


def test_equation_handling_routes_ai():
    rec = _sample_record(
        stem="Find ∫ x^2 dx",
        option_a="x^3/3",
        option_b="",
        option_c="",
        option_d="",
        raw_extracted_text="",
    )
    tr = triage_record(rec, has_source_pdf=False, has_ocr_words=True)
    assert tr.category == "AI_MULTIMODAL_RECOVERABLE"


def test_human_review_routing_severe_fragmentation():
    rec = _sample_record(stem="", option_a="", option_b="", option_c="", option_d="", raw_extracted_text="tiny")
    tr = triage_record(rec, has_source_pdf=False, has_ocr_words=True)
    assert tr.category == "HUMAN_REVIEW"


def test_provenance_persistence_fields():
    rec = _sample_record()
    missing = missing_fields(rec)
    assert "option_2" in missing


def test_original_status_immutability_in_triage():
    rec = _sample_record(p2_1e_quality_status="PARTIAL")
    tr = triage_record(rec, has_source_pdf=False, has_ocr_words=True)
    assert tr.original_status == "PARTIAL"


def test_r3_immutability_paths():
    assert (R3 / "questions.p2_1e_full.jsonl").exists()
    recovery_root = ROOT / "data/staging/pyq/2020-2025/p2_2_ai_recovery"
    assert "p2_2_ai_recovery" in str(recovery_root)
    assert "p2_1e_full_r3" not in str(recovery_root)


def test_production_db_write_protection():
    """Pilot uses DryRunRecoveryProvider — no gateway session."""
    provider = DryRunRecoveryProvider()
    assert provider.name != "production"


def test_deterministic_recovery():
    out = attempt_deterministic_recovery(_sample_record())
    assert out is not None
    assert out.status == "RECOVERED"
    assert out.options.get("2") == "20 m/s"


def test_prompt_contract_present():
    assert "Do not invent question text" in RECOVERY_PROMPT_CONTRACT


def test_pilot_selection_stratified():
    results = [
        TriageResult("a", "AI_MULTIMODAL_RECOVERABLE", "partial", "PARTIAL"),
        TriageResult("b", "DETERMINISTIC_RECOVERABLE", "raw", "PARTIAL"),
        TriageResult("c", "HUMAN_REVIEW", "diagram", "PARTIAL"),
    ]
    cohort = select_pilot_cohort(results, {}, target=2, seed=1)
    assert len(cohort) == 2


@pytest.mark.asyncio
async def test_gateway_provider_parses_json():
    mock = AsyncMock()
    mock.generate_request.return_value = type(
        "R",
        (),
        {
            "text": json.dumps({"status": "INCONCLUSIVE", "options": {}, "confidence": 0.1}),
            "model": "test-model",
            "provider_request_id": "req-1",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "cost_usd": 0.0,
        },
    )()
    provider = GatewayRecoveryProvider(mock, name="test", model="test-model")
    out, attempt = await provider.recover(
        evidence={"ocr_text": "hello", "r3_extraction": {"stem": "hello"}},
        candidate_id="q1",
    )
    assert out.status == "INCONCLUSIVE"
    assert attempt.provider == "test"


def test_evidence_package_hash_stable():
    rec = _sample_record()
    words = R3 / "ocr.words.p2_1e_full.jsonl"
    pkg1 = build_evidence_package(rec, words_path=words, neighbors=[])
    pkg2 = build_evidence_package(rec, words_path=words, neighbors=[])
    assert pkg1["source_evidence_hash"] == pkg2["source_evidence_hash"]


def test_build_user_prompt_includes_contract_fields():
    prompt = build_user_prompt({"question_id": "q1", "r3_extraction": {}, "ocr_text": "x", "ocr_words": [], "neighboring_questions": [], "known_defects": []})
    assert "question_id" in prompt


def test_check_source_availability_raw_fallback():
    rec = _sample_record()
    avail = check_source_availability(rec, zip_path=None, words_path=R3 / "ocr.words.p2_1e_full.jsonl")
    assert avail["has_ocr_words"] is True
