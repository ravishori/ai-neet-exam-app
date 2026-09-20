"""Focused tests for PYTHON-MCQ-ENGINE-012 non-definitional review wave."""

from __future__ import annotations

import json
from pathlib import Path

from app.modules.cms.schemas.deterministic_fact_pack import DeterministicFact

ROOT = Path(__file__).resolve().parents[3]
PACK_010 = Path(__file__).parent / "fixtures/python_mcq_engine_010_reviewed_corpus.json"
PACK_006 = Path(__file__).parent / "fixtures/python_mcq_engine_006_reviewed_100.json"
PACK_011 = (
    Path(__file__).parent / "fixtures/python_mcq_engine_011_fact_type_candidates.json"
)
PACK_012 = (
    Path(__file__).parent / "fixtures/python_mcq_engine_012_reviewed_nondef_v1.json"
)
AUDIT = ROOT / "docs/audits/python_mcq_engine_012.json"
RETIRED = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)


def test_review_wave_counts_and_safety():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["candidates_selected"] == 100
    assert audit["candidates_reviewed"] == 100
    assert audit["MCQ_ELIGIBLE"] + audit["REVIEW_REQUIRED"] + audit["REJECTED"] == 100
    assert audit["provider_api_calls"] == 0
    assert audit["production_db_mutations"] == 0
    assert audit["automatic_promotion"] is False
    assert audit["fixture_mutations"]["engine_006_modified"] is False
    assert audit["fixture_mutations"]["engine_010_modified"] is False
    assert audit["fixture_mutations"]["engine_011_modified"] is False
    assert audit["fixture_mutations"]["engine_010_eligible_count_unchanged"] is True


def test_target_mix_and_subject_coverage():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    selected = audit["fact_type_breakdown"]["selected"]
    assert selected == {
        "DIRECT_FACT": 40,
        "RELATIONSHIP_FORMULA": 25,
        "CONTROLLED_ASSOCIATION": 20,
        "CONTROLLED_NUMERICAL": 10,
        "SI_UNIT_DIMENSION": 5,
    }
    subjects = set(audit["subject_breakdown"]["selected"])
    assert subjects == {"ZOOLOGY", "PHYSICS", "BOTANY", "CHEMISTRY"}


def test_eligible_fixture_schema_and_exclusions():
    payload = json.loads(PACK_012.read_text(encoding="utf-8"))
    assert payload["pack"]["pack_id"] == "python-mcq-engine-012-reviewed-nondef-v1"
    assert len(payload["review_dispositions"]) == 100
    facts = payload["pack"]["facts"]
    assert facts
    assert RETIRED not in {fact["fact_id"] for fact in facts}
    for fact in facts:
        model = DeterministicFact.model_validate(fact)
        assert model.review_status == "REVIEWED"
        assert model.question_template is not None
        assert model.scope_review is not None
        assert model.scope_review.outcome == "SUPPORTED"
        assert model.fact_type != "DEFINITION"
        correct = next(
            option
            for option in model.question_template.options
            if option.key == model.question_template.correct_key
        )
        assert correct.text.casefold() in model.evidence_text.casefold()


def test_prior_fixtures_unchanged():
    pack010 = json.loads(PACK_010.read_text(encoding="utf-8"))
    pack006 = json.loads(PACK_006.read_text(encoding="utf-8"))
    pack011 = json.loads(PACK_011.read_text(encoding="utf-8"))
    assert pack010["pack_id"] == "python-mcq-engine-010-reviewed-corpus-v1"
    assert len(pack010["facts"]) == 414
    assert pack006["pack_id"] == "python-mcq-engine-006-reviewed-multisubject-v1"
    assert pack011["pack"]["pack_id"]
    assert all(
        fact["review_status"] == "REVIEW_REQUIRED" for fact in pack011["pack"]["facts"]
    )
