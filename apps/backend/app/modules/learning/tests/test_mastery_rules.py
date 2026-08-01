from app.modules.learning.services.mastery_service import compute_mastery


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
