"""Unit/regression tests for the 5K driver's subject-quota round-robin
selector — the fix for the Botany-only generation defect (2026-09-18 audit).

Root cause being regression-tested: the superseded driver grouped blueprints
by concept_id and interleaved one-per-concept-per-lap. For any subject with
a 1:1 concept:blueprint ratio (Botany, Chemistry, Zoology all had this),
that interleave degenerated into the original subject-alphabetical fetch
order, so Botany (sorts first) could consume an entire wall-clock budget
before Chemistry/Physics/Zoology were ever reached.
"""

from __future__ import annotations

import pytest

from app.modules.cms.services.subject_quota_round_robin import (
    CANONICAL_QUEUE_ORDER,
    build_queues,
    queue_label,
    round_robin_order,
)


def test_queue_label_normalizes_subject_and_class():
    assert queue_label("botany", "11") == "Botany-11"
    assert queue_label("PHYSICS", 12) == "Physics-12"
    assert queue_label("  Zoology  ", "11") == "Zoology-11"


def test_round_robin_visits_every_non_empty_queue_before_any_repeats():
    """Core regression: given queues sized like the real prod-5k pool
    (Botany 1:1 ratio == 95 items, Physics skewed larger == 379 items),
    the FIRST lap must touch every non-empty queue exactly once — no queue
    may be revisited before all others have had a turn."""
    queues = {
        "Botany-11": list(range(52)),
        "Botany-12": list(range(43)),
        "Chemistry-11": list(range(28)),
        "Chemistry-12": list(range(64)),
        "Physics-11": list(range(54)),
        "Physics-12": list(range(325)),
        "Zoology-11": list(range(38)),
        "Zoology-12": list(range(16)),
    }
    order = round_robin_order(queues)

    first_lap = order[:8]
    first_lap_labels = [r.label for r in first_lap]
    assert set(first_lap_labels) == set(queues.keys())
    assert len(first_lap_labels) == len(set(first_lap_labels))  # no repeats in lap 1


def test_round_robin_reaches_every_subject_within_first_32_selections():
    """Direct regression for the observed defect: the old driver's first 46
    calls (an entire 10-hour run) never left Botany. The new selector must
    cover all 4 subjects well within the first 32 selections, matching the
    dry-run preview size used operationally."""
    queues = {
        "Botany-11": list(range(52)),
        "Botany-12": list(range(43)),
        "Chemistry-11": list(range(28)),
        "Chemistry-12": list(range(64)),
        "Physics-11": list(range(54)),
        "Physics-12": list(range(325)),
        "Zoology-11": list(range(38)),
        "Zoology-12": list(range(16)),
    }
    order = round_robin_order(queues)
    first_32_subjects = {r.label.split("-")[0] for r in order[:32]}
    assert first_32_subjects == {"Physics", "Chemistry", "Botany", "Zoology"}


def test_round_robin_skips_exhausted_queues_without_stalling():
    queues = {
        "Physics-11": [1, 2, 3],
        "Physics-12": [10],
        "Chemistry-11": [],
        "Botany-11": [100, 101],
    }
    order = round_robin_order(queues)
    labels = [r.label for r in order]
    assert "Chemistry-11" not in labels  # empty queue contributes nothing
    assert len(order) == 6  # 3 + 1 + 0 + 2
    # Physics-12's single item must appear in lap 1 (before Physics-11's 2nd item).
    physics12_index = labels.index("Physics-12")
    physics11_second_index = [i for i, l in enumerate(labels) if l == "Physics-11"][1]
    assert physics12_index < physics11_second_index


def test_round_robin_preserves_in_queue_order():
    queues = {"Physics-11": ["a", "b", "c"], "Botany-11": ["x"]}
    order = round_robin_order(queues)
    physics_items = [r.item for r in order if r.label == "Physics-11"]
    assert physics_items == ["a", "b", "c"]


def test_round_robin_empty_input_returns_empty_list():
    assert round_robin_order({}) == []


def test_round_robin_all_empty_queues_returns_empty_list():
    assert round_robin_order({"Physics-11": [], "Botany-12": []}) == []


def test_round_robin_unknown_label_appended_after_canonical_order():
    queues = {"Physics-11": [1], "Sanskrit-11": [99]}
    order = round_robin_order(queues)
    labels = [r.label for r in order]
    assert labels[0] == "Physics-11"
    assert "Sanskrit-11" in labels


def test_build_queues_groups_rows_by_canonical_label():
    rows = [
        {"subject": "Botany", "class_level": "11", "id": "b1"},
        {"subject": "Physics", "class_level": "12", "id": "p1"},
        {"subject": "Botany", "class_level": "11", "id": "b2"},
    ]
    queues = build_queues(rows)
    assert [r["id"] for r in queues["Botany-11"]] == ["b1", "b2"]
    assert [r["id"] for r in queues["Physics-12"]] == ["p1"]


def test_canonical_order_covers_all_eight_neet_subject_class_cells():
    subjects = {label.split("-")[0] for label in CANONICAL_QUEUE_ORDER}
    classes = {label.split("-")[1] for label in CANONICAL_QUEUE_ORDER}
    assert subjects == {"Physics", "Chemistry", "Botany", "Zoology"}
    assert classes == {"11", "12"}
    assert len(CANONICAL_QUEUE_ORDER) == 8


@pytest.mark.parametrize(
    "sizes",
    [
        {"Physics-11": 1, "Physics-12": 1, "Chemistry-11": 1, "Chemistry-12": 1,
         "Botany-11": 1, "Botany-12": 1, "Zoology-11": 1, "Zoology-12": 1},
        {"Physics-12": 500, "Zoology-12": 1},
        {"Botany-11": 95, "Chemistry-11": 92, "Zoology-11": 54},  # the exact 1:1-ratio defect shape
    ],
)
def test_round_robin_total_item_count_is_conserved(sizes):
    queues = {label: list(range(n)) for label, n in sizes.items()}
    order = round_robin_order(queues)
    assert len(order) == sum(sizes.values())
