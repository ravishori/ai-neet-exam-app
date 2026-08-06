"""Assemble Volume 1 master Markdown and clean filler."""
from __future__ import annotations

import re
from pathlib import Path

DIR = Path(__file__).resolve().parent

PARTS = [
    "01-front-matter-and-strategy.md",
    "02-market-and-business.md",
    "03-product-design.md",
    "04-requirements-and-scope.md",
    "05-risk-metrics-governance.md",
]


def strip_yaml(body: str) -> str:
    text = body.lstrip()
    if not text.startswith("---"):
        return body
    rest = text[3:]
    end = rest.find("\n---")
    if end == -1:
        return body
    return rest[end + 4 :].lstrip("\n")


def clean_part5() -> None:
    path = DIR / "05-risk-metrics-governance.md"
    text = path.read_text(encoding="utf-8")
    marker = "\n### Enterprise elaboration"
    idx = text.find(marker)
    if idx == -1:
        print("No elaboration marker in 05")
        return
    cleaned = (
        text[:idx].rstrip()
        + "\n\n---\n\n"
        + "*End of Part E (`05-risk-metrics-governance.md`). "
        + "Duplicate elaboration padding removed during Volume 1 assembly.*\n"
    )
    path.write_text(cleaned, encoding="utf-8")
    print(f"Cleaned 05: removed {len(text) - idx} chars of filler")


def assemble() -> None:
    header = """---
title: "Trinetra AI Learning OS (TALOS) — Volume 1: Executive & Product Blueprint"
subtitle: "AI NEET Exam App — First Product Vertical"
author:
  - "Office of the CTO"
  - "Chief Software Architect"
  - "Product Strategy"
date: "2026-08-07"
version: "1.0.0"
document_id: "TALOS-VOL-01"
classification: "Internal — Confidential"
toc: true
toc-depth: 3
numbersections: true
---

\\newpage

"""
    chunks: list[str] = [header]
    for i, name in enumerate(PARTS):
        body = (DIR / name).read_text(encoding="utf-8")
        if name.startswith("01"):
            body = strip_yaml(body)
        if i > 0:
            chunks.append("\n\\newpage\n\n")
        chunks.append(body if body.endswith("\n") else body + "\n")

    out = DIR / "VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md"
    out.write_text("".join(chunks), encoding="utf-8")
    print(f"Wrote {out}")


def report() -> None:
    print("--- WORD COUNTS ---")
    part_total = 0
    for name in PARTS + ["VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md"]:
        text = (DIR / name).read_text(encoding="utf-8")
        words = len(text.split())
        print(f"{name}: {words} words (~{words / 400:.1f} pages)")
        if name != "VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md":
            part_total += words
    print(f"SUM PARTS: {part_total} words (~{part_total / 400:.1f} pages)")

    master = (DIR / "VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md").read_text(encoding="utf-8")
    print("--- CHAPTER CHECK ---")
    for n in range(1, 41):
        ok = bool(re.search(rf"^#{{1,3}} {n}\. ", master, re.M))
        if not ok or n in {1, 12, 13, 19, 24, 31, 40}:
            print(f"Ch {n}: {'OK' if ok else 'MISSING'}")


if __name__ == "__main__":
    clean_part5()
    assemble()
    report()
