"""P2.3 pre-human gold sample audit tests."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import pytest

from app.modules.cms.mcq.p2_3.pre_human_audit.auditors import (
    audit_assertion_reason,
    audit_duplicates,
    audit_ncert,
    audit_one_row,
    audit_options,
    audit_question_type,
    audit_stem,
    score_priority_and_verdict,
)
from app.modules.cms.mcq.p2_3.pre_human_audit.loader import (
    HUMAN_REVIEW_COLUMNS,
    load_gold_sample_csv,
    verify_human_fields_unchanged,
)
from app.modules.cms.mcq.p2_3.pre_human_audit.numerical import audit_numerical
from app.modules.cms.mcq.p2_3.pre_human_audit.pipeline import run_pre_human_audit
from app.modules.cms.mcq.p2_3.pre_human_audit.schemas import empty_audit_record
from app.modules.cms.mcq.p2_3.pre_human_audit.report import build_summary

ROOT = Path(__file__).resolve().parents[6]
GOLD = ROOT / "data/staging/mcq/p2_3/human_gold_sample.csv"


def _row(**kwargs) -> dict:
    base = {
        "question_id": "p3-mcq-test-0001",
        "subject": "PHYSICS",
        "class": "11",
        "chapter": "3",
        "topic": "kinematics",
        "provider": "gemini",
        "difficulty": "MEDIUM",
        "question_type": "numerical",
        "question": "The coordinates are x(t)=3t^2 and y(t)=4t^2. Magnitude of velocity at t=1 s?",
        "option_A": "5 unit",
        "option_B": "7 unit",
        "option_C": "10 unit",
        "option_D": "14 unit",
        "proposed_answer": "C",
        "NCERT_source": "Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-3.pdf",
        "validator_verdict": "READY",
        **{c: "PENDING" for c in HUMAN_REVIEW_COLUMNS},
        "reviewer_notes": "",
    }
    base.update(kwargs)
    return base


def test_wrong_proposed_answer_numerical():
    row = _row(proposed_answer="A")
    result = audit_numerical(row)
    assert result["preaudit_calculation_check"] == "FAIL"
    assert result["preaudit_answer_check"] == "WRONG"


def test_numerical_recalculation_pass():
    row = _row(proposed_answer="C")
    result = audit_numerical(row)
    assert result["preaudit_calculation_check"] == "PASS"
    assert result["preaudit_calculated_answer"] == "C"


def test_multiple_correct_duplicate_options():
    row = _row(
        option_A="same",
        option_B="same",
        option_C="other",
        option_D="another",
        question_type="factual",
    )
    result = audit_options(row)
    assert result["preaudit_option_quality"] == "BAD"


def test_assertion_reason_position_vector_trap():
    row = _row(
        question_type="assertion_reasoning",
        question=(
            "Assertion A: A position vector in a plane can be expressed using x and y coordinates.\n"
            "Reason R: Displacement is the difference between position vectors at two different times.\n"
            "Choose the correct option."
        ),
        option_A="Both true and Reason explains Assertion",
        option_B="Both true but Reason does not explain Assertion",
        option_C="Assertion true, Reason false",
        option_D="Assertion false, Reason true",
        proposed_answer="A",
    )
    result = audit_assertion_reason(row)
    assert "reason_explains_assertion=FALSE" in result["preaudit_assertion_reason_check"]


def test_unsupported_ncert_low_overlap(tmp_path: Path):
    row = _row(
        question="Quantum chromodynamics color confinement at Planck energy?",
        NCERT_source="missing/file.pdf",
        _source_page="1",
    )
    result = audit_ncert(row, study_root=tmp_path)
    assert result["preaudit_ncert_support"] in ("INCORRECT_CITATION", "NOT_VERIFIABLE")


def test_incorrect_ncert_citation(tmp_path: Path):
    row = _row(NCERT_source="no/such/book.pdf", _source_page="1")
    result = audit_ncert(row, study_root=tmp_path)
    assert result["preaudit_ncert_support"] == "INCORRECT_CITATION"


def test_weak_distractor_length_clue():
    row = _row(
        option_A="A",
        option_B="B",
        option_C="C",
        option_D="A very long distractor with excessive detail that may clue the answer",
        question_type="factual",
    )
    result = audit_options(row)
    assert result["preaudit_option_quality"] in ("ACCEPTABLE", "WEAK", "BAD")


def test_duplicate_detection_exact():
    a = _row(question_id="a", question="What is photosynthesis in plants?")
    b = _row(question_id="b", question="What is photosynthesis in plants?")
    result = audit_duplicates(b, sample_stems={"a": a["question"]}, corpus_stems={})
    assert result["preaudit_duplicate_status"] == "EXACT_DUPLICATE"


def test_question_type_mismatch():
    row = _row(
        question_type="factual",
        question="Match Column I with Column II and select the correct option.",
    )
    result = audit_question_type(row)
    assert result["preaudit_question_type_check"] == "TYPE_MISMATCH"


def test_neet_suitability_unsuitable_bad_options():
    audit = empty_audit_record(_row())
    audit["preaudit_option_quality"] = "BAD"
    audit["preaudit_stem_severity"] = "NONE"
    audit["preaudit_ncert_support"] = "DIRECT"
    audit["preaudit_question_type_check"] = "TYPE_CORRECT"
    from app.modules.cms.mcq.p2_3.pre_human_audit.auditors import audit_neet_suitability

    result = audit_neet_suitability(_row(), audit)
    assert result["preaudit_neet_suitability"] == "UNSUITABLE"


def test_inconclusive_not_automatic_pass():
    audit = empty_audit_record(_row())
    audit["preaudit_answer_check"] = "INCONCLUSIVE"
    audit["preaudit_answer_confidence"] = 0.2
    scored = score_priority_and_verdict(audit)
    assert scored["preaudit_verdict"] in ("PREAUDIT_REVIEW", "PREAUDIT_FLAGGED")
    assert scored["preaudit_verdict"] != "PREAUDIT_LIKELY_PASS"


def test_preserves_human_fields():
    row = _row()
    audit = audit_one_row(row, sample_stems={}, corpus_stems={}, study_root=Path("/nonexistent"))
    for col in HUMAN_REVIEW_COLUMNS:
        assert audit[col] == row[col]


def test_malformed_missing_option():
    row = _row(option_D="")
    result = audit_options(row)
    assert result["preaudit_option_quality"] == "BAD"


def test_stem_ambiguity_major():
    row = _row(question="Which?")
    result = audit_stem(row)
    assert result["preaudit_stem_severity"] == "MAJOR"


def test_integration_audit_on_real_sample():
    if not GOLD.exists():
        pytest.skip("gold sample missing")
    before = load_gold_sample_csv(GOLD)
    r1 = run_pre_human_audit(root=ROOT)
    r2 = run_pre_human_audit(root=ROOT)
    assert r1["executive_summary"] == r2["executive_summary"]
    assert r1["executive_summary"]["total_audited"] == 100
    assert r1["production_db_writes"] == 0
    after = load_gold_sample_csv(GOLD)
    verify_human_fields_unchanged(before, after)


def test_stable_output_ordering():
    records = [
        {**empty_audit_record(_row(question_id="z")), "preaudit_priority": "LOW"},
        {**empty_audit_record(_row(question_id="a")), "preaudit_priority": "CRITICAL"},
    ]
    summary = build_summary(records, gold_checksum="x")
    queue = summary["human_review_queue"]
    if queue:
        assert queue[0]["preaudit_priority"] == "CRITICAL"


def test_missing_ncert_source():
    row = _row(NCERT_source="")
    result = audit_ncert(row, study_root=Path("/tmp"))
    assert result["preaudit_ncert_support"] == "NOT_VERIFIABLE"
