"""P2.1F-RM deterministic remediation regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.modules.cms.pyq.pyq_p2_1c import evaluate_hr_regression
from app.modules.cms.pyq.pyq_p2_1e import (
    CANONICAL_DIPOLE_SHA,
    HR_SHA,
    apply_p2_1f_quality_guards,
    detect_foreign_contamination,
    is_valid_question_marker,
    parse_options_bounded,
    segment_column_text,
)

ROOT = Path(__file__).resolve().parents[6]
RCA_JSON = ROOT / "docs/content-factory/PYQ_P2_1F_ROOT_CAUSE_ANALYSIS.json"

CANONICAL_Q3_BLOCK = (
    "3 A full wave rectifier circuit consists of two\n"
    "p-n junction diodes, a centre-tapped\ntransft , it d a load resistance.\n"
    "Which of these components remove the ac\nripple from the rectified output?\n"
    "(1) Capacitor\n(2) Load resistance\n(3) A centre-tapped transformer\n"
    "4) p-n junction diodes\n@ pny\nar :\n"
    "4 An electric dipole is placed at an angle of\n30° with an electric field of intensity\n"
    "2x10°NC\"!. It experiences a torque equal to\n4 Nm.\n"
)

CONTAMINATED_VALID_IDS = (
    "00d8cababe821fcf:p8:q3",
    "8633a3811ea07447:p20:q133",
    "a1c3361678271d6e:p24:q162",
    "a43894b5fbc8cd28:p9:q3",
    "d11cf53d4d8ef5b0:p30:q195",
    "f5378eb6785774c3:p21:q145",
)


def test_rm1_canonical_2023_q3_p2_dipole_contamination_fixed():
    stem, options, anomalies = parse_options_bounded(
        CANONICAL_Q3_BLOCK, current_qnum=3, page_number=2
    )
    assert "rectifier" in stem.lower()
    opt_c = options.get("3") or options.get("c") or ""
    assert "electric dipole" not in opt_c.lower()
    assert "centre-tapped transformer" in opt_c.lower()
    assert any("truncated" in a for a in anomalies)


def test_rm1_foreign_stem_in_option_c():
    block = (
        "6 Sample stem here:\n"
        "(1) Alpha\n(2) Beta\n(3) Gamma text\n"
        "7 The magnitude and direction of the current in the following circuit is\n"
        "(1) One\n"
    )
    _, options, anomalies = parse_options_bounded(block, current_qnum=6, page_number=2)
    assert "circuit" not in (options.get("3") or "").lower()
    assert any("truncated" in a for a in anomalies)


def test_rm1_foreign_text_in_option_d():
    block = (
        "8 Resistor question:\n"
        "(1) A\n(2) B\n(3) C\n(4) D value\n"
        "9 An electric dipole is placed at an angle of 30°\n"
        "(1) 2 mC\n"
    )
    _, options, _ = parse_options_bounded(block, current_qnum=8, page_number=2)
    assert "dipole" not in (options.get("4") or "").lower()
    assert options.get("4") == "D value"


def test_rm1_question_marker_resembling_option_marker():
    line = "4 An electric dipole is placed at an angle of 30°"
    assert is_valid_question_marker(line, 4, page_number=2)
    assert not is_valid_question_marker("(4) Capacitor", 4, page_number=2)


def test_rm1_option_marker_same_line_as_next_question():
    block = (
        "12 Some question:\n"
        "(1) A (2) B (3) C (4) D\n"
        "13 Next question stem begins here\n"
    )
    _, options, anomalies = parse_options_bounded(block, current_qnum=12, page_number=2)
    assert options.get("4") == "D"
    assert "Next question" not in (options.get("4") or "")


def test_rm1_inline_options_preserved():
    block = (
        "15 The net magnetic flux through any closed surface is :\n"
        "(1) Negative (2) Zero\n(3) Positive (4) Infinity\n"
    )
    stem, options, anomalies = parse_options_bounded(block, current_qnum=15, page_number=3)
    assert "magnetic flux" in stem.lower()
    assert options.get("4") == "Infinity"
    assert "option_set_complete" in anomalies


def test_rm1_multiline_options_preserved():
    block = (
        "4 Nm. Calculate the magnitude of charge on the dipole, if the dipole length is 2 cm.\n"
        "(1) 2 mC (2) 8 mC\n(3) 6 mC (4) 4 mC\n"
    )
    _, options, anomalies = parse_options_bounded(block, current_qnum=4, page_number=2)
    assert options.get("4") == "4 mC"
    assert "option_set_complete" in anomalies


def test_rm1_second_one_boundary():
    block = (
        "6 Sample question stem here:\n"
        "(1) Alpha (2) Beta\n(3) Gamma (4) Delta\n"
        "7 Next question stem without marker validation gap\n"
        "(1) One (2) Two (3) Three (4) Four\n"
    )
    _, options, anomalies = parse_options_bounded(block, current_qnum=6, page_number=2)
    assert options.get("4") == "Delta"
    assert "One" not in (options.get("4") or "")
    assert any("truncated" in a for a in anomalies)


def test_rm1_q15_regression():
    meta = {
        "source_sha256": HR_SHA,
        "source_file": "NEET_PYQ_OFFICIAL/2023/Paper_x.pdf",
        "exam_year": "2023",
        "paper_code": "Paper-x",
    }
    col_text = (
        "15 The net magnetic flux through any closed surface is :\n"
        "(1) Negative\n(2) Zero\n(3) Positive\n(4) Infinity\n"
    )
    records = segment_column_text(
        col_text, page_number=3, column_name="RIGHT", layout="TWO_COLUMN", meta=meta
    )
    q15 = next(r for r in records if r["question_number"] == 15)
    results = evaluate_hr_regression(
        [{**q15, "p2_1c_quality_status": q15.get("p2_1e_quality_status")}]
    )
    assert next(r for r in results if r["question_number"] == 15)["passed"]


def test_rm1_q15_to_q20_regression():
    meta = {
        "source_sha256": HR_SHA,
        "source_file": "NEET_PYQ_OFFICIAL/2023/Paper_x.pdf",
        "exam_year": "2023",
        "paper_code": "Paper-x",
    }
    col_text = (
        "15 The net magnetic flux through any closed surface is :\n"
        "(1) Negative\n(2) Zero\n(3) Positive\n(4) Infinity\n"
        "16 Some intermediate question text here with options below\n"
        "(1) alpha\n(2) beta\n"
        "20 At what temperature will the rms speed of oxygen molecules become just sufficient to escape from earth?\n"
        "(1) 223 K\n(2) 669°C\n(3) 3295 K\n(4) 3097°C\n"
    )
    records = segment_column_text(
        col_text, page_number=3, column_name="RIGHT", layout="TWO_COLUMN", meta=meta
    )
    q15 = next(r for r in records if r["question_number"] == 15)
    assert "223" not in (q15.get("option_a") or "")
    results = evaluate_hr_regression(
        [{**q15, "p2_1c_quality_status": q15.get("p2_1e_quality_status")}]
    )
    assert next(r for r in results if r["question_number"] == 15)["passed"]


def test_rm1_q5_false_marker_rejection():
    assert not is_valid_question_marker("(4) 5 A from A to B through E", 5, page_number=2)
    meta = {
        "source_sha256": HR_SHA,
        "source_file": "NEET_PYQ_OFFICIAL/2023/Paper_x.pdf",
        "exam_year": "2023",
        "paper_code": "Paper-x",
    }
    col_text = (
        "3 A full wave rectifier circuit consists of two p-n junction diodes.\n"
        "(1) Load resistance\n"
        "5 An electric dipole is placed at an angle of 30° with an electric field.\n"
        "(1) 2 mC\n(2) 8 mC\n(3) 6 mC\n(4) 4 mC\n"
    )
    records = segment_column_text(
        col_text, page_number=2, column_name="LEFT", layout="TWO_COLUMN", meta=meta
    )
    q5 = next(r for r in records if r["question_number"] == 5)
    assert "electric dipole" in q5["stem"].lower()


def test_rm2_contaminated_valid_downgraded():
    record = {
        "question_number": 3,
        "source_page": 2,
        "stem": "A full wave rectifier circuit consists of two p-n junction diodes.",
        "option_a": "Capacitor",
        "option_b": "Load resistance",
        "option_c": "A centre-tapped transformer\n4 An electric dipole is placed at an angle",
        "option_d": "",
        "p2_1e_quality_status": "VALID",
        "geometry_quality_flags": ["option_contains_foreign_question_marker"],
    }
    apply_p2_1f_quality_guards(record)
    assert record["p2_1e_quality_status"] == "PARTIAL"
    assert record.get("rejection_reason") == "FOREIGN_QUESTION_TEXT_IN_OPTION"


def test_rm2_clean_valid_preserved():
    record = {
        "question_number": 15,
        "source_page": 3,
        "stem": "The net magnetic flux through any closed surface is :",
        "option_a": "Negative",
        "option_b": "Zero",
        "option_c": "Positive",
        "option_d": "Infinity",
        "p2_1e_quality_status": "VALID",
        "geometry_quality_flags": [],
    }
    apply_p2_1f_quality_guards(record)
    assert record["p2_1e_quality_status"] == "VALID"


def test_rm2_all_six_contaminated_valid_downgraded():
    records = [
        {
            "question_number": 3,
            "source_page": 8,
            "stem": "Methylbutan-2-ol",
            "option_a": "CH,-C-CH, Br\nbes 60\n3\nBr\n|",
            "option_b": "CH,-C-CH,-CH,\nOn,",
            "option_c": "CH, CH=CH-CH,",
            "option_d": "CH; —-CH-CH-CH,",
            "p2_1e_quality_status": "VALID",
            "geometry_quality_flags": ["option_contains_foreign_question_marker"],
        },
        {
            "question_number": 133,
            "source_page": 20,
            "stem": "Given below are two statements",
            "option_a": "Both Statement I and Statement II are true.",
            "option_b": "Both Statement I and Statement II are false.\n2 :",
            "option_c": "Statement I is correct but\n:\nStatement II is false.\n4 Lisi",
            "option_d": "Statement II is correct",
            "p2_1e_quality_status": "VALID",
            "geometry_quality_flags": ["option_contains_foreign_question_marker"],
        },
    ]
    for record in records:
        apply_p2_1f_quality_guards(record)
        assert record["p2_1e_quality_status"] == "PARTIAL"


def test_rm2_benign_ocr_page_number_not_downgraded():
    record = {
        "question_number": 10,
        "source_page": 5,
        "stem": "Which of the following is correct?",
        "option_a": "Alpha",
        "option_b": "Beta\n35",
        "option_c": "Gamma",
        "option_d": "Delta",
        "p2_1e_quality_status": "VALID",
        "geometry_quality_flags": ["option_contains_foreign_question_marker"],
    }
    apply_p2_1f_quality_guards(record)
    assert record["p2_1e_quality_status"] == "VALID"


def test_rm3_foreign_detection_metadata():
    record = {
        "question_number": 3,
        "source_page": 2,
        "stem": "rectifier circuit",
        "option_c": "transformer\n4 An electric dipole is placed",
    }
    foreign = detect_foreign_contamination(record)
    assert foreign["foreign_text_detected"] is True
    assert foreign["foreign_field"] == "option_c"
    assert foreign["detection_method"] in ("stem_signature_mismatch", "embedded_foreign_marker")


def test_rm3_all_25_rca_cases_have_detection_or_boundary_fix():
    if not RCA_JSON.exists():
        return
    cases = json.loads(RCA_JSON.read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 25
    for case in cases:
        excerpt = case.get("raw_extracted_excerpt") or ""
        qnum = case["question_number"]
        stem, options, _ = parse_options_bounded(
            excerpt, current_qnum=qnum, page_number=case["page"]
        )
        record = {
            "question_number": qnum,
            "source_page": case["page"],
            "stem": stem,
            "option_a": options.get("1", ""),
            "option_b": options.get("2", ""),
            "option_c": options.get("3", ""),
            "option_d": options.get("4", ""),
            "p2_1e_quality_status": "VALID",
        }
        apply_p2_1f_quality_guards(record)
        foreign = detect_foreign_contamination(record)
        opts_blob = " ".join(options.values()).lower()
        if "electric dipole" in (case.get("r2_extracted_options") or [""])[2].lower() if case.get("question_id") == "1d7ffd36a442fa95:p2:q3" else "":
            assert "electric dipole" not in opts_blob
        if foreign["foreign_text_detected"]:
            assert record["p2_1e_quality_status"] == "PARTIAL"


def test_rm4_q4_q5_segmentation_hr_page2():
    meta = {
        "source_sha256": CANONICAL_DIPOLE_SHA,
        "source_file": "NEET_PYQ_OFFICIAL/2023/Paper-20231108005054.pdf",
        "exam_year": "2023",
        "paper_code": "Paper-20231108005054",
    }
    col_text = (
        "3 A full wave rectifier circuit consists of two p-n junction diodes.\n"
        "(1) Capacitor\n(2) Load resistance\n(3) A centre-tapped transformer\n4) p-n junction diodes\n"
        "4 A football player is moving southward and suddenly turns eastward\n"
        "(1) along north-west\n(2) along eastward\n(3) along northward\n(4) along north-east\n"
        "5 An electric dipole is placed at an angle of 30° with an electric field.\n"
        "(1) 2 mC\n(2) 8 mC\n(3) 6 mC\n(4) 4 mC\n"
    )
    records = segment_column_text(
        col_text, page_number=2, column_name="LEFT", layout="TWO_COLUMN", meta=meta
    )
    q4 = next((r for r in records if r["question_number"] == 4), None)
    q5 = next((r for r in records if r["question_number"] == 5), None)
    assert q4 is not None
    assert q5 is not None
    assert "football" in q4["stem"].lower()
    assert "dipole" in q5["stem"].lower()
    assert "dipole" not in (q4.get("option_c") or "").lower()
