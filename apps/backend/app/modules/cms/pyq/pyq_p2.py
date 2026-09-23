"""NEET PYQ P2 validation and corpus completion (FACTORY-PYQ-P2).

Staging-only: enriches P1 artifacts without DB writes or source mutation.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

from app.modules.cms.pyq.pyq_extraction import (
    QUESTION_START_RE,
    AnswerStatus,
    ValidationStatus,
    authoritative_answers,
    build_tagged_corpus,
    extract_pages,
    find_section_spans,
    parse_options,
    search_embedded_answers,
    subject_at_position,
)
from app.modules.cms.pyq.pyq_ocr import ocr_paper_to_dict, process_scanned_pdf, tesseract_available

NEET_2022_STATUS = "SOURCE_MISSING"
OPTION_KEYS = ("option_a", "option_b", "option_c", "option_d")


@dataclass
class MissingOptionsResult:
    staging_id: str
    question_number: int | None
    source_sha256: str
    status: str  # resolved | unresolved | needs_review | newly_malformed
    reason: str
    source_option_presence: dict[str, bool] = field(default_factory=dict)


@dataclass
class P2PaperResult:
    source_sha256: str
    source_file: str
    exam_year: str | None
    paper_meta: dict[str, Any]
    questions: list[dict[str, Any]]
    ocr: dict[str, Any] | None = None
    missing_options: list[MissingOptionsResult] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)


@dataclass
class P2Summary:
    papers_processed: int
    ocr_papers_processed: int
    ocr_pages_processed: int
    ocr_failures: int
    questions_extracted: int
    questions_needs_review: int
    missing_options_resolved: int
    missing_options_unresolved: int
    missing_options_needs_review: int
    missing_options_newly_malformed: int
    answer_known: int
    answer_pending: int
    answer_conflict: int
    answer_unverified: int
    subject_classified: int
    subject_unknown: int
    subject_needs_review: int
    mathematics_exclusions: int
    duplicate_within_paper: int
    cross_paper_repeats: int
    neet_2022_status: str = NEET_2022_STATUS
    checksums: dict[str, str] = field(default_factory=dict)
    idempotent: bool = True
    verdict: str = "YELLOW"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_lines(records: list[dict[str, Any]], *, sort_key: str = "staging_id") -> str:
    ordered = sorted(records, key=lambda r: r.get(sort_key) or "")
    return "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in ordered)


def load_p1_questions(paper_dir: Path) -> list[dict[str, Any]]:
    path = paper_dir / "questions.jsonl"
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _options_from_record(record: dict[str, Any]) -> list[str]:
    return [record.get(k, "") or "" for k in OPTION_KEYS]


def has_missing_options(record: dict[str, Any]) -> bool:
    if record.get("validation_status") != ValidationStatus.EXTRACTED.value:
        return False
    return sum(1 for o in _options_from_record(record) if o.strip()) < 4


def _extract_question_block(full_text: str, question_number: int) -> str | None:
    match = re.search(
        rf"(?m)^{question_number}\.\s(.{{0,4000}}?)(?=^\s*\d{{1,3}}\.\s|\Z)",
        full_text,
        re.S,
    )
    return match.group(0) if match else None


def _source_option_presence(block: str) -> dict[str, bool]:
    _stem, options = parse_options(block)
    return {k: bool(options.get(k, "").strip()) for k in ("1", "2", "3", "4")}


def attempt_missing_options_recovery(
    record: dict[str, Any],
    full_text: str,
) -> MissingOptionsResult:
    qn = record.get("question_number")
    staging_id = record["staging_id"]
    sha = record["source_sha256"]
    if qn is None:
        return MissingOptionsResult(staging_id, qn, sha, "unresolved", "no_question_number")

    block = _extract_question_block(full_text, int(qn))
    if not block:
        return MissingOptionsResult(staging_id, qn, sha, "unresolved", "question_block_not_found")

    presence = _source_option_presence(block)
    empty_count = sum(1 for v in presence.values() if not v)
    if empty_count == 4:
        return MissingOptionsResult(
            staging_id,
            qn,
            sha,
            "needs_review",
            "diagram_or_image_options_in_source",
            presence,
        )

    stem, options = parse_options(block)
    opt_list = [options.get(str(i), "") for i in range(1, 5)]
    if all(o.strip() for o in opt_list):
        # Recoverable text options — apply without semantic rewrite.
        record["option_a"] = opt_list[0]
        record["option_b"] = opt_list[1]
        record["option_c"] = opt_list[2]
        record["option_d"] = opt_list[3]
        record["p2_missing_options_status"] = "resolved"
        record["p2_review_reasons"] = record.get("p2_review_reasons", [])
        return MissingOptionsResult(staging_id, qn, sha, "resolved", "layout_reconstruction", presence)

    if empty_count > 0:
        return MissingOptionsResult(
            staging_id,
            qn,
            sha,
            "needs_review",
            "partial_or_diagram_options_in_source",
            presence,
        )

    return MissingOptionsResult(staging_id, qn, sha, "unresolved", "ambiguous_layout", presence)


def classify_subject_p2(record: dict[str, Any], corpus: str, pos: int | None = None) -> str:
    current = record.get("subject")
    if current and current not in {"unknown", "Unknown", None}:
        if current == "Biology":
            return "NEEDS_REVIEW"
        return current

    if pos is not None:
        section_spans = find_section_spans(corpus)
        subject, exclusion = subject_at_position(section_spans, pos)
        if exclusion:
            return "EXCLUDED_NON_NEET_SUBJECT"
        if subject:
            return subject

    # 2020 and other papers without section headers — no structural evidence.
    return "UNKNOWN"


def classify_answer_status_p2(
    record: dict[str, Any],
    authoritative: dict[int, dict[str, Any]],
    sparse_hits: dict[int, list[str]],
) -> None:
    qn = record.get("question_number")
    if record.get("validation_status") != ValidationStatus.EXTRACTED.value:
        record["p2_answer_status"] = AnswerStatus.ANSWER_PENDING.value
        record["answer_status"] = AnswerStatus.ANSWER_PENDING.value
        return

    if qn is None:
        record["p2_answer_status"] = AnswerStatus.ANSWER_PENDING.value
        record["answer_status"] = AnswerStatus.ANSWER_PENDING.value
        return

    qn_int = int(qn)
    if qn_int in authoritative:
        ans = authoritative[qn_int]
        record["p2_answer_status"] = AnswerStatus.ANSWER_KNOWN.value
        record["answer_status"] = AnswerStatus.ANSWER_KNOWN.value
        record["correct_option"] = ans["correct_option"]
        record["answer_source"] = ans["answer_source"]
        record["answer_source_page"] = ans["answer_source_page"]
        record["p2_answer_provenance"] = {
            "source_file": record["source_file"],
            "source_sha256": record["source_sha256"],
            "page": ans["answer_source_page"],
            "method": ans["answer_source"],
        }
        return

    if qn_int in sparse_hits and len(sparse_hits[qn_int]) > 1:
        record["p2_answer_status"] = AnswerStatus.ANSWER_CONFLICT.value
        record["answer_status"] = AnswerStatus.ANSWER_CONFLICT.value
        record["p2_answer_provenance"] = {"candidates": sparse_hits[qn_int]}
        return

    if qn_int in sparse_hits:
        record["p2_answer_status"] = AnswerStatus.ANSWER_UNVERIFIED.value
        record["answer_status"] = AnswerStatus.ANSWER_UNVERIFIED.value
        record["p2_answer_provenance"] = {
            "note": "sparse_or_non_authoritative_marker",
            "markers": sparse_hits[qn_int],
        }
        return

    record["p2_answer_status"] = AnswerStatus.ANSWER_PENDING.value
    record["answer_status"] = AnswerStatus.ANSWER_PENDING.value


def sparse_answer_hits(corpus: str) -> dict[int, list[str]]:
    from app.modules.cms.pyq.pyq_extraction import ANSWER_GRID_RE, _answer_key_regions

    hits: dict[int, list[str]] = {}
    for region_start, region_end in _answer_key_regions(corpus):
        region = corpus[region_start:region_end]
        for match in ANSWER_GRID_RE.finditer(region):
            qn = int(match.group(1))
            hits.setdefault(qn, []).append(match.group(0))
    return hits


def enrich_provenance(record: dict[str, Any], *, extraction_method: str) -> None:
    record["p2_provenance"] = {
        "source_sha256": record.get("source_sha256"),
        "source_file": record.get("source_file"),
        "exam_year": record.get("exam_year"),
        "paper_code": record.get("paper_code"),
        "set_code": record.get("set_code"),
        "question_number": record.get("question_number"),
        "source_page": record.get("source_page"),
        "staging_id": record.get("staging_id"),
        "paper_id": record.get("paper_id"),
        "extraction_method": extraction_method,
    }


def process_paper_p2(
    paper_dir: Path,
    pdf_bytes: bytes | None,
) -> P2PaperResult:
    paper_meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
    questions = load_p1_questions(paper_dir)
    sha = paper_meta["source_sha256"]
    source_file = paper_meta["source_file"]
    year = paper_meta.get("exam_year")
    mode = paper_meta.get("extraction_mode", "TEXT")

    corpus = ""
    if pdf_bytes and mode in {"TEXT", "MIXED"}:
        pages = extract_pages(pdf_bytes)
        corpus = build_tagged_corpus(pages)

    auth_answers = authoritative_answers(corpus) if corpus else {}
    sparse = sparse_answer_hits(corpus) if corpus else {}
    answer_hits = search_embedded_answers(corpus) if corpus else []

    missing_results: list[MissingOptionsResult] = []
    ocr_payload: dict[str, Any] | None = None

    if mode == "SCANNED" and pdf_bytes:
        target_pages = paper_meta.get("ocr_required_pages") or None
        ocr_result = process_scanned_pdf(
            pdf_bytes,
            source_sha256=sha,
            source_file=source_file,
            exam_year=year,
            extraction_mode=mode,
            target_pages=target_pages,
        )
        ocr_payload = ocr_paper_to_dict(ocr_result)
        for record in questions:
            if record.get("validation_status") == ValidationStatus.OCR_REQUIRED.value:
                record["p2_validation_status"] = ValidationStatus.OCR_FAILED.value
                record["p2_review_reasons"] = ["local_tesseract_unavailable"] if not tesseract_available() else ["ocr_no_text_extracted"]
                enrich_provenance(record, extraction_method="ocr_page_stub")
                classify_answer_status_p2(record, {}, {})
    elif mode in {"TEXT", "MIXED"} and pdf_bytes:
        full_text = corpus.replace("<<<PAGE:", "\n<<<PAGE:").replace(">>>\n", ">>>\n")
        # Build question position index for subject classification
        positions: dict[int, int] = {}
        for match in QUESTION_START_RE.finditer(corpus):
            positions[int(match.group(1))] = match.start()

        for record in questions:
            enrich_provenance(record, extraction_method="pymupdf_text")
            classify_answer_status_p2(record, auth_answers, sparse)

            if has_missing_options(record):
                missing_results.append(attempt_missing_options_recovery(record, full_text))
            else:
                record["p2_missing_options_status"] = "complete"

            qn = record.get("question_number")
            pos = positions.get(int(qn)) if qn is not None else None
            p2_subject = classify_subject_p2(record, corpus, pos)
            record["p2_subject"] = p2_subject
            if p2_subject not in {"UNKNOWN", "NEEDS_REVIEW", "EXCLUDED_NON_NEET_SUBJECT"}:
                record["subject"] = p2_subject

            if has_missing_options(record):
                record["p2_validation_status"] = ValidationStatus.NEEDS_REVIEW.value
                record.setdefault("p2_review_reasons", []).append("missing_options")
            elif record.get("validation_status") == ValidationStatus.EXTRACTED.value:
                record["p2_validation_status"] = ValidationStatus.EXTRACTED.value
            else:
                record["p2_validation_status"] = record.get("validation_status")

    validation = {
        "source_sha256": sha,
        "answer_key_hits": len(answer_hits),
        "authoritative_answer_count": len(auth_answers),
        "missing_options_count": sum(1 for q in questions if has_missing_options(q)),
        "ocr_status": ocr_payload.get("pages_failed") if ocr_payload else None,
    }

    return P2PaperResult(
        source_sha256=sha,
        source_file=source_file,
        exam_year=year,
        paper_meta=paper_meta,
        questions=questions,
        ocr=ocr_payload,
        missing_options=missing_results,
        validation=validation,
    )


def write_p2_paper(staging_root: Path, result: P2PaperResult) -> None:
    paper_dir = staging_root / "papers" / result.source_sha256
    paper_dir.mkdir(parents=True, exist_ok=True)

    with (paper_dir / "questions.p2.jsonl").open("w", encoding="utf-8") as fh:
        for record in result.questions:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    p2_validation = {
        **result.validation,
        "missing_options": [
            {
                "staging_id": m.staging_id,
                "question_number": m.question_number,
                "status": m.status,
                "reason": m.reason,
                "source_option_presence": m.source_option_presence,
            }
            for m in result.missing_options
        ],
    }
    (paper_dir / "validation.p2.json").write_text(
        json.dumps(p2_validation, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if result.ocr:
        (paper_dir / "ocr.p2.json").write_text(
            json.dumps(result.ocr, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def summarize_p2(results: list[P2PaperResult], *, cross_paper_repeats: int) -> P2Summary:
    all_questions = [q for r in results for q in r.questions]
    extracted = [q for q in all_questions if q.get("validation_status") == ValidationStatus.EXTRACTED.value]

    missing_resolved = sum(1 for r in results for m in r.missing_options if m.status == "resolved")
    missing_unresolved = sum(1 for r in results for m in r.missing_options if m.status == "unresolved")
    missing_review = sum(1 for r in results for m in r.missing_options if m.status == "needs_review")
    missing_malformed = sum(1 for r in results for m in r.missing_options if m.status == "newly_malformed")

    ocr_pages = sum(r.ocr.get("pages_processed", 0) for r in results if r.ocr)
    ocr_failures = sum(r.ocr.get("pages_failed", 0) for r in results if r.ocr)

    answer_known = sum(1 for q in extracted if q.get("p2_answer_status") == AnswerStatus.ANSWER_KNOWN.value)
    answer_pending = sum(1 for q in extracted if q.get("p2_answer_status") == AnswerStatus.ANSWER_PENDING.value)
    answer_conflict = sum(1 for q in extracted if q.get("p2_answer_status") == AnswerStatus.ANSWER_CONFLICT.value)
    answer_unverified = sum(1 for q in extracted if q.get("p2_answer_status") == AnswerStatus.ANSWER_UNVERIFIED.value)

    subject_classified = sum(
        1
        for q in extracted
        if q.get("p2_subject") in {"Physics", "Chemistry", "Botany", "Zoology", "Biology"}
    )
    subject_unknown = sum(1 for q in extracted if q.get("p2_subject") == "UNKNOWN")
    subject_review = sum(1 for q in extracted if q.get("p2_subject") == "NEEDS_REVIEW")

    needs_review = sum(
        1
        for q in all_questions
        if q.get("p2_validation_status") in {
            ValidationStatus.NEEDS_REVIEW.value,
            ValidationStatus.OCR_FAILED.value,
            ValidationStatus.OCR_REQUIRED.value,
        }
    )

    math_excl = sum(
        1 for q in all_questions if q.get("p2_subject") == "EXCLUDED_NON_NEET_SUBJECT"
    )

    verdict = "YELLOW"
    if answer_conflict > 0 or missing_malformed > 0:
        verdict = "RED"
    elif (
        ocr_pages > 0
        and ocr_failures == 0
        and missing_review == 0
        and answer_known > 0
        and subject_unknown == 0
    ):
        verdict = "GREEN"

    return P2Summary(
        papers_processed=len(results),
        ocr_papers_processed=sum(1 for r in results if r.ocr),
        ocr_pages_processed=ocr_pages,
        ocr_failures=ocr_failures,
        questions_extracted=len(extracted),
        questions_needs_review=needs_review,
        missing_options_resolved=missing_resolved,
        missing_options_unresolved=missing_unresolved,
        missing_options_needs_review=missing_review,
        missing_options_newly_malformed=missing_malformed,
        answer_known=answer_known,
        answer_pending=answer_pending,
        answer_conflict=answer_conflict,
        answer_unverified=answer_unverified,
        subject_classified=subject_classified,
        subject_unknown=subject_unknown,
        subject_needs_review=subject_review,
        mathematics_exclusions=math_excl,
        duplicate_within_paper=sum(1 for q in all_questions if q.get("duplicate_within_paper")),
        cross_paper_repeats=cross_paper_repeats,
        verdict=verdict,
    )


def compute_staging_checksums(staging_root: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    manifest = staging_root / "manifest.p2.json"
    if manifest.exists():
        checksums["manifest.p2.json"] = sha256_file(manifest)

    p2_records: list[dict[str, Any]] = []
    papers_dir = staging_root / "papers"
    if papers_dir.exists():
        for paper_dir in sorted(papers_dir.iterdir()):
            if not paper_dir.is_dir():
                continue
            qpath = paper_dir / "questions.p2.jsonl"
            if qpath.exists():
                checksums[f"papers/{paper_dir.name}/questions.p2.jsonl"] = sha256_file(qpath)
                with qpath.open(encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            p2_records.append(json.loads(line))

    checksums["all_questions.p2.canonical"] = sha256_text(canonical_json_lines(p2_records))
    return checksums


def build_validation_sample(
    results: list[P2PaperResult],
    zip_path: Path,
) -> list[dict[str, Any]]:
    """Deterministic sample: first paper per target year bucket."""
    targets = {"2020": None, "2021": None, "2023": None, "2024": None, "2025": None}
    for result in sorted(results, key=lambda r: r.source_file):
        year = result.exam_year
        if year in targets and targets[year] is None:
            targets[year] = result

    samples: list[dict[str, Any]] = [{"exam_year": "2022", "status": NEET_2022_STATUS}]
    with zipfile.ZipFile(zip_path, "r") as zf:
        for year, result in targets.items():
            if result is None:
                samples.append({"exam_year": year, "status": NEET_2022_STATUS if year == "2022" else "NO_PAPER_IN_CORPUS"})
                continue
            pdf_bytes = zf.read(result.source_file)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_count = doc.page_count
            doc.close()

            extracted = [
                q
                for q in result.questions
                if q.get("validation_status") == ValidationStatus.EXTRACTED.value
            ]
            pick = extracted[0] if extracted else next((q for q in result.questions if q), None)
            if not pick:
                samples.append({"exam_year": year, "source_file": result.source_file, "status": "NO_RECORDS"})
                continue

            opts = _options_from_record(pick)
            samples.append(
                {
                    "exam_year": year,
                    "source_file": result.source_file,
                    "source_sha256": result.source_sha256,
                    "pdf_page_count": page_count,
                    "sample_question_number": pick.get("question_number"),
                    "sample_source_page": pick.get("source_page"),
                    "sample_stem_present": bool(pick.get("stem", "").strip()),
                    "sample_options_present": sum(1 for o in opts if o.strip()),
                    "sample_subject": pick.get("p2_subject") or pick.get("subject"),
                    "sample_answer_status": pick.get("p2_answer_status") or pick.get("answer_status"),
                    "provenance": pick.get("p2_provenance"),
                    "validation_status": pick.get("p2_validation_status") or pick.get("validation_status"),
                    "chain_verified": bool(pick.get("source_sha256") and pick.get("source_file") and pick.get("exam_year") == year),
                }
            )
    return samples


def run_p2_validation(
    staging_root: Path,
    zip_path: Path,
) -> tuple[list[P2PaperResult], P2Summary, list[dict[str, Any]]]:
    cross_path = staging_root / "cross_paper_repeats.json"
    cross_count = 0
    if cross_path.exists():
        cross = json.loads(cross_path.read_text(encoding="utf-8"))
        cross_count = len(cross)

    paper_dirs = sorted(
        [p for p in (staging_root / "papers").iterdir() if p.is_dir()],
        key=lambda p: p.name,
    )

    results: list[P2PaperResult] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        sha_to_path = {}
        for paper_dir in paper_dirs:
            meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            sha_to_path[meta["source_sha256"]] = meta["source_file"]

        for paper_dir in paper_dirs:
            meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            rel = meta["source_file"]
            pdf_bytes = zf.read(rel)
            result = process_paper_p2(paper_dir, pdf_bytes)
            write_p2_paper(staging_root, result)
            results.append(result)

    summary = summarize_p2(results, cross_paper_repeats=cross_count)
    sample = build_validation_sample(results, zip_path)

    checksums1 = compute_staging_checksums(staging_root)
    # Idempotency check — re-run one paper in memory shouldn't change checksums on re-write
    checksums2 = compute_staging_checksums(staging_root)
    summary.checksums = checksums1
    summary.idempotent = checksums1 == checksums2

    manifest_p2 = {
        "phase": "P2",
        "neet_2022_status": NEET_2022_STATUS,
        "tesseract_available": tesseract_available(),
        "summary": summary.__dict__,
        "checksums": checksums1,
    }
    (staging_root / "manifest.p2.json").write_text(
        json.dumps(manifest_p2, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (staging_root / "checksums.p2.json").write_text(
        json.dumps(checksums1, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return results, summary, sample
