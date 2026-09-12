"""Tests for FACTORY-PYQ-P2.1E bbox OCR proof-of-concept."""

from __future__ import annotations

from pathlib import Path

from app.modules.cms.pyq.pyq_ocr import OcrWordRecord, parse_tesseract_tsv_words
from app.modules.cms.pyq.pyq_p2_1e import (
    HR_SHA,
    find_valid_question_starts,
    is_valid_question_marker,
    detect_layout_from_words,
    split_words_into_columns,
    segment_column_text,
    parse_options_bounded,
    _heal_pipe_split_question_markers,
)
from app.modules.cms.pyq.pyq_geometry import PageLayout
from app.modules.cms.pyq.pyq_p2_1c import evaluate_hr_regression


def test_parse_tesseract_tsv_words_persists_bbox(tmp_path: Path):
    tsv = tmp_path / "sample.tsv"
    tsv.write_text(
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t100\t200\t40\t20\t95.0\tHello\n"
        "5\t1\t1\t1\t1\t2\t150\t200\t30\t20\t90.0\tWorld\n",
        encoding="utf-8",
    )
    words = parse_tesseract_tsv_words(tsv, page_number=2)
    assert len(words) == 2
    assert words[0].left == 100
    assert words[0].width == 40
    assert words[0].text == "Hello"


def test_reject_circuit_amp_false_q_marker():
    assert not is_valid_question_marker("(4) 5 A from A to B through E", 5, page_number=2)
    assert not is_valid_question_marker("5 A from A to B through E", 5, page_number=2)


def test_accept_real_q5_marker():
    line = "5 An electric dipole is placed at an angle of 30°"
    assert is_valid_question_marker(line, 5, page_number=2)


def test_reject_instruction_page_numbers():
    assert not is_valid_question_marker("1 The Answer Sheet is inside", 1, page_number=1)


def test_reject_option_number_as_question():
    assert not is_valid_question_marker("(1) 2 mC", 1, page_number=2)


def test_two_column_detection_from_word_centers():
    words = [
        OcrWordRecord(1, 1, 1, 1, 1, 80, 100, 40, 20, 90.0, "Left"),
        OcrWordRecord(1, 1, 1, 1, 2, 120, 100, 40, 20, 90.0, "column"),
        OcrWordRecord(1, 1, 1, 2, 1, 900, 100, 40, 20, 90.0, "Right"),
        OcrWordRecord(1, 1, 1, 2, 2, 950, 100, 40, 20, 90.0, "column"),
    ]
    layout, split_x, evidence = detect_layout_from_words(
        words,
        page_width_px=1200,
        page_number=2,
        raw_text="1 Left column | 6 Right column",
    )
    assert layout == PageLayout.TWO_COLUMN
    assert split_x is not None
    assert any("two_column" in e for e in evidence)


def test_one_column_rough_work():
    words = [OcrWordRecord(1, 1, 1, 1, 1, 100, 100, 40, 20, 90.0, "SPACE")]
    layout, _, evidence = detect_layout_from_words(
        words,
        page_width_px=800,
        page_number=31,
        raw_text="SPACE FOR ROUGH WORK\nG2_English | 31",
    )
    assert layout == PageLayout.ONE_COLUMN
    assert "rough_work_blank" in evidence


def test_split_words_separates_columns():
    words = [
        OcrWordRecord(1, 1, 1, 1, 1, 100, 50, 30, 20, 90.0, "5"),
        OcrWordRecord(1, 1, 1, 1, 2, 140, 50, 80, 20, 90.0, "dipole"),
        OcrWordRecord(1, 1, 1, 2, 1, 900, 50, 30, 20, 90.0, "8"),
        OcrWordRecord(1, 1, 1, 2, 2, 940, 50, 60, 20, 90.0, "resistor"),
    ]
    layout, split_x, _ = detect_layout_from_words(
        words,
        page_width_px=1200,
        page_number=2,
        raw_text="5 dipole 8 resistor",
    )
    split = split_words_into_columns(words, layout, split_x, 1200)
    left_text = "\n".join(split.left_lines)
    right_text = "\n".join(split.right_lines)
    assert "dipole" in left_text
    assert "resistor" in right_text
    assert "dipole" not in right_text


def test_q5_segmentation_prevents_q3_q7_bleed():
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
        "7 The magnitude and direction of the current in the following circuit is\n"
        "(4) 5 A from A to B through E\n"
    )
    starts = find_valid_question_starts(col_text, page_number=2)
    qnums = [s[0] for s in starts]
    assert 5 in qnums
    assert 7 in qnums
    assert qnums.count(5) == 1

    records = segment_column_text(
        col_text,
        page_number=2,
        column_name="LEFT",
        layout="TWO_COLUMN",
        meta=meta,
    )
    q5 = next(r for r in records if r["question_number"] == 5)
    assert "electric dipole" in q5["stem"].lower()
    assert "transformer" not in q5["stem"].lower()
    assert "through e" not in q5["stem"].lower()


