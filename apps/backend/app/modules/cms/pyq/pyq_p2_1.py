"""FACTORY-PYQ-P2.1 — OCR enablement and revalidation for SCANNED papers only."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.cms.pyq.pyq_discovery import FileClassification, ZipFileEntry, sha256_bytes
from app.modules.cms.pyq.pyq_extraction import (
    AnswerStatus,
    ValidationStatus,
    mark_within_paper_duplicates,
    question_hash,
    segment_questions_from_text,
)
from app.modules.cms.pyq.pyq_discovery import normalized_question_hash
from app.modules.cms.pyq.pyq_ocr import (
    OCR_FAILED,
    OCR_LOW_CONFIDENCE,
    OCR_SUCCESS,
    NEEDS_REVIEW,
    build_ocr_corpus,
    discover_tesseract,
    ocr_paper_to_dict,
    process_scanned_pdf,
)
from app.modules.cms.pyq.pyq_p2 import (
    NEET_2022_STATUS,
    attempt_missing_options_recovery,
    has_missing_options,
    load_p1_questions,
)


@dataclass
class P21Summary:
    generated_at: str
    tesseract_version: str | None
    tesseract_discovery: str | None
    ocr_engine: str
    dpi: int
    papers_targeted: int
    pages_targeted: int
    pages_processed: int
    ocr_success: int
    ocr_low_confidence: int
    ocr_failed: int
    ocr_needs_review: int
    questions_extracted_from_ocr: int
    questions_needs_review: int
    missing_options_before: int
    missing_options_resolved: int
    missing_options_still_missing: int
    missing_options_needs_review: int
    missing_options_ocr_failed: int
    answer_known: int
    answer_pending: int
    answer_conflict: int
    subject_unknown: int
    subject_classified: int
    mathematics_count: int
    neet_2022_status: str = NEET_2022_STATUS
    source_checksums_unchanged: bool = True
    zip_sha256_before: str = ""
    zip_sha256_after: str = ""
    staging_checksums: dict[str, str] = field(default_factory=dict)
    idempotent: bool = False
    verdict: str = "YELLOW"
    safety: dict[str, int] = field(default_factory=dict)


def _entry_from_paper_meta(meta: dict[str, Any]) -> ZipFileEntry:
    return ZipFileEntry(
        relative_path=meta["source_file"],
        file_name=Path(meta["source_file"]).name,
        file_size=0,
        compressed_size=0,
        sha256=meta["source_sha256"],
        year=meta.get("exam_year"),
        classification=FileClassification.NEET_QUESTION_PAPER,
        paper_code=meta.get("paper_code"),
        language=meta.get("language"),
        set_code=meta.get("set_code"),
        notes="",
    )


def select_scanned_paper_dirs(staging_root: Path) -> list[Path]:
    papers = staging_root / "papers"
    selected: list[Path] = []
    for paper_dir in sorted(papers.iterdir()):
        if not paper_dir.is_dir():
            continue
        meta_path = paper_dir / "paper.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        mode = meta.get("extraction_mode")
        anomalies = meta.get("validation_anomalies") or []
        if mode == "SCANNED" or "paper_requires_ocr" in anomalies:
            selected.append(paper_dir)
    return selected


def capture_source_checksums(zip_path: Path, relative_paths: list[str]) -> dict[str, str]:
    checksums: dict[str, str] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        for rel in relative_paths:
            checksums[rel] = sha256_bytes(zf.read(rel))
    return checksums


def extract_questions_from_ocr(
    *,
    corpus: str,
    meta: dict[str, Any],
    ocr_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    entry = _entry_from_paper_meta(meta)
    paper_id = meta.get("paper_id") or meta["source_sha256"][:16]
    questions = segment_questions_from_text(
        corpus,
        paper_id=paper_id,
        entry=entry,
        extraction_mode="OCR",
        extraction_confidence=0.55,
        ocr_pages=[],
    )
    mark_within_paper_duplicates(questions)

    records: list[dict[str, Any]] = []
    for q in questions:
        opts = [q.option_a, q.option_b, q.option_c, q.option_d]
        filled = sum(1 for o in opts if o.strip())
        missing = filled < 4
        status = q.validation_status
        review_reasons: list[str] = []
        if missing:
            status = ValidationStatus.NEEDS_REVIEW.value
            review_reasons.append("missing_options")
            review_reasons.append("possible_image_dependent_options")
        if not q.stem.strip():
            status = ValidationStatus.NEEDS_REVIEW.value
            review_reasons.append("empty_stem")

        record = {
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
            "extraction_mode": "OCR",
            "extraction_method": "tesseract_local_ocr",
            "extraction_confidence": q.extraction_confidence,
            "validation_status": status,
            "raw_extracted_text": q.raw_extracted_text,
            "duplicate_within_paper": q.duplicate_within_paper,
            "anomalies": list(q.anomalies) + review_reasons,
            "missing_options": missing,
            "p2_1_validation_status": status,
            "p2_answer_status": AnswerStatus.ANSWER_PENDING.value,
            "p2_subject": q.subject or "UNKNOWN",
            "p2_1_provenance": {
                "source_sha256": q.source_sha256,
                "source_file": q.source_file,
                "exam_year": q.exam_year,
                "paper_code": q.paper_code,
                "set_code": q.set_code,
                "question_number": q.question_number,
                "source_page": q.source_page,
                "staging_id": q.staging_id,
                "extraction_method": "tesseract_local_ocr",
                "ocr_engine": ocr_meta.get("tesseract_executable_basename"),
                "ocr_version": ocr_meta.get("tesseract_version"),
                "dpi": ocr_meta.get("dpi"),
            },
        }
        records.append(record)
    return records


def revalidate_missing_options(
    staging_root: Path,
    zip_path: Path,
    ocr_by_sha: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Revisit P1/P2 missing_options records; resolve only with deterministic evidence."""
    before = 0
    resolved = 0
    still_missing = 0
    needs_review = 0
    ocr_failed = 0
    details: list[dict[str, Any]] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        for paper_dir in sorted((staging_root / "papers").iterdir()):
            if not paper_dir.is_dir():
                continue
            meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            # Prefer P2 enriched file, else P1
            qpath = paper_dir / "questions.p2.jsonl"
            if not qpath.exists():
                qpath = paper_dir / "questions.jsonl"
            records = []
            with qpath.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        records.append(json.loads(line))

            missing = [r for r in records if has_missing_options(r) or r.get("missing_options")]
            # Also count P2 needs_review missing_options from validation.p2.json
            val_path = paper_dir / "validation.p2.json"
            p2_missing_ids: set[str] = set()
            if val_path.exists():
                val = json.loads(val_path.read_text(encoding="utf-8"))
                for item in val.get("missing_options") or []:
                    p2_missing_ids.add(item.get("staging_id") or "")
                    before += 1

            if not p2_missing_ids and missing:
                before += len(missing)
                p2_missing_ids = {r["staging_id"] for r in missing}

            if not p2_missing_ids:
                continue

            sha = meta["source_sha256"]
            full_text = ""
            if meta.get("extraction_mode") in {"TEXT", "MIXED"}:
                from app.modules.cms.pyq.pyq_extraction import build_tagged_corpus, extract_pages

                full_text = build_tagged_corpus(extract_pages(zf.read(meta["source_file"])))
            elif sha in ocr_by_sha:
                pages = ocr_by_sha[sha].get("pages") or []
                # Load raw text from companion pages file if present
                text_path = paper_dir / "ocr.pages.p2_1.jsonl"
                if text_path.exists():
                    chunks = []
                    with text_path.open(encoding="utf-8") as fh:
                        for line in fh:
                            page = json.loads(line)
                            chunks.append(f"<<<PAGE:{page['page_number']}>>>\n{page.get('raw_text','')}")
                    full_text = "\n".join(chunks)

            for record in records:
                if record.get("staging_id") not in p2_missing_ids and not has_missing_options(record):
                    continue
                if not has_missing_options(record) and record.get("staging_id") not in p2_missing_ids:
                    continue

                # Force check via recovery when text available
                if full_text and record.get("question_number") is not None:
                    result = attempt_missing_options_recovery(record, full_text)
                    status = result.status
                    if status == "resolved":
                        resolved += 1
                    elif status == "needs_review":
                        needs_review += 1
                    else:
                        still_missing += 1
                    details.append(
                        {
                            "staging_id": record["staging_id"],
                            "source_sha256": sha,
                            "question_number": record.get("question_number"),
                            "status": status,
                            "reason": result.reason,
                        }
                    )
                else:
                    if meta.get("extraction_mode") == "SCANNED" and sha not in ocr_by_sha:
                        ocr_failed += 1
                        status = "ocr_failed"
                    else:
                        needs_review += 1
                        status = "needs_review"
                    details.append(
                        {
                            "staging_id": record["staging_id"],
                            "source_sha256": sha,
                            "question_number": record.get("question_number"),
                            "status": status,
                            "reason": "diagram_or_no_recoverable_text",
                        }
                    )

    return {
        "before": before,
        "resolved": resolved,
        "still_missing": still_missing,
        "needs_review": needs_review,
        "ocr_failed": ocr_failed,
        "details": details,
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_p21_checksums(staging_root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in ("manifest.p2_1.json", "checksums.p2_1.json", "missing_options.p2_1.json"):
        path = staging_root / name
        if path.exists():
            out[name] = sha256_file(path)
    for paper_dir in sorted((staging_root / "papers").iterdir()):
        if not paper_dir.is_dir():
            continue
        for fname in ("ocr.p2_1.json", "questions.p2_1.jsonl", "ocr.pages.p2_1.jsonl"):
            path = paper_dir / fname
            if path.exists():
                out[f"papers/{paper_dir.name}/{fname}"] = sha256_file(path)
    return out


def process_scanned_paper_p21(
    paper_dir: Path,
    pdf_bytes: bytes,
    *,
    dpi: int,
    tesseract_path: str | None,
    force: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    """Returns (ocr_dict_with_text_meta, question_records, skipped_idempotent)."""
    meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
    ocr_path = paper_dir / "ocr.p2_1.json"
    pages_path = paper_dir / "ocr.pages.p2_1.jsonl"
    questions_path = paper_dir / "questions.p2_1.jsonl"

    if (
        not force
        and ocr_path.exists()
        and pages_path.exists()
        and questions_path.exists()
    ):
        existing = json.loads(ocr_path.read_text(encoding="utf-8"))
        if existing.get("pages_processed", 0) > 0 and existing.get("tesseract_available"):
            questions = []
            with questions_path.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        questions.append(json.loads(line))
            return existing, questions, True

    ocr_result = process_scanned_pdf(
        pdf_bytes,
        source_sha256=meta["source_sha256"],
        source_file=meta["source_file"],
        exam_year=meta.get("exam_year"),
        extraction_mode=meta.get("extraction_mode", "SCANNED"),
        target_pages=meta.get("ocr_required_pages") or None,
        dpi=dpi,
        tesseract_path=tesseract_path,
    )
    ocr_dict = ocr_paper_to_dict(ocr_result, include_text=False)
    # Persist page texts separately for extraction / review
    with pages_path.open("w", encoding="utf-8") as fh:
        for page in ocr_result.page_results:
            fh.write(
                json.dumps(
                    {
                        "page_number": page.page_number,
                        "status": page.status,
                        "validation_status": page.validation_status,
                        "ocr_confidence": page.ocr_confidence,
                        "text_chars": page.text_chars,
                        "raw_text": page.raw_text,
                        "anomalies": page.anomalies,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    corpus = build_ocr_corpus(ocr_result.page_results)
    questions = extract_questions_from_ocr(corpus=corpus, meta=meta, ocr_meta=ocr_dict)
    with questions_path.open("w", encoding="utf-8") as fh:
        for record in questions:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    ocr_path.write_text(json.dumps(ocr_dict, indent=2, ensure_ascii=False), encoding="utf-8")
    return ocr_dict, questions, False


def run_p21(
    staging_root: Path,
    zip_path: Path,
    *,
    dpi: int = 300,
    tesseract_path: str | None = None,
    force: bool = False,
) -> P21Summary:
    tess = discover_tesseract(tesseract_path)
    if not tess.available:
        raise RuntimeError(
            "Tesseract unavailable. Install local Tesseract or set TESSERACT_CMD. "
            f"anomalies={tess.anomalies}"
        )

    zip_sha_before = sha256_file(zip_path)
    selected = select_scanned_paper_dirs(staging_root)
    rels = []
    for paper_dir in selected:
        meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
        rels.append(meta["source_file"])
    checksums_before = capture_source_checksums(zip_path, rels)

    ocr_by_sha: dict[str, dict[str, Any]] = {}
    all_questions: list[dict[str, Any]] = []
    pages_processed = 0
    ocr_success = 0
    ocr_low = 0
    ocr_failed = 0
    ocr_review = 0
    skipped = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for idx, paper_dir in enumerate(selected, start=1):
            meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            print(
                f"[P2.1] ({idx}/{len(selected)}) OCR {meta.get('exam_year')} "
                f"{Path(meta['source_file']).name} ...",
                flush=True,
            )
            pdf_bytes = zf.read(meta["source_file"])
            # verify source sha matches paper.json
            digest = sha256_bytes(pdf_bytes)
            if digest != meta["source_sha256"]:
                raise RuntimeError(f"Source SHA mismatch for {meta['source_file']}")

            ocr_dict, questions, was_skipped = process_scanned_paper_p21(
                paper_dir,
                pdf_bytes,
                dpi=dpi,
                tesseract_path=tesseract_path or tess.executable,
                force=force,
            )
            if was_skipped:
                skipped += 1
                print(f"  skipped (idempotent cache)", flush=True)
            else:
                print(
                    f"  pages={ocr_dict.get('pages_processed')} "
                    f"success={ocr_dict.get('pages_success')} "
                    f"failed={ocr_dict.get('pages_failed')} "
                    f"questions={len(questions)}",
                    flush=True,
                )
            ocr_by_sha[meta["source_sha256"]] = ocr_dict
            all_questions.extend(questions)
            pages_processed += ocr_dict.get("pages_processed", 0)
            ocr_success += ocr_dict.get("pages_success", 0)
            ocr_low += ocr_dict.get("pages_low_confidence", 0)
            ocr_failed += ocr_dict.get("pages_failed", 0)
            ocr_review += ocr_dict.get("pages_needs_review", 0)

    checksums_after = capture_source_checksums(zip_path, rels)
    source_unchanged = checksums_before == checksums_after
    zip_sha_after = sha256_file(zip_path)

    missing = revalidate_missing_options(staging_root, zip_path, ocr_by_sha)
    (staging_root / "missing_options.p2_1.json").write_text(
        json.dumps(missing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    q_needs_review = sum(
        1
        for q in all_questions
        if q.get("validation_status") in {ValidationStatus.NEEDS_REVIEW.value, ValidationStatus.OCR_FAILED.value}
        or q.get("missing_options")
    )
    subject_unknown = sum(1 for q in all_questions if (q.get("p2_subject") or q.get("subject") or "UNKNOWN") == "UNKNOWN")
    subject_classified = sum(
        1
        for q in all_questions
        if (q.get("p2_subject") or q.get("subject")) in {"Physics", "Chemistry", "Botany", "Zoology", "Biology"}
    )
    math_count = sum(
        1
        for q in all_questions
        if (q.get("subject") or "").lower().startswith("math")
        or q.get("validation_status") == ValidationStatus.EXCLUDED_NON_NEET_SUBJECT.value
    )

    summary = P21Summary(
        generated_at=datetime.now(UTC).isoformat(),
        tesseract_version=tess.version,
        tesseract_discovery=tess.discovery_method,
        ocr_engine="tesseract",
        dpi=dpi,
        papers_targeted=len(selected),
        pages_targeted=pages_processed,
        pages_processed=pages_processed,
        ocr_success=ocr_success,
        ocr_low_confidence=ocr_low,
        ocr_failed=ocr_failed,
        ocr_needs_review=ocr_review,
        questions_extracted_from_ocr=len(all_questions),
        questions_needs_review=q_needs_review,
        missing_options_before=missing["before"],
        missing_options_resolved=missing["resolved"],
        missing_options_still_missing=missing["still_missing"],
        missing_options_needs_review=missing["needs_review"],
        missing_options_ocr_failed=missing["ocr_failed"],
        answer_known=sum(1 for q in all_questions if q.get("answer_status") == AnswerStatus.ANSWER_KNOWN.value),
        answer_pending=sum(1 for q in all_questions if q.get("answer_status") == AnswerStatus.ANSWER_PENDING.value),
        answer_conflict=sum(1 for q in all_questions if q.get("answer_status") == AnswerStatus.ANSWER_CONFLICT.value),
        subject_unknown=subject_unknown,
        subject_classified=subject_classified,
        mathematics_count=math_count,
        source_checksums_unchanged=source_unchanged and zip_sha_before == zip_sha_after,
        zip_sha256_before=zip_sha_before,
        zip_sha256_after=zip_sha_after,
        safety={
            "ai_provider_calls": 0,
            "gemini_calls": 0,
            "anthropic_calls": 0,
            "openai_calls": 0,
            "mistral_calls": 0,
            "content_factory_generation": 0,
            "production_db_writes": 0,
            "cms_pyq_tables": 0,
            "content_items_modified": 0,
            "content_versions_modified": 0,
            "knowledge_units_modified": 0,
            "ecaep_changes": 0,
            "publication_changes": 0,
            "original_zip_modified": 0,
            "original_pdfs_modified": 0,
            "env_modified": 0,
        },
    )

    # Idempotency: second pass should skip
    skipped2 = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for paper_dir in selected:
            meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            _, _, was_skipped = process_scanned_paper_p21(
                paper_dir,
                zf.read(meta["source_file"]),
                dpi=dpi,
                tesseract_path=tesseract_path or tess.executable,
                force=False,
            )
            if was_skipped:
                skipped2 += 1
    summary.idempotent = skipped2 == len(selected)

    staging_checksums = compute_p21_checksums(staging_root)
    summary.staging_checksums = staging_checksums

    # Verdict
    if not summary.source_checksums_unchanged:
        summary.verdict = "RED"
    elif ocr_failed == pages_processed and pages_processed > 0:
        summary.verdict = "RED"
    elif ocr_success > 0 and summary.idempotent and summary.source_checksums_unchanged:
        # Meaningful OCR gaps remain for diagram options / answer keys / 2022
        summary.verdict = "YELLOW" if (q_needs_review > 0 or ocr_failed > 0 or ocr_low > 0) else "GREEN"
    else:
        summary.verdict = "YELLOW"

    manifest = {
        "phase": "P2.1",
        "summary": asdict(summary),
        "source_pdf_checksums": checksums_after,
        "idempotency_skips_second_pass": skipped2,
        "first_pass_skips": skipped,
    }
    (staging_root / "manifest.p2_1.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (staging_root / "checksums.p2_1.json").write_text(
        json.dumps(
            {
                "zip_sha256": zip_sha_after,
                "source_pdfs": checksums_after,
                "staging": staging_checksums,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # refresh staging checksums after writing manifest
    summary.staging_checksums = compute_p21_checksums(staging_root)
    return summary
