"""P2.3 NCERT MCQ content factory tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.cms.mcq.p2_3.duplicates import classify_duplicates, near_duplicate
from app.modules.cms.mcq.p2_3.plan import build_generation_plan, build_concept_inventory
from app.modules.cms.mcq.p2_3.qa import automated_qa, map_validator_to_status
from app.modules.cms.mcq.p2_3.report import build_pilot_report
from app.modules.cms.mcq.p2_3.safeguard import (
    assert_p2_2_not_regenerated,
    is_p2_2_mcq_id,
    load_p2_2_protected_ids,
    verify_p2_2_population,
)
from app.modules.cms.mcq.p2_3.sampling import GOLD_SAMPLE_SIZE, GOLD_SEED, select_gold_sample
from app.modules.cms.mcq.p2_3.schemas import ConceptSlot, GenerationSlot, McqRecord
from app.modules.cms.mcq.p2_3.pipeline import dry_run_preflight, load_records, save_records, staging_paths
from app.modules.cms.pyq.p2_2.budget import BudgetGuard, BudgetExceededError
from app.modules.cms.pyq.p2_2.ncert_sources import NcertPageSource

ROOT = Path(__file__).resolve().parents[6]
MCQ_P2_2 = ROOT / "docs/content-factory/PYQ_P2_2_MCQ_RESULTS.jsonl"


def _sample_concept() -> ConceptSlot:
    return ConceptSlot(
        concept_id="bio:c1:p1:abc",
        source_id="abc",
        subject="BIOLOGY",
        class_level="11",
        chapter=1,
        topic="intro",
        source_locator="bio.pdf#page=1",
        source_file="Biology/class11/ch1.pdf",
        source_page=1,
        source_excerpt_hash="hash123",
    )


def _valid_record(**kwargs) -> McqRecord:
    base = McqRecord(
        question_id="p3-mcq-0001-test",
        run_id="run-1",
        batch_id="batch-1",
        slot_index=0,
        concept_id="bio:c1:p1:abc",
        subject="BIOLOGY",
        class_level="11",
        chapter=1,
        topic="intro",
        question_type="factual",
        difficulty="EASY",
        source_id="abc",
        source_locator="bio.pdf#page=1",
        source_file="Biology/class11/ch1.pdf",
        source_page=1,
        source_excerpt_hash="hash123",
        question="What is the basic unit of life?",
        options={"A": "Cell", "B": "Tissue", "C": "Organ", "D": "Atom"},
        correct_option="A",
        explanation="Cell is the basic unit of life per NCERT.",
        source_support="NCERT-SUPPORTED",
        generation_provider="gemini",
        generation_model="gemini-3.6-flash",
        generation_status="GENERATED",
    )
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def test_mcq_schema_four_options():
    rec = _valid_record()
    status, errors = automated_qa(rec)
    assert status == "PASS"
    assert len(rec.options) == 4


def test_qa_rejects_empty_stem():
    rec = _valid_record(question="")
    status, errors = automated_qa(rec)
    assert status == "REJECT"
    assert "EMPTY_STEM" in errors


def test_qa_rejects_invalid_answer():
    rec = _valid_record(correct_option="E")
    status, errors = automated_qa(rec)
    assert status == "REJECT"


def test_qa_rejects_duplicate_options():
    rec = _valid_record(options={"A": "Same", "B": "Same", "C": "C", "D": "D"})
    status, errors = automated_qa(rec)
    assert status == "REJECT"


def test_p2_2_safeguard_blocks_regeneration():
    protected = {"mcq-0001-abc", "mcq-0002-def"}
    with pytest.raises(RuntimeError, match="P2.2 SAFEGUARD"):
        assert_p2_2_not_regenerated(question_ids=["p3-mcq-0001-new", "mcq-0001-abc"], protected=protected)


def test_p2_2_id_detection():
    assert is_p2_2_mcq_id("mcq-0001-abc")
    assert not is_p2_2_mcq_id("p3-mcq-0001-abc")


def test_p2_2_population():
    if not MCQ_P2_2.exists():
        pytest.skip("P2.2 MCQ results not present")
    info = verify_p2_2_population(MCQ_P2_2)
    assert info["protected_count"] == info["expected"]


def test_protected_ids_load():
    if not MCQ_P2_2.exists():
        pytest.skip("P2.2 MCQ results not present")
    ids = load_p2_2_protected_ids(MCQ_P2_2)
    assert len(ids) >= 300
    assert all(i.startswith("mcq-") for i in ids)


def test_exact_duplicate_detection():
    a = _valid_record(question_id="p3-mcq-0001-a", question="What is DNA?")
    b = _valid_record(question_id="p3-mcq-0002-b", question="What is DNA?")
    classify_duplicates([a, b])
    assert b.duplicate_status == "EXACT_DUPLICATE"


def test_near_duplicate_detection():
    a = _valid_record(question_id="p3-mcq-0001-a", question="What is the speed of light in vacuum?")
    b = _valid_record(question_id="p3-mcq-0002-b", question="What is speed of light in vacuum?")
    classify_duplicates([a, b])
    assert b.duplicate_status in ("NEAR_DUPLICATE", "EXACT_DUPLICATE")


def test_p2_2_semantic_duplicate():
    rec = _valid_record(question="Sample P2.2 stem for duplicate test")
    classify_duplicates([rec], protected_stems=["Sample P2.2 stem for duplicate test"])
    assert rec.duplicate_status == "SEMANTIC_DUPLICATE"


def test_validator_status_mapping():
    assert map_validator_to_status({"overall": "PASS", "ncert_support_class": "DIRECT_NCERT_SUPPORT"}) == "READY"
    assert map_validator_to_status({"overall": "FAIL"}) == "REJECT"
    assert map_validator_to_status(None) == "INCONCLUSIVE"


def test_generation_plan_distribution():
    src = NcertPageSource(
        source_id="s1",
        relative_path="Biology/c11/ch1.pdf",
        subject="BIOLOGY",
        class_level="11",
        chapter=1,
        page=1,
        text="x" * 200,
        text_hash="h1",
    )
    concepts = build_concept_inventory([src] * 50)
    slots, meta = build_generation_plan(concepts, total=100, seed=42)
    assert len(slots) == 100
    assert sum(meta["actual_subject"].values()) == 100


def test_gold_sample_exactly_100():
    records = [_valid_record(question_id=f"p3-mcq-{i:04d}", slot_index=i, qa_status="PASS") for i in range(200)]
    sample = select_gold_sample(records, seed=GOLD_SEED, target=GOLD_SAMPLE_SIZE)
    assert len(sample) == 100


def test_gold_sample_reproducible():
    records = [_valid_record(question_id=f"p3-mcq-{i:04d}", slot_index=i, qa_status="PASS") for i in range(200)]
    s1 = select_gold_sample(records, seed=GOLD_SEED, target=100)
    s2 = select_gold_sample(records, seed=GOLD_SEED, target=100)
    assert [r.question_id for r in s1] == [r.question_id for r in s2]


def test_budget_guard_stops():
    bg = BudgetGuard(max_cost_usd=1.0)
    bg.record(track="t", provider="p", model="m", candidate_id="c", cost_usd=0.5, status="ok")
    bg.record(track="t", provider="p", model="m", candidate_id="c2", cost_usd=0.4, status="ok")
    with pytest.raises(BudgetExceededError):
        bg.record(track="t", provider="p", model="m", candidate_id="c3", cost_usd=0.2, status="ok")


def test_idempotency_save_load(tmp_path: Path):
    rec = _valid_record()
    path = tmp_path / "gen.jsonl"
    save_records(path, [rec])
    loaded = load_records(path)
    assert len(loaded) == 1
    assert loaded[0].question_id == rec.question_id
    save_records(path, [rec])
    assert len(load_records(path)) == 1


def test_numerical_qa_requires_numbers():
    rec = _valid_record(question_type="numerical", question="What is force?", options={"A": "a", "B": "b", "C": "c", "D": "d"})
    status, errors = automated_qa(rec)
    assert status == "REJECT"
    assert "NUMERICAL_MISSING_NUMBERS" in errors


def test_report_structure():
    records = [_valid_record(qa_status="PASS", validation_status="READY")]
    report = build_pilot_report(
        records=records,
        manifest={"run_id": "test"},
        p2_2_info={"protected_count": 326, "expected": 326},
        usd_inr=83.0,
    )
    assert report["production"]["db_writes"] == 0
    assert report["executive_summary"]["p2_2_protected"] == 326


def test_dry_run_preflight():
    pre = dry_run_preflight(ROOT)
    assert pre["production_db_writes"] == 0
    assert pre["p2_2_protected"]["expected"] == 326


def test_staging_paths_no_production():
    paths = staging_paths(ROOT)
    assert "staging/mcq/p2_3" in str(paths["base"]).replace("\\", "/")
