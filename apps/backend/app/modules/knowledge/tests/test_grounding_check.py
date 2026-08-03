from app.modules.knowledge.services.grounding_check import check_grounding, is_fact_grounded

SOURCE_TEXT = (
    "Ohm's law states that the current through a conductor is directly "
    "proportional to the potential difference across it, provided the "
    "temperature remains constant. This relationship is written V = IR, "
    "where R is the resistance of the conductor."
)


def test_grounded_fact_passes():
    fact = "The current through a conductor is proportional to the potential difference across it."
    assert is_fact_grounded(fact, SOURCE_TEXT) is True


def test_ungrounded_fact_fails():
    fact = "Photosynthesis occurs in the chloroplasts of plant cells during daylight hours."
    assert is_fact_grounded(fact, SOURCE_TEXT) is False


def test_bare_symbol_fact_passes_trivially():
    # No substantive vocabulary to check — this gate isn't meant to
    # evaluate a fact with nothing meaningful in it, and rejecting it
    # would be a false positive.
    assert is_fact_grounded("V = IR", SOURCE_TEXT) is True


def test_check_grounding_passes_when_all_facts_grounded():
    facts = [
        "Current through a conductor is proportional to potential difference.",
        "This relationship holds provided temperature remains constant.",
    ]
    passed, detail = check_grounding(facts, SOURCE_TEXT)
    assert passed is True
    assert detail is None


def test_check_grounding_fails_when_any_fact_ungrounded():
    facts = [
        "Current through a conductor is proportional to potential difference.",
        "Photosynthesis occurs in chloroplasts during daylight hours.",
    ]
    passed, detail = check_grounding(facts, SOURCE_TEXT)
    assert passed is False
    assert detail is not None
    assert "1/2" in detail


def test_check_grounding_fails_on_empty_facts():
    passed, detail = check_grounding([], SOURCE_TEXT)
    assert passed is False
    assert detail == "no structured facts extracted"
