"""Deterministic extraction of MCQs from the 3 text-native NEET 2024
chapter-wise PYQ compilation PDFs. No AI, no OCR (native text layer only).
Read-only against the database (dedup check via session.rollback()).
"""
from __future__ import annotations
import fitz, re, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FILES = {
    "Chemistry": r"D:\ravishori\AI Neet Exam App\PYExamPapers\2024\NEET 2024 Paper - Chemistry.pdf",
    "Physics": r"D:\ravishori\AI Neet Exam App\PYExamPapers\2024\NEET 2024 Paper - Physics.pdf",
    "Botany": r"D:\ravishori\AI Neet Exam App\PYExamPapers\2024\NEET 2024 Paper-Botany.pdf",
}

# A question starts with a line that is just a number (the extracted layout
# puts the question number alone on its own line), followed by stem text,
# then 4 lines each starting with "a.", "b.", "c.", "d." (case-insensitive,
# allowing a trailing space or different punctuation the source used).
Q_NUM_RE = re.compile(r"^\s*(\d{1,3})\.\s+(\S.*)$")
OPT_RE = re.compile(r"^\s*([a-dA-D])\.\s+(.+)$")


def parse_file(path: str, subject: str) -> list[dict]:
    doc = fitz.open(path)
    full_text = "\n".join(doc[i].get_text() for i in range(len(doc)))
    lines = full_text.split("\n")

    questions = []
    current_chapter = ""
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = Q_NUM_RE.match(line)
        if m:
            qnum = int(m.group(1))
            # Scan backward a few lines for the most recent non-empty,
            # non-option header line as the chapter/topic context.
            j = i - 1
            header_lines = []
            while j >= 0 and len(header_lines) < 3 and lines[j].strip():
                if not OPT_RE.match(lines[j]) and not Q_NUM_RE.match(lines[j] + "\n"):
                    header_lines.insert(0, lines[j].strip())
                j -= 1
            chapter_context = " | ".join(header_lines[-2:]) if header_lines else current_chapter

            # Collect stem lines until we hit an option line (a./b./c./d.)
            stem_lines = [m.group(2).strip()]
            k = i + 1
            while k < n and not OPT_RE.match(lines[k]):
                if lines[k].strip():
                    stem_lines.append(lines[k].strip())
                k += 1
                if k - i > 40:  # safety bound
                    break
            stem = " ".join(stem_lines).strip()

            options = {}
            while k < n:
                om = OPT_RE.match(lines[k])
                if not om:
                    break
                label = om.group(1).upper()
                options[label] = om.group(2).strip()
                k += 1
                if len(options) >= 4:
                    break

            has_figure_ref = bool(re.search(r"given figure|shown (?:in|below)|diagram", stem, re.I))

            if stem and len(options) == 4:
                questions.append(
                    {
                        "question_number": qnum,
                        "subject": subject,
                        "chapter_context": chapter_context,
                        "stem": stem,
                        "options": options,
                        "requires_figure": has_figure_ref,
                        "source_file": path.split("\\")[-1],
                    }
                )
            i = k
        else:
            i += 1
    return questions


all_q = []
for subj, path in FILES.items():
    qs = parse_file(path, subj)
    print(f"{subj}: {len(qs)} questions extracted")
    all_q.extend(qs)

print("TOTAL extracted:", len(all_q))
needs_figure = sum(1 for q in all_q if q["requires_figure"])
print("requires_figure (flagged, not dropped):", needs_figure)

with open("extracted_book_mcqs.json", "w", encoding="utf-8") as f:
    json.dump(all_q, f, indent=2, ensure_ascii=False)

for q in all_q[:3]:
    print("---")
    print(q["subject"], q["question_number"], q["chapter_context"])
    print(q["stem"][:150])
    print(q["options"])
