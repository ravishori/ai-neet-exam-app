"""Focused unit tests for the deterministic largest-remainder allocator.

Pure math — no DB, no fixtures. Covers happy paths, edge fractions,
invariants, and the validation contract (never trust client totals).
"""

from __future__ import annotations

import pytest

from app.modules.assessment.services.allocation import (
    Allocation,
    WeightageError,
    allocate_by_weightage,
)


# --------------------------------------------------------------------- happy paths


def test_30_questions_40_30_30():
    result = allocate_by_weightage(30, {"Physics": 40, "Chemistry": 30, "Biology": 30})
    assert isinstance(result, Allocation)
    assert result.quotas == {"Physics": 12, "Chemistry": 9, "Biology": 9}
    assert sum(result.quotas.values()) == 30


def test_10_questions_fractional_distribution_deterministic_and_sums_to_total():
    # 33.33/33.33/33.34 → exact quotas 3.333/3.333/3.334, floors 3/3/3,
    # remaining 1 goes to the largest remainder (Biology 0.334).
    result = allocate_by_weightage(10, {"Physics": 33.33, "Chemistry": 33.33, "Biology": 33.34})
    assert result.quotas == {"Physics": 3, "Chemistry": 3, "Biology": 4}
    assert sum(result.quotas.values()) == 10

    # Deterministic: same call → same answer.
    again = allocate_by_weightage(10, {"Physics": 33.33, "Chemistry": 33.33, "Biology": 33.34})
    assert again.quotas == result.quotas


def test_10_questions_equal_thirds_ties_break_by_insertion_order():
    # 33.34/33.33/33.33 — Physics has the largest remainder, gets the +1.
    result = allocate_by_weightage(10, {"Physics": 33.34, "Chemistry": 33.33, "Biology": 33.33})
    assert result.quotas == {"Physics": 4, "Chemistry": 3, "Biology": 3}


def test_50_questions_official_neet_split_25_25_50():
    result = allocate_by_weightage(50, {"Physics": 25, "Chemistry": 25, "Biology": 50})
    assert result.quotas == {"Physics": 13, "Chemistry": 12, "Biology": 25} or \
           result.quotas == {"Physics": 12, "Chemistry": 13, "Biology": 25}
    # Both perfectly-tied variants preserve the total; assert that.
    assert sum(result.quotas.values()) == 50
    # Ties resolve by earlier-insertion-index, so Physics wins the extra unit.
    assert result.quotas == {"Physics": 13, "Chemistry": 12, "Biology": 25}


def test_100_questions_25_25_50_exact_integers():
    result = allocate_by_weightage(100, {"Physics": 25, "Chemistry": 25, "Biology": 50})
    assert result.quotas == {"Physics": 25, "Chemistry": 25, "Biology": 50}
    assert sum(result.quotas.values()) == 100


def test_final_sum_invariant_across_many_sizes():
    for total in (1, 7, 10, 30, 50, 100, 180, 999):
        r = allocate_by_weightage(total, {"Physics": 33.33, "Chemistry": 33.33, "Biology": 33.34})
        assert sum(r.quotas.values()) == total, f"failed for total={total}"


def test_preserves_input_key_order():
    r = allocate_by_weightage(30, {"Biology": 30, "Physics": 40, "Chemistry": 30})
    assert list(r.quotas.keys()) == ["Biology", "Physics", "Chemistry"]


def test_zero_weight_gets_zero_allocation():
    r = allocate_by_weightage(10, {"Physics": 50, "Chemistry": 50, "Biology": 0})
    assert r.quotas == {"Physics": 5, "Chemistry": 5, "Biology": 0}


# -------------------------------------------------------------- validation errors


def test_invalid_totals_rejected_at_boundary():
    # Above tolerance in both directions.
    for bad in ({"a": 40, "b": 30, "c": 29}, {"a": 40, "b": 30, "c": 31}, {"a": 60, "b": 60}):
        with pytest.raises(WeightageError):
            allocate_by_weightage(10, bad)


def test_within_tolerance_totals_accepted():
    # 33.33 + 33.33 + 33.34 = 100.00; and 33.333 + 33.333 + 33.334 = 100.00
    allocate_by_weightage(10, {"a": 33.33, "b": 33.33, "c": 33.34})
    allocate_by_weightage(10, {"a": 33.333, "b": 33.333, "c": 33.334})


def test_negative_weight_rejected():
    with pytest.raises(WeightageError):
        allocate_by_weightage(10, {"Physics": 110, "Chemistry": -5, "Biology": -5})
    with pytest.raises(WeightageError):
        allocate_by_weightage(10, {"Physics": 50, "Chemistry": 55, "Biology": -5})


def test_over_100_single_key_rejected():
    with pytest.raises(WeightageError):
        allocate_by_weightage(10, {"Physics": 101, "Chemistry": 0, "Biology": 0})


def test_zero_or_negative_total_rejected():
    for bad in (0, -1, -100):
        with pytest.raises(WeightageError):
            allocate_by_weightage(bad, {"Physics": 100})


def test_non_int_total_rejected():
    with pytest.raises(WeightageError):
        allocate_by_weightage(10.5, {"Physics": 100})  # type: ignore[arg-type]
    with pytest.raises(WeightageError):
        allocate_by_weightage(True, {"Physics": 100})  # type: ignore[arg-type]


def test_empty_or_malformed_weightages_rejected():
    with pytest.raises(WeightageError):
        allocate_by_weightage(10, {})
    with pytest.raises(WeightageError):
        allocate_by_weightage(10, {"": 100})
    with pytest.raises(WeightageError):
        allocate_by_weightage(10, {"Physics": float("nan"), "Chemistry": 50, "Biology": 50})
    with pytest.raises(WeightageError):
        allocate_by_weightage(10, {"Physics": float("inf")})


def test_client_total_never_trusted():
    """Even if the caller believes their numbers are valid, the allocator
    re-validates the sum. This is the "never trust client totals" contract."""
    with pytest.raises(WeightageError):
        allocate_by_weightage(10, {"Physics": 33, "Chemistry": 33, "Biology": 33})  # sums to 99
