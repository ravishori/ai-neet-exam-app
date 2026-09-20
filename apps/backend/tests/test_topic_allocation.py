"""Task D coverage — unit tests for allocate_topics_within_subject.

Pure. No DB, no fixtures beyond ordinary Python. Covers the eleven
behaviours listed in the task brief plus the validation contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.assessment.services.topic_allocation import (
    DEFAULT_CONFIG,
    SubjectTopicAllocation,
    TopicAllocationConfig,
    TopicAllocationError,
    TopicInput,
    allocate_topics_within_subject,
)


def _ids(prefix: str, n: int) -> tuple[str, ...]:
    return tuple(f"{prefix}-{i:03d}" for i in range(n))


# --------------------------------------------------------- behaviours


def test_weak_topics_receive_higher_selection_priority():
    """Two topics, equal inventory (100 each), WEAK vs NEUTRAL: WEAK gets more."""
    result = allocate_topics_within_subject(
        subject_quota=30,
        topics=[
            TopicInput("weak", "WEAK", _ids("w", 100)),
            TopicInput("neutral", "NEUTRAL", _ids("n", 100)),
        ],
    )
    weak = next(q for q in result.per_topic if q.topic_id == "weak")
    neutral = next(q for q in result.per_topic if q.topic_id == "neutral")
    assert weak.allocated > neutral.allocated
    assert weak.allocated + neutral.allocated == 30


def test_neutral_topics_remain_eligible():
    """NEUTRAL topics always get a non-zero share when quota + inventory permit."""
    result = allocate_topics_within_subject(
        subject_quota=15,
        topics=[
            TopicInput("weak", "WEAK", _ids("w", 20)),
            TopicInput("neutral-1", "NEUTRAL", _ids("n1", 20)),
            TopicInput("neutral-2", "NEUTRAL", _ids("n2", 20)),
        ],
    )
    for q in result.per_topic:
        assert q.allocated > 0, f"{q.topic_id}: expected non-zero, got {q.allocated}"


def test_strong_topics_receive_floor_exposure():
    """With strong_floor_pct=10, on a 30-quota paper STRONG collectively must get ≥3."""
    result = allocate_topics_within_subject(
        subject_quota=30,
        topics=[
            TopicInput("weak", "WEAK", _ids("w", 100)),
            TopicInput("neutral", "NEUTRAL", _ids("n", 100)),
            TopicInput("strong", "STRONG", _ids("s", 100)),
        ],
        config=TopicAllocationConfig(strong_floor_pct=10.0),
    )
    strong = next(q for q in result.per_topic if q.topic_id == "strong")
    assert strong.allocated >= 3


def test_strong_floor_respects_zero_capacity():
    """If STRONG has no inventory, the floor cannot fire and the caller doesn't crash."""
    result = allocate_topics_within_subject(
        subject_quota=10,
        topics=[
            TopicInput("weak", "WEAK", _ids("w", 20)),
            TopicInput("strong", "STRONG", ()),
        ],
    )
    strong = next(q for q in result.per_topic if q.topic_id == "strong")
    assert strong.allocated == 0
    assert result.subject_quota_fulfilled == 10


def test_allocation_respects_subject_quota_sum():
    """Sum(allocated) == min(quota, total_available)."""
    result = allocate_topics_within_subject(
        subject_quota=50,
        topics=[
            TopicInput("weak", "WEAK", _ids("w", 20)),
            TopicInput("neutral", "NEUTRAL", _ids("n", 20)),
            TopicInput("strong", "STRONG", _ids("s", 20)),
        ],
    )
    assert result.subject_quota_fulfilled == 50
    assert sum(q.allocated for q in result.per_topic) == 50


def test_never_exceeds_available_inventory_per_topic_or_total():
    """No topic may be allocated more than its own available_ids length; the
    total also caps at global inventory when quota > pool."""
    result = allocate_topics_within_subject(
        subject_quota=100,
        topics=[
            TopicInput("small-weak", "WEAK", _ids("sw", 5)),
            TopicInput("neutral", "NEUTRAL", _ids("n", 10)),
        ],
    )
    per = {q.topic_id: q for q in result.per_topic}
    assert per["small-weak"].allocated <= 5
    assert per["neutral"].allocated <= 10
    assert result.subject_quota_fulfilled == 15  # capped at total inventory


def test_deterministic_repeat_identical_output():
    """Repeat with the same inputs → identical picked_ids sequence (including order)."""
    topics = [
        TopicInput("weak", "WEAK", _ids("w", 30)),
        TopicInput("neutral", "NEUTRAL", _ids("n", 30)),
        TopicInput("strong", "STRONG", _ids("s", 30)),
    ]
    a = allocate_topics_within_subject(subject_quota=27, topics=topics)
    b = allocate_topics_within_subject(subject_quota=27, topics=topics)
    c = allocate_topics_within_subject(subject_quota=27, topics=topics)
    assert a.picked_ids == b.picked_ids == c.picked_ids
    # And the per-topic layout too.
    assert tuple((q.topic_id, q.allocated) for q in a.per_topic) == tuple(
        (q.topic_id, q.allocated) for q in b.per_topic
    )


