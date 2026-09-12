"""Write local PYQ staging artifacts (FACTORY-PYQ-P1). No database writes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.cms.pyq.pyq_extraction import (
    ExtractedQuestion,
    PaperExtractionResult,
    ValidationStatus,
)


@dataclass
class StagingManifest:
    generated_at: str
    zip_path: str
    zip_sha256: str
    staging_root: str
    papers_processed: int
    unique_papers: int
    total_question_records: int
    extracted_questions: int
    ocr_required_records: int
    answer_known: int
    answer_pending: int
    duplicate_within_paper: int
    cross_paper_repeats: int
    by_year: dict[str, int] = field(default_factory=dict)
    by_extraction_mode: dict[str, int] = field(default_factory=dict)
    by_subject: dict[str, int] = field(default_factory=dict)
    mathematics_exclusions: int = 0
    safety_attestation: dict[str, int] = field(default_factory=dict)


def default_staging_root(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[6]
    return root / "data" / "staging" / "pyq" / "2020-2025"


def question_to_record(question: ExtractedQuestion) -> dict[str, Any]:
    data = asdict(question)
    return data


def paper_metadata(result: PaperExtractionResult) -> dict[str, Any]:
    extracted = [
        q for q in result.questions if q.validation_status == ValidationStatus.EXTRACTED.value
    ]
    return {
        "paper_id": result.paper_id,
        "source_file": result.source_file,
        "source_sha256": result.source_sha256,
        "exam_year": result.exam_year,
        "paper_code": result.paper_code,
        "set_code": result.set_code,
        "language": result.language,
        "booklet_code": result.booklet_code,
        "page_count": result.page_count,
        "extraction_mode": result.extraction_mode,
        "extraction_confidence": result.extraction_confidence,
        "question_count_extracted": len(extracted),
        "ocr_required_pages": result.ocr_required_pages,
        "validation_anomalies": result.validation_anomalies,
        "mathematics_exclusions": result.mathematics_exclusions,
        "answer_key_hits": result.answer_key_hits,
    }


def extraction_report(result: PaperExtractionResult) -> dict[str, Any]:
    extracted = [
        q for q in result.questions if q.validation_status == ValidationStatus.EXTRACTED.value
    ]
    ocr = [q for q in result.questions if q.validation_status == ValidationStatus.OCR_REQUIRED.value]
    dupes = [q for q in result.questions if q.duplicate_within_paper]
    answer_known = [q for q in extracted if q.answer_status == "ANSWER_KNOWN"]
    return {
        "paper_id": result.paper_id,
        "source_file": result.source_file,
        "extraction_mode": result.extraction_mode,
        "extraction_confidence": result.extraction_confidence,
        "counts": {
            "extracted_questions": len(extracted),
            "ocr_required_records": len(ocr),
            "duplicate_within_paper": len(dupes),
            "answer_known": len(answer_known),
            "answer_pending": len(extracted) - len(answer_known),
        },
        "validation_anomalies": result.validation_anomalies,
        "ocr_required_pages": result.ocr_required_pages,
    }


def write_paper_staging(staging_root: Path, result: PaperExtractionResult) -> Path:
    paper_dir = staging_root / "papers" / result.source_sha256
    paper_dir.mkdir(parents=True, exist_ok=True)

    (paper_dir / "paper.json").write_text(
        json.dumps(paper_metadata(result), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with (paper_dir / "questions.jsonl").open("w", encoding="utf-8") as fh:
        for question in result.questions:
            fh.write(json.dumps(question_to_record(question), ensure_ascii=False) + "\n")
    (paper_dir / "extraction_report.json").write_text(
        json.dumps(extraction_report(result), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return paper_dir


def compute_cross_paper_repeats(all_questions: list[ExtractedQuestion]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for q in all_questions:
        if not q.normalized_question_hash or q.validation_status != ValidationStatus.EXTRACTED.value:
            continue
        index.setdefault(q.normalized_question_hash, []).append(q.paper_id)
    return {h: papers for h, papers in index.items() if len(set(papers)) > 1}


def write_manifest(
    staging_root: Path,
    *,
    zip_path: str,
    zip_sha256: str,
    results: list[PaperExtractionResult],
    cross_paper_repeats: dict[str, list[str]],
) -> StagingManifest:
    all_questions = [q for r in results for q in r.questions]
    extracted = [
        q for q in all_questions if q.validation_status == ValidationStatus.EXTRACTED.value
    ]
    ocr = [q for q in all_questions if q.validation_status == ValidationStatus.OCR_REQUIRED.value]

    by_year: dict[str, int] = {}
    by_mode: dict[str, int] = {}
    by_subject: dict[str, int] = {}
    for r in results:
        year = r.exam_year or "unknown"
        by_year[year] = by_year.get(year, 0) + len(
            [q for q in r.questions if q.validation_status == ValidationStatus.EXTRACTED.value]
        )
        by_mode[r.extraction_mode] = by_mode.get(r.extraction_mode, 0) + 1
    for q in extracted:
        subj = q.subject or "unknown"
        by_subject[subj] = by_subject.get(subj, 0) + 1

    manifest = StagingManifest(
        generated_at=datetime.now(UTC).isoformat(),
        zip_path=zip_path,
        zip_sha256=zip_sha256,
        staging_root=str(staging_root),
        papers_processed=len(results),
        unique_papers=len({r.source_sha256 for r in results}),
        total_question_records=len(all_questions),
        extracted_questions=len(extracted),
        ocr_required_records=len(ocr),
        answer_known=sum(1 for q in extracted if q.answer_status == "ANSWER_KNOWN"),
        answer_pending=sum(1 for q in extracted if q.answer_status == "ANSWER_PENDING"),
        duplicate_within_paper=sum(1 for q in all_questions if q.duplicate_within_paper),
        cross_paper_repeats=len(cross_paper_repeats),
        by_year=by_year,
        by_extraction_mode=by_mode,
        by_subject=by_subject,
        mathematics_exclusions=sum(r.mathematics_exclusions for r in results),
        safety_attestation={
            "ai_provider_calls": 0,
            "generation_calls": 0,
            "database_writes": 0,
            "content_items_modified": 0,
            "content_versions_modified": 0,
            "knowledge_units_modified": 0,
            "ecaep_changes": 0,
            "publication_changes": 0,
            "source_zip_modified": 0,
        },
    )
    staging_root.mkdir(parents=True, exist_ok=True)
    (staging_root / "manifest.json").write_text(
        json.dumps(asdict(manifest), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (staging_root / "cross_paper_repeats.json").write_text(
        json.dumps(cross_paper_repeats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest
