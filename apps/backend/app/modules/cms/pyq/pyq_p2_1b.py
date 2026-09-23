"""FACTORY-PYQ-P2.1B — resegment-only refresh from existing OCR artifacts.

Consumes ocr.pages.p2_1.jsonl; does NOT invoke Tesseract; does NOT overwrite OCR evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.cms.pyq.pyq_extraction import (
    AnswerStatus,
    ValidationStatus,
)
from app.modules.cms.pyq.pyq_ocr import (
    NEEDS_REVIEW,
    OCR_FAILED,
    OCR_LOW_CONFIDENCE,
    OCR_SUCCESS,
)
from app.modules.cms.pyq.pyq_p2_1 import (
    extract_questions_from_ocr,
    select_scanned_paper_dirs,
    sha256_file,
)

INSTRUCTION_MARKERS = (
    "important instructions",
    "answer sheet is inside",
    "candidate must show",
    "do not open this test booklet",
    "read carefully the following instructions",
    "following instructions",
    "admit card",
    "attendance sheet",
    "unfair means",
    "space for rough work",
    "booklet code",
    "centre superintendent",
    "invigilator",
)

DIAGRAM_CUES = (
    "circuit",
    "diagram",
    "figure",
    "graph",
    "shown in the",
    "following figure",
    "as shown",
)


@dataclass
class ResegmentSummary:
    generated_at: str
    mode: str
    papers: int
    pages: int
    ocr_success: int
    ocr_low_confidence: int
    ocr_failed: int
    ocr_needs_review_pages: int
    rough_work_blank_pages: int
    old_question_count: int
    new_question_count: int
    delta: int
    quality_valid: int
    quality_needs_review: int
    quality_partial: int
    quality_diagram_dependent: int
    quality_incorrect_candidate: int
    missing_options: int
    duplicate_within_paper: int
    duplicate_qnum_within_paper: int
    fragment_candidates: int
    header_or_instruction_candidates: int
    answer_pending: int
    answer_known: int
    by_year: dict[str, int] = field(default_factory=dict)
    questions_per_paper: dict[str, int] = field(default_factory=dict)
    idempotent: bool = False
    corpus_hash_pass1: str = ""
    corpus_hash_pass2: str = ""
    verdict: str = "YELLOW"
    safety: dict[str, int] = field(default_factory=dict)


def deterministic_staging_id(
    *,
    source_sha256: str,
    question_number: int | None,
    source_page: int | None,
    stem: str,
    options: list[str],
) -> str:
    blob = "|".join(
        [
            source_sha256,
            str(question_number),
            str(source_page),
            re.sub(r"\s+", " ", (stem or "").strip().lower()),
            *[re.sub(r"\s+", " ", (o or "").strip().lower()) for o in options],
        ]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_ocr_pages(paper_dir: Path) -> list[dict[str, Any]]:
    path = paper_dir / "ocr.pages.p2_1.jsonl"
    pages: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                pages.append(json.loads(line))
    return pages


def annotate_rough_work_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate rough-work blanks without mutating original file contents on disk here."""
    out: list[dict[str, Any]] = []
    for page in pages:
        text = (page.get("raw_text") or "").strip()
        upper = text.upper()
        annotated = dict(page)
        if "SPACE FOR ROUGH WORK" in upper and len(text) < 120:
            annotated["rough_work_blank_page"] = True
            annotated["status"] = OCR_SUCCESS
            anomalies = list(annotated.get("anomalies") or [])
            if "rough_work_blank_page" not in anomalies:
                anomalies.append("rough_work_blank_page")
            annotated["anomalies"] = anomalies
        else:
            annotated["rough_work_blank_page"] = bool(annotated.get("rough_work_blank_page"))
        out.append(annotated)
    return out


