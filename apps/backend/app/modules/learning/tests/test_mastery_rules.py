from datetime import UTC, datetime, timedelta

from app.modules.learning.services.mastery_service import compute_mastery, next_review_at_for


def test_no_attempts_is_not_started():
    score, level = compute_mastery(0, 0)
    assert score == 0
    assert level == "NOT_STARTED"


def test_below_attempt_floor_is_learning_even_if_perfect():
    score, level = compute_mastery(2, 2)
    assert score == 100
    assert level == "LEARNING"


def test_high_score_at_floor_is_mastered():
    score, level = compute_mastery(4, 4)
    assert score == 100
    assert level == "MASTERED"


def test_low_score_at_floor_is_practicing():
    score, level = compute_mastery(5, 1)
    assert score == 20
    assert level == "PRACTICING"


def test_score_exactly_at_threshold_is_mastered():
    score, level = compute_mastery(5, 4)
    assert score == 80
    assert level == "MASTERED"


def test_not_started_has_no_review_schedule():
    assert next_review_at_for("NOT_STARTED") is None


def test_learning_reviews_sooner_than_practicing_and_mastered():
    now = datetime.now(UTC)
    learning_at = next_review_at_for("LEARNING")
    practicing_at = next_review_at_for("PRACTICING")
    mastered_at = next_review_at_for("MASTERED")

    assert learning_at is not None and practicing_at is not None and mastered_at is not None
    assert now < learning_at < practicing_at < mastered_at


def test_mastered_review_interval_is_seven_days():
    before = datetime.now(UTC)
    mastered_at = next_review_at_for("MASTERED")
    assert mastered_at is not None
    assert timedelta(days=6) < mastered_at - before < timedelta(days=8)
