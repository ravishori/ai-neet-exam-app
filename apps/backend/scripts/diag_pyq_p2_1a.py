"""P2.1A diagnostic: locate NEEDS_REVIEW pages and analyze OCR segmentation."""
from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from pathlib import Path

import fitz

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
STAGING = ROOT / "data" / "staging" / "pyq" / "2020-2025" / "papers"
ZIP_PATH = ROOT / "NEET_PYQ_OFFICIAL.zip"
OUT = ROOT / "data" / "staging" / "pyq" / "2020-2025"

QMARK = re.compile(r"(?m)^\s*(\d{1,3})\.\s+")
QMARK_INLINE = re.compile(r"(?<!\d)(\d{1,3})\.\s+\S")
OMARK = re.compile(r"\(\s*([1-4])\s*\)")
SECTION = re.compile(r"Section\s*-\s*[AB]", re.I)


def classify_page(text: str, chars: int, anomalies: list[str]) -> list[str]:
    cats: list[str] = []
    if chars < 40 or "low_ocr_yield" in " ".join(anomalies):
        cats.append("G_or_blank_low_yield")
    if any("low_mean_confidence" in a for a in anomalies):
        cats.append("G_ocr_character_recognition")
    q_line = len(QMARK.findall(text))
    q_inline = len(QMARK_INLINE.findall(text))
    if q_inline > q_line * 2 and q_inline >= 4:
        cats.append("A_multi_column_reading_order")
    if "Space For Rough Work" in text or "Rough Work" in text:
        cats.append("D_header_footer_or_rough_work")
    if chars < 80 and ("Admit" in text or "Booklet" in text or "Signature" in text or not text.strip()):
        cats.append("D_cover_or_instruction")
    if q_line == 0 and q_inline == 0 and chars > 100:
        cats.append("B_question_number_detection_failure")
    if OMARK.search(text) and q_line == 0:
        cats.append("B_question_number_detection_failure")
    # two-column heuristic: many short lines with numbers mid-line
    mid_num = len(re.findall(r"\S\s+(\d{1,3})\.\s+\S", text))
    if mid_num >= 3:
        cats.append("A_multi_column_reading_order")
    if not cats:
        cats.append("J_other")
    return cats


