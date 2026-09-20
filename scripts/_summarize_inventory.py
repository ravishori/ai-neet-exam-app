import json
from pathlib import Path

d = json.loads(Path(r"D:\ravishori\AI Neet Exam App\scripts\StudyMaterial_INVENTORY.json").read_text(encoding="utf-8"))
neet = [f for f in d["files"] if f["subject"] in ("Physics", "Chemistry", "Biology")]
print("NEET PDFs", len(neet), "pages", sum(f["page_count"] or 0 for f in neet))
for sub in ("Physics", "Chemistry", "Biology"):
    for cls in ("11", "12"):
        xs = [f for f in neet if f["subject"] == sub and f["class"] == cls]
        pages = sum(f["page_count"] or 0 for f in xs)
        print(f"{sub} Class {cls}: {len(xs)} files, {pages} pages")
print("Maths (out of NEET MCQ target):", sum(1 for f in d["files"] if f["subject"] == "Maths"))
print("Duplicates:", d["duplicate_count"])
print("All readability ok:", d["by_readability"])
