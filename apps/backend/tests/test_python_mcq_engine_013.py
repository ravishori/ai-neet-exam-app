"""Focused tests for PYTHON-MCQ-ENGINE-013 high-yield non-definitional expansion."""

from __future__ import annotations

import json
from pathlib import Path

from app.modules.cms.schemas.deterministic_fact_pack import DeterministicFact

ROOT = Path(__file__).resolve().parents[3]
PACK_006 = Path(__file__).parent / "fixtures/python_mcq_engine_006_reviewed_100.json"
PACK_010 = Path(__file__).parent / "fixtures/python_mcq_engine_010_reviewed_corpus.json"
PACK_011 = (
    Path(__file__).parent / "fixtures/python_mcq_engine_011_fact_type_candidates.json"
)
PACK_012 = (
    Path(__file__).parent / "fixtures/python_mcq_engine_012_reviewed_nondef_v1.json"
)
PACK_013 = (
    Path(__file__).parent / "fixtures/python_mcq_engine_013_reviewed_nondef_v1.json"
)
AUDIT = ROOT / "docs/audits/python_mcq_engine_013.json"
RETIRED = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)


def test_wave_counts_and_safety():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["candidates_selected"] == audit["candidates_reviewed"]
    assert 1 <= audit["candidates_reviewed"] <= 200
    assert (
        audit["MCQ_ELIGIBLE"] + audit["REVIEW_REQUIRED"] + audit["REJECTED"]
        == audit["candidates_reviewed"]
    )
    assert 0.0 <= audit["eligibility_rate"] <= 1.0
    assert audit["provider_api_calls"] == 0
    assert audit["production_db_mutations"] == 0
    assert audit["automatic_promotion"] is False
    assert audit["deferred_categories"] == ["RELATIONSHIP_FORMULA"]
    assert audit["engine012_distractor_failure_analysis"]["count"] == 19
    mutations = audit["fixture_mutations"]
    assert mutations["engine_006_modified"] is False
    assert mutations["engine_010_modified"] is False
    assert mutations["engine_011_modified"] is False
    assert mutations["engine_012_modified"] is False
    assert mutations["engine_010_eligible_count_unchanged"] is True
    assert mutations["engine_012_eligible_count_unchanged"] is True


def test_no_relationship_formula_and_no_prior_overlap():
    payload = json.loads(PACK_013.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert "RELATIONSHIP_FORMULA" not in audit["fact_type_breakdown"]["selected"]
    assert (
        audit["fact_type_breakdown"]["eligible_by_category"].get(
            "RELATIONSHIP_FORMULA", 0
        )
        == 0
    )
    prior = set()
    prior |= {
        fact["fact_id"]
        for fact in json.loads(PACK_010.read_text(encoding="utf-8"))["facts"]
    }
    prior |= {
        fact["fact_id"]
        for fact in json.loads(PACK_012.read_text(encoding="utf-8"))["pack"]["facts"]
    }
    prior |= {
        disposition["fact_id"]
        for disposition in json.loads(PACK_012.read_text(encoding="utf-8"))[
            "review_dispositions"
        ]
    }
    for fact in payload["pack"]["facts"]:
        assert fact["fact_id"] not in prior
        assert fact["fact_id"] != RETIRED


def test_eligible_fixture_schema():
    payload = json.loads(PACK_013.read_text(encoding="utf-8"))
    assert payload["pack"]["pack_id"] == "python-mcq-engine-013-reviewed-nondef-v1"
    assert len(payload["review_dispositions"]) == json.loads(
        AUDIT.read_text(encoding="utf-8")
    )["candidates_reviewed"]
    facts = payload["pack"]["facts"]
    assert facts
    for fact in facts:
        model = DeterministicFact.model_validate(fact)
        assert model.review_status == "REVIEWED"
        assert model.question_template is not None
        assert model.scope_review is not None
        assert model.scope_review.outcome == "SUPPORTED"
        assert model.fact_type in {
            "DIRECT_FACT",
            "ASSOCIATION",
            "SI_UNIT_TERMINOLOGY",
            "FORMULA",
        }
        correct = next(
            option
            for option in model.question_template.options
            if option.key == model.question_template.correct_key
        )
        assert correct.text.casefold() in model.evidence_text.casefold()


def test_prior_fixtures_unchanged():
    pack006 = json.loads(PACK_006.read_text(encoding="utf-8"))
    pack010 = json.loads(PACK_010.read_text(encoding="utf-8"))
    pack011 = json.loads(PACK_011.read_text(encoding="utf-8"))
    pack012 = json.loads(PACK_012.read_text(encoding="utf-8"))
    assert pack006["pack_id"] == "python-mcq-engine-006-reviewed-multisubject-v1"
    assert pack010["pack_id"] == "python-mcq-engine-010-reviewed-corpus-v1"
    assert len(pack010["facts"]) == 414
    assert pack012["pack"]["pack_id"] == "python-mcq-engine-012-reviewed-nondef-v1"
    assert len(pack012["pack"]["facts"]) == 58
    assert all(
        fact["review_status"] == "REVIEW_REQUIRED" for fact in pack011["pack"]["facts"]
    )
