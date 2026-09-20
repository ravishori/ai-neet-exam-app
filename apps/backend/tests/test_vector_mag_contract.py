"""Vector-magnitude numerical contract — T6-F1 fix regression tests."""

from __future__ import annotations

import math

import pytest

from app.modules.cms.acquisition.physics_t6f1_bank import build_bank
from app.modules.cms.services.numerical_validation import classify_and_verify

# Exact historical payloads (pre mag_precision field) from T6-F1 forensic audit.
HISTORICAL_15_CALCS = [
    {"formula": "vector_mag", "ax": 10, "ay": 13, "mag": 16.4, "unit": "m"},
    {"formula": "vector_mag", "ax": 6, "ay": 13, "mag": 14.32, "unit": "m"},
    {"formula": "vector_mag", "ax": 4, "ay": 13, "mag": 13.6, "unit": "m"},
    {"formula": "vector_mag", "ax": 10, "ay": 13, "mag": 16.4, "unit": "m"},
    {"formula": "vector_mag", "ax": 8, "ay": 13, "mag": 15.26, "unit": "m"},
    {"formula": "vector_mag", "ax": 4, "ay": 13, "mag": 13.6, "unit": "m"},
    {"formula": "vector_mag", "ax": 12, "ay": 13, "mag": 17.69, "unit": "m"},
    {"formula": "vector_mag", "ax": 8, "ay": 13, "mag": 15.26, "unit": "m"},
    {"formula": "vector_mag", "ax": 6, "ay": 13, "mag": 14.32, "unit": "m"},
    {"formula": "vector_mag", "ax": 12, "ay": 13, "mag": 17.69, "unit": "m"},
    {"formula": "vector_mag", "ax": 10, "ay": 13, "mag": 16.4, "unit": "m"},
    {"formula": "vector_mag", "ax": 6, "ay": 13, "mag": 14.32, "unit": "m"},
    {"formula": "vector_mag", "ax": 4, "ay": 13, "mag": 13.6, "unit": "m"},
    {"formula": "vector_mag", "ax": 10, "ay": 13, "mag": 16.4, "unit": "m"},
    {"formula": "vector_mag", "ax": 8, "ay": 13, "mag": 15.26, "unit": "m"},
]


def test_vector_mag_exact_value_passes():
    """CASE A — integer exact magnitude (T6-D convention, no mag_precision)."""
    status, msg = classify_and_verify({"formula": "vector_mag", "ax": 3, "ay": 4, "mag": 5.0})
    assert status == "NUMERICAL_COMPLETE"
    assert msg == "vector mag ok"


def test_vector_mag_two_decimal_rounding_passes():
    """CASE B — 2-decimal display precision declared."""
    exact = math.hypot(3, 13)
    display = round(exact, 2)
    status, msg = classify_and_verify(
        {"formula": "vector_mag", "ax": 3, "ay": 13, "mag": display, "mag_precision": 2}
    )
    assert status == "NUMERICAL_COMPLETE"
    assert msg == "vector mag ok"
    assert display == 13.34


@pytest.mark.parametrize(
    "ax,ay",
    [(4, 13), (6, 13), (8, 13), (10, 13), (12, 13)],
)
def test_vector_mag_legitimate_rounding_pairs_pass(ax: int, ay: int):
    """CASE C — parametric pairs from historical failures."""
    exact = math.hypot(ax, ay)
    display = round(exact, 2)
    status, msg = classify_and_verify(
        {"formula": "vector_mag", "ax": ax, "ay": ay, "mag": display, "mag_precision": 2}
    )
    assert status == "NUMERICAL_COMPLETE", msg


def test_vector_mag_incorrect_value_fails():
    """CASE D — materially wrong magnitude."""
    status, msg = classify_and_verify(
        {"formula": "vector_mag", "ax": 3, "ay": 4, "mag": 6.0, "mag_precision": 2}
    )
    assert status == "NUMERICAL_INVALID"
    assert msg == "vector mag mismatch"


