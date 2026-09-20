"""P2.1A: classify 14 NEEDS_REVIEW questions + marker pattern stats."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025\papers")
OUT = Path(r"D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025")

pat_period_line = re.compile(r"(?m)^\s*(\d{1,3})\.\s+\S")
pat_noperiod_line = re.compile(r"(?m)^\s*(\d{1,3})\s+[A-Z]")
pat_pipe_q = re.compile(r"\|\s*(\d{1,3})(?:\.|\s)+(?=[A-Z(])")
pat_mid = re.compile(r"(?<=\S)\s+(\d{1,3})\.\s+(?=[A-Z(])")


def main() -> None:
    counts = {"period_line": 0, "noperiod_line": 0, "pipe_q": 0, "mid_period": 0, "pages": 0}
    for d in sorted(ROOT.iterdir()):
        pp = d / "ocr.pages.p2_1.jsonl"
        if not pp.exists():
            continue
        for line in pp.open(encoding="utf-8"):
            p = json.loads(line)
            if p.get("status") != "OCR_SUCCESS":
                continue
            t = p.get("raw_text") or ""
            counts["pages"] += 1
            counts["period_line"] += len(pat_period_line.findall(t))
            counts["noperiod_line"] += len(pat_noperiod_line.findall(t))
            counts["pipe_q"] += len(pat_pipe_q.findall(t))
            counts["mid_period"] += len(pat_mid.findall(t))
    print("marker counts on OCR_SUCCESS pages:", counts)

    results = []
    for d in sorted(ROOT.iterdir()):
        qp = d / "questions.p2_1.jsonl"
        if not qp.exists():
            continue
        meta = json.loads((d / "paper.json").read_text(encoding="utf-8"))
        pages: dict[int, str] = {}
        for line in (d / "ocr.pages.p2_1.jsonl").open(encoding="utf-8"):
            p = json.loads(line)
            pages[p["page_number"]] = p.get("raw_text") or ""
        for line in qp.open(encoding="utf-8"):
            q = json.loads(line)
            if q.get("validation_status") != "NEEDS_REVIEW":
                continue
            page = q.get("source_page")
            ocr = pages.get(page or -1, "")
            stem = q.get("stem") or ""
            reasons: list[str] = []
            verdict = "PARTIAL"

            if q.get("missing_options"):
                reasons.append("missing_options")
            if page and "SPACE FOR ROUGH WORK" in ocr:
                verdict = "INCORRECT"
                reasons.append("rough_work_page")
            if re.search(r"\|\s*\d{1,3}(?:\.|\s)", stem) or "|" in stem and re.search(r"\d{1,3}\s+[A-Z]", stem):
                verdict = "REQUIRES_RESEGMENTATION"
                reasons.append("multicolumn_contamination")
            if page and ("Read carefully" in ocr or "following instructions" in ocr.lower()):
                verdict = "INCORRECT"
                reasons.append("instruction_page_false_positive")
            if "candidate" in stem.lower() or "Admit Card" in stem or "Attendance Sheet" in stem:
                verdict = "INCORRECT"
                reasons.append("instruction_text_in_stem")
            if any(k in stem.lower() for k in ("circuit", "graph", "figure", "diagram")) and q.get("missing_options"):
                if verdict not in {"INCORRECT"}:
                    verdict = "DIAGRAM_DEPENDENT"
                    reasons.append("circuit_or_figure")
            # Hindi garbage / bilingual OCR on instruction pages
            if re.search(r"[\u0900-\u097F]", stem) and "instruction" in " ".join(reasons):
                reasons.append("bilingual_instruction_ocr")

            filled = sum(1 for k in ("option_a", "option_b", "option_c", "option_d") if (q.get(k) or "").strip())
            item = {
                "year": meta.get("exam_year"),
                "paper": Path(meta["source_file"]).name,
                "question_number": q.get("question_number"),
                "page": page,
                "options_filled": filled,
                "verdict": verdict,
                "reasons": reasons,
                "stem_preview": stem[:160].replace("\n", " "),
            }
            results.append(item)
            print(
                f"Q{item['question_number']} y={item['year']} p={page} filled={filled} -> {verdict} {reasons}"
            )
            print("  ", item["stem_preview"])

    print("verdict counts:", {v: sum(1 for r in results if r["verdict"] == v) for v in {x["verdict"] for x in results}})
    (OUT / "diagnostics_p2_1a_needs_questions_validated.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
