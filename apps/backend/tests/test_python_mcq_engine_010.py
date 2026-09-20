"""Focused tests for PYTHON-MCQ-ENGINE-010 reviewed corpus expansion."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from app.modules.cms.services.deterministic_fact_adapter import (
    DeterministicFactToQuestionAdapter,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (
    load_deterministic_fact_pack,
)
from app.modules.cms.services.fact_quality_gate import TaxonomyBinding

ROOT = Path(__file__).resolve().parents[3]
SYLLABUS = ROOT / "NEETSyllabus.txt"
PACK_006 = Path(__file__).parent / "fixtures/python_mcq_engine_006_reviewed_100.json"
PACK_010 = Path(__file__).parent / "fixtures/python_mcq_engine_010_reviewed_corpus.json"
AUDIT_010 = ROOT / "docs/audits/python_mcq_engine_010.json"
RETIRED = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)


def _taxonomy(fact) -> TaxonomyBinding:
    return TaxonomyBinding(
        subject=fact.subject,
        class_level=fact.class_level,
        chapter_id=fact.chapter_id,
        chapter=fact.chapter,
        topic_id=fact.topic_id,
        topic=fact.topic,
        concept_id=fact.concept_id or "",
        concept=fact.concept_name or "",
    )


def test_engine010_corpus_expanded_but_below_1000_target():
    loaded = load_deterministic_fact_pack(PACK_010)
    audit = json.loads(AUDIT_010.read_text(encoding="utf-8"))
    assert loaded.pack_id == "python-mcq-engine-010-reviewed-corpus-v1"
    assert len(loaded.facts) == audit["pack"]["fact_count"]
    assert len(loaded.facts) >= 99
    assert len(loaded.facts) < 1000
    assert audit["targets"]["reached_1000_total"] is False
    assert audit["targets"]["reached_250_per_subject"] is False
    counts = Counter(fact.subject for fact in loaded.facts)
    assert set(counts) == {"PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY"}
    assert RETIRED not in {fact.fact_id for fact in loaded.facts}


def test_engine006_fixture_unchanged_and_not_overwritten():
    audit = json.loads(AUDIT_010.read_text(encoding="utf-8"))
    assert audit["engine_006_fixture_modified"] is False
    loaded = load_deterministic_fact_pack(PACK_006)
    assert loaded.pack_id == "python-mcq-engine-006-reviewed-multisubject-v1"
    assert len(loaded.facts) == 100


def test_sample_facts_remain_mcq_eligible():
    loaded = load_deterministic_fact_pack(PACK_010)
    adapter = DeterministicFactToQuestionAdapter()
    sample = sorted(loaded.facts, key=lambda fact: fact.fact_id)[:5]
    for fact in sample:
        assert fact.review_status == "REVIEWED"
        adapted = adapter.adapt(
            fact,
            taxonomy=_taxonomy(fact),
            authoritative_syllabus_path=SYLLABUS,
        )
        assert adapted.quality.mcq_eligible is True


def test_unique_fact_ids_and_deterministic_order():
    loaded = load_deterministic_fact_pack(PACK_010)
    ids = [fact.fact_id for fact in loaded.facts]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids)
