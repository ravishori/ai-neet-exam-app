"""Re-verify SME VERIFIED promotions against chapter PDF text.

Demotes VERIFIED → REVIEW when distinctive answer/claim tokens are absent
from the mapped NCERT PDF(s). Does not invent citations.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import fitz

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
OUT = REPO / "docs" / "acquisition" / "flashcards" / "SEED-V1"
ZIP_PATH = REPO / "StudyMaterial (2).zip"

STOP = {
    "the", "and", "or", "of", "a", "an", "in", "to", "is", "are", "for", "with", "by",
    "from", "that", "this", "as", "on", "at", "be", "it", "its", "into", "which", "when",
    "what", "how", "why", "name", "state", "define", "give", "write", "example", "claim",
    "both", "have", "has", "also", "each", "using", "used", "via", "such", "than", "then",
}

# Chapter → PDF paths (subject-aware where needed)
CHAPTER_PDFS: dict[str, list[str]] = {
    "The Living World": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-1.pdf"],
    "Biological Classification": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-2.pdf"],
    "Plant Kingdom": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-3.pdf"],
    "Animal Kingdom": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-4.pdf"],
    "Morphology of Flowering Plants": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-5.pdf"],
    "Structural Organisation in Animals": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-7.pdf"],
    "Cell - The Unit of Life": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-8.pdf"],
    "Biomolecules": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-9.pdf"],
    # Rationalised: Photosynthesis is Ch 11 PDF (not Ch 13 filename)
    "Photosynthesis in Higher Plants": [
        "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf",
        "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-13.pdf",
    ],
    "Plant Growth and Development": [
        "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-15.pdf"
    ],
    "Breathing and Exchange of Gases": [
        "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-17.pdf"
    ],
    "Body Fluids and Circulation": [
        "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-18.pdf"
    ],
    "Sexual Reproduction in Flowering Plants": [
        "StudyMaterial/Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-1.pdf"
    ],
    "Human Reproduction": [
        "StudyMaterial/Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-2.pdf",
        "StudyMaterial/Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-3.pdf",
    ],
    "Some Basic Concepts of Chemistry": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-1.pdf"
    ],
    "Structure of Atom": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-2.pdf"
    ],
    "Chemical Bonding and Molecular Structure": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf"
    ],
    "Thermodynamics": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-6.pdf",
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-12.pdf",
    ],
    "Equilibrium": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-7.pdf"
    ],
    "Redox Reactions": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-8.pdf"
    ],
    "Organic Chemistry - Basic Principles": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-9.pdf"
    ],
    # Electrochemistry lives in Unit 2 / chapter-2 PDF in this corpus
    "Electrochemistry": [
        "StudyMaterial/Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-2.pdf",
        "StudyMaterial/Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-3.pdf",
    ],
    "Units and Measurement": [
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-2.pdf",
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-1.pdf",
    ],
    "Laws of Motion": ["StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-5.pdf"],
    "Work, Energy and Power": [
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-6.pdf"
    ],
    "Mechanical Properties of Solids": [
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-9.pdf"
    ],
    "Kinetic Theory": ["StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-13.pdf"],
    "Current Electricity": [
        "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf"
    ],
    "Optics": [
        "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-2-chapter-9.pdf"
    ],
}

# Explicit demotions (known unsupported in available PDFs)
FORCE_REVIEW: dict[str, str] = {}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (s or "").lower())).strip()


def tokens(s: str) -> list[str]:
    return [t for t in norm(s).split() if len(t) >= 5 and t not in STOP]


def load_corpus() -> dict[str, str]:
    cache: dict[str, str] = {}
    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = set(zf.namelist())
        for chapter, paths in CHAPTER_PDFS.items():
            blobs = []
            for rel in paths:
                data = None
                if rel in names:
                    data = zf.read(rel)
                else:
                    base = Path(rel).name.lower()
                    hit = next((n for n in names if Path(n).name.lower() == base), None)
                    if hit:
                        data = zf.read(hit)
                if data:
                    doc = fitz.open(stream=data, filetype="pdf")
                    blobs.append("\n".join(p.get_text() for p in doc))
                    doc.close()
            if blobs:
                cache[chapter] = norm("\n".join(blobs))
    return cache


def main() -> None:
    queue = {c["id"]: c for c in json.loads((OUT / "sme_review_queue.json").read_text(encoding="utf-8"))}
    corpus = load_corpus()
    demotions = []

    for fname in (
        "sme_decisions_biology.json",
        "sme_decisions_chemistry.json",
        "sme_decisions_physics.json",
    ):
        path = OUT / fname
        decisions = json.loads(path.read_text(encoding="utf-8"))
        changed = 0
        for d in decisions:
            if d["new_status"] != "VERIFIED":
                continue
            card = queue[d["id"]]
            chapter = card["chapter"]
            # Fluids/Rotational must never be VERIFIED without Class 11 PDF
            if chapter in {
                "Mechanical Properties of Fluids",
                "Systems of Particles and Rotational Motion",
            }:
                d["new_status"] = "REVIEW"
                d["evidence_class"] = "MISSING_SOURCE"
                d["reason"] = "MISSING_SOURCE: Class 11 NCERT PDF unavailable; promotion revoked"
                demotions.append(d["id"])
                changed += 1
                continue

            text = corpus.get(chapter)
            if not text:
                d["new_status"] = "REVIEW"
                d["evidence_class"] = "MISSING_SOURCE"
                d["reason"] = f"MISSING_SOURCE: no NCERT text loaded for chapter {chapter}"
                demotions.append(d["id"])
                changed += 1
                continue

            blob = " ".join(
                [
                    d.get("claim") or "",
                    card.get("back") or "",
                    card.get("front") or "",
                ]
            )
            toks = tokens(blob)
            uniq = list(dict.fromkeys(toks))[:20]
            if not uniq:
                d["new_status"] = "REVIEW"
                d["evidence_class"] = "INSUFFICIENT_EVIDENCE"
                d["reason"] = "INSUFFICIENT_EVIDENCE: no distinctive claim tokens to ground"
                demotions.append(d["id"])
                changed += 1
                continue
            hits = sum(1 for t in uniq if t in text)
            score = hits / len(uniq)

            # Special: Chargaff name absent from Biomolecules PDF
            if "chargaff" in norm(blob) and "chargaff" not in text:
                d["new_status"] = "REVIEW"
                d["evidence_class"] = "INSUFFICIENT_EVIDENCE"
                d["reason"] = (
                    "INSUFFICIENT_EVIDENCE: Chargaff not found in available NCERT Biomolecules PDF; "
                    "A=T/G=C pairing also not stated in that PDF"
                )
                d["scientific_ok"] = True
                demotions.append(d["id"])
                changed += 1
                continue

            # Require stronger grounding than original automated audit
            if score < 0.35:
                d["new_status"] = "REVIEW"
                d["evidence_class"] = "INSUFFICIENT_EVIDENCE"
                d["reason"] = (
                    f"INSUFFICIENT_EVIDENCE: claim-token support {score:.2f} against chapter PDF "
                    f"(hits={hits}/{len(uniq)}); SME promotion revoked pending stronger source"
                )
                demotions.append(d["id"])
                changed += 1
                continue

            # Annotate reverify score without changing status
            d["reverify_token_score"] = round(score, 3)

        path.write_text(json.dumps(decisions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(fname, "demotions_in_file_pass", changed)

    # recount
    from collections import Counter

    all_d = []
    for fname in (
        "sme_decisions_biology.json",
        "sme_decisions_chemistry.json",
        "sme_decisions_physics.json",
    ):
        all_d.extend(json.loads((OUT / fname).read_text(encoding="utf-8")))
    print("final", Counter(d["new_status"] for d in all_d))
    print("demoted_ids", len(set(demotions)))
    (OUT / "sme_reverify_demotions.json").write_text(
        json.dumps({"demoted_ids": demotions, "count": len(demotions)}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
