"""P2.2 live pilot tests — mocked providers, no API spend."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.modules.cms.pyq.p2_2.budget import BudgetExceededError, BudgetGuard
from app.modules.cms.pyq.p2_2.live_mcq import near_duplicate, structural_validate
from app.modules.cms.pyq.p2_2.live_pilot import (
    _overall_verdict,
    _track_a_verdict,
    _track_b_verdict,
    estimate_preflight_cost,
    select_human_mcq_sample,
)
from app.modules.cms.pyq.p2_2.live_recovery import _field_agreement
from app.modules.cms.pyq.p2_2.live_schemas import LiveMcqRecord
from app.modules.cms.pyq.p2_2.schemas import AIRecoveryOutput

pytestmark = pytest.mark.asyncio(loop_scope="session")


def test_budget_guard_stops():
    bg = BudgetGuard(max_cost_usd=0.01)
    with pytest.raises(BudgetExceededError):
        bg.record(track="t", provider="p", model="m", candidate_id="c", cost_usd=0.02, status="ok")
    with pytest.raises(BudgetExceededError):
        bg.check()


def test_structural_validate_four_options():
    body = {
        "status": "GENERATED",
        "question": "What is photosynthesis primarily?",
        "options": {"A": "x", "B": "y", "C": "z", "D": "w"},
        "correct_answer": "A",
        "explanation": "Because the excerpt states x clearly and others do not.",
        "source_support": "NCERT-SUPPORTED",
        "difficulty": "EASY",
    }
    assert structural_validate(body) == []


def test_structural_reject_wrong_option_count():
    body = {
        "question": "q",
        "options": {"A": "1", "B": "2"},
        "correct_answer": "A",
        "explanation": "x" * 25,
        "source_support": "NCERT-SUPPORTED",
        "difficulty": "EASY",
    }
    assert "OPTION_COUNT" in structural_validate(body)


def test_exactly_one_correct_answer_enforced():
    body = {
        "question": "Which is correct?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "correct_answer": "Z",
        "explanation": "Explanation long enough for validation.",
        "source_support": "NCERT-SUPPORTED",
        "difficulty": "MEDIUM",
    }
    assert "INVALID_ANSWER" in structural_validate(body)


def test_ncert_source_requirement():
    body = {
        "question": "Which is correct?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "correct_answer": "A",
        "explanation": "Explanation long enough for validation.",
        "source_support": "GENERAL_KNOWLEDGE",
        "difficulty": "MEDIUM",
    }
    assert "NOT_NCERT_SUPPORTED" in structural_validate(body)


def test_duplicate_detection():
    assert near_duplicate("What is the speed of light in vacuum?", "What is the speed of light in vacuum?")


def test_hallucination_detection_via_review_contract():
    from app.modules.cms.pyq.p2_2.live_schemas import MCQ_REVIEW_SYSTEM_PROMPT

    assert "ncert_supported" in MCQ_REVIEW_SYSTEM_PROMPT


def test_provenance_fields():
    rec = LiveMcqRecord(
        mcq_id="m1",
        provider="gemini",
        model="g",
        status="GENERATED",
        subject="PHYSICS",
        class_level="11",
        chapter=1,
        topic="t",
        source_file="f.pdf",
        source_page=1,
        source_hash="abc",
    )
    d = rec.to_dict()
    assert d["source_file"] == "f.pdf"
    assert d["human_verdict"] == "PENDING"


def test_field_agreement_disagreement():
    a = AIRecoveryOutput(status="RECOVERED", stem="A", options={"1": "x", "2": "y", "3": "z", "4": "w"})
    b = AIRecoveryOutput(status="RECOVERED", stem="B", options={"1": "x", "2": "y", "3": "z", "4": "w"})
    fa = _field_agreement([a, b])
    assert fa["overall"] < 1.0


def test_track_verdicts():
    assert _track_a_verdict({"processed": 10, "verified": 5, "provider_disagreement": 1}, false_recovery=0) in ("GREEN", "YELLOW")
    assert _track_a_verdict({"processed": 10, "verified": 1, "provider_disagreement": 0}, false_recovery=2) == "RED"
    assert _track_b_verdict({"generated": 1000, "validated": 600, "exact_duplicate_count": 10, "near_duplicate_count": 5}) == "GREEN"
    assert _overall_verdict("GREEN", "YELLOW") == "YELLOW"


def test_preflight_cost_estimate():
    est = estimate_preflight_cost(recovery_count=40, mcq_count=1000, providers_available=3)
    assert est["estimated_max_api_cost_usd"] > 0


def test_human_sample_selection():
    records = [
        LiveMcqRecord(
            mcq_id=f"m{i}",
            provider=["gemini", "openai", "anthropic"][i % 3],
            model="m",
            status="VALIDATED",
            subject=["PHYSICS", "CHEMISTRY", "BIOLOGY"][i % 3],
            class_level="11",
            chapter=1,
            topic="t",
            source_file="f",
            source_page=1,
            source_hash="h",
            difficulty=["EASY", "MEDIUM", "HARD"][i % 3],
        )
        for i in range(50)
    ]
    sample = select_human_mcq_sample(records, target=10, seed=1)
    assert len(sample) == 10


def test_production_db_write_protection():
    """Live pilot modules never import SQLAlchemy session factories."""
    import app.modules.cms.pyq.p2_2.live_pilot as lp

    assert "AsyncSession" not in open(lp.__file__, encoding="utf-8").read()


@pytest.mark.asyncio
async def test_malformed_provider_json_handling():
    from app.modules.cms.pyq.p2_2.providers import parse_recovery_json

    with pytest.raises(json.JSONDecodeError):
        parse_recovery_json("{")


def test_rate_limit_error_surface():
    from app.modules.ai.gateway.base import PROVIDER_RATE_LIMITED, ProviderError

    err = ProviderError(PROVIDER_RATE_LIMITED, "rate limited", provider="gemini", retryable=True)
    assert err.retryable


def test_caching_recovery_cache(tmp_path):
    from app.modules.cms.pyq.p2_2.cache import RecoveryCache

    c = RecoveryCache(tmp_path)
    c.put("a", "b", "gemini", {"status": "RECOVERED", "stem": "s", "options": {}})
    assert c.get("a", "b", "gemini") is not None
