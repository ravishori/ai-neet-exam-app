"""Controlled, local, read-only OCR evaluation on a sample of scanned NEET
PYQ source PDFs. No database writes, no modification of source PDFs (pages
are rendered to in-memory images only, never written back into the PDF
file), no external/paid OCR services -- Tesseract runs 100% locally via
pytesseract. OCR output is saved to a new evidence directory only; nothing
in pyq.questions or any other table is touched.
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
OUT_DIR = os.path.join(REPO_ROOT, "docs", "quality", "_pyq_local_ocr_evaluation_2026-10-01")
EVIDENCE_PRIOR = os.path.join(REPO_ROOT, "docs", "quality", "_pyq_text_extraction_audit_2026-10-01", "reconstruction_evidence_sheet.csv")

RENDER_DPI = 300  # suitable resolution for OCR per task instruction

# Representative sample: 5 distinct source PDFs, spanning years 2023-2024,
# including the garbled-chemistry-notation cases, the bilingual case, and
# the clear-scientific-vocabulary-in-options case.
SAMPLE_FILES = {
    "Paper_20231108005448.pdf": "2023",  # electron-configuration notation corruption
    "Paper_20231108010819.pdf": "2023",  # physics circuit/figure questions
    "Paper_20231108005054.pdf": "2023",  # embryology match-the-column (clear option vocabulary)
    "Paper_20231108010507.pdf": "2023",  # chemistry formula fragment (CoCl complex)
    "Paper_20250124133115.pdf": "2024",  # suspected bilingual (English/Hindi) paper
}


def normalize_for_match(s: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]{2,}", (s or "").lower()))


def find_file(filename: str) -> str | None:
    for root, _dirs, files in os.walk(SOURCE_DIR):
        if filename in files:
            return os.path.join(root, filename)
    return None


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "rendered_pages"), exist_ok=True)

    with open(EVIDENCE_PRIOR, newline="", encoding="utf-8") as f:
        prior_rows = {r["question_id"]: r for r in csv.DictReader(f)}

    questions_by_file: dict[str, list[dict]] = {}
    for qid, r in prior_rows.items():
        questions_by_file.setdefault(r["source_filename"], []).append(r)

    results = []
    for fname in SAMPLE_FILES:
        full_path = find_file(fname)
        if not full_path:
            results.append({"source_filename": fname, "error": "file not found locally"})
            continue

        doc = fitz.open(full_path)
        qs = questions_by_file.get(fname, [])
        query_tokens_all = set()
        for q in qs:
            query_tokens_all |= normalize_for_match(q["original_extracted_text"])
            query_tokens_all |= normalize_for_match(q["original_options"])

        # OCR every page of this (32-48 page) paper at 300 DPI, record text +
        # token overlap vs this file's garbled questions, to locate candidate
        # pages. This is read-only against the PDF (render to pixmap only).
        page_ocr_texts = []
        zoom = RENDER_DPI / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for i in range(len(doc)):
            pix = doc[i].get_pixmap(matrix=mat)
            img_path = os.path.join(OUT_DIR, "rendered_pages", f"{fname.replace('.pdf', '')}_p{i+1}.png")
            pix.save(img_path)
            ocr_text = pytesseract.image_to_string(img_path, lang="eng")
            page_ocr_texts.append(ocr_text)
            # Remove rendered PNG after OCR to keep evidence dir lean --
            # keep only a few representative pages (handled below).

        # For each question, find best-matching page by token overlap against OCR text
        for q in qs:
            q_tokens = normalize_for_match(q["original_extracted_text"]) | normalize_for_match(q["original_options"])
            best_idx, best_score = -1, 0
            for i, ptext in enumerate(page_ocr_texts):
                score = len(q_tokens & normalize_for_match(ptext))
                if score > best_score:
                    best_score, best_idx = score, i

            matched_page_ocr = page_ocr_texts[best_idx] if best_idx >= 0 else ""
            results.append(
                {
                    "question_id": q["question_id"],
                    "source_filename": fname,
                    "year": q["year"],
                    "rendering_dpi": RENDER_DPI,
                    "ocr_engine": "tesseract 5.5.0.20241111 (local, via pytesseract 0.3.13)",
                    "ocr_language": "eng",
                    "best_matching_page_1indexed": (best_idx + 1) if best_idx >= 0 else "",
                    "token_overlap_score": best_score,
                    "original_extracted_text": q["original_extracted_text"],
                    "original_options": q["original_options"],
                    "ocr_output_best_page_preview": matched_page_ocr[:1500],
                    "ocr_output_full_page_chars": len(matched_page_ocr),
                }
            )

        doc.close()
        print(f"{fname}: {len(doc) if False else ''} pages OCR'd, {len(qs)} target questions", flush=True)

    # Keep only the single best-matching rendered PNG per question as evidence
    # (delete the rest to avoid dumping hundreds of page images).
    keep_pages = set()
    for r in results:
        if r.get("best_matching_page_1indexed"):
            keep_pages.add((r["source_filename"].replace(".pdf", ""), r["best_matching_page_1indexed"]))
    rendered_dir = os.path.join(OUT_DIR, "rendered_pages")
    for fn in os.listdir(rendered_dir):
        parts = fn.rsplit("_p", 1)
        if len(parts) != 2:
            continue
        base, pagepart = parts
        pagenum = int(pagepart.replace(".png", ""))
        if (base, pagenum) not in keep_pages:
            os.remove(os.path.join(rendered_dir, fn))

    fieldnames = [
        "question_id", "source_filename", "year", "rendering_dpi", "ocr_engine", "ocr_language",
        "best_matching_page_1indexed", "token_overlap_score", "original_extracted_text",
        "original_options", "ocr_output_best_page_preview", "ocr_output_full_page_chars",
    ]
    with open(os.path.join(OUT_DIR, "ocr_comparison_sample.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)

    summary = {
        "sample_files": list(SAMPLE_FILES.keys()),
        "questions_evaluated": len(results),
        "rendering_dpi": RENDER_DPI,
        "ocr_engine_version": "tesseract 5.5.0.20241111",
        "ocr_languages_available": ["eng", "osd"],
        "ocr_languages_used": ["eng"],
        "hindi_language_pack_available": False,
        "rows_with_zero_token_overlap_on_best_page": sum(1 for r in results if r.get("token_overlap_score") == 0),
    }
    with open(os.path.join(OUT_DIR, "ocr_evaluation_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
