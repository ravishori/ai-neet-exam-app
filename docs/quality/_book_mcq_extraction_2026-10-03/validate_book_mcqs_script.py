"""Validate the 148 extracted book MCQs: near-duplicate detection (with
deterministic answer inheritance from high-confidence matches to already
VERIFIED existing PYQs), chapter/topic classification against the project's
own curriculum taxonomy, and diagram page extraction for figure-dependent
questions. No AI, no network calls. Read-only against the DB except the
final, explicit staging import in Phase 2."""
from __future__ import annotations
import asyncio, json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.modules.knowledge.services.grounding_check import _significant_words
import fitz

EVIDENCE_DIR = r"D:\ravishori\AI Neet Exam App\docs\quality\_book_mcq_extraction_2026-10-03"
SOURCE_FILES = {
    "Chemistry": r"D:\ravishori\AI Neet Exam App\PYExamPapers\2024\NEET 2024 Paper - Chemistry.pdf",
    "Physics": r"D:\ravishori\AI Neet Exam App\PYExamPapers\2024\NEET 2024 Paper - Physics.pdf",
    "Botany": r"D:\ravishori\AI Neet Exam App\PYExamPapers\2024\NEET 2024 Paper-Botany.pdf",
}

TAXONOMY_PATH = r"D:\ravishori\AI Neet Exam App\NEET_UG_2026_Curriculum_Taxonomy.txt"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_taxonomy_chapters() -> dict[str, list[tuple[str, set]]]:
    """Coarse subject -> list of (chapter_label, significant_words) from the
    taxonomy file's unit/topic lines, for keyword-overlap chapter matching."""
    subjects: dict[str, list[tuple[str, set]]] = {"PHYSICS": [], "CHEMISTRY": [], "BIOLOGY": []}
    current = None
    current_unit = None
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        for line in f:
            s = line.strip().lstrip("│├└─ ")
            if s.startswith("1. PHYSICS"):
                current = "PHYSICS"
            elif s.startswith("2. CHEMISTRY"):
                current = "CHEMISTRY"
            elif s.startswith("3. BIOLOGY"):
                current = "BIOLOGY"
            if current and s.startswith("UNIT"):
                current_unit = s
                subjects[current].append((current_unit, set()))
            elif current and current_unit and s and not s.startswith("│") and len(s) > 3:
                words = _significant_words(s)
                if subjects[current] and subjects[current][-1][0] == current_unit:
                    subjects[current][-1][1].update(words)
    return subjects


