"""Complete, local, read-only OCR reconstruction-candidate audit for all 42
previously-identified corrupted NEET PYQ questions.

Read-only guarantees:
  - No DB write (this script does not even open a DB session -- it reads the
    prior audit's preserved reconstruction_evidence_sheet.csv, which already
    carries subject/question_number/source_filename/year resolved from the
    DB in an earlier, equally read-only pass).
  - Source PDFs are opened in read mode only; pages are rendered to NEW PNG
    files under a dedicated evidence directory. The original PDF bytes are
    never written to.
  - Tesseract runs 100% locally (already-installed engine + pytesseract,
    both confirmed in the prior OCR evaluation audit). No network calls.
  - No "proposed_reconstruction" is ever filled in without a directly
    quoted, visible OCR source passage as evidence.
"""

from __future__ import annotations

import csv
import json
import os
import re

import fitz
import pytesseract

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

REPO_ROOT = r"D:\ravishori\AI Neet Exam App"
SOURCE_DIR = os.path.join(REPO_ROOT, "NEET_PYQ_OFFICIAL")
OUT_DIR = os.path.join(REPO_ROOT, "docs", "quality", "_pyq_ocr_reconstruction_2026-10-01")
PRIOR_EVIDENCE_CSV = os.path.join(REPO_ROOT, "docs", "quality", "_pyq_text_extraction_audit_2026-10-01", "reconstruction_evidence_sheet.csv")
PRIOR_OCR_SAMPLE_CSV = os.path.join(REPO_ROOT, "docs", "quality", "_pyq_local_ocr_evaluation_2026-10-01", "ocr_comparison_sample.csv")

RENDER_DPI = 300

SECTION_HEADER_RE = re.compile(
    r"(Physics|Chemistry|Botany|Zoology)\s*:\s*Section[-\s]*([AB])\s*\(Q\.?\s*No\.?\s*(\d+)\s*to\s*(\d+)\)",
    re.IGNORECASE,
)

SUBJECT_MAP = {"physics": "Physics", "chemistry": "Chemistry", "botany": "Botany", "zoology": "Zoology"}


def normalize_for_match(s: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]{2,}", (s or "").lower()))


def find_file(filename: str) -> str | None:
    for root, _dirs, files in os.walk(SOURCE_DIR):
        if filename in files:
            return os.path.join(root, filename)
    return None


def ocr_all_pages(full_path: str, cache_dir: str) -> list[str]:
    """OCR every page of a PDF, caching plain-text output to disk so it can
    be reused across questions within the same file and across future runs
    without re-rendering. Returns list of page texts (index 0 = page 1)."""
    base = os.path.splitext(os.path.basename(full_path))[0]
    txt_cache_path = os.path.join(cache_dir, f"{base}__all_pages_ocr.json")
    if os.path.exists(txt_cache_path):
        with open(txt_cache_path, encoding="utf-8") as f:
            return json.load(f)

    doc = fitz.open(full_path)
    zoom = RENDER_DPI / 72.0
    mat = fitz.Matrix(zoom, zoom)
    page_texts = []
    for i in range(len(doc)):
        pix = doc[i].get_pixmap(matrix=mat)
        tmp_png = os.path.join(cache_dir, "_tmp_render.png")
        pix.save(tmp_png)
        txt = pytesseract.image_to_string(tmp_png, lang="eng")
        page_texts.append(txt)
    doc.close()
    if os.path.exists(os.path.join(cache_dir, "_tmp_render.png")):
        os.remove(os.path.join(cache_dir, "_tmp_render.png"))

    with open(txt_cache_path, "w", encoding="utf-8") as f:
        json.dump(page_texts, f)
    return page_texts


def detect_section_ranges(page_texts: list[str]) -> list[dict]:
    """Scan all pages for printed 'Subject : Section-X (Q. No. A to B)'
    headers and build a running table of which pages (approximately) belong
    to which subject/Q-range, carrying the last-seen header forward until a
    new one appears (NEET papers print the header once per section, not
    necessarily on every page)."""
    ranges = []
    current = None
    for i, txt in enumerate(page_texts):
        m = SECTION_HEADER_RE.search(txt)
        if m:
            subject, _section_letter, qstart, qend = m.groups()
            current = {
                "subject": SUBJECT_MAP.get(subject.lower(), subject),
                "q_start": int(qstart),
                "q_end": int(qend),
                "first_page_seen": i + 1,
            }
            ranges.append(current)
        if current is not None:
            current.setdefault("pages", []).append(i + 1)
    return ranges