def build_corpus_excluding_rough_work(pages: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for page in pages:
        if page.get("rough_work_blank_page"):
            # Keep page marker for provenance continuity but no text that could yield Qs.
            chunks.append(f"<<<PAGE:{page['page_number']}>>>\n")
            continue
        chunks.append(f"<<<PAGE:{page['page_number']}>>>\n{page.get('raw_text') or ''}")
    return "\n".join(chunks)


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


def classify_quality(record: dict[str, Any]) -> str:
    stem = record.get("stem") or ""
    raw = record.get("raw_extracted_text") or ""
    missing = bool(record.get("missing_options"))
    filled = sum(
        1
        for k in ("option_a", "option_b", "option_c", "option_d")
        if (record.get(k) or "").strip()
    )
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
    if filled == 4 and len(stem.strip()) >= 12:
        return "VALID"
    return "NEEDS_REVIEW"


def enrich_resegment_record(
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
    record["extraction_method"] = "resegment_only_from_ocr_pages_p2_1"
    record["p2_1b_mode"] = "resegment-only"
    record["answer_status"] = AnswerStatus.ANSWER_PENDING.value
    record["p2_answer_status"] = AnswerStatus.ANSWER_PENDING.value
    record["correct_option"] = None
    quality = classify_quality(record)
    record["p2_1b_quality_status"] = quality
    if quality == "INCORRECT_CANDIDATE":
        record["validation_status"] = ValidationStatus.NEEDS_REVIEW.value
        record.setdefault("anomalies", []).append("instruction_or_metadata_false_positive_candidate")
    elif quality in {"PARTIAL", "DIAGRAM_DEPENDENT", "NEEDS_REVIEW"}:
        record["validation_status"] = ValidationStatus.NEEDS_REVIEW.value
    elif quality == "VALID":
        record["validation_status"] = ValidationStatus.EXTRACTED.value

    page = record.get("source_page")
    record["p2_1_provenance"] = {
        "source_sha256": record.get("source_sha256"),
        "source_file": record.get("source_file"),
        "exam_year": record.get("exam_year"),
        "paper_code": record.get("paper_code"),
        "set_code": record.get("set_code"),
        "question_number": record.get("question_number"),
        "source_page": page,
        "staging_id": staging_id,
        "extraction_method": "resegment_only_from_ocr_pages_p2_1",
        "ocr_engine": ocr_meta.get("tesseract_executable_basename"),
        "ocr_version": ocr_meta.get("tesseract_version"),
        "dpi": ocr_meta.get("dpi"),
        "source_ocr_artifact": "ocr.pages.p2_1.jsonl",
        "page_anomalies": page_anomalies.get(page or -1, []),
    }
    return record


def canonical_questions_hash(records: list[dict[str, Any]]) -> str:
    # Hash without generated_at; sort by staging_id for stability.
    ordered = sorted(records, key=lambda r: r.get("staging_id") or "")
    slim = []
    for r in ordered:
        slim.append(
            {
                "staging_id": r.get("staging_id"),
                "source_sha256": r.get("source_sha256"),
                "question_number": r.get("question_number"),
                "source_page": r.get("source_page"),
                "stem": r.get("stem"),
                "option_a": r.get("option_a"),
                "option_b": r.get("option_b"),
                "option_c": r.get("option_c"),
                "option_d": r.get("option_d"),
                "validation_status": r.get("validation_status"),
                "p2_1b_quality_status": r.get("p2_1b_quality_status"),
                "missing_options": r.get("missing_options"),
            }
        )
    blob = "\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in slim)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def analyze_duplicates_and_fragments(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_paper_qnum: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    by_norm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    fragment = 0
    header_like = 0
    for r in records:
        sha = r.get("source_sha256") or ""
        qn = r.get("question_number")
        if isinstance(qn, int):
            by_paper_qnum[(sha, qn)].append(r)
        nh = r.get("normalized_question_hash") or ""
        if nh:
            by_norm[nh].append(r)
        stem = (r.get("stem") or "").strip()
        if len(stem) < 20 and not any((r.get(k) or "").strip() for k in ("option_a", "option_b", "option_c", "option_d")):
            fragment += 1
        if _looks_like_instruction(stem, r.get("raw_extracted_text") or ""):
            header_like += 1
        # Option-looking stems: mostly option markers
        if re.fullmatch(r"[\(\)\s1-4A-Dabcd\.\-]+", stem or ""):
            fragment += 1

    dup_qnum = sum(1 for items in by_paper_qnum.values() if len(items) > 1)
    dup_norm_within = 0
    for items in by_norm.values():
        papers = {i.get("source_sha256") for i in items}
        if len(items) > 1 and len(papers) == 1:
            dup_norm_within += len(items) - 1

    return {
        "duplicate_qnum_within_paper_groups": dup_qnum,
        "duplicate_normalized_within_paper_extra": dup_norm_within,
        "fragment_candidates": fragment,
        "header_or_instruction_candidates": header_like,
    }


def build_validation_samples(records: list[dict[str, Any]], pages_by_sha: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    def preview(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_file": r.get("source_file"),
            "source_sha256": r.get("source_sha256"),
            "exam_year": r.get("exam_year"),
            "question_number": r.get("question_number"),
            "source_page": r.get("source_page"),
            "quality": r.get("p2_1b_quality_status"),
            "missing_options": r.get("missing_options"),
            "stem_preview": (r.get("stem") or "")[:160],
            "options_filled": sum(
                1 for k in ("option_a", "option_b", "option_c", "option_d") if (r.get(k) or "").strip()
            ),
        }

    ordinary = [r for r in records if r.get("p2_1b_quality_status") == "VALID"]
    two_col = []
    no_period = []
    for r in records:
        sha = r.get("source_sha256") or ""
        page_no = r.get("source_page")
        page_text = ""
        for p in pages_by_sha.get(sha, []):
            if p.get("page_number") == page_no:
                page_text = p.get("raw_text") or ""
                break
        if " | " in page_text:
            two_col.append(r)
        raw = r.get("raw_extracted_text") or ""
        qn = r.get("question_number")
        if qn is not None and re.search(rf"(?m)^\s*{qn}\s+[A-Z(]", raw) and not re.search(
            rf"(?m)^\s*{qn}\.\s+", raw
        ):
            no_period.append(r)

    boundary = [r for r in records if r.get("source_page") in {1, 2} or (isinstance(r.get("source_page"), int) and r["source_page"] >= 30)]
    with_opts = [
        r
        for r in records
        if sum(1 for k in ("option_a", "option_b", "option_c", "option_d") if (r.get(k) or "").strip()) >= 3
    ]
    diagram = [r for r in records if r.get("p2_1b_quality_status") == "DIAGRAM_DEPENDENT"]
    bilingual = []
    for r in records:
        sha = r.get("source_sha256") or ""
        page_no = r.get("source_page")
        for p in pages_by_sha.get(sha, []):
            if p.get("page_number") == page_no:
                text = p.get("raw_text") or ""
                if re.search(r"[\u0900-\u097F]", text) or "instructions" in text.lower():
                    bilingual.append(r)
                break
    previously_missed = [r for r in records if isinstance(r.get("question_number"), int) and r["question_number"] > 50]

    def take(items: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
        return [preview(x) for x in items[:n]]

    return {
        "ordinary_20": take(ordinary, 20),
        "two_column_20": take(two_col, 20),
        "missing_period_10": take(no_period, 10),
        "page_boundary_10": take(boundary, 10),
        "with_options_10": take(with_opts, 10),
        "diagram_dependent_10": take(diagram, 10),
        "bilingual_instruction_10": take(bilingual, 10),
        "previously_missed_high_qnum_10": take(previously_missed, 10),
    }


def resegment_paper(paper_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
    ocr_meta_path = paper_dir / "ocr.p2_1.json"
    ocr_meta = json.loads(ocr_meta_path.read_text(encoding="utf-8")) if ocr_meta_path.exists() else {}
    pages = annotate_rough_work_pages(load_ocr_pages(paper_dir))
    page_anomalies = {p["page_number"]: list(p.get("anomalies") or []) for p in pages}
    corpus = build_corpus_excluding_rough_work(pages)

    # Reuse extraction; then replace staging ids / quality fields for P2.1B.
    raw_records = extract_questions_from_ocr(corpus=corpus, meta=meta, ocr_meta=ocr_meta)
    records = [
        enrich_resegment_record(r, ocr_meta=ocr_meta, page_anomalies=page_anomalies) for r in raw_records
    ]

    # Filter: rough-work pages must not generate questions (extra guard).
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

    paper_report = {
        "source_sha256": meta["source_sha256"],
        "source_file": meta["source_file"],
        "exam_year": meta.get("exam_year"),
        "pages": len(pages),
        "rough_work_pages": sum(1 for p in pages if p.get("rough_work_blank_page")),
        "old_questions": 0,
        "new_questions": len(records),
        "quality": dict(Counter(r.get("p2_1b_quality_status") for r in records)),
    }
    old_path = paper_dir / "questions.p2_1.jsonl"
    if old_path.exists():
        paper_report["old_questions"] = sum(1 for line in old_path.open(encoding="utf-8") if line.strip())

    out_path = paper_dir / "questions.p2_1_resegmented.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

    # Side annotation file for rough-work (does not overwrite ocr.pages.p2_1.jsonl)
    ann_path = paper_dir / "ocr.pages.p2_1b_annotations.json"
    ann_path.write_text(
        json.dumps(
            [
                {
                    "page_number": p["page_number"],
                    "status": p.get("status"),
                    "rough_work_blank_page": p.get("rough_work_blank_page", False),
                    "anomalies": p.get("anomalies") or [],
                    "text_chars": p.get("text_chars"),
                }
                for p in pages
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return records, paper_report, pages


def run_resegment_only(staging_root: Path) -> tuple[ResegmentSummary, dict[str, Any]]:
    selected = select_scanned_paper_dirs(staging_root)
    all_records: list[dict[str, Any]] = []
    paper_reports: list[dict[str, Any]] = []
    pages_by_sha: dict[str, list[dict[str, Any]]] = {}

    page_status = Counter()
    rough_work = 0
    old_total = 0

    for paper_dir in selected:
        records, paper_report, pages = resegment_paper(paper_dir)
        all_records.extend(records)
        paper_reports.append(paper_report)
        pages_by_sha[paper_report["source_sha256"]] = pages
        old_total += paper_report["old_questions"]
        for p in pages:
            page_status[p.get("status") or "UNKNOWN"] += 1
            if p.get("rough_work_blank_page"):
                rough_work += 1

    hash1 = canonical_questions_hash(all_records)

    # Idempotency: second pass
    all_records_2: list[dict[str, Any]] = []
    for paper_dir in selected:
        records2, _, _ = resegment_paper(paper_dir)
        all_records_2.extend(records2)
    hash2 = canonical_questions_hash(all_records_2)

    dup = analyze_duplicates_and_fragments(all_records)
    quality = Counter(r.get("p2_1b_quality_status") for r in all_records)
    by_year = Counter(str(r.get("exam_year") or "unknown") for r in all_records)
    per_paper = {pr["source_file"]: pr["new_questions"] for pr in paper_reports}

    samples = build_validation_samples(all_records, pages_by_sha)

    # Verdict: quantity alone insufficient
    valid = quality.get("VALID", 0)
    needs = quality.get("NEEDS_REVIEW", 0) + quality.get("PARTIAL", 0)
    incorrect = quality.get("INCORRECT_CANDIDATE", 0)
    new_count = len(all_records)
    verdict = "YELLOW"
    if (
        hash1 == hash2
        and new_count > old_total
        and valid > 0
        and incorrect / max(new_count, 1) < 0.05
        and needs / max(new_count, 1) < 0.35
    ):
        # Still YELLOW unless quality is strong — require low NEEDS_REVIEW share
        if needs / max(new_count, 1) < 0.15 and incorrect == 0:
            verdict = "GREEN"
        else:
            verdict = "YELLOW"

    summary = ResegmentSummary(
        generated_at=datetime.now(UTC).isoformat(),
        mode="resegment-only",
        papers=len(selected),
        pages=sum(page_status.values()),
        ocr_success=page_status.get(OCR_SUCCESS, 0),
        ocr_low_confidence=page_status.get(OCR_LOW_CONFIDENCE, 0),
        ocr_failed=page_status.get(OCR_FAILED, 0),
        ocr_needs_review_pages=page_status.get(NEEDS_REVIEW, 0),
        rough_work_blank_pages=rough_work,
        old_question_count=old_total,
        new_question_count=new_count,
        delta=new_count - old_total,
        quality_valid=valid,
        quality_needs_review=quality.get("NEEDS_REVIEW", 0),
        quality_partial=quality.get("PARTIAL", 0),
        quality_diagram_dependent=quality.get("DIAGRAM_DEPENDENT", 0),
        quality_incorrect_candidate=incorrect,
        missing_options=sum(1 for r in all_records if r.get("missing_options")),
        duplicate_within_paper=sum(1 for r in all_records if r.get("duplicate_within_paper")),
        duplicate_qnum_within_paper=dup["duplicate_qnum_within_paper_groups"],
        fragment_candidates=dup["fragment_candidates"],
        header_or_instruction_candidates=dup["header_or_instruction_candidates"],
        answer_pending=sum(1 for r in all_records if r.get("answer_status") == AnswerStatus.ANSWER_PENDING.value),
        answer_known=sum(1 for r in all_records if r.get("answer_status") == AnswerStatus.ANSWER_KNOWN.value),
        by_year=dict(by_year),
        questions_per_paper=per_paper,
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
            "p3_p4_p5_executed": 0,
        },
    )

    manifest = {
        "phase": "P2.1B",
        "mode": "resegment-only",
        "summary": asdict(summary),
        "paper_reports": paper_reports,
        "duplicate_analysis": dup,
        "samples": samples,
        "notes": [
            "ocr.pages.p2_1.jsonl was NOT modified",
            "questions written to questions.p2_1_resegmented.jsonl",
            "answers remain ANSWER_PENDING",
        ],
    }
    (staging_root / "manifest.p2_1b_resegment.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (staging_root / "samples.p2_1b.json").write_text(
        json.dumps(samples, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (staging_root / "checksums.p2_1b.json").write_text(
        json.dumps(
            {
                "corpus_hash_pass1": hash1,
                "corpus_hash_pass2": hash2,
                "idempotent": hash1 == hash2,
                "manifest_sha256": sha256_file(staging_root / "manifest.p2_1b_resegment.json"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return summary, manifest
