from app.modules.knowledge.models import KnowledgeUnit
from app.modules.knowledge.services.knowledge_rendering import render_facts_for_prompt


def _unit(*, summary: str, structured_facts: list[str]) -> KnowledgeUnit:
    return KnowledgeUnit(
        version=1,
        content_hash="deadbeef",
        structured_facts=structured_facts,
        summary=summary,
        extraction_confidence=0.9,
        validation_status="PASSED",
    )


def test_renders_summary_then_facts_as_bullets():
    unit = _unit(
        summary="Ohm's Law relates current and voltage.",
        structured_facts=[
            "Current is proportional to potential difference.",
            "The relationship is written V = IR.",
        ],
    )

    rendered = render_facts_for_prompt(unit)

    assert rendered == (
        "Ohm's Law relates current and voltage.\n\n"
        "- Current is proportional to potential difference.\n"
        "- The relationship is written V = IR."
    )


def test_renders_summary_only_when_no_facts():
    unit = _unit(summary="A concept with no extracted facts.", structured_facts=[])

    rendered = render_facts_for_prompt(unit)

    assert rendered == "A concept with no extracted facts.\n\n"
