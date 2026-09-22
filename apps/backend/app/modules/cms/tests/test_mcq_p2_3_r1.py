"""P2.3-R1 provider routing repair tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.cms.mcq.p2_3.provider_routing import (
    GENERATION_PROVIDERS,
    assert_cross_provider,
    cross_validator_for,
    is_same_provider_validation,
    resolve_validator_bundle,
)
from app.modules.cms.mcq.p2_3.r1.pipeline import (
    build_r1_row,
    compute_metrics,
    effective_validation_status,
    is_same_provider_blocked,
    r1_staging_paths,
)
from app.modules.cms.mcq.p2_3.r1.taxonomy import build_qa_failure_taxonomy, classify_qa_failure
from app.modules.cms.mcq.p2_3.schemas import McqRecord
from app.modules.cms.mcq.p2_3.validator import validation_cost_usd

pytestmark = pytest.mark.asyncio(loop_scope="session")

ROOT = Path(__file__).resolve().parents[6]


def _rec(**kwargs) -> McqRecord:
    base = McqRecord(
        question_id="p3-mcq-0001-test",
        run_id="r",
        batch_id="b",
        slot_index=0,
        concept_id="c",
        subject="BIOLOGY",
        class_level="11",
        chapter=1,
        topic="t",
        question_type="factual",
        difficulty="EASY",
        source_id="s",
        source_locator="loc",
        source_file="f.pdf",
        source_page=1,
        source_excerpt_hash="h",
        question="What is the cell?",
        options={"A": "1", "B": "2", "C": "3", "D": "4"},
        correct_option="A",
        explanation="Cell is the basic unit of life per NCERT.",
        generation_provider="gemini",
        qa_status="PASS",
        generation_status="GENERATED",
        source_support="NCERT-SUPPORTED",
    )
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def test_cross_provider_routing_map():
    assert cross_validator_for("gemini") == "openai"
    assert cross_validator_for("openai") == "gemini"
    assert cross_validator_for("anthropic") == "openai"


def test_same_provider_validation_rejected():
    assert is_same_provider_validation("openai", "openai")
    assert not is_same_provider_validation("gemini", "openai")
    with pytest.raises(ValueError, match="Same-provider"):
        assert_cross_provider("gemini", "gemini")


def test_anthropic_disabled_in_generation_providers():
    assert "anthropic" not in GENERATION_PROVIDERS


def test_same_provider_blocked_detection():
    row = {"errors": ["independent_validation_blocked:same_provider"]}
    assert is_same_provider_blocked(row)


def test_build_r1_row_preserves_original():
    orig = {
        "question_id": "p3-mcq-0001-x",
        "validation_status": "INCONCLUSIVE",
        "validator_provider": "",
        "question": "stem",
        "generation_provider": "openai",
    }
    r1 = build_r1_row(orig)
    assert r1["original_validation_status"] == "INCONCLUSIVE"
    assert r1["question"] == "stem"
    assert r1["r1_validation_status"] is None


def test_effective_status_prefers_r1():
    row = {"validation_status": "INCONCLUSIVE", "r1_validation_status": "READY"}
    assert effective_validation_status(row) == "READY"


def test_compute_metrics_rates_on_qa_pass_only():
    merged = [
        {"qa_status": "PASS", "validation_status": "READY", "generation_provider": "gemini", "validator_provider": "openai"},
        {"qa_status": "PASS", "r1_validation_status": "REJECT", "generation_provider": "openai", "r1_validator_provider": "gemini"},
        {"qa_status": "REJECT"},
    ]
    m = compute_metrics(merged, qa_pass_base=2)
    assert m["qa_pass"] == 2
    assert m["independent_validation_rate"] == 1.0
    assert m["ai_ready_rate"] == 0.5


def test_qa_failure_taxonomy_provider_failure():
    rec = {"qa_status": "REJECT", "generation_status": "FAILED", "errors": ["Provider billing/credits blocked"]}
    c = classify_qa_failure(rec)
    assert c["bucket"] == "provider_failure"
    assert c["origin"] == "MODEL_GENERATION_FAILURE"


def test_r1_staging_not_production():
    paths = r1_staging_paths(ROOT)
    assert "p2_3_r1" in str(paths["base"]).replace("\\", "/")


def test_validation_cost_estimates_when_zero():
    meta = {"cost_usd": 0.0, "prompt_tokens": 1000, "completion_tokens": 200, "model": "gpt-4o-mini"}
    cost = validation_cost_usd(meta, provider_name="openai", model="gpt-4o-mini")
    assert cost > 0


@pytest.mark.asyncio
async def test_revalidation_without_regeneration():
    from app.modules.cms.mcq.p2_3.validator import validate_record

    rec = _rec(generation_provider="openai")
    mock_provider = AsyncMock()
    mock_provider.generate_request = AsyncMock(
        return_value=MagicMock(
            text=json.dumps(
                {
                    "overall": "PASS",
                    "stem": "PASS",
                    "options": {"A": "PASS", "B": "PASS", "C": "PASS", "D": "PASS"},
                    "correct_answer": "PASS",
                    "explanation": "PASS",
                    "ncert_support": "PASS",
                    "ambiguity": "PASS",
                    "duplicate_risk": "PASS",
                    "difficulty": "PASS",
                    "ncert_support_class": "DIRECT_NCERT_SUPPORT",
                    "issues": [],
                    "confidence": 0.9,
                }
            ),
            model="gemini-3.6-flash",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.0,
        )
    )
    budget = MagicMock()
    budget.check = MagicMock()
    budget.record = MagicMock()
    original_q = rec.question
    with patch("app.modules.cms.mcq.p2_3.validator.validate_one", new_callable=AsyncMock) as vo:
        vo.return_value = (
            {"overall": "PASS", "ncert_support_class": "DIRECT_NCERT_SUPPORT", "issues": [], "confidence": 0.9},
            0.001,
            {"model": "gemini-3.6-flash", "cost_usd": 0.001, "prompt_tokens": 100, "completion_tokens": 50},
        )
        out = await validate_record(
            rec,
            provider_inst=mock_provider,
            provider_name="gemini",
            model="gemini-3.6-flash",
            ncert_excerpt="excerpt",
            budget=budget,
        )
    assert out.question == original_q
    assert out.validation_status == "READY"


def test_idempotent_r1_snapshot(tmp_path: Path):
    from app.modules.cms.mcq.p2_3.r1.pipeline import load_jsonl_dicts, save_jsonl_dicts

    p = tmp_path / "snap.jsonl"
    rows = [{"question_id": "a", "validation_status": "INCONCLUSIVE"}]
    save_jsonl_dicts(p, rows)
    assert len(load_jsonl_dicts(p)) == 1
    save_jsonl_dicts(p, rows)
    assert len(load_jsonl_dicts(p)) == 1
