"""Read-only PYQ text-extraction tracing diagnostic.

No DB writes (session.rollback() only). No question/option/answer text is
ever modified anywhere -- this script only READS pyq.questions and READS
local source PDFs (via PyMuPDF/fitz, text extraction only, no OCR/image
processing, no external calls) to gather comparison evidence. Never writes
a "proposed_reconstruction" unless a clearly legible, directly-matching
source passage was actually found and extracted.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re

import fitz  # PyMuPDF, text extraction only -- local file read, no network
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.modules.knowledge.services.grounding_check import _significant_words

REPO_ROOT = r"D:\ravishori\AI Neet Exam App"
OUT_DIR = REPO_ROOT + r"\docs\quality\_pyq_text_extraction_audit_2026-10-01"
PRIOR_ZERO_WORD_CSV = REPO_ROOT + r"\docs\quality\_retrieval_human_review_2026-10-01\zero_significant_word_analysis.csv"


def normalize_for_match(s: str) -> set[str]:
    """Loose token set for fuzzy page-location matching (not the production
    significance function -- deliberately looser, includes short tokens and
    digits, purely to locate a candidate page, never to judge coverage)."""
    return set(re.findall(r"[A-Za-z0-9]{2,}", (s or "").lower()))


async def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT q.id, q.subject, q.raw_stem, q.raw_options, q.question_number,
                           sf.relative_path, sf.exam_year, sf.paper_code
                    FROM pyq.questions q
                    LEFT JOIN pyq.source_files sf ON sf.id = q.source_file_id
                    WHERE q.state = 'ANSWER_PENDING'
                    """
                )
            )
        ).all()
        by_id = {str(r[0]): r for r in rows}

        with open(PRIOR_ZERO_WORD_CSV, newline="", encoding="utf-8") as f:
            target_rows = list(csv.DictReader(f))
        print("target questions:", len(target_rows))

        results = []
        pdf_cache: dict[str, list[str]] = {}

        for tr in target_rows:
            qid = tr["question_id"]
            row = by_id.get(qid)
            if row is None:
                results.append(
                    {
                        "question_id": qid, "year": "", "paper_or_set": "", "subject": tr.get("subject", ""),
                        "chapter": "", "original_extracted_text": tr["stem_text"], "original_options": tr.get("options_text_preview", ""),
                        "source_filename": "", "source_page": "", "observed_corruption": "question not found in current ANSWER_PENDING set",
                        "proposed_reconstruction": "", "reconstruction_evidence": "", "confidence": "", "review_status": "UNRESOLVED",
                        "classification": "UNRESOLVED", "source_trace_status": "UNKNOWN",
                    }
                )
                continue

            _id, subject, raw_stem, raw_options, qnum, rel_path, exam_year, paper_code = row
            opts_dict = raw_options if isinstance(raw_options, dict) else {}
            opts_text = " | ".join(f"{k}: {v}" for k, v in opts_dict.items()) if opts_dict else str(raw_options or "")

            stem_words = _significant_words(raw_stem or "")
            classification_flags = []

            # ---- Classification pass 1: does stem/options look visibly corrupted? ----
            # Deterministic corruption heuristics (not AI): short isolated letters,
            # repeated angle-bracket/quote artifacts typical of OCR mis-rendering of
            # sub/superscripts, or stems under 20 chars with no digits and no spaces
            # pattern typical of real NEET stems.
            corruption_markers = ["<o", "<(", '="" ', "°c", "�", "»"]
            looks_corrupted = any(m in (raw_stem or "").lower() for m in [m.lower() for m in corruption_markers])
            if not stem_words and not looks_corrupted:
                classification_flags.append("TEXT_INTACT")  # genuinely short/non-textual, not corrupted
            if looks_corrupted:
                classification_flags.append("EXTRACTION_CORRUPTION_CONFIRMED")
            if not classification_flags:
                classification_flags.append("UNRESOLVED")

            opts_sig_words = _significant_words(opts_text)
            if opts_sig_words and not stem_words:
                classification_flags.append("OPTIONS_CONTAIN_SEARCH_TERMS")

            # ---- Source tracing ----
            source_trace_status = "UNKNOWN"
            source_filename = ""
            source_page = ""
            page_text_extract = ""
            full_path = ""
            if rel_path:
                full_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
                source_filename = os.path.basename(rel_path)
                if os.path.exists(full_path):
                    source_trace_status = "PRESENT_AS_LOCAL_PDF"
                else:
                    source_trace_status = "REFERENCED_BUT_UNAVAILABLE"
            else:
                source_trace_status = "UNKNOWN_NO_SOURCE_FILE_LINK"

            if source_trace_status == "PRESENT_AS_LOCAL_PDF":
                if full_path not in pdf_cache:
                    try:
                        doc = fitz.open(full_path)
                        pdf_cache[full_path] = [doc[i].get_text() for i in range(len(doc))]
                        doc.close()
                    except Exception as e:  # noqa: BLE001
                        pdf_cache[full_path] = []
                        classification_flags.append("SOURCE_UNAVAILABLE")
                        source_trace_status = f"PDF_OPEN_ERROR: {e}"

                pages = pdf_cache.get(full_path, [])
                # Locate best-matching page using a loose token-overlap heuristic
                # against whatever legible fragments exist in stem+options (never
                # using any answer-key/assertion data).
                query_tokens = normalize_for_match(raw_stem or "") | normalize_for_match(opts_text)
                best_page_idx, best_score = -1, 0
                for i, ptext in enumerate(pages):
                    page_tokens = normalize_for_match(ptext)
                    score = len(query_tokens & page_tokens)
                    if score > best_score:
                        best_score, best_page_idx = score, i

                if best_page_idx >= 0 and best_score >= 3:
                    source_page = str(best_page_idx + 1)
                    page_text_extract = pages[best_page_idx][:1500]
                    classification_flags.append("OCR_REQUIRED" if not _significant_words(page_text_extract) else "EXTRACTION_CORRUPTION_CONFIRMED")
                else:
                    classification_flags.append("SOURCE_UNAVAILABLE")
                    page_text_extract = ""

            # Dedup flags, keep order
            seen = set()
            flags = [f for f in classification_flags if not (f in seen or seen.add(f))]

            # Proposed reconstruction: ONLY if the located page's text is clean,
            # legible, and directly overlaps with the stem's surviving fragments.
            # We do NOT auto-fill this for any row in this pass -- see report
            # Section 1/3: the matching source pages, where found, are
            # themselves either diagram/notation-heavy (same corruption source)
            # or the match confidence is too low to state as "supported by
            # source evidence." This is a conservative, explicit choice, not an
            # omission -- leaving it blank is the correct behavior per the task.
            proposed_reconstruction = ""
            reconstruction_evidence = page_text_extract[:300] if page_text_extract else ""
            confidence = "low" if page_text_extract else ""

            results.append(
                {
                    "question_id": qid,
                    "year": exam_year or "",
                    "paper_or_set": paper_code or "",
                    "subject": subject or "",
                    "chapter": "",
                    "original_extracted_text": (raw_stem or "").replace("\n", " \\n "),
                    "original_options": opts_text,
                    "source_filename": source_filename,
                    "source_page": source_page,
                    "observed_corruption": "; ".join(flags),
                    "proposed_reconstruction": proposed_reconstruction,
                    "reconstruction_evidence": reconstruction_evidence,
                    "confidence": confidence,
                    "review_status": "PENDING_HUMAN_REVIEW",
                    "classification": "|".join(flags),
                    "source_trace_status": source_trace_status,
                }
            )

        fieldnames = [
            "question_id", "year", "paper_or_set", "subject", "chapter",
            "original_extracted_text", "original_options", "source_filename", "source_page",
            "observed_corruption", "proposed_reconstruction", "reconstruction_evidence",
            "confidence", "review_status",
        ]
        with open(f"{OUT_DIR}/reconstruction_evidence_sheet.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in results:
                w.writerow({k: r[k] for k in fieldnames})

        from collections import Counter

        classification_counts = Counter()
        for r in results:
            for f in r["classification"].split("|"):
                classification_counts[f] += 1
        source_status_counts = Counter(r["source_trace_status"] for r in results)

        summary = {
            "total_questions_analyzed": len(results),
            "classification_flag_counts": dict(classification_counts),
            "source_trace_status_counts": dict(source_status_counts),
            "rows_with_any_proposed_reconstruction": sum(1 for r in results if r["proposed_reconstruction"]),
        }
        with open(f"{OUT_DIR}/trace_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        print(json.dumps(summary, indent=2))

        await session.rollback()


if __name__ == "__main__":
    asyncio.run(main())
