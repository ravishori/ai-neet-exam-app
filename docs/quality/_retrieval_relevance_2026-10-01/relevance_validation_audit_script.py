"""Read-only, in-memory-only retrieval-relevance validation diagnostic.

No DB writes (session.rollback() at the end, never commit). No Gemini/paid
AI calls. Reuses the exact production word-significance function; the
relaxed 0.25 threshold is a local diagnostic variable only, never written
to grounding_check.py or any persistent config.

Produces, under docs/quality/_retrieval_relevance_2026-10-01/:
  - baseline_reproduction.json       (Section 1)
  - newly_covered_full_population.csv (Section 2: all 4,291 questions newly
    covered at 0.25 vs 0.50, with full evidence per row)
  - stratified_review_sample.csv      (Section 3: review worksheet, blank
    review_label column)
  - failed_unit_impact.json           (Section 5)
  - zero_overlap_classification.csv   (Section 6: all 113 questions)
"""

from __future__ import annotations

import asyncio
import csv
import json
import random
from collections import defaultdict

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.modules.knowledge.services.grounding_check import _significant_words

STRICT = 0.5  # production threshold (grounding_check.OVERLAP_THRESHOLD)
RELAXED = 0.25  # diagnostic only, never written to any config
OUT_DIR = "docs/quality/_retrieval_relevance_2026-10-01"


