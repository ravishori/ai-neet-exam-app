"""FACTORY-PYQ-P2.1C — geometry-first resegmentation from OCR + PDF layout."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz

from app.modules.cms.pyq.pyq_extraction import (
    AnswerStatus,
    ValidationStatus,
    mark_within_paper_duplicates,
    question_hash,
    segment_questions_from_text,
)
from app.modules.cms.pyq.pyq_discovery import normalized_question_hash
from app.modules.cms.pyq.pyq_geometry import (
    COLUMN_MARKER_RE,
    LAYOUT_MARKER_RE,
    PageLayout,
    build_geometry_page_corpus,
    detect_cross_column_contamination,
    run_automated_quality_checks,
)
from app.modules.cms.pyq.pyq_ocr import OCR_FAILED, OCR_LOW_CONFIDENCE, OCR_SUCCESS, NEEDS_REVIEW
from app.modules.cms.pyq.pyq_p2_1 import _entry_from_paper_meta, select_scanned_paper_dirs, sha256_file
from app.modules.cms.pyq.pyq_p2_1b import (
    INSTRUCTION_MARKERS,
    DIAGRAM_CUES,
    annotate_rough_work_pages,
    canonical_questions_hash,
    deterministic_staging_id,
    load_ocr_pages,
)

PAGE_BLOCK_RE = re.compile(r"<<<PAGE:(\d+)>>>")
SECTION_HEADER_FRAGMENT_RE = re.compile(
    r"(Physics|Chemistry|Biology(?:\s*:\s*(?:Botany|Zoology))?)\s*:\s*Section\s*-?\s*[AB]",
    re.I,
)

# Mandatory P2.1B-HR regression targets (paper sha, qnum, page).
HR_REGRESSION_TARGETS = [
    {
        "source_sha256": "00d8cababe821fcfc73db558ed7355083c52de1d3e78a073d59efa6e7c0c8fb5",
        "question_number": 5,
        "source_page": 2,
        "forbidden_option_tokens": ["Yellow", "Red", "Green", "Orange"],
        "forbidden_stem_tokens": ["through E", "transformer, capacitor", "remove the ac ripple"],
        "label": "Q5_must_not_have_Q8_resistor_colors",
    },
    {
        "source_sha256": "00d8cababe821fcfc73db558ed7355083c52de1d3e78a073d59efa6e7c0c8fb5",
        "question_number": 15,
        "source_page": 3,
        "forbidden_option_tokens": ["Random error", "Instrumental error", "Personal error"],
        "forbidden_stem_tokens": ["unpredictable fluctuations"],
        "label": "Q15_must_not_have_Q11_error_types",
    },
]


@dataclass
class GeometryResegmentSummary:
    generated_at: str
    mode: str
    papers: int
    pages: int
    layout_one_column: int
    layout_two_column: int
    layout_unknown: int
    ocr_success: int
    ocr_low_confidence: int
    ocr_failed: int
    ocr_needs_review_pages: int
    rough_work_blank_pages: int
    old_p2_1_count: int
    old_p2_1b_count: int
    new_question_count: int
    quality_valid: int
    quality_needs_review: int
    quality_partial: int
    quality_diagram_dependent: int
    quality_incorrect_candidate: int
    cross_column_flags: int
    duplicate_within_paper: int
    fragment_candidates: int
    false_positive_candidates: int
    by_year: dict[str, int] = field(default_factory=dict)
    questions_per_paper: dict[str, int] = field(default_factory=dict)
    idempotent: bool = False
    corpus_hash_pass1: str = ""
    corpus_hash_pass2: str = ""
    verdict: str = "YELLOW"
    safety: dict[str, int] = field(default_factory=dict)
    automated_checks: dict[str, Any] = field(default_factory=dict)
    hr_regression: list[dict[str, Any]] = field(default_factory=list)


def _looks_like_instruction(stem: str, raw: str) -> bool:
    blob = f"{stem}\n{raw}".lower()
    hits = sum(1 for m in INSTRUCTION_MARKERS if m in blob)
    return hits >= 2 or any(
        m in blob
        for m in (
            "read carefully the following instructions",
            "space for rough work",
            "unfair means",
        )
    )


def _looks_like_diagram(stem: str, missing_options: bool) -> bool:
    low = (stem or "").lower()
    return missing_options and any(c in low for c in DIAGRAM_CUES)


def classify_quality_p2_1c(record: dict[str, Any]) -> str:
    stem = record.get("stem") or ""
    raw = record.get("raw_extracted_text") or ""
    missing = bool(record.get("missing_options"))
    filled = sum(
        1
        for k in ("option_a", "option_b", "option_c", "option_d")
        if (record.get(k) or "").strip()
    )
    if record.get("geometry_quality_flags"):
        if any("cross_column" in f for f in record["geometry_quality_flags"]):
            return "NEEDS_REVIEW"
    if _looks_like_instruction(stem, raw):
        return "INCORRECT_CANDIDATE"
    if _looks_like_diagram(stem, missing):
        return "DIAGRAM_DEPENDENT"
    if not stem.strip() or len(stem.strip()) < 12:
        return "NEEDS_REVIEW"
    if missing and filled == 0:
        return "PARTIAL"
    if missing and filled < 4:
        return "PARTIAL"
    if record.get("duplicate_within_paper"):
        return "NEEDS_REVIEW"
    if record.get("geometry_layout") == PageLayout.UNKNOWN.value:
        return "NEEDS_REVIEW"
    if filled == 4 and len(stem.strip()) >= 12:
        return "VALID"
    return "NEEDS_REVIEW"


def _extract_section_prefix(page_body: str) -> str:
    """Carry section header into column segments when present at page top."""
    m = SECTION_HEADER_FRAGMENT_RE.search(page_body)
    if m:
        start = page_body.rfind("\n", 0, m.start())
        end = page_body.find("\n", m.end())
        if end == -1:
            end = min(len(page_body), m.end() + 80)
        return page_body[start + 1 : end].strip()
    return ""


def _parse_geometry_page_block(page_block: str) -> tuple[str, str, str, str]:
    layout_m = LAYOUT_MARKER_RE.search(page_block)
    layout = layout_m.group(1) if layout_m else PageLayout.UNKNOWN.value

    columns: dict[str, str] = {"FULL": page_block}
    if layout == PageLayout.TWO_COLUMN.value:
        parts = COLUMN_MARKER_RE.split(page_block)
        # split yields: [pre, LEFT, left_body, RIGHT, right_body]
        columns = {}
        idx = 1
        while idx + 1 < len(parts):
            col_name = parts[idx]
            col_body = parts[idx + 1]
            columns[col_name] = col_body.strip()
            idx += 2

    return layout, columns.get("LEFT", ""), columns.get("RIGHT", ""), columns.get("FULL", page_block)


def segment_questions_from_geometry_corpus(
    corpus: str,
    *,
    meta: dict[str, Any],
    ocr_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    """Segment questions per geometric column; never merge L/R before boundary detection."""
    entry = _entry_from_paper_meta(meta)
    paper_id = meta.get("paper_id") or meta["source_sha256"][:16]

    all_questions: list[Any] = []
    page_blocks = PAGE_BLOCK_RE.split(corpus)
    # page_blocks: [pre, page_num, body, page_num, body, ...]
    idx = 1
    while idx + 1 < len(page_blocks):
        page_num = int(page_blocks[idx])
        body = page_blocks[idx + 1]
        if "<<<SKIP_QUESTIONS:" in body:
            idx += 2
            continue
        layout, left_text, right_text, _full = _parse_geometry_page_block(body)
        section_prefix = _extract_section_prefix(body)

        segments: list[tuple[str, str]] = []
        if layout == PageLayout.TWO_COLUMN.value:
            if left_text.strip():
                segments.append(("LEFT", left_text))
            if right_text.strip():
                segments.append(("RIGHT", right_text))
        else:
            text = left_text or right_text or body
            segments.append(("FULL", text))

        for col_name, col_text in segments:
            col_corpus = f"<<<PAGE:{page_num}>>>\n"
            if section_prefix:
                col_corpus += section_prefix + "\n"
            col_corpus += col_text

            qs = segment_questions_from_text(
                col_corpus,
                paper_id=paper_id,
                entry=entry,
                extraction_mode="OCR_GEOMETRY",
                extraction_confidence=0.6,
                ocr_pages=[],
            )
            for q in qs:
                q.source_page = page_num
                # Attach geometry metadata via anomalies/raw — converted to dict below.
                q.anomalies = list(q.anomalies) + [f"geometry_column:{col_name}", f"geometry_layout:{layout}"]
            all_questions.extend(qs)
        idx += 2

    mark_within_paper_duplicates(all_questions)

    records: list[dict[str, Any]] = []
    for q in all_questions:
        opts = [q.option_a, q.option_b, q.option_c, q.option_d]
        filled = sum(1 for o in opts if o.strip())
        missing = filled < 4
        status = q.validation_status
        review_reasons: list[str] = []
        if missing:
            status = ValidationStatus.NEEDS_REVIEW.value
            review_reasons.append("missing_options")
        if not q.stem.strip():
            status = ValidationStatus.NEEDS_REVIEW.value
            review_reasons.append("empty_stem")

        geom_col = "UNKNOWN"
        geom_layout = PageLayout.UNKNOWN.value
        for a in q.anomalies:
            if a.startswith("geometry_column:"):
                geom_col = a.split(":", 1)[1]
            if a.startswith("geometry_layout:"):
                geom_layout = a.split(":", 1)[1]

        record: dict[str, Any] = {
            "staging_id": q.staging_id,
            "paper_id": q.paper_id,
            "exam_year": q.exam_year,
            "paper_code": q.paper_code,
            "set_code": q.set_code,
            "language": q.language,
            "question_number": q.question_number,
            "subject": q.subject,
            "subsection": q.subsection,
            "stem": q.stem,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "correct_option": None,
            "answer_status": AnswerStatus.ANSWER_PENDING.value,
            "answer_source": None,
            "answer_source_page": None,
            "source_file": q.source_file,
            "source_sha256": q.source_sha256,
            "source_page": q.source_page,
            "question_hash": q.question_hash or question_hash(q.stem, opts),
            "normalized_question_hash": q.normalized_question_hash
            or normalized_question_hash(q.stem, opts),
            "extraction_mode": "OCR_GEOMETRY",
            "extraction_method": "geometry_first_ocr_pdf_layout",
            "extraction_confidence": q.extraction_confidence,
            "validation_status": status,
            "raw_extracted_text": q.raw_extracted_text,
            "raw_ocr_preserved": True,
            "duplicate_within_paper": q.duplicate_within_paper,
            "anomalies": [a for a in q.anomalies if not a.startswith("geometry_")],
            "missing_options": missing,
            "geometry_column": geom_col,
            "geometry_layout": geom_layout,
            "p2_1c_validation_status": status,
            "p2_answer_status": AnswerStatus.ANSWER_PENDING.value,
        }
        geom_flags = detect_cross_column_contamination(record)
        if geom_flags:
            record["geometry_quality_flags"] = geom_flags
            record.setdefault("anomalies", []).extend(geom_flags)
        records.append(record)
    return records


def build_geometry_corpus_from_pdf(
    *,
    pdf_bytes: bytes,
    pages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chunks: list[str] = []
    annotations: list[dict[str, Any]] = []
    try:
        for page in pages:
            pn = page["page_number"]
            if page.get("rough_work_blank_page"):
                chunks.append(f"<<<PAGE:{pn}>>>\n<<<LAYOUT:ONE_COLUMN>>>\n")
                annotations.append(
                    {
                        "page_number": pn,
                        "layout": PageLayout.ONE_COLUMN.value,
                        "rough_work_blank_page": True,
                    }
                )
                continue
            ocr_text = page.get("raw_text") or ""
            fitz_page = doc.load_page(pn - 1)
            page_corpus, ann = build_geometry_page_corpus(
                page_number=pn,
                ocr_text=ocr_text,
                page=fitz_page,
                rough_work=bool(page.get("rough_work_blank_page")),
            )
            chunks.append(page_corpus)
            annotations.append(
                {
                    "page_number": ann.page_number,
                    "layout": ann.layout,
                    "width": ann.width,
                    "height": ann.height,
                    "split_x": ann.split_x,
                    "pipe_line_ratio": ann.pipe_line_ratio,
                    "word_count": ann.word_count,
                    "evidence": ann.evidence,
                }
            )
    finally:
        doc.close()
    return "\n".join(chunks), annotations


def enrich_geometry_record(
    record: dict[str, Any],
    *,
    ocr_meta: dict[str, Any],
    page_anomalies: dict[int, list[str]],
) -> dict[str, Any]:
    opts = [record.get(k, "") or "" for k in ("option_a", "option_b", "option_c", "option_d")]
    staging_id = deterministic_staging_id(
        source_sha256=record["source_sha256"],
        question_number=record.get("question_number"),
        source_page=record.get("source_page"),
        stem=record.get("stem") or "",
        options=opts,
    )
    record = dict(record)
    record["staging_id"] = staging_id
    quality = classify_quality_p2_1c(record)
    record["p2_1c_quality_status"] = quality
    if quality == "INCORRECT_CANDIDATE":
        record["validation_status"] = ValidationStatus.NEEDS_REVIEW.value
    elif quality in {"PARTIAL", "DIAGRAM_DEPENDENT", "NEEDS_REVIEW"}:
        record["validation_status"] = ValidationStatus.NEEDS_REVIEW.value
    elif quality == "VALID":
        record["validation_status"] = ValidationStatus.EXTRACTED.value

    page = record.get("source_page")
    record["p2_1c_provenance"] = {
        "source_sha256": record.get("source_sha256"),
        "source_file": record.get("source_file"),
        "exam_year": record.get("exam_year"),
        "question_number": record.get("question_number"),
        "source_page": page,
        "staging_id": staging_id,
        "extraction_method": "geometry_first_ocr_pdf_layout",
        "geometry_column": record.get("geometry_column"),
        "geometry_layout": record.get("geometry_layout"),
        "source_ocr_artifact": "ocr.pages.p2_1.jsonl",
        "source_pdf_geometry": "zip_pdf_mediabox",
        "ocr_engine": ocr_meta.get("tesseract_executable_basename"),
        "ocr_version": ocr_meta.get("tesseract_version"),
        "dpi": ocr_meta.get("dpi"),
        "page_anomalies": page_anomalies.get(page or -1, []),
    }
    return record


def analyze_fragments(records: list[dict[str, Any]]) -> dict[str, int]:
    fragment = 0
    false_pos = 0
    for r in records:
        stem = (r.get("stem") or "").strip()
        filled = sum(1 for k in ("option_a", "option_b", "option_c", "option_d") if (r.get(k) or "").strip())
        if len(stem) < 20 and filled == 0:
            fragment += 1
        if not stem and filled <= 3:
            false_pos += 1
        if r.get("geometry_quality_flags") and any("impossible" in f for f in r["geometry_quality_flags"]):
            false_pos += 1
    return {"fragment_candidates": fragment, "false_positive_candidates": false_pos}


def build_p2_1c_samples(
    records: list[dict[str, Any]],
    layout_annotations: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    def preview(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_file": r.get("source_file"),
            "source_sha256": r.get("source_sha256"),
            "exam_year": r.get("exam_year"),
            "question_number": r.get("question_number"),
            "source_page": r.get("source_page"),
            "quality": r.get("p2_1c_quality_status"),
            "geometry_column": r.get("geometry_column"),
            "geometry_layout": r.get("geometry_layout"),
            "missing_options": r.get("missing_options"),
            "stem_preview": (r.get("stem") or "")[:160],
            "options_filled": sum(
                1 for k in ("option_a", "option_b", "option_c", "option_d") if (r.get(k) or "").strip()
            ),
            "geometry_flags": r.get("geometry_quality_flags") or [],
        }

    def take(items: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
        return [preview(x) for x in items[:n]]

    two_col = [r for r in records if r.get("geometry_layout") == PageLayout.TWO_COLUMN.value]
    one_col = [r for r in records if r.get("geometry_layout") == PageLayout.ONE_COLUMN.value]
    partial = [r for r in records if r.get("p2_1c_quality_status") == "PARTIAL"]
    diagram = [r for r in records if r.get("p2_1c_quality_status") == "DIAGRAM_DEPENDENT"]
    boundary = [
        r
        for r in records
        if r.get("source_page") in {1, 2} or (isinstance(r.get("source_page"), int) and r["source_page"] >= 30)
    ]
    instr = [r for r in records if r.get("p2_1c_quality_status") == "INCORRECT_CANDIDATE"]
    cross = [r for r in records if r.get("geometry_quality_flags")]

    # P2.1B-HR mandatory regression cases
    hr_failed: list[dict[str, Any]] = []
    for target in HR_REGRESSION_TARGETS:
        for r in records:
            if (
                r.get("source_sha256") == target["source_sha256"]
                and r.get("question_number") == target["question_number"]
                and r.get("source_page") == target["source_page"]
            ):
                hr_failed.append(preview(r))

    return {
        "two_column_20": take(two_col, 20),
        "hr_regression_mandatory": hr_failed,
        "partial_10": take(partial, 10),
        "diagram_dependent_10": take(diagram, 10),
        "page_boundary_10": take(boundary, 10),
        "instruction_false_positive_10": take(instr, 10),
        "one_column_10": take(one_col, 10),
        "cross_column_flagged_10": take(cross, 10),
    }


def evaluate_hr_regression(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for target in HR_REGRESSION_TARGETS:
        match = None
        for r in records:
            if (
                r.get("source_sha256") == target["source_sha256"]
                and r.get("question_number") == target["question_number"]
                and r.get("source_page") == target["source_page"]
            ):
                match = r
                break
        opts = []
        if match:
            opts = [match.get(f"option_{x}") or "" for x in "abcd"]
        forbidden_hits = [
            tok for tok in target["forbidden_option_tokens"] if any(tok.lower() in (o or "").lower() for o in opts)
        ]
        stem = (match.get("stem") or "").lower() if match else ""
        forbidden_stem_hits = [
            tok for tok in target.get("forbidden_stem_tokens") or [] if tok.lower() in stem
        ]
        cross_flags = detect_cross_column_contamination(match) if match else ["missing_record"]
        passed = (
            match is not None
            and not forbidden_hits
            and not forbidden_stem_hits
            and not any("cross_column" in f for f in cross_flags)
        )
        results.append(
            {
                "label": target["label"],
                "question_number": target["question_number"],
                "source_page": target["source_page"],
                "passed": passed,
                "forbidden_option_hits": forbidden_hits,
                "forbidden_stem_hits": forbidden_stem_hits,
                "cross_column_flags": cross_flags,
                "stem_preview": (match.get("stem") or "")[:120] if match else "",
                "options": opts,
            }
        )
    return results


def geometry_resegment_paper(
    paper_dir: Path,
    *,
    pdf_bytes: bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
    ocr_meta_path = paper_dir / "ocr.p2_1.json"
    ocr_meta = json.loads(ocr_meta_path.read_text(encoding="utf-8")) if ocr_meta_path.exists() else {}
    pages = annotate_rough_work_pages(load_ocr_pages(paper_dir))
    page_anomalies = {p["page_number"]: list(p.get("anomalies") or []) for p in pages}

    geometry_corpus, layout_annotations = build_geometry_corpus_from_pdf(pdf_bytes=pdf_bytes, pages=pages)
    raw_records = segment_questions_from_geometry_corpus(
        geometry_corpus, meta=meta, ocr_meta=ocr_meta
    )
    records = [
        enrich_geometry_record(r, ocr_meta=ocr_meta, page_anomalies=page_anomalies) for r in raw_records
    ]

    # Exclude rough-work pages
    records = [
        r
        for r in records
        if not (
            isinstance(r.get("source_page"), int)
            and any(
                p.get("page_number") == r["source_page"] and p.get("rough_work_blank_page") for p in pages
            )
        )
    ]

    layout_counts = Counter(a.get("layout") for a in layout_annotations)

    old_p2_1 = 0
    p2_1_path = paper_dir / "questions.p2_1.jsonl"
    if p2_1_path.exists():
        old_p2_1 = sum(1 for line in p2_1_path.open(encoding="utf-8") if line.strip())
    old_p2_1b = 0
    p2_1b_path = paper_dir / "questions.p2_1_resegmented.jsonl"
    if p2_1b_path.exists():
        old_p2_1b = sum(1 for line in p2_1b_path.open(encoding="utf-8") if line.strip())

    paper_report = {
        "source_sha256": meta["source_sha256"],
        "source_file": meta["source_file"],
        "exam_year": meta.get("exam_year"),
        "pages": len(pages),
        "rough_work_pages": sum(1 for p in pages if p.get("rough_work_blank_page")),
        "layout_one_column": layout_counts.get(PageLayout.ONE_COLUMN.value, 0),
        "layout_two_column": layout_counts.get(PageLayout.TWO_COLUMN.value, 0),
        "layout_unknown": layout_counts.get(PageLayout.UNKNOWN.value, 0),
        "old_p2_1_questions": old_p2_1,
        "old_p2_1b_questions": old_p2_1b,
        "new_questions": len(records),
        "quality": dict(Counter(r.get("p2_1c_quality_status") for r in records)),
    }

    out_path = paper_dir / "questions.p2_1c_geometry.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

    ann_path = paper_dir / "ocr.pages.p2_1c_geometry_annotations.json"
    ann_path.write_text(json.dumps(layout_annotations, indent=2, ensure_ascii=False), encoding="utf-8")

    corpus_path = paper_dir / "geometry.corpus.p2_1c.txt"
    corpus_path.write_text(geometry_corpus, encoding="utf-8")

    return records, paper_report, pages, layout_annotations


def run_geometry_resegment(
    staging_root: Path,
    zip_path: Path,
) -> tuple[GeometryResegmentSummary, dict[str, Any]]:
    selected = select_scanned_paper_dirs(staging_root)
    all_records: list[dict[str, Any]] = []
    paper_reports: list[dict[str, Any]] = []
    all_layout_annotations: list[dict[str, Any]] = []
    page_status = Counter()
    rough_work = 0
    old_p2_1_total = 0
    old_p2_1b_total = 0
    layout_totals = Counter()

    with zipfile.ZipFile(zip_path, "r") as zf:
        pdf_cache: dict[str, bytes] = {}
        for paper_dir in selected:
            meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            rel = meta["source_file"]
            if rel not in pdf_cache:
                pdf_cache[rel] = zf.read(rel)
            pdf_bytes = pdf_cache[rel]
            records, paper_report, pages, layout_ann = geometry_resegment_paper(
                paper_dir, pdf_bytes=pdf_bytes
            )
            all_records.extend(records)
            paper_reports.append(paper_report)
            all_layout_annotations.extend(
                [{**a, "source_sha256": meta["source_sha256"]} for a in layout_ann]
            )
            old_p2_1_total += paper_report["old_p2_1_questions"]
            old_p2_1b_total += paper_report["old_p2_1b_questions"]
            layout_totals[PageLayout.ONE_COLUMN.value] += paper_report["layout_one_column"]
            layout_totals[PageLayout.TWO_COLUMN.value] += paper_report["layout_two_column"]
            layout_totals[PageLayout.UNKNOWN.value] += paper_report["layout_unknown"]
            for p in pages:
                page_status[p.get("status") or "UNKNOWN"] += 1
                if p.get("rough_work_blank_page"):
                    rough_work += 1

    hash1 = canonical_questions_hash(
        [{**r, "p2_1b_quality_status": r.get("p2_1c_quality_status")} for r in all_records]
    )

    # Idempotency pass
    all_records_2: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        pdf_cache2: dict[str, bytes] = {}
        for paper_dir in selected:
            meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            rel = meta["source_file"]
            if rel not in pdf_cache2:
                pdf_cache2[rel] = zf.read(rel)
            recs, _, _, _ = geometry_resegment_paper(paper_dir, pdf_bytes=pdf_cache2[rel])
            all_records_2.extend(recs)
    hash2 = canonical_questions_hash(
        [{**r, "p2_1b_quality_status": r.get("p2_1c_quality_status")} for r in all_records_2]
    )

    auto_checks = run_automated_quality_checks(all_records)
    frag = analyze_fragments(all_records)
    hr_reg = evaluate_hr_regression(all_records)
    samples = build_p2_1c_samples(all_records, all_layout_annotations)
    quality = Counter(r.get("p2_1c_quality_status") for r in all_records)
    by_year = Counter(str(r.get("exam_year") or "unknown") for r in all_records)

    cross_flags = sum(1 for r in all_records if r.get("geometry_quality_flags"))
    new_count = len(all_records)

    # Verdict: never GREEN from count alone; HR regression must pass for YELLOW upgrade signal
    hr_pass = all(r["passed"] for r in hr_reg)
    verdict = "YELLOW"
    if (
        hash1 == hash2
        and hr_pass
        and cross_flags == 0
        and quality.get("VALID", 0) / max(new_count, 1) > 0.5
    ):
        verdict = "YELLOW"  # still not GREEN without human fidelity review
    if not hr_pass or cross_flags > 0:
        verdict = "YELLOW"

    summary = GeometryResegmentSummary(
        generated_at=datetime.now(UTC).isoformat(),
        mode="geometry-resegment",
        papers=len(selected),
        pages=sum(page_status.values()),
        layout_one_column=layout_totals[PageLayout.ONE_COLUMN.value],
        layout_two_column=layout_totals[PageLayout.TWO_COLUMN.value],
        layout_unknown=layout_totals[PageLayout.UNKNOWN.value],
        ocr_success=page_status.get(OCR_SUCCESS, 0),
        ocr_low_confidence=page_status.get(OCR_LOW_CONFIDENCE, 0),
        ocr_failed=page_status.get(OCR_FAILED, 0),
        ocr_needs_review_pages=page_status.get(NEEDS_REVIEW, 0),
        rough_work_blank_pages=rough_work,
        old_p2_1_count=old_p2_1_total,
        old_p2_1b_count=old_p2_1b_total,
        new_question_count=new_count,
        quality_valid=quality.get("VALID", 0),
        quality_needs_review=quality.get("NEEDS_REVIEW", 0),
        quality_partial=quality.get("PARTIAL", 0),
        quality_diagram_dependent=quality.get("DIAGRAM_DEPENDENT", 0),
        quality_incorrect_candidate=quality.get("INCORRECT_CANDIDATE", 0),
        cross_column_flags=cross_flags,
        duplicate_within_paper=sum(1 for r in all_records if r.get("duplicate_within_paper")),
        fragment_candidates=frag["fragment_candidates"],
        false_positive_candidates=frag["false_positive_candidates"],
        by_year=dict(by_year),
        questions_per_paper={pr["source_file"]: pr["new_questions"] for pr in paper_reports},
        idempotent=hash1 == hash2,
        corpus_hash_pass1=hash1,
        corpus_hash_pass2=hash2,
        verdict=verdict,
        safety={
            "ai_provider_calls": 0,
            "network_calls": 0,
            "production_db_writes": 0,
            "source_zip_modified": 0,
            "source_pdfs_modified": 0,
            "env_modified": 0,
            "tesseract_invocations": 0,
            "full_ocr_run": 0,
            "force_flag_used": 0,
            "p3_p4_p5_executed": 0,
        },
        automated_checks=auto_checks,
        hr_regression=hr_reg,
    )

    manifest = {
        "phase": "P2.1C",
        "mode": "geometry-resegment",
        "summary": asdict(summary),
        "paper_reports": paper_reports,
        "layout_annotations_sample": all_layout_annotations[:50],
        "samples": samples,
        "automated_checks": auto_checks,
        "hr_regression": hr_reg,
        "notes": [
            "ocr.pages.p2_1.jsonl was NOT modified",
            "questions written to questions.p2_1c_geometry.jsonl",
            "geometry.corpus.p2_1c.txt per paper for audit",
            "answers remain ANSWER_PENDING",
        ],
    }
    (staging_root / "manifest.p2_1c_geometry.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (staging_root / "samples.p2_1c_geometry.json").write_text(
        json.dumps(samples, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (staging_root / "checksums.p2_1c_geometry.json").write_text(
        json.dumps(
            {
                "corpus_hash_pass1": hash1,
                "corpus_hash_pass2": hash2,
                "idempotent": hash1 == hash2,
                "manifest_sha256": sha256_file(staging_root / "manifest.p2_1c_geometry.json"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return summary, manifest