async def main():
    with open(f"{EVIDENCE_DIR}/extracted_book_mcqs.json", encoding="utf-8") as f:
        extracted = json.load(f)
    assert len(extracted) == 158

    taxonomy = load_taxonomy_chapters()
    subj_map = {"Chemistry": "CHEMISTRY", "Physics": "PHYSICS", "Botany": "BIOLOGY"}

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT q.id, q.raw_stem, q.state, a.asserted_option, a.verification_status "
                    "FROM pyq.questions q LEFT JOIN pyq.answer_assertions a ON a.question_id = q.id"
                )
            )
        ).all()
        existing = []
        for qid, stem, state, opt, vstatus in rows:
            existing.append(
                {
                    "id": str(qid),
                    "words": _significant_words(stem or ""),
                    "norm": norm(stem or ""),
                    "state": state,
                    "answer": opt,
                    "verified": vstatus == "VERIFIED",
                }
            )
        await session.rollback()

    results = []
    for q in extracted:
        q_words = _significant_words(q["stem"])
        q_norm = norm(q["stem"])

        classification = "unique"
        best_match = None
        best_score = 0.0
        for e in existing:
            if e["norm"] == q_norm:
                classification = "exact_duplicate"
                best_match = e
                best_score = 1.0
                break
            score = jaccard(q_words, e["words"])
            if score > best_score:
                best_score = score
                best_match = e

        inherited_answer = None
        inherited_answer_source = None
        if classification != "exact_duplicate":
            if best_score >= 0.85:
                classification = "near_duplicate_high_confidence"
                if best_match and best_match["verified"] and best_match["answer"]:
                    inherited_answer = best_match["answer"]
                    inherited_answer_source = f"inherited_from_verified_pyq:{best_match['id']}:similarity={best_score:.2f}"
            elif best_score >= 0.55:
                classification = "near_duplicate_uncertain"  # flagged for review, not discarded
            else:
                classification = "unique"

        # Within-batch duplicate check (against other extracted questions, same subject)
        within_batch_dupe = False
        for other in extracted:
            if other is q:
                continue
            if other["subject"] == q["subject"] and norm(other["stem"]) == q_norm:
                within_batch_dupe = True
                break

        # Chapter/topic classification via taxonomy keyword overlap
        tax_subject = subj_map.get(q["subject"], "")
        best_chapter, best_chapter_score = "", 0.0
        for chapter_label, chapter_words in taxonomy.get(tax_subject, []):
            score = jaccard(q_words, chapter_words)
            if score > best_chapter_score:
                best_chapter_score = score
                best_chapter = chapter_label
        chapter_assigned = best_chapter if best_chapter_score >= 0.08 else ""  # conservative floor

        results.append(
            {
                **q,
                "classification": classification,
                "best_match_existing_id": best_match["id"] if best_match and classification != "unique" else "",
                "match_similarity": round(best_score, 3),
                "within_batch_duplicate": within_batch_dupe,
                "inherited_answer": inherited_answer,
                "inherited_answer_source": inherited_answer_source,
                "taxonomy_chapter": chapter_assigned,
                "taxonomy_chapter_confidence": round(best_chapter_score, 3),
            }
        )

    from collections import Counter

    print("classification_counts:", Counter(r["classification"] for r in results))
    print("within_batch_duplicates:", sum(1 for r in results if r["within_batch_duplicate"]))
    print("inherited_answers:", sum(1 for r in results if r["inherited_answer"]))
    print("chapter_assigned:", sum(1 for r in results if r["taxonomy_chapter"]))
    print("figure_dependent:", sum(1 for r in results if r["requires_figure"]))

    with open(f"{EVIDENCE_DIR}/validated_book_mcqs.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Diagram page extraction for figure-dependent questions: render the
    # full source page as an image (deterministic, no redrawing).
    os.makedirs(f"{EVIDENCE_DIR}/diagram_pages", exist_ok=True)
    diagram_log = []
    for subj, path in SOURCE_FILES.items():
        doc = fitz.open(path)
        full_text_per_page = [doc[i].get_text() for i in range(len(doc))]
        for r in results:
            if r["subject"] != subj or not r["requires_figure"]:
                continue
            # Locate the page containing this question's stem text (first 40 chars)
            needle = r["stem"][:40]
            found_page = None
            for i, pt in enumerate(full_text_per_page):
                if needle[:20] in pt:
                    found_page = i
                    break
            if found_page is not None:
                pix = doc[found_page].get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72))
                out_name = f"{subj}_q{r['question_number']}_p{found_page+1}.png"
                pix.save(f"{EVIDENCE_DIR}/diagram_pages/{out_name}")
                diagram_log.append({"subject": subj, "question_number": r["question_number"], "page": found_page + 1, "image": out_name})
            else:
                diagram_log.append({"subject": subj, "question_number": r["question_number"], "page": None, "image": None, "status": "PAGE_NOT_LOCATED"})

    with open(f"{EVIDENCE_DIR}/diagram_extraction_log.json", "w", encoding="utf-8") as f:
        json.dump(diagram_log, f, indent=2)
    print("diagram_pages_extracted:", sum(1 for d in diagram_log if d.get("image")))
    print("diagram_pages_not_located:", sum(1 for d in diagram_log if not d.get("image")))


if __name__ == "__main__":
    asyncio.run(main())
