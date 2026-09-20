"""Tests for FACTORY-PYQ-P2.1C geometry-first resegmentation."""

from __future__ import annotations

import io
import json
from pathlib import Path

import fitz

from app.modules.cms.pyq.pyq_geometry import (
    PageGeometry,
    detect_cross_column_contamination,
    detect_page_layout,
    split_page_columns,
)
from app.modules.cms.pyq.pyq_geometry import PageLayout
from app.modules.cms.pyq.pyq_p2_1c import (
    HR_REGRESSION_TARGETS,
    evaluate_hr_regression,
    segment_questions_from_geometry_corpus,
)


def test_detect_two_column_from_pipe_density():
    geom = PageGeometry(page_number=2, width=595.0, height=841.0)
    ocr = (
        "1 A vehicle travels half | 6 The amount of energy\n"
        "the distance with speed | required to form a soap\n"
        "(1) 3v/4 (2) v/3 | (1) 50.1 (2) 30.16\n"
    )
    layout, evidence, ratio = detect_page_layout(ocr, geom)
    assert layout == PageLayout.TWO_COLUMN
    assert ratio > 0.2
    assert any("two_column" in e for e in evidence)


def test_split_columns_left_then_right_ordering():
    geom = PageGeometry(page_number=2, width=595.0, height=841.0)
    ocr = (
        "1 A vehicle travels half | 6 The amount of energy\n"
        "the distance with speed | required to form a soap\n"
        "(1) 3v/4 (2) v/3 | (1) 50.1 (2) 30.16\n"
        "2 The half life is 20 minutes\n"
        "(1) 80 minutes (2) 20 minutes\n"
    )
    layout, _, _ = detect_page_layout(ocr, geom)
    split = split_page_columns(ocr, layout, geom)
    assert "vehicle" in split.left_text
    assert "amount of energy" in split.right_text
    assert split.left_text.find("vehicle") < split.left_text.find("half life")
    assert " | " not in split.left_text
    assert " | " not in split.right_text


def test_geometry_corpus_segments_columns_independently():
    corpus = """<<<PAGE:2>>>
<<<LAYOUT:TWO_COLUMN>>>
<<<SPLIT_X:297.50>>>
<<<COLUMN:LEFT>>>
Physics : Section-A
5. An electric dipole is placed at an angle of 30° with an electric field.
(1) 2 mC
(2) 8 mC
(3) 6 mC
(4) 4 mC
<<<COLUMN:RIGHT>>>
8 Resistance of a carbon resistor determined from colour codes is (22000±5%)Ω.
(1) Yellow
(2) Red
(3) Green
(4) Orange
"""
    meta = {
        "source_sha256": "00d8cababe821fcfc73db558ed7355083c52de1d3e78a073d59efa6e7c0c8fb5",
        "source_file": "NEET_PYQ_OFFICIAL/2023/Paper_x.pdf",
        "exam_year": "2023",
        "paper_code": "Paper-x",
        "paper_id": "00d8cababe821fcfc73db558ed7355083c52de1d3e78a073d59efa6e7c0c8fb5"[:16],
        "set_code": None,
        "language": None,
    }
    records = segment_questions_from_geometry_corpus(corpus, meta=meta, ocr_meta={"dpi": 200})
    q5 = next(r for r in records if r["question_number"] == 5)
    q8 = next(r for r in records if r["question_number"] == 8)
    assert q5["geometry_column"] == "LEFT"
    assert q8["geometry_column"] == "RIGHT"
    assert "Yellow" not in q5["option_a"]
    assert "electric dipole" in q5["stem"].lower()
    assert "Yellow" in q8["option_a"] or "yellow" in (q8["option_a"] or "").lower()


def test_cross_column_contamination_detector_q5_q8():
    bad = {
        "stem": "Which of these components remove the ac ripple from the rectified output?",
        "option_a": "Yellow",
        "option_b": "Red",
        "option_c": "Green",
        "option_d": "Orange",
        "geometry_column": "LEFT",
        "geometry_layout": "TWO_COLUMN",
    }
    flags = detect_cross_column_contamination(bad)
    assert any("cross_column" in f for f in flags)


def test_cross_column_contamination_detector_q15_q11():
    bad = {
        "stem": "The net magnetic flux through any closed surface is :",
        "option_a": "Random errors",
        "option_b": "Instrumental errors",
        "option_c": "Personal errors",
        "option_d": "Least count errors",
        "geometry_column": "LEFT",
        "geometry_layout": "TWO_COLUMN",
    }
    flags = detect_cross_column_contamination(bad)
    assert any("q15_q11" in f for f in flags)


def test_hr_regression_evaluation_passes_clean_record():
    clean_q5 = {
        "source_sha256": HR_REGRESSION_TARGETS[0]["source_sha256"],
        "question_number": 5,
        "source_page": 2,
        "stem": "An electric dipole is placed at an angle of 30° with an electric field.",
        "option_a": "2 mC",
        "option_b": "8 mC",
        "option_c": "6 mC",
        "option_d": "4 mC",
        "geometry_column": "LEFT",
        "geometry_layout": "TWO_COLUMN",
    }
    clean_q15 = {
        "source_sha256": HR_REGRESSION_TARGETS[1]["source_sha256"],
        "question_number": 15,
        "source_page": 3,
        "stem": "The net magnetic flux through any closed surface is :",
        "option_a": "Negative",
        "option_b": "Zero",
        "option_c": "Positive",
        "option_d": "Infinity",
        "geometry_column": "LEFT",
        "geometry_layout": "TWO_COLUMN",
    }
    results = evaluate_hr_regression([clean_q5, clean_q15])
    assert all(r["passed"] for r in results)


def test_build_geometry_page_corpus_from_fitz():
    from app.modules.cms.pyq.pyq_geometry import build_geometry_page_corpus

    doc = fitz.open()
    page = doc.new_page(width=595, height=841)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    doc2 = fitz.open(stream=buf.getvalue(), filetype="pdf")
    page = doc2.load_page(0)
    ocr = "1 Left question text here | 6 Right question text here\n(1) A | (1) X\n"
    corpus, ann = build_geometry_page_corpus(page_number=2, ocr_text=ocr, page=page)
    assert "<<<LAYOUT:TWO_COLUMN>>>" in corpus
    assert "<<<COLUMN:LEFT>>>" in corpus
    assert ann.layout == PageLayout.TWO_COLUMN.value
    doc2.close()


def test_geometry_module_exports():
    from app.modules.cms.pyq import pyq_p2_1c

    assert callable(pyq_p2_1c.run_geometry_resegment)
    assert callable(pyq_p2_1c.geometry_resegment_paper)