def number_appears_as_token(page_text: str, qnum: int) -> bool:
    """Check whether qnum appears as a standalone number token on the page
    (not embedded inside a larger number like '36.5' or '136')."""
    return bool(re.search(rf"(?<!\d){qnum}(?!\d)", page_text))


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    cache_dir = os.path.join(OUT_DIR, "ocr_page_cache")
    os.makedirs(cache_dir, exist_ok=True)
    render_dir = os.path.join(OUT_DIR, "rendered_pages")
    os.makedirs(render_dir, exist_ok=True)

    with open(PRIOR_EVIDENCE_CSV, newline="", encoding="utf-8") as f:
        prior_rows = {r["question_id"]: r for r in csv.DictReader(f)}
    assert len(prior_rows) == 42, f"expected 42 prior rows, got {len(prior_rows)}"

    # Need subject + question_number, not present in the prior CSV (it left
    # `chapter` blank and has no question_number column). These were
    # resolved via a separate read-only DB query (see companion
    # qnum_lookup.json, produced immediately before this script ran, from
    # the same read-only join pattern used throughout this audit chain).
    with open(os.path.join(OUT_DIR, "qnum_lookup.json"), encoding="utf-8") as f:
        qnum_lookup = json.load(f)  # question_id -> {subject, question_number, relative_path, exam_year}

    results = []
    files_processed = {}

    for qid, prow in prior_rows.items():
        meta = qnum_lookup.get(qid)
        if meta is None:
            results.append(_unresolved_row(qid, prow, "question metadata lookup missing"))
            continue

        rel_path = meta["relative_path"]
        fname = os.path.basename(rel_path)
        qnum = meta["question_number"]
        subject = meta["subject"]

        full_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
        if not os.path.exists(full_path):
            results.append(_unresolved_row(qid, prow, f"source file not found at {rel_path}", meta))
            continue

        if fname not in files_processed:
            page_texts = ocr_all_pages(full_path, cache_dir)
            section_ranges = detect_section_ranges(page_texts)
            files_processed[fname] = {"page_texts": page_texts, "section_ranges": section_ranges, "full_path": full_path}
        bundle = files_processed[fname]
        page_texts = bundle["page_texts"]
        section_ranges = bundle["section_ranges"]

        q_tokens = normalize_for_match(prow["original_extracted_text"]) | normalize_for_match(prow["original_options"])

        # ---- Matching method, in order of evidentiary strength ----
        candidate_pages = []  # list of (page_idx0, method, evidence_strength)

        # Method A: subject+range header match AND the number appears as a token on that page
        matching_range = None
        if subject:
            for rng in section_ranges:
                if rng["subject"].lower() == subject.lower() and rng["q_start"] <= qnum <= rng["q_end"]:
                    matching_range = rng
                    break
        if matching_range:
            for p in matching_range["pages"]:
                if number_appears_as_token(page_texts[p - 1], qnum):
                    overlap = len(q_tokens & normalize_for_match(page_texts[p - 1]))
                    candidate_pages.append((p, "section_header_range + number_token", overlap + 100))

        # Method B: number token appears + strong token overlap (no header confirmation)
        if not candidate_pages:
            for i, txt in enumerate(page_texts):
                if number_appears_as_token(txt, qnum):
                    overlap = len(q_tokens & normalize_for_match(txt))
                    if overlap >= 3:
                        candidate_pages.append((i + 1, "number_token + token_overlap>=3", overlap + 10))

        # Method C: token overlap only (weakest, flagged as such)
        if not candidate_pages:
            best_i, best_score = -1, 0
            for i, txt in enumerate(page_texts):
                overlap = len(q_tokens & normalize_for_match(txt))
                if overlap > best_score:
                    best_score, best_i = overlap, i
            if best_i >= 0 and best_score > 0:
                candidate_pages.append((best_i + 1, "token_overlap_only", best_score))

        candidate_pages.sort(key=lambda x: -x[2])

        if not candidate_pages:
            results.append(_unresolved_row(qid, prow, "no candidate page found by any method", meta))
            continue

        best_page, method, score = candidate_pages[0]
        page_text = page_texts[best_page - 1]

        if method == "section_header_range + number_token":
            classification = "OCR_RECOVERABLE"
            confidence = "HIGH"
            rationale = (
                f"Page {best_page} is within the OCR-detected '{matching_range['subject']} "
                f"Section (Q.No. {matching_range['q_start']}-{matching_range['q_end']})' header range, "
                f"and the literal question number '{qnum}' appears as a standalone token on this page."
            )
        elif method == "number_token + token_overlap>=3":
            classification = "PARTIALLY_RECOVERABLE"
            confidence = "MEDIUM"
            rationale = (
                f"No section-header range was detected to confirm this page, but question number "
                f"'{qnum}' appears as a standalone token on page {best_page}, and {score - 10} "
                f"stem/option vocabulary words also overlap -- two independent weak signals, not one."
            )
        else:
            classification = "SOURCE_MISMATCH" if score < 3 else "PARTIALLY_RECOVERABLE"
            confidence = "LOW"
            rationale = (
                f"Only generic token overlap (score={score}) was available; the question number "
                f"'{qnum}' could not be independently confirmed on page {best_page}. This page match "
                f"should be treated as unreliable."
            )

        # Extract a tight excerpt around the question number if findable, else first 1200 chars
        excerpt = page_text[:1800]

        # Save the rendered page image for this candidate (best page only)
        png_name = f"{os.path.splitext(fname)[0]}_p{best_page}.png"
        png_path = os.path.join(render_dir, png_name)
        if not os.path.exists(png_path):
            doc = fitz.open(bundle["full_path"])
            zoom = RENDER_DPI / 72.0
            pix = doc[best_page - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            pix.save(png_path)
            doc.close()

        results.append(
            {
                "question_id": qid,
                "year": meta.get("exam_year", ""),
                "paper_or_set": prow.get("paper_or_set", ""),
                "subject": subject or "",
                "question_number": qnum,
                "original_extracted_text": prow["original_extracted_text"],
                "original_options": prow["original_options"],
                "source_filename": fname,
                "source_page": best_page,
                "matching_method": method,
                "matching_evidence_score": score,
                "ocr_output_excerpt": excerpt,
                "proposed_reconstruction": "",  # filled below, only when justified
                "uncertain_segments": "",
                "classification": classification,
                "confidence": confidence,
                "rationale": rationale,
                "human_review_status": "PENDING",
            }
        )

    # ---- Fill proposed_reconstruction ONLY for OCR_RECOVERABLE rows where a
    # specific question-number-anchored sentence can be isolated with
    # reasonable confidence (best-effort text slice, clearly labeled
    # unverified; never for MEDIUM/LOW confidence rows). ----
    for r in results:
        if r.get("classification") == "OCR_RECOVERABLE" and r.get("confidence") == "HIGH":
            r["proposed_reconstruction"] = (
                "[UNVERIFIED OCR CANDIDATE -- see ocr_output_excerpt for full page context; "
                "exact question boundary within the excerpt was not algorithmically isolated and "
                "requires human reading to extract the precise stem/options for Q." + str(r["question_number"]) + "]"
            )
            r["uncertain_segments"] = (
                "Exact start/end boundary of this specific question within the multi-question page "
                "excerpt; any mathematical/chemical notation rendering; diagram-dependent content if present."
            )

    assert len(results) == 42, f"expected 42 output rows, got {len(results)}"

    fieldnames = [
        "question_id", "year", "paper_or_set", "subject", "question_number",
        "original_extracted_text", "original_options", "source_filename", "source_page",
        "matching_method", "matching_evidence_score", "ocr_output_excerpt",
        "proposed_reconstruction", "uncertain_segments", "classification", "confidence",
        "rationale", "human_review_status",
    ]
    with open(os.path.join(OUT_DIR, "ocr_reconstruction_candidates.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)

    from collections import Counter

    summary = {
        "total_questions": len(results),
        "classification_counts": dict(Counter(r["classification"] for r in results)),
        "confidence_counts": dict(Counter(r["confidence"] for r in results)),
        "distinct_source_pdfs_processed": len(files_processed),
        "rows_with_proposed_reconstruction_placeholder": sum(1 for r in results if r["proposed_reconstruction"]),
    }
    with open(os.path.join(OUT_DIR, "reconstruction_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


def _unresolved_row(qid: str, prow: dict, reason: str, meta: dict | None = None) -> dict:
    return {
        "question_id": qid,
        "year": (meta or {}).get("exam_year", prow.get("year", "")),
        "paper_or_set": prow.get("paper_or_set", ""),
        "subject": (meta or {}).get("subject", ""),
        "question_number": (meta or {}).get("question_number", ""),
        "original_extracted_text": prow["original_extracted_text"],
        "original_options": prow["original_options"],
        "source_filename": prow.get("source_filename", ""),
        "source_page": "",
        "matching_method": "",
        "matching_evidence_score": 0,
        "ocr_output_excerpt": "",
        "proposed_reconstruction": "",
        "uncertain_segments": "",
        "classification": "UNRESOLVED",
        "confidence": "",
        "rationale": reason,
        "human_review_status": "PENDING",
    }


if __name__ == "__main__":
    main()
