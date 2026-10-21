"""Focused tests for the deterministic batch runner (staged MCQ batches).

Follows the pattern of tests/test_python_mcq_engine_006.py: skipped when the
NCERT Books canonical corpus is not present on disk (no provider/AI calls,
no DB access, file-based only).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.cms.services.deterministic_batch_runner import (
    CorpusRow,
    find_duplicate,
    load_checkpoint,
    run_batch,
    write_batch_outputs,
    write_checkpoint,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (
    load_deterministic_fact_pack,
)

ROOT = Path(__file__).resolve().parents[3]
BACKEND = Path(__file__).resolve().parents[1]
SYLLABUS = ROOT / "NEETSyllabus.txt"
PACK = Path(__file__).parent / "fixtures/python_mcq_engine_006_reviewed_100.json"

pytestmark = pytest.mark.skipif(
    not (ROOT / "NCERT Books").exists(), reason="NCERT Books corpus not present"
)


@pytest.fixture(scope="module")
def facts():
    return load_deterministic_fact_pack(PACK).facts


# ---------------------------------------------------------------------------
# Pure helper tests (no filesystem corpus dependency beyond import)
# ---------------------------------------------------------------------------


def test_jaccard_duplicate_detection_against_near_duplicate_question():
    existing_row = CorpusRow(
        source_file="neet_mcq_batch_001.json",
        row_id="GEN-NEET-0001",
        stem="carl woeses three domain classification system divides life into archaea bacteria and eukarya primarily based on differences in",
        words={"carl", "woeses", "three", "domain", "classification", "system",
               "divides", "life", "into", "archaea", "bacteria", "eukarya",
               "primarily", "based", "differences"},
    )
    near_duplicate_stem = (
        "Carl Woese's three-domain system divides life into Archaea, Bacteria, "
        "and Eukarya mainly based on differences in:"
    )
    match = find_duplicate(near_duplicate_stem, [existing_row])
    assert match is not None
    assert match.row_id == "GEN-NEET-0001"


def test_jaccard_no_match_for_unrelated_question():
    existing_row = CorpusRow(
        source_file="neet_mcq_batch_001.json",
        row_id="GEN-NEET-0002",
        stem="what is the si unit of force",
        words={"what", "unit", "force"},
    )
    unrelated_stem = "Which organelle is the site of photosynthesis in plant cells?"
    assert find_duplicate(unrelated_stem, [existing_row]) is None


def test_load_corpus_rows_reads_hand_authored_and_deterministic_batches(tmp_path):
    hand_authored = [
        {
            "id": "GEN-NEET-0001",
            "question": "What is the powerhouse of the cell?",
        }
    ]
    (tmp_path / "neet_mcq_batch_001.json").write_text(
        json.dumps(hand_authored), encoding="utf-8"
    )
    det_batch = {
        "batch_id": "20260101T000000-abcd1234",
        "questions": [
            {"id": "DET-NEET-aaa", "question": "What is the site of cellular respiration?"}
        ],
    }
    (tmp_path / "deterministic_batch_20260101T000000-abcd1234.json").write_text(
        json.dumps(det_batch), encoding="utf-8"
    )
    from app.modules.cms.services.deterministic_batch_runner import load_corpus_rows

    rows = load_corpus_rows(tmp_path)
    assert {r.row_id for r in rows} == {"GEN-NEET-0001", "DET-NEET-aaa"}


def test_checkpoint_roundtrip(tmp_path):
    checkpoint_path = tmp_path / "batch.checkpoint.json"
    assert load_checkpoint(checkpoint_path) == set()
    write_checkpoint(checkpoint_path, "b1", ["fact-1", "fact-2"])
    assert load_checkpoint(checkpoint_path) == {"fact-1", "fact-2"}
    write_checkpoint(checkpoint_path, "b1", ["fact-2", "fact-3"])
    assert load_checkpoint(checkpoint_path) == {"fact-1", "fact-2", "fact-3"}


# ---------------------------------------------------------------------------
# Integration tests against the real reviewed cohort + real NCERT PDFs
# ---------------------------------------------------------------------------


def test_run_batch_determinism_same_seed_same_output(facts, tmp_path):
    first = run_batch(
        facts[:5], seed=20260914, generated_mcqs_dir=tmp_path, syllabus_path=SYLLABUS
    )
    second = run_batch(
        facts[:5], seed=20260914, generated_mcqs_dir=tmp_path, syllabus_path=SYLLABUS
    )
    assert [c["stem_hash"] for c in first.accepted] == [
        c["stem_hash"] for c in second.accepted
    ]
    assert [c["question"] for c in first.accepted] == [
        c["question"] for c in second.accepted
    ]


def test_run_batch_never_requires_concept_id(facts, tmp_path):
    result = run_batch(
        facts[:10], seed=20260914, generated_mcqs_dir=tmp_path, syllabus_path=SYLLABUS
    )
    # concept/concept_id may legitimately be None on accepted records; the
    # presence of the key (not its non-null-ness) is all that's required.
    for record in result.accepted:
        assert "concept" in record
        assert "concept_id" in record
    assert len(result.accepted) + len(result.rejections) >= 0  # ran without raising


def test_run_batch_respects_batch_size_cap(facts, tmp_path):
    result = run_batch(
        facts,
        seed=20260914,
        generated_mcqs_dir=tmp_path,
        syllabus_path=SYLLABUS,
        batch_size_cap=3,
    )
    assert len(result.accepted) <= 3


def test_run_batch_staging_output_schema(facts, tmp_path):
    result = run_batch(
        facts[:5], seed=20260914, generated_mcqs_dir=tmp_path, syllabus_path=SYLLABUS
    )
    if not result.accepted:
        pytest.skip("No eligible candidates generated from this fact slice")
    out_path, rej_path = write_batch_outputs(result, tmp_path)
    assert out_path.exists()
    assert rej_path.exists()
    assert out_path.name.startswith("deterministic_batch_")
    assert not out_path.name.startswith("neet_mcq_batch_")
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["generation_method"] == "deterministic_fact_engine"
    for record in payload["questions"]:
        assert record["generation_method"] == "deterministic_fact_engine"
        assert record["fact_id"]
        assert record["source"]["source_pdf"]
        assert len(record["options"]) == 4
        assert record["correct_answer"] in record["options"]


def test_run_batch_resume_without_duplicating_accepted_facts(facts, tmp_path):
    subset = facts[:8]
    first = run_batch(
        subset, seed=20260914, generated_mcqs_dir=tmp_path, syllabus_path=SYLLABUS
    )
    checkpoint_path = tmp_path / "resume.checkpoint.json"
    write_checkpoint(checkpoint_path, first.batch_id, first.attempted_fact_ids)
    out_path, _ = write_batch_outputs(first, tmp_path)

    checkpoint_ids = load_checkpoint(checkpoint_path)
    resumed = run_batch(
        subset,
        seed=20260914,
        generated_mcqs_dir=tmp_path,
        syllabus_path=SYLLABUS,
        checkpoint_fact_ids=checkpoint_ids,
    )
    # Every fact already attempted in the first run is skipped entirely on
    # resume, so nothing already-accepted is reprocessed or re-emitted.
    assert resumed.attempted_fact_ids == []
    assert resumed.accepted == []


def test_run_batch_rejects_near_duplicate_of_hand_authored_corpus(facts, tmp_path):
    # Seed the staging dir with a hand-authored row engineered to be a
    # near-duplicate (by significant-word Jaccard) of whatever the first
    # fact in the cohort will generate, by first running once to learn the
    # real generated stem, then re-running against a corpus containing it.
    probe = run_batch(
        facts[:3], seed=20260914, generated_mcqs_dir=tmp_path, syllabus_path=SYLLABUS
    )
    if not probe.accepted:
        pytest.skip("No eligible candidates generated from this fact slice")
    real_stem = probe.accepted[0]["question"]

    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / "neet_mcq_batch_900.json").write_text(
        json.dumps([{"id": "GEN-NEET-9000", "question": real_stem}]),
        encoding="utf-8",
    )

    rerun = run_batch(
        facts[:3], seed=20260914, generated_mcqs_dir=corpus_dir, syllabus_path=SYLLABUS
    )
    assert len(rerun.accepted) < len(probe.accepted) or any(
        r.reason == "DUPLICATE_OF_EXISTING_CORPUS_ROW" for r in rerun.rejections
    )
    dup_rejections = [
        r for r in rerun.rejections if r.reason == "DUPLICATE_OF_EXISTING_CORPUS_ROW"
    ]
    assert dup_rejections, "expected at least one duplicate rejection against seeded corpus"
    assert dup_rejections[0].matched_row_id == "GEN-NEET-9000"
