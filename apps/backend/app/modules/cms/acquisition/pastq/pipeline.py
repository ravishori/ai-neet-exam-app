"""End-to-end pastq dry-run / extract pipeline (no DB by default)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.modules.cms.acquisition.pastq.dedupe import classify_duplicates
from app.modules.cms.acquisition.pastq.enrich import detect_visual, enrich_paper_result
from app.modules.cms.acquisition.pastq.inventory import (
    DEFAULT_SOURCE_ROOT,
    inventory_source_root,
    inventory_to_dict,
    write_inventory_reports,
)
from app.modules.cms.acquisition.pastq.paper_meta import classify_filename, resolve_paper_meta
from app.modules.cms.acquisition.pastq.validate import (
    question_to_staging_record,
    validate_extracted_question,
)
from app.modules.cms.pyq.pyq_discovery import FileClassification, ZipFileEntry
from app.modules.cms.pyq.pyq_extraction import extract_paper

STAGING_DIR_DEFAULT = Path(r"D:\ravishori\AI Neet Exam App\data\staging\pastq_import_001")


def _entry_for_file(rec) -> ZipFileEntry:
    classification = FileClassification.NEET_QUESTION_PAPER
    kind = classify_filename(rec.filename)
    if kind == "SYLLABUS":
        classification = FileClassification.UNKNOWN
    elif kind == "ANSWER_KEY":
        classification = FileClassification.ANSWER_KEY
    year = None
    meta_probe = resolve_paper_meta(filename=rec.filename, corpus_sample="")
    if meta_probe.year is not None:
        year = str(meta_probe.year)
    return ZipFileEntry(
        relative_path=rec.relative_path,
        file_name=rec.filename,
        file_size=rec.file_size,
        compressed_size=rec.file_size,
        sha256=rec.sha256,
        year=year,
        classification=classification,
        paper_code=None,
        language=None,
        set_code=meta_probe.set_code,
    )


def run_pastq_pipeline(
    *,
    source_root: Path | str | None = None,
    staging_dir: Path | str | None = None,
    only_files: list[str] | None = None,
    write_inventory: bool = True,
    audit_dir: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(source_root or DEFAULT_SOURCE_ROOT)
    staging = Path(staging_dir or STAGING_DIR_DEFAULT)
    staging.mkdir(parents=True, exist_ok=True)
    audit = Path(audit_dir or r"D:\ravishori\AI Neet Exam App\docs\audits")

    inv = inventory_source_root(root)
    if write_inventory:
        write_inventory_reports(
            inv,
            md_path=audit / "pastq_import_001_source_inventory.md",
            json_path=audit / "pastq_import_001_source_inventory.json",
        )

    only = {f.lower() for f in (only_files or [])}
    papers_out: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    summary = {
        "files_discovered": inv.total_files,
        "files_readable": sum(1 for f in inv.files if f.readable),
        "files_failed": len(inv.unreadable),
        "papers_detected": 0,
        "papers_requiring_review": 0,
        "questions_extracted": 0,
        "questions_valid": 0,
        "questions_invalid": 0,
        "questions_requiring_review": 0,
        "questions_ready_for_import": 0,
        "answers_detected": 0,
        "answer_conflicts": 0,
        "visual_questions": 0,
        "duplicates": {},
        "years_detected": [],
        "subjects_detected": [],
        "scanned_ocr_required_files": [],
        "pilot_candidates": [],
    }

    years: set[int] = set()
    subjects: set[str] = set()

    for rec in inv.files:
        if only and rec.filename.lower() not in only and rec.relative_path.lower() not in only:
            continue
        if rec.extraction_status == "EXCLUDED_NON_PAPER":
            continue
        if rec.extension != ".pdf":
            continue

        path = Path(rec.absolute_path)
        pdf_bytes = path.read_bytes()
        # Integrity: re-hash must match inventory
        from app.modules.cms.pyq.pyq_discovery import sha256_bytes

        if sha256_bytes(pdf_bytes) != rec.sha256:
            papers_out.append(
                {
                    "source_file": rec.relative_path,
                    "error": "SHA256_MISMATCH_ON_READ",
                    "needs_review": True,
                }
            )
            continue

        entry = _entry_for_file(rec)
        result = extract_paper(entry, pdf_bytes)
        # Build corpus sample for meta from first pages text already in questions/raw
        sample = "\n".join(
            (q.raw_extracted_text or "")[:500] for q in result.questions[:5]
        )
        if not sample.strip():
            # fall back: open lightly
            import fitz

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                sample = "\n".join((doc.load_page(i).get_text() or "") for i in range(min(3, doc.page_count)))
            finally:
                doc.close()

        meta = resolve_paper_meta(filename=rec.filename, corpus_sample=sample)
        if meta.year is not None:
            entry.year = str(meta.year)
            result.exam_year = str(meta.year)
            years.add(meta.year)
        if meta.set_code:
            entry.set_code = meta.set_code
            result.set_code = meta.set_code

        enrich_stats = enrich_paper_result(result)
        summary["answer_conflicts"] += len(enrich_stats["answer_conflicts"])
        summary["visual_questions"] += enrich_stats["visual_questions"]

        if result.extraction_mode in {"SCANNED", "OCR_REQUIRED"} or rec.extraction_status.startswith("SCANNED"):
            summary["scanned_ocr_required_files"].append(rec.filename)

        summary["papers_detected"] += 1
        if meta.needs_review:
            summary["papers_requiring_review"] += 1

        paper_info = {
            "source_file": rec.relative_path,
            "sha256": rec.sha256,
            "page_count": result.page_count,
            "extraction_mode": result.extraction_mode,
            "extraction_confidence": result.extraction_confidence,
            "booklet_code": result.booklet_code,
            "meta": asdict(meta) if hasattr(meta, "__dataclass_fields__") else meta.__dict__,
            "question_count": len(result.questions),
            "enrich": enrich_stats,
            "ocr_required_pages": result.ocr_required_pages,
            "validation_anomalies": result.validation_anomalies,
        }
        papers_out.append(paper_info)

        for q in result.questions:
            # Skip pure OCR placeholder rows with empty stems when counting extracted content questions
            if q.validation_status == "OCR_REQUIRED" and not (q.stem or "").strip():
                summary["questions_requiring_review"] += 1
                continue
            summary["questions_extracted"] += 1
            if q.subject:
                subjects.add(q.subject)
            if q.answer_status == "ANSWER_KNOWN":
                summary["answers_detected"] += 1

            validation = validate_extracted_question(
                q,
                inventory_sha256=rec.sha256,
                paper_year=meta.year,
                paper_needs_review=meta.needs_review,
            )
            if validation.ok:
                summary["questions_valid"] += 1
            else:
                summary["questions_invalid"] += 1
            if validation.needs_review:
                summary["questions_requiring_review"] += 1
            if validation.ready_for_import:
                summary["questions_ready_for_import"] += 1

            visual = detect_visual(q)
            rec_out = question_to_staging_record(
                q,
                meta={
                    "exam_name": meta.exam_name,
                    "year": meta.year,
                    "year_source": meta.year_source,
                    "set_code": meta.set_code,
                    "set_source": meta.set_source,
                    "language": meta.language,
                    "needs_review": meta.needs_review,
                    "warnings": meta.warnings,
                },
                validation=validation,
                visual=visual,
                duplicate_class="UNIQUE",
            )
            records.append(rec_out)

    summary["duplicates"] = classify_duplicates(records)
    summary["years_detected"] = sorted(years)
    summary["subjects_detected"] = sorted(subjects)

    # Pilot candidates: recent + older + answered + visual + difficult OCR
    def _pick(pred, limit=3):
        out = []
        for r in records:
            if pred(r) and r["quality"].get("ready_for_import"):
                out.append(
                    {
                        "file": r["source"]["file"],
                        "year": r["paper"]["year"],
                        "q": r["question"]["number"],
                        "staging_id": r["hashes"]["staging_id"],
                    }
                )
            if len(out) >= limit:
                break
        return out

    summary["pilot_candidates"] = {
        "recent_ready": _pick(lambda r: (r["paper"].get("year") or 0) >= 2023),
        "older_ready": _pick(lambda r: (r["paper"].get("year") or 9999) <= 2018),
        "with_answer": _pick(lambda r: r["answer"].get("value")),
        "visual_flagged": [
            {
                "file": r["source"]["file"],
                "q": r["question"]["number"],
                "year": r["paper"]["year"],
            }
            for r in records
            if r.get("visual", {}).get("has_visual")
        ][:5],
        "ocr_files": summary["scanned_ocr_required_files"][:5],
    }

    # Write staging artifacts
    jsonl_path = staging / "questions.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (staging / "papers.json").write_text(json.dumps(papers_out, indent=2), encoding="utf-8")
    (staging / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (staging / "inventory_snapshot.json").write_text(
        json.dumps(inventory_to_dict(inv), indent=2), encoding="utf-8"
    )

    return {
        "inventory": inventory_to_dict(inv),
        "summary": summary,
        "papers": papers_out,
        "records": records,
        "staging_dir": str(staging),
        "jsonl_path": str(jsonl_path),
    }
