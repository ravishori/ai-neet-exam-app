"""Phase 3 — second-stage resolution for questions Phase 2 left AMBIGUOUS
or UNRESOLVED. Reuses the exact same weight constants and confidence/
margin thresholds as Phase 2 (imported, never redefined) — per instruction
to add evidence, not lower standards. The one genuine addition is
page-level exact-phrase search (via phase3_index's per-page cache) instead
of whole-chapter concatenated text, which also yields a real NCERT page
number for evidence (previously always None).
"""

from __future__ import annotations

from app.modules.knowledge.services.grounding_check import _significant_words

from .ncert_index import SubjectTermIndex
from .normalize import normalize_text
from .phase2_index import Phase2Index
from .phase2_scoring import (
    CHAPTER_MATCH_SCORE,
    MAX_OPTION_TERMS_COUNTED,
    MAX_TERMINOLOGY_TERMS_COUNTED,
    OPTION_SCORE,
    PHRASE_NGRAM_SIZE,
    PHRASE_SCORE,
    SUBJECTS,
    TERMINOLOGY_SCORE,
    Phase2Result,
    _best_chapter_match,
    _ngrams,
)
from .phase3_index import Phase3Index


def _page_level_phrase_hits(stem_norm: str, options_norm: str, phase3_idx: Phase3Index) -> dict:
    hits = {}
    for source_text in (stem_norm, options_norm):
        tokens = [t for t in source_text.split() if len(t) >= 3]
        if len(tokens) < PHRASE_NGRAM_SIZE:
            continue
        for ngram in _ngrams(tokens, PHRASE_NGRAM_SIZE):
            if len(ngram) < 20:
                continue
            for page in phase3_idx.pages:
                if page.subject in hits:
                    continue
                if ngram in page.normalized_text:
                    hits[page.subject] = {
                        "match_type": "EXACT_NCERT_PHRASE",
                        "ncert_book": page.book,
                        "ncert_chapter": page.chapter_id,
                        "ncert_page": page.page_number,
                        "matched_text": ngram,
                    }
    return hits


def classify_phase3(
    stem: str, options: dict, term_idx: SubjectTermIndex, phase2_idx: Phase2Index, phase3_idx: Phase3Index
) -> Phase2Result:
    stem_norm = normalize_text(stem)
    options_norm = normalize_text(" ".join(str(v) for v in (options or {}).values() if isinstance(v, str)))

    stem_words = _significant_words(stem_norm)
    option_words = _significant_words(options_norm)

    phrase_hits = _page_level_phrase_hits(stem_norm, options_norm, phase3_idx)

    scores = {}
    evidence_by_subject = {}
    for subject in SUBJECTS:
        exclusive = term_idx.exclusive_words.get(subject, set())
        best_chapter, chapter_count = _best_chapter_match(stem_words, subject, exclusive, phase2_idx)
        terminology_count = len(stem_words & exclusive)
        option_count = len(option_words & exclusive)

        score = 0.0
        ev = []
        if subject in phrase_hits:
            score += PHRASE_SCORE
            ev.append(phrase_hits[subject])
        if chapter_count >= 2:
            score += CHAPTER_MATCH_SCORE + chapter_count
            ev.append({
                "match_type": "CHAPTER_CONCENTRATION", "ncert_book": best_chapter.book,
                "ncert_chapter": best_chapter.chapter_id, "ncert_page": None,
                "matched_text": f"{chapter_count} exclusive terms",
            })
        score += TERMINOLOGY_SCORE * min(terminology_count, MAX_TERMINOLOGY_TERMS_COUNTED)
        score += OPTION_SCORE * min(option_count, MAX_OPTION_TERMS_COUNTED)

        scores[subject] = score
        evidence_by_subject[subject] = ev

    ranked = sorted(SUBJECTS, key=lambda s: -scores[s])
    top, second = ranked[0], ranked[1]
    top_score, second_score = scores[top], scores[second]
    margin = top_score - second_score

    if top_score == 0:
        return Phase2Result(scores, None, None, 0, "UNRESOLVED", "UNRESOLVED", [])

    required_margin = max(6.0, 0.35 * top_score)  # identical to Phase 2 — not lowered
    if margin < required_margin:
        return Phase2Result(
            scores, top, second, margin, "UNRESOLVED", "AMBIGUOUS",
            evidence_by_subject[top] + evidence_by_subject[second],
        )

    if top_score >= 18 and margin >= 15:
        confidence = "HIGH"
    elif top_score >= 10 and margin >= 6:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    if top_score <= 2 and margin == 1:
        return Phase2Result(
            scores, top, second, margin, "UNRESOLVED", "AMBIGUOUS",
            evidence_by_subject[top] + evidence_by_subject[second],
        )

    status = "RESOLVED" if confidence in ("HIGH", "MEDIUM") else "AMBIGUOUS"
    return Phase2Result(scores, top, second, margin, confidence, status, evidence_by_subject[top])
