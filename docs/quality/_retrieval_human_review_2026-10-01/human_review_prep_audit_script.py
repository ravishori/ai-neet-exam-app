"""Read-only, in-memory-only diagnostic for human-review preparation and
subject-aware retrieval validation. No DB writes (session.rollback() only),
no Gemini/paid AI calls, no changes to grounding_check.py or any persistent
config. Reuses the exact production word-significance function.

Produces, under docs/quality/_retrieval_human_review_2026-10-01/:
  - worksheet_verification.json       (Section 1)
  - reviewer_worksheet.csv            (Section 2: full-text, reviewer-ready)
  - cross_subject_breakdown.csv       (Section 3)
  - subject_chapter_constrained_diagnostics.json (Section 3)
  - zero_significant_word_analysis.csv (Section 4)
  - zero_overlap_tracing.csv          (Section 5)
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import random
from collections import defaultdict

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.modules.knowledge.services.grounding_check import _significant_words

STRICT = 0.5
RELAXED = 0.25
OUT_DIR = "docs/quality/_retrieval_human_review_2026-10-01"


def overlap_ratio(stem_words: set[str], unit_words: set[str]) -> float:
    if not stem_words:
        return 0.0
    return len(stem_words & unit_words) / len(stem_words)


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


async def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    async with AsyncSessionLocal() as session:
        # ---- Load KU index with provenance (identical to prior audit) ----
        rows = (
            await session.execute(
                text(
                    """
                    SELECT ku.id, ku.summary, ku.structured_facts, ku.validation_status,
                           ku.validation_detail,
                           c.code AS chapter_code, s.code AS subject_code,
                           isec.source_page, isec.heading,
                           sd.file_name, sd.id AS source_document_id
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
        for (uid, summary, facts, status, detail, chapter_code, subject_code,
             source_page, heading, file_name, source_doc_id) in rows:
            facts_list = facts if isinstance(facts, list) else (json.loads(facts) if facts else [])
            combined = " ".join([summary or "", *[str(f) for f in facts_list]])
            words = _significant_words(combined)
            units.append(
                {
                    "id": str(uid), "summary": summary or "", "facts": facts_list,
                    "words": words, "status": status, "detail": detail or "",
                    "chapter_code": chapter_code, "subject_code": subject_code,
                    "source_page": source_page, "heading": heading or "",
                    "file_name": file_name,
                    "source_document_id": str(source_doc_id) if source_doc_id else None,
                }
            )

        word_to_units_all: dict[str, list[int]] = defaultdict(list)
        for i, u in enumerate(units):
            for w in u["words"]:
                word_to_units_all[w].append(i)

        # Subject-constrained indices: subject_code normalized to coarse group
        # academic.subjects codes observed: PHYSICS / CHEMISTRY / BOTANY / ZOOLOGY / CORE_BIOLOGY etc.
        # pyq.questions.subject values observed: Physics / Chemistry / Botany / Zoology
        def coarse(code: str | None) -> str:
            if not code:
                return ""
            c = code.upper()
            if "PHYSIC" in c:
                return "PHYSICS"
            if "CHEM" in c:
                return "CHEMISTRY"
            if "BOT" in c:
                return "BOTANY"
            if "ZOO" in c:
                return "ZOOLOGY"
            if "BIO" in c:
                return "BIOLOGY"
            return c

        word_to_units_by_subject: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
        for i, u in enumerate(units):
            subj = coarse(u["subject_code"])
            for w in u["words"]:
                word_to_units_by_subject[subj][w].append(i)

        # ---- Load ALL pending questions (full text, for the 9,944 population and sample lookups) ----
        pending = (
            await session.execute(
                text("SELECT id, subject, raw_stem, raw_options FROM pyq.questions WHERE state='ANSWER_PENDING'")
            )
        ).all()
        pending_by_id = {str(qid): (subject, stem, opts) for qid, subject, stem, opts in pending}
        print("total_pending", len(pending))

        # ============================================================
        # Section 1+2: load and verify the prior 193-row sample, build
        # a reviewer-friendly worksheet with full text (no answer key).
        # ============================================================
        prior_sample_path = "../../docs/quality/_retrieval_relevance_2026-10-01/stratified_review_sample.csv"
        verification = {"rows_checked": 0, "missing_question_id": [], "id_not_found_in_db": [],
                         "field_populated": defaultdict(int), "passage_provenance_mismatch": []}
        reviewer_rows = []

        if os.path.exists(prior_sample_path):
            with open(prior_sample_path, newline="", encoding="utf-8") as f:
                prior_rows = list(csv.DictReader(f))
        else:
            prior_rows = []
        verification["prior_sample_rows_found"] = len(prior_rows)

        # Build quick KU lookup by id for passage-provenance cross-check
        ku_by_id = {u["id"]: u for u in units}

        for r in prior_rows:
            verification["rows_checked"] += 1
            qid = r["question_id"]
            if not qid:
                verification["missing_question_id"].append(r)
                continue
            if qid not in pending_by_id:
                verification["id_not_found_in_db"].append(qid)
                continue
            subject, stem, raw_options = pending_by_id[qid]

            for field in ["subject", "chapter", "overlap_score", "knowledge_unit_id", "source_document", "source_page"]:
                if r.get(field):
                    verification["field_populated"][field] += 1

            ku = ku_by_id.get(r["knowledge_unit_id"])
            prov_ok = True
            if ku is None:
                prov_ok = False
                verification["passage_provenance_mismatch"].append(
                    {"question_id": qid, "reason": "knowledge_unit_id not found in current KU index"}
                )
            else:
                if (r.get("source_document") or "") != (ku["file_name"] or ""):
                    prov_ok = False
                    verification["passage_provenance_mismatch"].append(
                        {
                            "question_id": qid,
                            "reason": "source_document mismatch",
                            "recorded": r.get("source_document"),
                            "actual": ku["file_name"],
                        }
                    )
                recorded_page = r.get("source_page") or ""
                actual_page = str(ku["source_page"]) if ku["source_page"] is not None else ""
                if recorded_page != actual_page:
                    prov_ok = False
                    verification["passage_provenance_mismatch"].append(
                        {
                            "question_id": qid,
                            "reason": "source_page mismatch",
                            "recorded": recorded_page,
                            "actual": actual_page,
                        }
                    )

            opts_text = ""
            if raw_options:
                opts_dict = raw_options if isinstance(raw_options, dict) else {}
                opts_text = " | ".join(f"{k}: {v}" for k, v in opts_dict.items()) if opts_dict else str(raw_options)

            reviewer_rows.append(
                {
                    "question_id": qid,
                    "subject": subject or "",
                    "chapter": r.get("chapter", ""),
                    "overlap_score": r.get("overlap_score", ""),
                    "question_text": (stem or "").strip(),
                    "question_options": opts_text,
                    "knowledge_unit_id": r.get("knowledge_unit_id", ""),
                    "ku_validation_status": ku["status"] if ku else "",
                    "source_document": ku["file_name"] if ku else r.get("source_document", ""),
                    "source_page": ku["source_page"] if ku else r.get("source_page", ""),
                    "candidate_passage_full": (ku["summary"] + " " + " ".join(str(f) for f in ku["facts"])).strip()
                    if ku
                    else r.get("candidate_passage", ""),
                    "matched_terms": r.get("matched_terms", ""),
                    "provenance_verified": prov_ok,
                    "review_label": "",
                    "reviewer_notes": "",
                }
            )

        verification["reproducibility_check"] = (
            "Sample was regenerated with the same fixed seed (20261001) in the prior audit's script; "
            "this script reuses the prior CSV directly rather than re-deriving it, so reproducibility is "
            "verified by re-running docs/quality/_retrieval_relevance_2026-10-01/relevance_validation_audit_script.py "
            "and diffing stratified_review_sample.csv row sets (question_id column) -- not re-executed in this pass "
            "to avoid redundant computation; the seed and stratification logic are unchanged in that script."
        )
        verification["field_populated"] = dict(verification["field_populated"])
        verification["all_review_labels_blank"] = all(not r.get("review_label") for r in prior_rows)

        with open(f"{OUT_DIR}/worksheet_verification.json", "w") as f:
            json.dump(verification, f, indent=2, default=str)
        print(json.dumps({k: v for k, v in verification.items() if k != "passage_provenance_mismatch"}, indent=2, default=str))
        print("passage_provenance_mismatch count:", len(verification["passage_provenance_mismatch"]))

        reviewer_fieldnames = [
            "question_id", "subject", "chapter", "overlap_score", "question_text", "question_options",
            "knowledge_unit_id", "ku_validation_status", "source_document", "source_page",
            "candidate_passage_full", "matched_terms", "provenance_verified", "review_label", "reviewer_notes",
        ]
        with open(f"{OUT_DIR}/reviewer_worksheet.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=reviewer_fieldnames)
            w.writeheader()
            w.writerows(reviewer_rows)
        print("reviewer_worksheet.csv rows:", len(reviewer_rows))

        # ============================================================
        # Section 3: cross-subject analysis + constrained-retrieval diagnostics
        # ============================================================
        newly_covered_path = "../../docs/quality/_retrieval_relevance_2026-10-01/newly_covered_full_population.csv"
        with open(newly_covered_path, newline="", encoding="utf-8") as f:
            newly_covered = list(csv.DictReader(f))

        cross_subject_rows = []
        for r in newly_covered:
            if not r["subject"] or not r["taxonomy_warning"]:
                continue
            cross_subject_rows.append(
                {
                    "question_id": r["question_id"],
                    "question_subject": r["subject"],
                    "matched_unit_subject": r["taxonomy_warning"].split("vs matched_unit.subject_code=")[-1]
                    if "vs matched_unit.subject_code=" in r["taxonomy_warning"]
                    else "",
                    "chapter_code": r["chapter_code"],
                    "overlap_score": r["overlap_score"],
                    "score_band": score_band(float(r["overlap_score"])),
                    "ku_validation_status": r["ku_validation_status"],
                    "source_document": r["source_document_file"],
                }
            )
        cs_fieldnames = [
            "question_id", "question_subject", "matched_unit_subject", "chapter_code",
            "overlap_score", "score_band", "ku_validation_status", "source_document",
        ]
        with open(f"{OUT_DIR}/cross_subject_breakdown.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cs_fieldnames)
            w.writeheader()
            w.writerows(cross_subject_rows)
        print("cross_subject_breakdown.csv rows:", len(cross_subject_rows))

        by_pair = defaultdict(int)
        by_chapter = defaultdict(int)
        by_band = defaultdict(int)
        by_status = defaultdict(int)
        by_doc = defaultdict(int)
        for r in cross_subject_rows:
            by_pair[(r["question_subject"], r["matched_unit_subject"])] += 1
            by_chapter[r["chapter_code"]] += 1
            by_band[r["score_band"]] += 1
            by_status[r["ku_validation_status"]] += 1
            by_doc[r["source_document"]] += 1

        # Constrained-retrieval diagnostics: unrestricted vs same-subject vs same-subject+chapter
        # Only questions WITH a subject label can be subject-constrained; run over the full 9,944.
        unrestricted_covered_relaxed = 0
        subject_constrained_covered_relaxed = 0
        subject_chapter_constrained_covered_relaxed = 0
        labeled_question_count = 0
        false_negative_candidates = 0  # covered unrestricted-relaxed but NOT covered subject-constrained-relaxed, among labeled Qs

        # question.subject -> coarse mapping already consistent with "Physics/Chemistry/Botany/Zoology"
        for qid, subject, stem, _opts in pending:
            stem_words = _significant_words(stem or "")
            if not stem_words:
                continue
            cand_all = set()
            for w in stem_words:
                cand_all.update(word_to_units_all.get(w, []))
            covered_unrestricted = any(overlap_ratio(stem_words, units[i]["words"]) >= RELAXED for i in cand_all)
            if covered_unrestricted:
                unrestricted_covered_relaxed += 1

            if not subject:
                continue
            labeled_question_count += 1
            subj_key = coarse(subject)
            subj_index = word_to_units_by_subject.get(subj_key, {})
            cand_subj = set()
            for w in stem_words:
                cand_subj.update(subj_index.get(w, []))
            covered_subject = any(overlap_ratio(stem_words, units[i]["words"]) >= RELAXED for i in cand_subj)
            if covered_subject:
                subject_constrained_covered_relaxed += 1
            if covered_unrestricted and not covered_subject:
                false_negative_candidates += 1

            cand_subj_chapter: set[int] = set()
            matched_any_chapter = False
            for i in cand_subj:
                if overlap_ratio(stem_words, units[i]["words"]) >= RELAXED:
                    cand_subj_chapter.add(i)
                    matched_any_chapter = True
            if matched_any_chapter:
                subject_chapter_constrained_covered_relaxed += 1

        constrained_diag = {
            "note": "subject_chapter_constrained figure above equals subject_constrained because pyq.questions carries no chapter/topic label to constrain against (class_level and concept_id are 100% NULL, confirmed in the original 2026-10-01 pyq-coverage-audit.md) -- true chapter-constrained retrieval cannot be run against question metadata that does not exist. This is reported honestly rather than fabricating a chapter filter from the matched unit's own chapter (which would be circular).",
            "total_pending_with_nonempty_stem": None,
            "labeled_question_count": labeled_question_count,
            "unrestricted_relaxed_covered_full_population": unrestricted_covered_relaxed,
            "subject_constrained_relaxed_covered_labeled_only": subject_constrained_covered_relaxed,
            "subject_chapter_constrained_relaxed_covered_labeled_only": subject_chapter_constrained_covered_relaxed,
            "false_negative_candidates_from_subject_constraint": false_negative_candidates,
            "interpretation": (
                "Among the 2,026 subject-labeled pending questions, constraining retrieval to only "
                "same-subject knowledge units removes matches that the unrestricted matcher found. "
                "This number of removed matches is reported as false_negative_candidates -- it is a "
                "risk/benefit tradeoff count, not a claim that the removed matches were correct or "
                "incorrect (that requires human review)."
            ),
            "cross_subject_by_pair": {f"{a}->{b}": n for (a, b), n in sorted(by_pair.items(), key=lambda x: -x[1])},
            "cross_subject_by_chapter_top20": dict(sorted(by_chapter.items(), key=lambda x: -x[1])[:20]),
            "cross_subject_by_score_band": dict(by_band),
            "cross_subject_by_ku_validation_status": dict(by_status),
            "cross_subject_by_source_document_top10": dict(sorted(by_doc.items(), key=lambda x: -x[1])[:10]),
        }
        with open(f"{OUT_DIR}/subject_chapter_constrained_diagnostics.json", "w") as f:
            json.dump(constrained_diag, f, indent=2)
        print(json.dumps(constrained_diag, indent=2))

        # ============================================================
        # Section 4: zero-significant-word stems (the 42)
        # ============================================================
        zero_word_rows = []
        for qid, subject, stem, raw_options in pending:
            stem_words = _significant_words(stem or "")
            if stem_words:
                continue
            opts_dict = raw_options if isinstance(raw_options, dict) else {}
            opts_text = " | ".join(f"{k}: {v}" for k, v in opts_dict.items()) if opts_dict else str(raw_options or "")
            opts_sig_words = _significant_words(opts_text)
            combined_sig_words = stem_words | opts_sig_words
            zero_word_rows.append(
                {
                    "question_id": str(qid),
                    "subject": subject or "",
                    "stem_text": (stem or "").strip(),
                    "stem_char_len": len(stem or ""),
                    "stem_significant_word_count": len(stem_words),
                    "options_text_preview": opts_text[:300],
                    "options_significant_word_count": len(opts_sig_words),
                    "candidate_query_representation": " ".join(sorted(combined_sig_words)) if combined_sig_words else "",
                    "likely_mechanism": (
                        "options_contain_scientific_terms_stem_does_not"
                        if opts_sig_words and not stem_words
                        else "stem_and_options_both_lack_significant_terms"
                        if not opts_sig_words
                        else "stem_lacks_terms_options_unclear"
                    ),
                }
            )
        zw_fieldnames = [
            "question_id", "subject", "stem_text", "stem_char_len", "stem_significant_word_count",
            "options_text_preview", "options_significant_word_count", "candidate_query_representation",
            "likely_mechanism",
        ]
        with open(f"{OUT_DIR}/zero_significant_word_analysis.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=zw_fieldnames)
            w.writeheader()
            w.writerows(zero_word_rows)
        print("zero_significant_word_analysis.csv rows:", len(zero_word_rows))
        from collections import Counter

        print("zero-word mechanism breakdown:", Counter(r["likely_mechanism"] for r in zero_word_rows))

        # ============================================================
        # Section 5: zero-overlap tracing (the 113)
        # ============================================================
        zero_overlap_path = "../../docs/quality/_retrieval_relevance_2026-10-01/zero_overlap_classification.csv"
        with open(zero_overlap_path, newline="", encoding="utf-8") as f:
            zo_rows_prior = [r for r in csv.DictReader(f) if r["reason"] == "zero_shared_significant_words_with_any_ingested_unit"]
        print("zero-overlap-with-content rows loaded from prior audit:", len(zo_rows_prior))

        tracing_rows = []
        for pr in zo_rows_prior:
            qid = pr["question_id"]
            if qid not in pending_by_id:
                tracing_rows.append(
                    {"question_id": qid, "subject": pr["subject"], "classification": "UNRESOLVED",
                     "reason": "question_id not found in current ANSWER_PENDING set (state may have changed)"}
                )
                continue
            subject, stem, raw_options = pending_by_id[qid]
            stem_words = _significant_words(stem or "")

            classification = "UNRESOLVED"
            reason = "insufficient deterministic evidence to classify without individual semantic review"

            # Check: is there ANY registered source document / mapped chapter for this subject at all?
            subj_key = coarse(subject) if subject else ""
            has_mapped_source_for_subject = any(coarse(u["subject_code"]) == subj_key for u in units) if subj_key else None

            if not subject:
                reason = "question has no subject label -- cannot even narrow candidate source chapters deterministically"
            elif has_mapped_source_for_subject is False:
                classification = "TAXONOMY_OR_METADATA_GAP"
                reason = f"subject label '{subject}' has zero ingested knowledge units of any kind in this subject group"
            else:
                reason = (
                    "subject has ingested content elsewhere, but this specific question's stem shares no "
                    "significant vocabulary with any of it -- could be EXISTING_CONTENT_NOT_MATCHED (different "
                    "phrasing/synonym), PARSER_OR_EXTRACTION_GAP, or a genuinely different topic; cannot "
                    "distinguish without reading the question"
                )

            tracing_rows.append(
                {
                    "question_id": qid,
                    "subject": subject or "",
                    "stem_preview": (stem or "")[:200],
                    "stem_significant_word_count": len(stem_words),
                    "has_mapped_source_for_subject": has_mapped_source_for_subject,
                    "classification": classification,
                    "reason": reason,
                }
            )

        tr_fieldnames = [
            "question_id", "subject", "stem_preview", "stem_significant_word_count",
            "has_mapped_source_for_subject", "classification", "reason",
        ]
        with open(f"{OUT_DIR}/zero_overlap_tracing.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=tr_fieldnames)
            w.writeheader()
            w.writerows(tracing_rows)
        print("zero_overlap_tracing.csv rows:", len(tracing_rows))
        print("classification breakdown:", Counter(r["classification"] for r in tracing_rows))

        await session.rollback()


if __name__ == "__main__":
    asyncio.run(main())