def overlap_ratio(stem_words: set[str], unit_words: set[str]) -> float:
    if not stem_words:
        return 0.0
    return len(stem_words & unit_words) / len(stem_words)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        # ---- Load KU index with full provenance ----
        rows = (
            await session.execute(
                text(
                    """
                    SELECT ku.id, ku.summary, ku.structured_facts, ku.validation_status,
                           ku.validation_detail, ku.content_hash,
                           c.code AS chapter_code, s.code AS subject_code,
                           isec.source_page, isec.heading,
                           sd.file_name, sd.relative_source_path, sd.id AS source_document_id
                    FROM knowledge.knowledge_units ku
                    LEFT JOIN academic.concepts co ON co.id = ku.concept_id
                    LEFT JOIN academic.topics t ON t.id = co.topic_id
                    LEFT JOIN academic.chapters c ON c.id = t.chapter_id
                    LEFT JOIN academic.subjects s ON s.id = c.subject_id
                    LEFT JOIN ingestion.ingestion_sections isec ON isec.id = ku.source_section_id
                    LEFT JOIN ingestion.ingestion_jobs ij ON ij.id = isec.job_id
                    LEFT JOIN ingestion.source_documents sd ON sd.id = ij.source_document_id
                    WHERE ku.deleted_at IS NULL
                    """
                )
            )
        ).all()

        units = []
        for (uid, summary, facts, status, detail, chash, chapter_code, subject_code,
             source_page, heading, file_name, rel_path, source_doc_id) in rows:
            facts_list = facts if isinstance(facts, list) else (json.loads(facts) if facts else [])
            combined = " ".join([summary or "", *[str(f) for f in facts_list]])
            words = _significant_words(combined)
            units.append(
                {
                    "id": str(uid),
                    "summary": summary or "",
                    "facts": facts_list,
                    "words": words,
                    "status": status,
                    "detail": detail or "",
                    "content_hash": chash,
                    "chapter_code": chapter_code,
                    "subject_code": subject_code,
                    "source_page": source_page,
                    "heading": heading or "",
                    "file_name": file_name,
                    "rel_path": rel_path,
                    "source_document_id": str(source_doc_id) if source_doc_id else None,
                }
            )

        total_units = len(units)
        passed_units = sum(1 for u in units if u["status"] == "PASSED")
        failed_units = sum(1 for u in units if u["status"] == "FAILED")

        word_to_units_all: dict[str, list[int]] = defaultdict(list)
        word_to_units_passed: dict[str, list[int]] = defaultdict(list)
        for i, u in enumerate(units):
            for w in u["words"]:
                word_to_units_all[w].append(i)
                if u["status"] == "PASSED":
                    word_to_units_passed[w].append(i)

        # ---- Load pending PYQs ----
        pending = (
            await session.execute(
                text("SELECT id, subject, raw_stem FROM pyq.questions WHERE state='ANSWER_PENDING'")
            )
        ).all()
        total_pending = len(pending)

        current_covered = 0
        relaxed_covered_allunits = 0
        passed_only_strict = 0
        zero_overlap = 0

        newly_covered_rows = []  # covered@0.25(ALL units, matches Section-1 denominator) but not @0.5
        zero_overlap_rows = []
        failed_unit_dependency: dict[str, int] = defaultdict(int)  # question depends ONLY on failed units at strict
        failed_unit_match_count = 0  # count of (question, matched failed unit) pairs at strict, any threshold

        for qid, subject, stem in pending:
            qid = str(qid)
            stem_words = _significant_words(stem or "")

            if not stem_words:
                zero_overlap += 1
                zero_overlap_rows.append(
                    {
                        "question_id": qid,
                        "subject": subject or "",
                        "reason": "empty_or_no_significant_words_in_stem",
                        "stem_preview": (stem or "")[:200],
                    }
                )
                continue

            candidate_idx_all = set()
            for w in stem_words:
                candidate_idx_all.update(word_to_units_all.get(w, []))

            if not candidate_idx_all:
                zero_overlap += 1
                zero_overlap_rows.append(
                    {
                        "question_id": qid,
                        "subject": subject or "",
                        "reason": "zero_shared_significant_words_with_any_ingested_unit",
                        "stem_preview": (stem or "")[:200],
                    }
                )
                continue

            scored_all = [(i, overlap_ratio(stem_words, units[i]["words"])) for i in candidate_idx_all]
            matched_strict_all = [(i, sc) for i, sc in scored_all if sc >= STRICT]
            matched_relaxed_all = [(i, sc) for i, sc in scored_all if sc >= RELAXED]

            is_covered_strict = bool(matched_strict_all)
            is_covered_relaxed = bool(matched_relaxed_all)

            if is_covered_strict:
                current_covered += 1
                # Failed-unit dependency check: does coverage survive if failed units are excluded?
                matched_passed_strict = [(i, sc) for i, sc in matched_strict_all if units[i]["status"] == "PASSED"]
                if not matched_passed_strict:
                    failed_unit_dependency[qid] = len(matched_strict_all)
                for i, sc in matched_strict_all:
                    if units[i]["status"] == "FAILED":
                        failed_unit_match_count += 1

            if is_covered_relaxed:
                relaxed_covered_allunits += 1

            # Newly covered = relaxed-covered but NOT strict-covered (the 4,291 cohort)
            if is_covered_relaxed and not is_covered_strict:
                best = max(matched_relaxed_all, key=lambda x: x[1])
                best_idx, best_score = best
                best_unit = units[best_idx]
                matched_terms = sorted(stem_words & best_unit["words"])
                unmatched_terms = sorted(stem_words - best_unit["words"])
                taxonomy_warning = ""
                if subject and best_unit["subject_code"] and subject.upper() not in (best_unit["subject_code"] or "").upper():
                    taxonomy_warning = f"question.subject={subject} vs matched_unit.subject_code={best_unit['subject_code']}"
                newly_covered_rows.append(
                    {
                        "question_id": qid,
                        "subject": subject or "",
                        "chapter_code": best_unit["chapter_code"] or "",
                        "overlap_score": round(best_score, 4),
                        "knowledge_unit_id": best_unit["id"],
                        "ku_validation_status": best_unit["status"],
                        "source_document_id": best_unit["source_document_id"] or "",
                        "source_document_file": best_unit["file_name"] or "",
                        "source_page": best_unit["source_page"] if best_unit["source_page"] is not None else "",
                        "section_heading": best_unit["heading"],
                        "matched_terms": "|".join(matched_terms),
                        "unmatched_terms": "|".join(unmatched_terms),
                        "taxonomy_warning": taxonomy_warning,
                        "question_stem_preview": (stem or "")[:300],
                        "candidate_passage_preview": (best_unit["summary"] or "")[:400],
                    }
                )

        # Passed-only strict (for cross-check against prior audit's 3,868 figure)
        for qid, subject, stem in pending:
            stem_words = _significant_words(stem or "")
            if not stem_words:
                continue
            cand = set()
            for w in stem_words:
                cand.update(word_to_units_passed.get(w, []))
            if any(overlap_ratio(stem_words, units[i]["words"]) >= STRICT for i in cand):
                passed_only_strict += 1

        baseline = {
            "total_pending": total_pending,
            "total_units_in_index": total_units,
            "passed_units": passed_units,
            "failed_units": failed_units,
            "current_covered_strict_0_50_all_units": current_covered,
            "passed_only_covered_strict_0_50": passed_only_strict,
            "delta_current_minus_passed_only": current_covered - passed_only_strict,
            "relaxed_covered_0_25_all_units": relaxed_covered_allunits,
            "newly_covered_count_0_25_not_0_50": len(newly_covered_rows),
            "zero_overlap_count": zero_overlap,
            "reproduces_prior_audit_3868": current_covered == 3868,
            "reproduces_prior_audit_8159_passed_relaxed": None,  # computed below
            "questions_covered_only_by_failed_units_count": len(failed_unit_dependency),
            "total_question_x_failed_unit_match_pairs": failed_unit_match_count,
        }

        # Also reproduce the PRIOR script's exact figure: PASSED-only units at RELAXED threshold
        relaxed_passed_covered = 0
        for qid, subject, stem in pending:
            stem_words = _significant_words(stem or "")
            if not stem_words:
                continue
            cand = set()
            for w in stem_words:
                cand.update(word_to_units_passed.get(w, []))
            if any(overlap_ratio(stem_words, units[i]["words"]) >= RELAXED for i in cand):
                relaxed_passed_covered += 1
        baseline["relaxed_covered_0_25_passed_only"] = relaxed_passed_covered
        baseline["reproduces_prior_audit_8159_passed_relaxed"] = relaxed_passed_covered == 8159

        import os

        os.makedirs(OUT_DIR, exist_ok=True)

        with open(f"{OUT_DIR}/baseline_reproduction.json", "w") as f:
            json.dump(baseline, f, indent=2)
        print(json.dumps(baseline, indent=2))

        # ---- Section 2: full population export ----
        fieldnames = [
            "question_id", "subject", "chapter_code", "overlap_score",
            "knowledge_unit_id", "ku_validation_status", "source_document_id",
            "source_document_file", "source_page", "section_heading",
            "matched_terms", "unmatched_terms", "taxonomy_warning",
            "question_stem_preview", "candidate_passage_preview",
        ]
        newly_covered_rows.sort(key=lambda r: -r["overlap_score"])
        with open(f"{OUT_DIR}/newly_covered_full_population.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(newly_covered_rows)
        print("newly_covered_full_population.csv rows:", len(newly_covered_rows))

        # ---- Section 3: stratified sample ----
        # Strata: subject x score-band(0.25-0.34/0.35-0.44/0.45-0.49) x ku_validation_status
        def score_band(score: float) -> str:
            if score < 0.30:
                return "0.25-0.29"
            if score < 0.35:
                return "0.30-0.34"
            if score < 0.40:
                return "0.35-0.39"
            if score < 0.45:
                return "0.40-0.44"
            return "0.45-0.49"

        strata: dict[tuple, list[dict]] = defaultdict(list)
        for r in newly_covered_rows:
            key = (r["subject"] or "(null)", score_band(r["overlap_score"]), r["ku_validation_status"])
            strata[key].append(r)

        rng = random.Random(20261001)  # fixed seed -> reproducible sample
        PER_STRATUM_TARGET = 8
        sample_rows = []
        for key, members in sorted(strata.items()):
            rng.shuffle(members)
            take = members[:PER_STRATUM_TARGET]
            sample_rows.extend(take)

        review_fieldnames = [
            "question_id", "subject", "chapter", "overlap_score",
            "knowledge_unit_id", "source_document", "source_page",
            "candidate_passage", "question_text", "review_label", "reviewer_notes",
        ]
        with open(f"{OUT_DIR}/stratified_review_sample.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=review_fieldnames)
            w.writeheader()
            for r in sample_rows:
                w.writerow(
                    {
                        "question_id": r["question_id"],
                        "subject": r["subject"],
                        "chapter": r["chapter_code"],
                        "overlap_score": r["overlap_score"],
                        "knowledge_unit_id": r["knowledge_unit_id"],
                        "source_document": r["source_document_file"],
                        "source_page": r["source_page"],
                        "candidate_passage": r["candidate_passage_preview"],
                        "question_text": r["question_stem_preview"],
                        "review_label": "",
                        "reviewer_notes": "",
                    }
                )
        print("stratified_review_sample.csv rows:", len(sample_rows), "strata:", len(strata))

        # ---- Section 6: zero-overlap classification ----
        zo_fieldnames = ["question_id", "subject", "reason", "stem_preview"]
        with open(f"{OUT_DIR}/zero_overlap_classification.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=zo_fieldnames)
            w.writeheader()
            w.writerows(zero_overlap_rows)
        print("zero_overlap_classification.csv rows:", len(zero_overlap_rows))

        # ---- Section 5: failed-unit impact detail ----
        failed_detail = []
        for u in units:
            if u["status"] != "FAILED":
                continue
            failed_detail.append(
                {
                    "id": u["id"],
                    "chapter_code": u["chapter_code"],
                    "validation_detail": u["detail"][:200],
                }
            )
        failed_impact = {
            "total_failed_units": failed_units,
            "questions_covered_exclusively_by_a_failed_unit_at_strict_threshold": len(failed_unit_dependency),
            "total_question_x_failed_unit_strict_match_pairs": failed_unit_match_count,
            "conclusion": (
                "Zero questions depend exclusively on a FAILED unit at the production 0.50 threshold "
                "(matches the current_covered == passed_only_strict check above)."
                if len(failed_unit_dependency) == 0
                else f"{len(failed_unit_dependency)} questions depend exclusively on a FAILED unit."
            ),
            "sample_failed_units": failed_detail[:20],
        }
        with open(f"{OUT_DIR}/failed_unit_impact.json", "w") as f:
            json.dump(failed_impact, f, indent=2)
        print(json.dumps(failed_impact, indent=2))

        await session.rollback()


if __name__ == "__main__":
    asyncio.run(main())