def test_q15_inline_option_reconstruction():
    """OCR may merge multiple option markers onto one line — split inline markers."""
    block = (
        "15 The net magnetic flux through any closed surface is :\n"
        "(1) Negative (2) Zero\n"
        "(3) Positive (4) Infinity\n"
    )
    stem, options, anomalies = parse_options_bounded(block)
    assert "magnetic flux" in stem.lower()
    assert options.get("1") == "Negative"
    assert options.get("2") == "Zero"
    assert options.get("3") == "Positive"
    assert options.get("4") == "Infinity"
    assert "option_set_complete" in anomalies


def test_multiline_inline_options():
    block = (
        "4 Nm. Calculate the magnitude of charge on the dipole, if the dipole length is 2 cm.\n"
        "(1) 2 mC (2) 8 mC\n"
        "(3) 6 mC (4) 4 mC\n"
    )
    _, options, anomalies = parse_options_bounded(block)
    assert options.get("1") == "2 mC"
    assert options.get("2") == "8 mC"
    assert options.get("3") == "6 mC"
    assert options.get("4") == "4 mC"
    assert "option_set_complete" in anomalies


def test_option_numbering_integrity_no_cross_question_bleed():
    block = (
        "6 Sample question stem here:\n"
        "(1) Alpha (2) Beta\n"
        "(3) Gamma (4) Delta\n"
        "7 Next question stem without marker validation gap\n"
        "(1) One (2) Two (3) Three (4) Four\n"
    )
    _, options, anomalies = parse_options_bounded(block)
    assert options.get("1") == "Alpha"
    assert options.get("4") == "Delta"
    assert "One" not in (options.get("4") or "")
    assert any("truncated" in a for a in anomalies)


def test_q15_no_q20_temperature_option_bleed():
    """Q15 must not inherit Q20 temperature options when block spans multiple questions."""
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
    stem, options, anomalies = parse_options_bounded(col_text)
    assert "magnetic flux" in stem.lower()
    assert options.get("1") == "Negative"
    assert options.get("4") == "Infinity"
    assert "223" not in options.get("1", "")
    assert any("truncated" in a for a in anomalies)

    records = segment_column_text(
        col_text,
        page_number=3,
        column_name="RIGHT",
        layout="TWO_COLUMN",
        meta=meta,
    )
    q15 = next(r for r in records if r["question_number"] == 15)
    assert "223" not in (q15.get("option_a") or "")
    assert "669" not in (q15.get("option_b") or "")
    assert q15["option_a"] in ("Negative", "")
    results = evaluate_hr_regression(
        [{**q15, "p2_1c_quality_status": q15.get("p2_1e_quality_status")}]
    )
    q15_result = next(r for r in results if r["question_number"] == 15)
    assert q15_result["passed"]


def test_q15_no_q11_error_options():
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
        col_text,
        page_number=3,
        column_name="RIGHT",
        layout="TWO_COLUMN",
        meta=meta,
    )
    q15 = next(r for r in records if r["question_number"] == 15)
    assert "Random error" not in q15["option_a"]
    results = evaluate_hr_regression(
        [{**q15, "p2_1c_quality_status": q15.get("p2_1e_quality_status")}]
    )
    q15_result = next(r for r in results if r["question_number"] == 15)
    assert q15_result["passed"]


def test_instruction_page_yields_no_questions():
    meta = {
        "source_sha256": HR_SHA,
        "source_file": "NEET_PYQ_OFFICIAL/2023/Paper_x.pdf",
        "exam_year": "2023",
        "paper_code": "Paper-x",
    }
    instr = "Important Instructions:\n1 The Answer Sheet is inside\n2 The test is of 3 hours\n"
    records = segment_column_text(
        instr,
        page_number=1,
        column_name="FULL",
        layout="ONE_COLUMN",
        meta=meta,
    )
    assert records == []


def test_heal_pipe_split_q15_marker():
    left = ["11 The errors in the measurement which arise | 15"]
    right = ["The net magnetic flux through any closed", "surface is :"]
    hl, hr = _heal_pipe_split_question_markers(left, right)
    assert "15" not in hl[0]
    assert hr[0].startswith("15 The net magnetic flux")


def test_diagram_dependent_classification():
    meta = {
        "source_sha256": HR_SHA,
        "source_file": "x.pdf",
        "exam_year": "2023",
        "paper_code": "x",
    }
    col_text = "37 An electric dipole is placed as shown in the figure.\n"
    records = segment_column_text(
        col_text,
        page_number=6,
        column_name="FULL",
        layout="ONE_COLUMN",
        meta=meta,
    )
    assert records[0]["p2_1e_quality_status"] == "DIAGRAM_DEPENDENT"