def test_largest_remainder_tie_breaks_by_caller_insertion_order():
    """With three equal-weight NEUTRAL topics and 10 questions each, quota 4:
    floors give 1 to each; the extra unit goes to the earliest topic."""
    result = allocate_topics_within_subject(
        subject_quota=4,
        topics=[
            TopicInput("first", "NEUTRAL", _ids("f", 10)),
            TopicInput("second", "NEUTRAL", _ids("s", 10)),
            TopicInput("third", "NEUTRAL", _ids("t", 10)),
        ],
    )
    per = {q.topic_id: q.allocated for q in result.per_topic}
    assert per == {"first": 2, "second": 1, "third": 1}


def test_unseen_questions_preferred_when_last_seen_data_provided():
    """With last_seen_by_id populated, unseen ids sort first, then oldest."""
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    available = ("q-recent", "q-old", "q-unseen-a", "q-unseen-b")
    topic = TopicInput(
        topic_id="t",
        preference="WEAK",
        available_ids=available,
        last_seen_by_id={
            "q-recent": now,
            "q-old": now - timedelta(days=30),
        },
    )
    result = allocate_topics_within_subject(subject_quota=3, topics=[topic])
    picked = result.per_topic[0].picked_ids
    # The unseen pair should come before either of the seen ids.
    assert "q-recent" not in picked
    # Both unseen ids must be present; the oldest-seen fills the last slot.
    assert set(picked) == {"q-unseen-a", "q-unseen-b", "q-old"}


def test_no_duplicate_question_ids_returned():
    """picked_ids has no repeats and every id came from some topic's inventory."""
    topics = [
        TopicInput("a", "WEAK", _ids("a", 5)),
        TopicInput("b", "NEUTRAL", _ids("b", 5)),
        TopicInput("c", "STRONG", _ids("c", 5)),
    ]
    result = allocate_topics_within_subject(subject_quota=10, topics=topics)
    assert len(result.picked_ids) == len(set(result.picked_ids))
    known = set().union(*(set(t.available_ids) for t in topics))
    assert set(result.picked_ids).issubset(known)


def test_duplicate_ids_across_topics_rejected_at_input():
    """Same question id can't appear in two topics' available_ids."""
    with pytest.raises(TopicAllocationError):
        allocate_topics_within_subject(
            subject_quota=2,
            topics=[
                TopicInput("a", "NEUTRAL", ("shared-1", "a-1")),
                TopicInput("b", "NEUTRAL", ("shared-1", "b-1")),
            ],
        )


def test_insufficient_weak_inventory_redistributes_safely():
    """WEAK topic with 2 questions receives at most 2; the remainder goes to
    the other topics without violating the total-quota invariant."""
    result = allocate_topics_within_subject(
        subject_quota=10,
        topics=[
            TopicInput("weak-small", "WEAK", _ids("ws", 2)),
            TopicInput("neutral-plenty", "NEUTRAL", _ids("np", 50)),
        ],
    )
    per = {q.topic_id: q for q in result.per_topic}
    assert per["weak-small"].allocated == 2  # never exceeds inventory
    assert per["neutral-plenty"].allocated == 8
    assert result.subject_quota_fulfilled == 10


def test_empty_inventory_returns_zero_fulfilled_without_raising():
    """No eligible questions across any topic: return a valid, zero-fill result."""
    result = allocate_topics_within_subject(
        subject_quota=15,
        topics=[
            TopicInput("a", "WEAK", ()),
            TopicInput("b", "STRONG", ()),
        ],
    )
    assert isinstance(result, SubjectTopicAllocation)
    assert result.subject_quota_fulfilled == 0
    assert result.picked_ids == ()
    for q in result.per_topic:
        assert q.allocated == 0


def test_topics_list_can_be_empty_topics_list_gives_zero():
    """No topics at all → zero fulfilment. Still no crash."""
    result = allocate_topics_within_subject(subject_quota=10, topics=[])
    assert result.subject_quota_fulfilled == 0
    assert result.picked_ids == ()


def test_validation_rejects_negative_quota_and_bad_preference():
    with pytest.raises(TopicAllocationError):
        allocate_topics_within_subject(-1, [TopicInput("a", "WEAK", ("q1",))])
    with pytest.raises(TopicAllocationError):
        allocate_topics_within_subject(
            5, [TopicInput("a", "UNKNOWN", ("q1", "q2", "q3", "q4", "q5"))]
        )
    with pytest.raises(TopicAllocationError):
        allocate_topics_within_subject(
            5,
            [
                TopicInput("dup", "WEAK", ("a1", "a2")),
                TopicInput("dup", "NEUTRAL", ("b1", "b2")),
            ],
        )


def test_default_config_matches_documented_multipliers():
    """Guards against silent config drift — matches the module doc."""
    assert DEFAULT_CONFIG.weak_multiplier == 2.0
    assert DEFAULT_CONFIG.neutral_multiplier == 1.0
    assert DEFAULT_CONFIG.strong_multiplier == 0.5
    assert DEFAULT_CONFIG.strong_floor_pct == 10.0
