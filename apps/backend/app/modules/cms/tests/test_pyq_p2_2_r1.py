"""P2.2-R1 validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.cms.pyq.p2_2.r1_validation.duplicates import classify_duplicates, near_duplicate
from app.modules.cms.pyq.p2_2.r1_validation.loader import EXPECTED_STRUCTURAL, is_structurally_valid, load_gemini_structural_candidates
from app.modules.cms.pyq.p2_2.r1_validation.pipeline import classify_quality, select_human_sample
from app.modules.cms.pyq.p2_2.r1_validation.validator import parse_validator_json

ROOT = Path(__file__).resolve().parents[6]
MCQ = ROOT / "docs/content-factory/PYQ_P2_2_MCQ_RESULTS.jsonl"


def test_input_population_exactly_326():
    if not MCQ.exists():
        pytest.skip("MCQ results not present")
    rows = load_gemini_structural_candidates(MCQ)
    assert len(rows) == EXPECTED_STRUCTURAL


def test_structural_filter_gemini_only():
    row = {
        "provider": "gemini",
        "question": "What is X?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
    }
    assert is_structurally_valid(row)
    row["provider"] = "openai"
    assert not is_structurally_valid(row)


def test_validator_json_contract():
    raw = json.dumps(
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
            "source_evidence": [],
            "confidence": 0.9,
        }
    )
    parsed = parse_validator_json(raw)
    assert parsed["overall"] == "PASS"


def test_duplicate_detection():
    a = {"mcq_id": "a", "question": "What is photosynthesis?"}
    b = {"mcq_id": "b", "question": "What is photosynthesis?"}
    d = classify_duplicates([a, b])
    assert d["b"] == "EXACT_DUPLICATE"


def test_near_duplicate():
    assert near_duplicate("What is the speed of light?", "What is the speed of light?", threshold=0.92)


def test_quality_grade_reject_on_fail():
    grade, failure = classify_quality(
        validator={"overall": "FAIL", "ambiguity": "FAIL", "issues": ["multiple correct"]},
        duplicate_class="NO_DUPLICATE",
        validator_available=True,
    )
    assert grade == "D"
    assert failure in ("AMBIGUOUS", "MULTIPLE_CORRECT", "WRONG_ANSWER")


def test_quality_inconclusive_without_provider():
    grade, _ = classify_quality(validator=None, duplicate_class="NO_DUPLICATE", validator_available=False)
    assert grade == "I"


def test_human_sample_size():
    candidates = [
        {
            "mcq_id": f"m{i}",
            "subject": ["PHYSICS", "CHEMISTRY", "BIOLOGY"][i % 3],
            "chapter": i % 5,
            "difficulty": ["EASY", "MEDIUM", "HARD"][i % 3],
            "question_type": "conceptual",
            "question": f"Q{i}?",
            "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
        }
        for i in range(326)
    ]
    sample = select_human_sample(candidates, seed=1, target=100)
    assert len(sample) == 100


def test_production_db_protection():
    import app.modules.cms.pyq.p2_2.r1_validation.pipeline as pl

    src = open(pl.__file__, encoding="utf-8").read()
    assert "AsyncSession" not in src
    assert "INSERT" not in src.upper()


def test_malformed_validator_json():
    with pytest.raises(json.JSONDecodeError):
        parse_validator_json("not-json")
