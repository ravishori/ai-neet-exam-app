"""P2.3 human-gold validation gate tests."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import pytest

from app.modules.cms.mcq.p2_3.human_gold_gate.gate import decide_gate
from app.modules.cms.mcq.p2_3.human_gold_gate.human_review import (
    human_review_status,
    is_incomplete_human_value,
    preserve_human_fields,
)
from app.modules.cms.mcq.p2_3.human_gold_gate.loader import (
    file_checksum,
    load_source_gold_sample,
    merge_review_row,
    sort_review_rows,
    staging_paths,
    verify_protected_artifacts,
    write_review_csv,
)
from app.modules.cms.mcq.p2_3.human_gold_gate.metrics import compute_metrics
from app.modules.cms.mcq.p2_3.human_gold_gate.normalization import (
    normalize_answer_key,
    normalize_ai_verdict,
    normalize_human_overall,
)
from app.modules.cms.mcq.p2_3.human_gold_gate.pipeline import prepare_human_gold_review, run_all
from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import GATE_VERSION, GateThresholds, HUMAN_REVIEW_COLUMNS

ROOT = Path(__file__).resolve().parents[6]


def _complete_human(**overrides) -> dict[str, str]:
    base = {
        "human_stem": "OK stem",
        "human_option_A": "a",
        "human_option_B": "b",
        "human_option_C": "c",
        "human_option_D": "d",
        "human_answer": "A",
        "human_explanation": "because",
        "human_ncert_support": "DIRECT",
        "human_ambiguity": "NO",
        "human_duplicate": "NO",
        "human_difficulty": "MEDIUM",
        "human_neet_suitability": "SUITABLE",
        "human_overall": "ACCEPT",
        "reviewer_notes": "",
    }
    base.update(overrides)
    return base


def _review_row(**kwargs) -> dict[str, str]:
    row = {
        "question_id": "p3-mcq-test-0001",
        "subject": "PHYSICS",
        "class": "11",
        "chapter": "3",
        "topic": "kinematics",
        "question": "What is velocity?",
        "option_A": "1",
        "option_B": "2",
        "option_C": "3",
        "option_D": "4",
        "proposed_answer": "A",
        "validator_verdict": "READY",
        "validation_status_before_R1": "READY",
        "validation_status_after_R1": "READY",
        "r1_validator_provider": "gemini",
        "preaudit_priority": "HIGH",
        "preaudit_verdict": "PREAUDIT_REVIEW",
        "preaudit_reason": "test",
        "preaudit_recommended_action": "HUMAN_VERIFY",
        **{c: "PENDING" for c in HUMAN_REVIEW_COLUMNS},
        "reviewer_notes": "",
    }
    row.update(kwargs)
    return row


def test_pending_preserved_in_merge():
    source = {"question_id": "x", "human_overall": "PENDING", "human_answer": "PENDING"}
    for c in HUMAN_REVIEW_COLUMNS:
        source.setdefault(c, "PENDING")
    merged = merge_review_row(source, None, None)
    assert merged["human_overall"] == "PENDING"
    assert merged["human_answer"] == "PENDING"


def test_empty_and_null_incomplete():
    assert is_incomplete_human_value("")
    assert is_incomplete_human_value("PENDING")
    assert is_incomplete_human_value("NOT_REVIEWED")
    assert not is_incomplete_human_value("ACCEPT")
    assert not is_incomplete_human_value("NO")
    assert not is_incomplete_human_value("0")
    assert not is_incomplete_human_value("FALSE")


def test_human_review_status_levels():
    pending = _review_row()
    assert human_review_status(pending) == "HUMAN_REVIEW_PENDING"
    partial = _review_row(**_complete_human(human_overall="PENDING"))
    assert human_review_status(partial) == "HUMAN_REVIEW_PARTIAL"
    complete = _review_row(**_complete_human())
    assert human_review_status(complete) == "HUMAN_REVIEW_COMPLETE"


def test_normalize_answer_key_variants():
    assert normalize_answer_key("A") == "A"
    assert normalize_answer_key("Option B") == "B"
    assert normalize_answer_key("(C)") == "C"
    assert normalize_answer_key("1") == "A"
    assert normalize_answer_key("PENDING") is None


def test_ai_human_label_mapping():
    row = _review_row(validation_status_after_R1="READY", **_complete_human(human_overall="ACCEPT"))
    assert normalize_ai_verdict(row) == "ACCEPT"
    assert normalize_human_overall(row) == "ACCEPT"


def test_false_pass_detection():
    row = _review_row(validation_status_after_R1="READY", **_complete_human(human_overall="REJECT"))
    metrics = compute_metrics([row], {})
    assert metrics["false_pass_count"] == 1
    assert len(metrics["false_passes"]) == 1


def test_false_reject_detection():
    row = _review_row(validation_status_after_R1="REJECT", **_complete_human(human_overall="ACCEPT"))
    metrics = compute_metrics([row], {})
    assert metrics["false_reject_count"] == 1


def test_partial_not_in_agreement_metrics():
    partial = _review_row(**_complete_human(human_overall="PENDING"))
    complete = _review_row(**_complete_human())
    metrics = compute_metrics([partial, complete], {})
    assert metrics["human_reviewed"] == 1
    assert metrics["eligible_human_reviewed_questions"] == 1


def test_incomplete_gate_yellow():
    metrics = {
        "sample_size": 100,
        "human_reviewed": 37,
        "pending": 63,
        "partial": 0,
        "completion_rate": 0.37,
    }
    gate = decide_gate(metrics, thresholds=GateThresholds(), integrity_errors=[])
    assert gate["gate_status"] == "YELLOW"
    assert gate["gate_reason"] == "HUMAN_REVIEW_INCOMPLETE"
    assert gate["ten_k_recommendation"] == "DO_NOT_PROCEED"


def test_complete_thresholds_pending_yellow():
    metrics = {
        "sample_size": 100,
        "human_reviewed": 100,
        "pending": 0,
        "partial": 0,
        "false_pass_count": 0,
        "false_passes": [],
    }
    gate = decide_gate(metrics, thresholds=GateThresholds(), integrity_errors=[])
    assert gate["gate_status"] == "YELLOW"
    assert gate["gate_reason"] == "THRESHOLDS_PENDING_POLICY"


def test_integrity_failure_red():
    metrics = {"human_reviewed": 100, "partial": 0}
    gate = decide_gate(metrics, thresholds=GateThresholds(), integrity_errors=["MODIFIED_PROTECTED_ARTIFACT:x"])
    assert gate["gate_status"] == "RED"


def test_green_with_thresholds():
    metrics = {
        "sample_size": 100,
        "human_reviewed": 100,
        "pending": 0,
        "partial": 0,
        "false_pass_count": 0,
        "false_pass_rate": 0.0,
        "answer_key_agreement_rate": 0.99,
        "overall_agreement_rate": 0.95,
        "false_passes": [],
    }
    th = GateThresholds(
        max_false_pass_rate_green=0.05,
        min_answer_key_agreement_green=0.9,
        min_overall_agreement_green=0.85,
    )
    gate = decide_gate(metrics, thresholds=th, integrity_errors=[])
    assert gate["gate_status"] == "GREEN"
    assert gate["ten_k_recommendation"] == "PROCEED"


def test_review_sort_order():
    rows = [
        _review_row(question_id="b", preaudit_priority="LOW", subject="BIOLOGY"),
        _review_row(question_id="a", preaudit_priority="CRITICAL", subject="PHYSICS"),
    ]
    ordered = sort_review_rows(rows)
    assert ordered[0]["preaudit_priority"] == "CRITICAL"


def test_preserve_human_fields():
    src = {"human_overall": "PENDING", "human_answer": "PENDING", "reviewer_notes": "note"}
    tgt = {"human_overall": "", "human_answer": "B"}
    out = preserve_human_fields(src, tgt)
    assert out["human_overall"] == "PENDING"
    assert out["human_answer"] == "PENDING"


@pytest.mark.skipif(not (ROOT / "data/staging/mcq/p2_3_r1/human_gold_sample_r1_annotated.csv").exists(), reason="no gold")
def test_integration_prepare_idempotent():
    before = file_checksum(ROOT / "data/staging/mcq/p2_3_r1/human_gold_sample_r1_annotated.csv")
    m1 = prepare_human_gold_review(root=ROOT)
    m2 = prepare_human_gold_review(root=ROOT)
    after = file_checksum(ROOT / "data/staging/mcq/p2_3_r1/human_gold_sample_r1_annotated.csv")
    assert before == after
    assert m1["sample_size"] == 100
    paths = staging_paths(ROOT)
    rows1 = list(csv.DictReader(paths["review_csv"].open(encoding="utf-8")))
    rows2 = list(csv.DictReader(paths["review_csv"].open(encoding="utf-8")))
    assert rows1 == rows2
    source = load_source_gold_sample(ROOT)
    for col in HUMAN_REVIEW_COLUMNS:
        for s, r in zip(source, rows1, strict=True):
            if s["question_id"] == r["question_id"]:
                assert s[col] == r[col]


@pytest.mark.skipif(not (ROOT / "data/staging/mcq/p2_3_pre_human_audit/pre_human_audit.jsonl").exists(), reason="no preaudit")
def test_integration_run_all_idempotent():
    before_checksums = {
        p: file_checksum(ROOT / p)
        for p in [
            "data/staging/mcq/p2_3_r1/human_gold_sample_r1_annotated.csv",
            "data/staging/mcq/p2_3/human_gold_sample.csv",
        ]
    }
    r1 = run_all(root=ROOT)
    r2 = run_all(root=ROOT)
    assert r1["gate_status"] == r2["gate_status"]
    assert r1["human_reviewed"] == r2["human_reviewed"]
    assert r1["ten_k_recommendation"] == r2["ten_k_recommendation"]
    for rel, cs in before_checksums.items():
        assert file_checksum(ROOT / rel) == cs
    assert r1["production_db_writes"] == 0
    manifest_path = staging_paths(ROOT)["run_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert verify_protected_artifacts(ROOT, manifest.get("protected_artifact_checksums")) == []
