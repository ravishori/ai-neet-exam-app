"""PASTQ-OCR-002 — OCR staging for scanned PastQuestionPapers (no production import)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.cms.acquisition.pastq.dedupe import classify_duplicates
from app.modules.cms.acquisition.pastq.enrich import (
    detect_visual,
    enrich_inline_answers,
    map_option_to_letter,
    repair_letter_options,
)
from app.modules.cms.acquisition.pastq.inventory import inventory_source_root
from app.modules.cms.acquisition.pastq.paper_meta import resolve_paper_meta
from app.modules.cms.acquisition.pastq.validate import (
    question_to_staging_record,
    validate_extracted_question,
)
from app.modules.cms.pyq.pyq_discovery import FileClassification, ZipFileEntry, sha256_bytes, sha256_file
from app.modules.cms.pyq.pyq_extraction import (
    AnswerStatus,
    ValidationStatus,
    authoritative_answers,
    mark_within_paper_duplicates,
    normalize_ocr_corpus,
    segment_questions_from_text,
)
from app.modules.cms.pyq.pyq_ocr import (
    build_ocr_corpus,
    discover_tesseract,
    ocr_paper_to_dict,
    process_scanned_pdf,
)

DEFAULT_SOURCE_ROOT = Path(r"D:\ravishori\AI Neet Exam App\PastQuestionPapers")
DEFAULT_STAGING = Path(r"D:\ravishori\AI Neet Exam App\data\staging\pastq_ocr_002")

# Exact seven from PASTQ-IMPORT-001 scanned_ocr_required_files
SCANNED_FILENAMES = (
    "NEET2015.pdf",
    "NEET2017.pdf",
    "NEET2021.pdf",
    "Neet2022.pdf",
    "NEET2026-11.pdf",
    "Neet2026-12.pdf",
    "RENeet2026.pdf",
)

OCR_CORRUPTION_RE = re.compile(r"[\ufffd\uf0b4\uf02d□■�]|[|]{3,}")
MERGED_Q_RE = re.compile(r"(?m)^\s*\d{1,3}\.\s+.+\n\s*\d{1,3}\.\s+")
# OCR-tolerant answer-key section + grid (still requires explicit key header + dense grid)
OCR_ANSWER_KEY_SECTION_RE = re.compile(
    r"(?mi)^\s*(?:answer\s*key|key\s*to\s*(?:the\s*)?questions|official\s*answers?)\s*:?\s*$"
)
OCR_ANSWER_GRID_RE = re.compile(
    r"(?m)^\s*(\d{1,3})\s*[\).:\-]\s*\(?\s*([1-4A-Da-d])\s*\)?\s*$"
)


@dataclass
class OcrStagingSummary:
    generated_at: str
    ocr_engine: str | None
    tesseract_version: str | None
    dpi: int
    scanned_targeted: int = 0
    pages_processed: int = 0
    pages_success: int = 0
    pages_low_confidence: int = 0
    pages_failed: int = 0
    pages_needs_review: int = 0
    questions_extracted: int = 0
    questions_staged: int = 0
    ocr_review_required: int = 0
    answer_review_required: int = 0
    visual_review_required: int = 0
    answers_known: int = 0
    answer_conflicts: int = 0
    answer_pending: int = 0
    duplicates: dict[str, int] = field(default_factory=dict)
    source_checksums_unchanged: bool = True
    idempotent_cache_hits: int = 0
    papers: list[dict[str, Any]] = field(default_factory=list)
    pilot_sample: list[dict[str, Any]] = field(default_factory=list)
    staging_dir: str = ""
    anomalies: list[str] = field(default_factory=list)


def list_scanned_from_inventory(source_root: Path) -> list[dict[str, Any]]:
    inv = inventory_source_root(source_root)
    wanted = {n.lower() for n in SCANNED_FILENAMES}
    out = []
    for f in inv.files:
        if f.filename.lower() not in wanted:
            continue
        out.append(
            {
                "filename": f.filename,
                "relative_path": f.relative_path,
                "absolute_path": f.absolute_path,
                "sha256": f.sha256,
                "page_count": f.page_count,
                "extraction_status": f.extraction_status,
                "ocr_required_reason": "; ".join(f.notes) or f.extraction_status,
                "file_size": f.file_size,
                "sample_chars": f.sample_chars,
            }
        )
    # Preserve documented order
    order = {n.lower(): i for i, n in enumerate(SCANNED_FILENAMES)}
    out.sort(key=lambda x: order.get(x["filename"].lower(), 99))
    return out


def _paper_dir(staging: Path, sha256: str) -> Path:
    d = staging / "papers" / sha256[:16]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_cached(paper_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    ocr_path = paper_dir / "ocr_meta.json"
    q_path = paper_dir / "questions.jsonl"
    if not (ocr_path.exists() and q_path.exists()):
        return None
    meta = json.loads(ocr_path.read_text(encoding="utf-8"))
    if meta.get("pages_processed", 0) <= 0:
        return None
    questions = []
    with q_path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                questions.append(json.loads(line))
    return meta, questions


def _detect_ocr_corruption(text: str) -> list[str]:
    flags: list[str] = []
    if OCR_CORRUPTION_RE.search(text or ""):
        flags.append("OCR_CORRUPTION_SYMBOLS")
    if MERGED_Q_RE.search(text or ""):
        flags.append("POSSIBLE_QUESTION_CONCATENATION")
    return flags


def _ocr_authoritative_answers(corpus: str) -> dict[int, dict[str, Any]]:
    """Like pyq authoritative_answers, with OCR-tolerant section/grid patterns.

    Safety: only inside explicit answer-key headings; require dense grids (>=8 hits).
    Never invent answers outside those regions.
    """
    from app.modules.cms.pyq.pyq_extraction import page_for_position

    base = authoritative_answers(corpus)
    answers = dict(base)
    regions: list[tuple[int, int]] = []
    for match in OCR_ANSWER_KEY_SECTION_RE.finditer(corpus):
        start = match.start()
        regions.append((start, min(len(corpus), start + 10000)))
    for region_start, region_end in regions:
        region = corpus[region_start:region_end]
        grid_hits: list[tuple[int, str, int]] = []
        for match in OCR_ANSWER_GRID_RE.finditer(region):
            qn = int(match.group(1))
            opt = match.group(2).upper()
            if opt in {"A", "B", "C", "D"}:
                mapped = {"A": "1", "B": "2", "C": "3", "D": "4"}[opt]
            elif opt in {"1", "2", "3", "4"}:
                mapped = opt
            else:
                continue
            grid_hits.append((qn, mapped, region_start + match.start()))
        if len(grid_hits) < 8:
            continue
        for qn, mapped, abs_pos in grid_hits:
            if qn in answers:
                # Conflict across detectors → leave for conflict handler below
                if answers[qn]["correct_option"] != mapped:
                    answers[qn] = {
                        **answers[qn],
                        "conflict_alt": mapped,
                        "answer_confidence": None,
                    }
                continue
            answers[qn] = {
                "correct_option": mapped,
                "answer_source": "ocr_embedded_answer_grid",
                "answer_source_page": page_for_position(corpus, abs_pos),
                "answer_confidence": None,  # engine did not provide answer confidence
            }
    return answers


def _associate_answers_from_corpus(questions: list, corpus: str) -> list[dict[str, Any]]:
    """Apply grid answers only from authoritative answer-key regions + inline Ans."""
    conflicts = enrich_inline_answers(questions)
    grid = _ocr_authoritative_answers(corpus)
    for q in questions:
        if q.question_number is None:
            continue
        hit = grid.get(q.question_number)
        if not hit:
            continue
        if hit.get("conflict_alt"):
            q.answer_status = AnswerStatus.ANSWER_CONFLICT.value
            q.anomalies.append("answer_key_detector_conflict")
            conflicts.append(
                {
                    "question_number": q.question_number,
                    "source_file": q.source_file,
                    "values": [hit["correct_option"], hit["conflict_alt"]],
                }
            )
            continue
        mapped = hit["correct_option"]  # 1-4
        existing = map_option_to_letter(q.correct_option)
        mapped_letter = map_option_to_letter(mapped)
        if existing and mapped_letter and existing != mapped_letter:
            q.answer_status = AnswerStatus.ANSWER_CONFLICT.value
            q.anomalies.append("grid_vs_existing_answer_conflict")
            conflicts.append(
                {
                    "question_number": q.question_number,
                    "source_file": q.source_file,
                    "values": [existing, mapped_letter],
                }
            )
            continue
        if not q.correct_option:
            q.correct_option = mapped
            q.answer_status = AnswerStatus.ANSWER_KNOWN.value
            q.answer_source = hit.get("answer_source") or "embedded_answer_grid"
            q.answer_source_page = hit.get("answer_source_page")
    return conflicts


def stage_one_scanned_pdf(
    *,
    absolute_path: Path,
    filename: str,
    expected_sha256: str,
    staging: Path,
    dpi: int = 300,
    force: bool = False,
    tesseract_path: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    """OCR + segment one PDF into staging. Returns (ocr_meta, staged_records, cache_hit)."""
    pdf_bytes = absolute_path.read_bytes()
    digest = sha256_bytes(pdf_bytes)
    if digest != expected_sha256:
        raise RuntimeError(f"SHA256_MISMATCH for {filename}: source may have changed")

    paper_dir = _paper_dir(staging, digest)
    if not force:
        cached = _load_cached(paper_dir)
        if cached is not None:
            return cached[0], cached[1], True

    # Sample text for meta (may be empty pre-OCR)
    meta_pre = resolve_paper_meta(filename=filename, corpus_sample="")
    ocr_result = process_scanned_pdf(
        pdf_bytes,
        source_sha256=digest,
        source_file=filename,
        exam_year=str(meta_pre.year) if meta_pre.year else None,
        extraction_mode="SCANNED",
        target_pages=None,
        dpi=dpi,
        tesseract_path=tesseract_path,
    )
    ocr_dict = ocr_paper_to_dict(ocr_result, include_text=False)
    ocr_dict["filename"] = filename
    ocr_dict["source_absolute_path"] = str(absolute_path)

    pages_path = paper_dir / "pages.jsonl"
    with pages_path.open("w", encoding="utf-8") as fh:
        for page in ocr_result.page_results:
            fh.write(
                json.dumps(
                    {
                        "page_number": page.page_number,
                        "status": page.status,
                        "validation_status": page.validation_status,
                        "ocr_engine": page.ocr_engine,
                        "ocr_version": page.ocr_version,
                        "ocr_confidence": page.ocr_confidence,
                        "text_chars": page.text_chars,
                        "raw_text": page.raw_text,
                        "anomalies": page.anomalies,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    corpus = normalize_ocr_corpus(build_ocr_corpus(ocr_result.page_results))
    meta = resolve_paper_meta(filename=filename, corpus_sample=corpus[:8000])
    if meta.year is not None:
        ocr_dict["exam_year"] = str(meta.year)
    ocr_dict["paper_meta"] = asdict(meta)

    entry = ZipFileEntry(
        relative_path=filename,
        file_name=filename,
        file_size=len(pdf_bytes),
        compressed_size=len(pdf_bytes),
        sha256=digest,
        year=str(meta.year) if meta.year else None,
        classification=FileClassification.NEET_QUESTION_PAPER,
        set_code=meta.set_code,
        language=meta.language,
    )
    paper_id = digest[:16]
    # Average page confidence when available (engine-provided only)
    confs = [p.ocr_confidence for p in ocr_result.page_results if p.ocr_confidence is not None]
    extraction_confidence = (sum(confs) / len(confs) / 100.0) if confs else 0.55

    questions = segment_questions_from_text(
        corpus,
        paper_id=paper_id,
        entry=entry,
        extraction_mode="OCR",
        extraction_confidence=min(0.85, max(0.2, extraction_confidence)),
        ocr_pages=[],
    )
    mark_within_paper_duplicates(questions)
    repair_letter_options(questions)
    conflicts = _associate_answers_from_corpus(questions, corpus)

    staged: list[dict[str, Any]] = []
    for q in questions:
        # Force OCR extraction mode labels
        q.extraction_mode = "OCR"
        vis = detect_visual(q)
        if vis["has_visual"]:
            q.anomalies.append("VISUAL_REVIEW_REQUIRED")
        corrupt = _detect_ocr_corruption((q.raw_extracted_text or "") + " " + (q.stem or ""))
        for c in corrupt:
            if c not in q.anomalies:
                q.anomalies.append(c)
            if c == "OCR_CORRUPTION_SYMBOLS":
                q.anomalies.append("OCR_REVIEW_REQUIRED")

        validation = validate_extracted_question(
            q,
            inventory_sha256=digest,
            paper_year=meta.year,
            paper_needs_review=meta.needs_review or True,  # OCR always review-leaning
        )
        # OCR path: never auto READY_FOR_IMPORT into production this task
        validation.ready_for_import = False
        if not q.correct_option:
            validation.warnings.append("ANSWER_REVIEW_REQUIRED")
            validation.needs_review = True
        if "OCR_REVIEW_REQUIRED" in q.anomalies or corrupt:
            validation.warnings.append("OCR_REVIEW_REQUIRED")
            validation.needs_review = True
        if vis["has_visual"]:
            validation.warnings.append("VISUAL_REVIEW_REQUIRED")

        # Staging status taxonomy
        statuses = []
        if "OCR_REVIEW_REQUIRED" in validation.warnings or "OCR_CORRUPTION_SYMBOLS" in q.anomalies:
            statuses.append("OCR_REVIEW_REQUIRED")
        if "ANSWER_REVIEW_REQUIRED" in validation.warnings or q.answer_status == "ANSWER_PENDING":
            statuses.append("ANSWER_REVIEW_REQUIRED")
        if "VISUAL_REVIEW_REQUIRED" in validation.warnings:
            statuses.append("VISUAL_REVIEW_REQUIRED")
        if meta.needs_review or meta.year is None:
            statuses.append("METADATA_REVIEW_REQUIRED")
        if validation.errors:
            statuses.append("OCR_REVIEW_REQUIRED")
        staging_status = statuses[0] if statuses else "READY_FOR_REVIEW"

        rec = question_to_staging_record(
            q,
            meta={
                "exam_name": meta.exam_name,
                "year": meta.year,
                "year_source": meta.year_source,
                "set_code": meta.set_code,
                "set_source": meta.set_source,
                "language": meta.language,
                "needs_review": True,
                "warnings": meta.warnings,
            },
            validation=validation,
            visual=vis,
            duplicate_class="UNIQUE",
        )
        rec["quality"]["staging_status"] = staging_status
        rec["quality"]["ocr_engine"] = ocr_dict.get("tesseract_version") and "tesseract"
        rec["quality"]["ocr_version"] = ocr_dict.get("tesseract_version")
        # Prefer page-level confidence when question page known
        page_conf = None
        if q.source_page:
            for p in ocr_result.page_results:
                if p.page_number == q.source_page and p.ocr_confidence is not None:
                    page_conf = p.ocr_confidence
                    break
        rec["quality"]["ocr_confidence"] = page_conf
        rec["provenance"]["origin"] = "past_question_paper"
        rec["provenance"]["ncert_derived"] = False
        rec["extraction"] = {
            "method": "tesseract_local_ocr",
            "mode": "OCR",
            "dpi": dpi,
        }
        staged.append(rec)

    # Persist
    (paper_dir / "paper.json").write_text(
        json.dumps(
            {
                "filename": filename,
                "source_sha256": digest,
                "source_file": filename,
                "page_count": ocr_dict.get("pages_processed"),
                "paper_meta": asdict(meta),
                "answer_conflicts": conflicts,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (paper_dir / "ocr_meta.json").write_text(json.dumps(ocr_dict, indent=2), encoding="utf-8")
    with (paper_dir / "questions.jsonl").open("w", encoding="utf-8") as fh:
        for rec in staged:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return ocr_dict, staged, False


def select_pilot_sample(records: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    """Human-reviewable sample — staging only, not import.

    Reserves diversity slots rather than greedily filling from one paper.
    """
    picked: list[dict[str, Any]] = []

    def _preview(r: dict[str, Any]) -> str:
        return (r["question"].get("stem") or "").strip()

    def _ok_stem(r: dict[str, Any]) -> bool:
        s = _preview(r)
        if len(s) < 25:
            return False
        if s.lower() in {"ans.", "ans", "answer"}:
            return False
        return True

    def _pack(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "file": r["source"]["file"],
            "year": r["paper"].get("year"),
            "q": r["question"].get("number"),
            "subject": r["question"].get("subject"),
            "staging_status": r["quality"].get("staging_status"),
            "answer": r["answer"].get("value"),
            "has_visual": r.get("visual", {}).get("has_visual"),
            "stem_preview": _preview(r)[:160],
            "staging_id": r["hashes"].get("staging_id"),
            "page": r["source"].get("page_start"),
        }

    def _seen(r: dict[str, Any]) -> bool:
        sid = r.get("hashes", {}).get("staging_id")
        return any(p.get("staging_id") == sid for p in picked)

    def take_one(pred) -> bool:
        if len(picked) >= limit:
            return False
        for r in records:
            if _seen(r) or not _ok_stem(r):
                continue
            if pred(r):
                picked.append(_pack(r))
                return True
        return False

    # Explicit reserved slots for review packet diversity
    take_one(lambda r: bool(r["answer"].get("value")) and not r.get("visual", {}).get("has_visual"))
    take_one(lambda r: bool(r.get("visual", {}).get("has_visual")))
    take_one(
        lambda r: bool(
            re.search(
                r"[α-ωΑ-Ω]|H[_2]|CO[_2]|°|×|÷|√|∫|→|mol|force|velocity|enzyme|circuit",
                (_preview(r) + str(r["question"].get("options"))).lower(),
            )
        )
    )
    used_files = {p["file"] for p in picked}
    take_one(lambda r: r["source"]["file"] not in used_files)
    take_one(
        lambda r: (r["question"].get("subject") or "").lower()
        in {"physics", "chemistry", "biology", "botany", "zoology"}
    )
    while len(picked) < limit:
        if not take_one(lambda r: True):
            break
    return picked[:limit]


def run_ocr_staging(
    *,
    source_root: Path | str | None = None,
    staging_dir: Path | str | None = None,
    dpi: int = 300,
    force: bool = False,
    only: list[str] | None = None,
) -> OcrStagingSummary:
    root = Path(source_root or DEFAULT_SOURCE_ROOT)
    staging = Path(staging_dir or DEFAULT_STAGING)
    staging.mkdir(parents=True, exist_ok=True)

    tess = discover_tesseract()
    summary = OcrStagingSummary(
        generated_at=datetime.now(UTC).isoformat(),
        ocr_engine="tesseract" if tess.available else None,
        tesseract_version=tess.version,
        dpi=dpi,
        staging_dir=str(staging),
    )
    if not tess.available:
        summary.anomalies.append("tesseract_unavailable")
        summary.anomalies.extend(tess.anomalies)
        return summary

    scanned = list_scanned_from_inventory(root)
    if only:
        only_l = {x.lower() for x in only}
        scanned = [s for s in scanned if s["filename"].lower() in only_l]
    summary.scanned_targeted = len(scanned)

    all_records: list[dict[str, Any]] = []
    sha_before: dict[str, str] = {}

    for idx, item in enumerate(scanned, start=1):
        path = Path(item["absolute_path"])
        sha_before[item["filename"]] = item["sha256"]
        print(f"[PASTQ-OCR-002] ({idx}/{len(scanned)}) OCR {item['filename']} ...", flush=True)
        ocr_meta, records, cache_hit = stage_one_scanned_pdf(
            absolute_path=path,
            filename=item["filename"],
            expected_sha256=item["sha256"],
            staging=staging,
            dpi=dpi,
            force=force,
        )
        if cache_hit:
            summary.idempotent_cache_hits += 1
        # Verify source immutable
        after = sha256_file(path)
        if after != item["sha256"]:
            summary.source_checksums_unchanged = False
            summary.anomalies.append(f"source_changed:{item['filename']}")

        summary.pages_processed += int(ocr_meta.get("pages_processed") or 0)
        summary.pages_success += int(ocr_meta.get("pages_success") or 0)
        summary.pages_low_confidence += int(ocr_meta.get("pages_low_confidence") or 0)
        summary.pages_failed += int(ocr_meta.get("pages_failed") or 0)
        summary.pages_needs_review += int(ocr_meta.get("pages_needs_review") or 0)
        summary.questions_extracted += len(records)
        summary.questions_staged += len(records)

        paper_stats = {
            "filename": item["filename"],
            "sha256": item["sha256"],
            "page_count": item["page_count"],
            "ocr_required_reason": item["ocr_required_reason"],
            "cache_hit": cache_hit,
            "pages_processed": ocr_meta.get("pages_processed"),
            "pages_success": ocr_meta.get("pages_success"),
            "questions": len(records),
            "year": (ocr_meta.get("paper_meta") or {}).get("year"),
            "set": (ocr_meta.get("paper_meta") or {}).get("set_code"),
        }
        summary.papers.append(paper_stats)
        all_records.extend(records)

    summary.duplicates = classify_duplicates(all_records)
    for r in all_records:
        st = r["quality"].get("staging_status") or ""
        if "OCR_REVIEW" in st or "OCR_REVIEW_REQUIRED" in (r["quality"].get("warnings") or []):
            summary.ocr_review_required += 1
        if "ANSWER_REVIEW" in st or not r["answer"].get("value"):
            summary.answer_review_required += 1
        if "VISUAL_REVIEW" in st or r.get("visual", {}).get("has_visual"):
            summary.visual_review_required += 1
        if r["answer"].get("status") == "ANSWER_KNOWN" and r["answer"].get("value"):
            summary.answers_known += 1
        elif r["answer"].get("status") == "ANSWER_CONFLICT":
            summary.answer_conflicts += 1
        else:
            summary.answer_pending += 1

    summary.pilot_sample = select_pilot_sample(all_records, limit=5)

    # Write aggregate artifacts
    with (staging / "questions_all.jsonl").open("w", encoding="utf-8") as fh:
        for r in all_records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    (staging / "summary.json").write_text(
        json.dumps(asdict(summary), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (staging / "scanned_targets.json").write_text(json.dumps(scanned, indent=2), encoding="utf-8")
    (staging / "pilot_sample.json").write_text(
        json.dumps(summary.pilot_sample, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary
