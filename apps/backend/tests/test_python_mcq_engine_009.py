"""Focused tests for PYTHON-MCQ-ENGINE-009 stop-on-insufficient-corpus behavior."""

from __future__ import annotations

import json
from pathlib import Path

from app.modules.cms.services.deterministic_fact_pack_loader import (
    load_deterministic_fact_pack,
)

ROOT = Path(__file__).resolve().parents[3]
PACK_006 = Path(__file__).parent / "fixtures/python_mcq_engine_006_reviewed_100.json"
PACK_008 = (
    Path(__file__).parent / "fixtures/python_mcq_engine_008_kinetics_rate_law_retired.json"
)
AUDIT_009 = ROOT / "docs/audits/python_mcq_engine_009.json"
RETIRED = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)


def test_available_eligible_facts_below_1000_triggers_stop():
    audit = json.loads(AUDIT_009.read_text(encoding="utf-8"))
    assert audit["requested_facts"] == 1000
    assert audit["available_eligible_facts"] == 99
    assert audit["stop_condition"]["triggered"] is True
    assert audit["evaluated_facts"] == 0
    assert audit["generated_candidates"] == 0
    assert audit["provider_api_calls"] == 0
    assert audit["production_db_mutations"] == 0
    assert audit["production_safety_unchanged"] is True
    assert audit["verified_yield"] is None


def test_engine008_retired_fact_remains_rejected_and_excluded():
    retired = load_deterministic_fact_pack(PACK_008, minimum_review_status="REJECTED")
    assert len(retired.facts) == 1
    assert retired.facts[0].fact_id == RETIRED
    assert retired.facts[0].review_status == "REJECTED"
    audit = json.loads(AUDIT_009.read_text(encoding="utf-8"))
    assert audit["engine_008_retired_fact"]["not_regenerated"] is True
    assert audit["engine_008_retired_fact"]["excluded_from_eligible_corpus"] is True


def test_engine006_fixture_not_modified_for_scale_attempt():
    audit = json.loads(AUDIT_009.read_text(encoding="utf-8"))
    assert audit["engine_006_fixture_modified"] is False
    loaded = load_deterministic_fact_pack(PACK_006)
    assert loaded.pack_id == "python-mcq-engine-006-reviewed-multisubject-v1"
    assert len(loaded.facts) == 100
