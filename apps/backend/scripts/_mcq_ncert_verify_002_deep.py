"""Deep-dive NCERT excerpts for selected verify-002 items."""
from __future__ import annotations

import json
import re
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[3]
compact = json.loads((ROOT / "docs/audits/_mcq_ncert_verify_002_compact.json").read_text(encoding="utf-8"))


def dump(idx: int, search_terms: list[str], extra_pages: list[int] | None = None) -> None:
    it = next(x for x in compact if x["idx"] == idx)
    print("\n" + "#" * 70)
    print(idx, it["subject"], it["concept"], "ans", it["correct"])
    print("STEM:\n", it["stem"])
    for k, v in it["options"].items():
        print(f"  {k}{'*' if k == it['correct'] else ' '}: {v}")
    print("EXPL:\n", (it["explanation"] or "")[:1200])
    pdf = Path(it["ncert_source_path"])
    doc = fitz.open(str(pdf))
    pages = set(int(p) for p in it["pages"])
    if extra_pages:
        pages |= set(extra_pages)
    for i in range(doc.page_count):
        t = doc.load_page(i).get_text("text") or ""
        if any(s.lower() in t.lower() for s in search_terms):
            pages.add(i + 1)
    for p in sorted(pages)[:14]:
        t = doc.load_page(p - 1).get_text("text") or ""
        keep = []
        for para in re.split(r"\n\s*\n", t):
            if any(s.lower() in para.lower() for s in search_terms) or p in it["pages"]:
                keep.append(para.strip())
        snippet = "\n...\n".join(keep)[:2800]
        print(f"\n--- PDF p.{p} ---")
        print(snippet[:2800])
    doc.close()


if __name__ == "__main__":
    dump(5, ["bulk modulus", "hydraulic", "volume strain"], [5, 6, 7])
    dump(10, ["ionizable", "amino acid", "enzyme", "zwitter"], None)
    dump(11, ["van't Hoff", "abnormal molar", "colligative", "i ="], None)
    dump(14, ["sucrose", "non-reducing", "glycosidic"], [7, 8, 9])
    dump(17, ["infertility", "RCH", "Reproductive and Child"], None)
    dump(19, ["spermatogenesis", "oogenesis", "puberty", "follicle"], [6, 7, 8])
    dump(20, ["antigen", "Blood Group", "anti-A", "compatible"], None)
    dump(7, ["Biocontrol", "Biofertilis"], [1])
    dump(8, ["humification", "humus", "leaching", "lignin"], [3, 4])
    dump(9, ["Avery", "Hershey", "DNase", "transformation"], [7, 8, 9])
    dump(12, ["acylation", "acid chloride", "pyridine"], [10, 11, 12])
    dump(15, ["Crystal Field", "point charges", "ligands"], [14, 15])
    dump(16, ["malignant", "metastasis", "benign"], [14, 15])
    dump(18, ["Miller", "Oparin", "Haldane", "reducing"], [1, 2, 3])