def test_vector_mag_incomplete_payload_fails():
    """CASE E — missing required keys."""
    status, msg = classify_and_verify({"formula": "vector_mag", "ax": 3, "ay": 4})
    assert status == "NUMERICAL_INCOMPLETE"
    assert "missing-keys" in msg


def test_vector_mag_invalid_payload_fails():
    """CASE F — non-numeric components."""
    status, msg = classify_and_verify(
        {"formula": "vector_mag", "ax": "x", "ay": 4, "mag": 5, "mag_precision": 2}
    )
    assert status == "NUMERICAL_INVALID"
    assert "invalid components" in msg


def test_vector_mag_precision_boundary_fails_one_centimeter_off():
    """CASE G — wrong by one display unit at 2 d.p."""
    exact = math.hypot(10, 13)
    display = round(exact, 2)
    wrong = display + 0.01
    status, msg = classify_and_verify(
        {"formula": "vector_mag", "ax": 10, "ay": 13, "mag": wrong, "mag_precision": 2}
    )
    assert status == "NUMERICAL_INVALID"
    assert msg == "vector mag mismatch"


def test_vector_mag_precision_boundary_passes_at_exact_round():
    """CASE G — boundary pass at declared 2 d.p."""
    exact = math.hypot(10, 13)
    display = round(exact, 2)
    status, msg = classify_and_verify(
        {"formula": "vector_mag", "ax": 10, "ay": 13, "mag": display, "mag_precision": 2}
    )
    assert status == "NUMERICAL_COMPLETE"


def test_vector_mag_without_precision_still_requires_exact_or_valid_round():
    """Undeclared precision: exact pass OR implicit 2 d.p. round pass only."""
    exact = math.hypot(10, 13)
    rounded = round(exact, 2)
    assert rounded != exact
    status_round, _ = classify_and_verify({"formula": "vector_mag", "ax": 10, "ay": 13, "mag": rounded})
    assert status_round == "NUMERICAL_COMPLETE"
    status_wrong, msg = classify_and_verify({"formula": "vector_mag", "ax": 10, "ay": 13, "mag": rounded + 0.01})
    assert status_wrong == "NUMERICAL_INVALID"
    assert msg == "vector mag mismatch"


def test_historical_15_exact_payloads_pass():
    """Replay exact pre-fix calc payloads — no DB, no mag_precision field."""
    assert len(HISTORICAL_15_CALCS) == 15
    for i, calc in enumerate(HISTORICAL_15_CALCS, start=1):
        assert "mag_precision" not in calc
        status, msg = classify_and_verify(calc)
        assert status == "NUMERICAL_COMPLETE", f"historical #{i}: {msg}"


def test_historical_15_regenerated_bank_passes():
    """Regenerated F1 bank includes explicit mag_precision."""
    bank = build_bank(1000)
    qids = [
        "t6f1-0162", "t6f1-0164", "t6f1-0165", "t6f1-0167", "t6f1-0168",
        "t6f1-0170", "t6f1-0171", "t6f1-0173", "t6f1-0174", "t6f1-0176",
        "t6f1-0177", "t6f1-0179", "t6f1-0180", "t6f1-0182", "t6f1-0183",
    ]
    by_id = {c.pilot_qid: c for c in bank}
    for qid in qids:
        calc = by_id[qid].calculation_check
        assert calc.get("mag_precision") == 2, qid
        status, msg = classify_and_verify(calc)
        assert status == "NUMERICAL_COMPLETE", f"{qid}: {msg}"


def test_f1_bank_vector_items_include_mag_precision():
    bank = build_bank(200)
    vector_items = [c for c in bank if c.concept_code == "vectors-in-plane-motion" and c.calculation_check]
    assert vector_items, "expected vector numerical items in first 200"
    for c in vector_items:
        calc = c.calculation_check or {}
        if calc.get("formula") == "vector_mag":
            assert calc.get("mag_precision") == 2
            status, _ = classify_and_verify(calc)
            assert status == "NUMERICAL_COMPLETE", c.pilot_qid
