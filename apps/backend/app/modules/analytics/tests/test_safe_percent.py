from app.modules.analytics.repositories.analytics_repository import safe_percent


def test_zero_denominator_is_zero_not_a_crash():
    assert safe_percent(5, 0) == 0.0


def test_basic_percentage():
    assert safe_percent(1, 4) == 25.0


def test_rounds_to_given_decimals():
    assert safe_percent(1, 3, decimals=2) == 33.33


def test_full_success_is_hundred_percent():
    assert safe_percent(10, 10) == 100.0