def main() -> None:
    needs_pages = []
    for d in sorted(STAGING.iterdir()):
        ocr_p = d / "ocr.p2_1.json"
        pages_p = d / "ocr.pages.p2_1.jsonl"
        if not ocr_p.exists() or not pages_p.exists():
            continue
        meta = json.loads((d / "paper.json").read_text(encoding="utf-8"))
        page_texts = {json.loads(line)["page_number"]: json.loads(line) for line in pages_p.open(encoding="utf-8")}
        # re-read properly
        page_texts = {}
        for line in pages_p.open(encoding="utf-8"):
            p = json.loads(line)
            page_texts[p["page_number"]] = p
        ocr = json.loads(ocr_p.read_text(encoding="utf-8"))
        for pg in ocr.get("pages") or []:
            if pg.get("status") != "NEEDS_REVIEW" and pg.get("validation_status") != "NEEDS_REVIEW":
                continue
            raw = page_texts.get(pg["page_number"], {})
            text = raw.get("raw_text") or ""
            chars = pg.get("text_chars") or len(text.strip())
            anomalies = pg.get("anomalies") or raw.get("anomalies") or []
            cats = classify_page(text, chars, anomalies)
            needs_pages.append(
                {
                    "paper": Path(meta["source_file"]).name,
                    "sha": meta["source_sha256"],
                    "source_file": meta["source_file"],
                    "year": meta.get("exam_year"),
                    "page": pg["page_number"],
                    "status": pg.get("status"),
                    "confidence": pg.get("ocr_confidence"),
                    "text_chars": chars,
                    "q_markers_line": len(QMARK.findall(text)),
                    "q_markers_inline": len(QMARK_INLINE.findall(text)),
                    "opt_markers": len(OMARK.findall(text)),
                    "section_markers": len(SECTION.findall(text)),
                    "anomalies": anomalies,
                    "likely_categories": cats,
                    "text_preview": text[:240].replace("\n", " | "),
                }
            )

    print("NEEDS_REVIEW pages:", len(needs_pages))
    print("by year:", dict(Counter(p["year"] for p in needs_pages)))
    print("category freqs:", dict(Counter(c for p in needs_pages for c in p["likely_categories"])))
    print(
        "text_chars min/med/max:",
        min(p["text_chars"] for p in needs_pages),
        sorted(p["text_chars"] for p in needs_pages)[len(needs_pages) // 2],
        max(p["text_chars"] for p in needs_pages),
    )
    for p in needs_pages:
        print(
            p["year"],
            p["paper"][:42],
            f"p{p['page']}",
            f"chars={p['text_chars']}",
            f"qL={p['q_markers_line']}",
            f"qI={p['q_markers_inline']}",
            f"opt={p['opt_markers']}",
            f"conf={p['confidence']}",
            ",".join(p["likely_categories"]),
        )

    (OUT / "diagnostics_p2_1a_needs_pages.json").write_text(
        json.dumps(needs_pages, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Systemic: sample OCR SUCCESS pages for multi-column / question marker loss
    sample_stats = Counter()
    q_yield = []
    for d in sorted(STAGING.iterdir()):
        pages_p = d / "ocr.pages.p2_1.jsonl"
        qp = d / "questions.p2_1.jsonl"
        if not pages_p.exists():
            continue
        meta = json.loads((d / "paper.json").read_text(encoding="utf-8"))
        n_q_line = 0
        n_q_inline = 0
        n_pages = 0
        for line in pages_p.open(encoding="utf-8"):
            p = json.loads(line)
            if p.get("status") not in {"OCR_SUCCESS", "OCR_LOW_CONFIDENCE"}:
                continue
            text = p.get("raw_text") or ""
            n_pages += 1
            n_q_line += len(QMARK.findall(text))
            n_q_inline += len(QMARK_INLINE.findall(text))
            mid = len(re.findall(r"\S\s+(\d{1,3})\.\s+\S", text))
            if mid >= 3:
                sample_stats["pages_with_midline_qnums"] += 1
        n_extracted = 0
        if qp.exists():
            n_extracted = sum(1 for _ in qp.open(encoding="utf-8") if _.strip())
        q_yield.append(
            {
                "paper": Path(meta["source_file"]).name,
                "year": meta.get("exam_year"),
                "success_pages": n_pages,
                "q_line_markers": n_q_line,
                "q_inline_markers": n_q_inline,
                "extracted_questions": n_extracted,
            }
        )
        if n_q_inline > n_q_line * 1.5 and n_q_inline > 20:
            sample_stats["papers_multicolumn_suspect"] += 1
        if n_q_line < 10 and n_extracted < 20:
            sample_stats["papers_low_line_markers"] += 1

    print("\nSYSTEMIC stats:", dict(sample_stats))
    print("total extracted", sum(x["extracted_questions"] for x in q_yield))
    print("total q_line", sum(x["q_line_markers"] for x in q_yield))
    print("total q_inline", sum(x["q_inline_markers"] for x in q_yield))
    for x in sorted(q_yield, key=lambda z: z["extracted_questions"])[:5]:
        print("low yield", x)
    for x in sorted(q_yield, key=lambda z: -z["extracted_questions"])[:5]:
        print("high yield", x)

    (OUT / "diagnostics_p2_1a_yield.json").write_text(
        json.dumps({"sample_stats": dict(sample_stats), "per_paper": q_yield}, indent=2),
        encoding="utf-8",
    )

    # Render a few NEEDS_REVIEW pages for visual inspection
    vis_dir = OUT / "diagnostics_p2_1a_renders"
    vis_dir.mkdir(exist_ok=True)
    # pick diverse sample: blank, rough work, multi-column, cover
    picks = []
    for cat in [
        "G_or_blank_low_yield",
        "D_header_footer_or_rough_work",
        "A_multi_column_reading_order",
        "D_cover_or_instruction",
        "J_other",
    ]:
        for p in needs_pages:
            if cat in p["likely_categories"] and p not in picks:
                picks.append(p)
                break
    # also first 8 always
    for p in needs_pages[:8]:
        if p not in picks:
            picks.append(p)

    with zipfile.ZipFile(ZIP_PATH) as zf:
        for i, p in enumerate(picks[:12]):
            pdf = zf.read(p["source_file"])
            doc = fitz.open(stream=pdf, filetype="pdf")
            page = doc.load_page(p["page"] - 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            out_png = vis_dir / f"{i:02d}_{p['year']}_p{p['page']}_{p['sha'][:8]}.png"
            out_png.write_bytes(pix.tobytes("png"))
            # also save OCR snippet
            (vis_dir / f"{i:02d}_{p['year']}_p{p['page']}_{p['sha'][:8]}.txt").write_text(
                json.dumps(
                    {
                        "paper": p["paper"],
                        "page": p["page"],
                        "categories": p["likely_categories"],
                        "preview": p["text_preview"],
                        "chars": p["text_chars"],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            doc.close()
            print("rendered", out_png.name)

    print("done")


if __name__ == "__main__":
    main()
