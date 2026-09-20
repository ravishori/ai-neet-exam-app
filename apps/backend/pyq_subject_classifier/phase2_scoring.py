"""Phase 2 — deeper multi-signal deterministic scoring.

Signals (all local, all NCERT-derived, no new hardcoded dictionaries beyond
a small generic-word stoplist per the task's own examples):
  - EXACT_NCERT_PHRASE: a >=5-word contiguous n-gram from the (normalized)
    stem/options appears verbatim inside a specific chapter's page text.
  - CHAPTER_CONCENTRATION: the single best-matching chapter for a subject
    (most Phase-1 subject-exclusive terms landing in ONE chapter) — this is
    what distinguishes real topical evidence from terms scattered thinly
    across many unrelated chapters.
  - TERMINOLOGY: breadth of distinct subject-exclusive terms in the stem.
  - OPTION_EVIDENCE: subject-exclusive terms found ONLY in the options,
    weighted lower than stem evidence per the task's own example.

Score weights are the task's own starting points (STEP 8), capped so no
single generic-term hit can dominate (STEP 2/7's "not from a single word"
and "no overlapping-term" requirements).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.knowledge.services.grounding_check import _significant_words

from .ncert_index import SubjectTermIndex
from .normalize import normalize_text
from .phase2_index import Phase2Index

SUBJECTS = ("Physics", "Chemistry", "Biology")

# STEP 2 — generic words that must never carry classification weight alone.
# Small, task-specified stoplist — not a subject dictionary.
GENERIC_STOPWORDS = frozenset({
    "calculate", "following", "correct", "statement", "given", "which",
    "according", "approximately", "value", "figure", "shown", "above",
    "below", "consider", "assume", "find", "determine", "represents",
})

PHRASE_NGRAM_SIZE = 5
PHRASE_SCORE = 10
CHAPTER_MATCH_SCORE = 8
TERMINOLOGY_SCORE = 4
OPTION_SCORE = 2
MAX_TERMINOLOGY_TERMS_COUNTED = 3
MAX_OPTION_TERMS_COUNTED = 2


@dataclass
class Phase2Result:
    scores: dict
    top_subject: str | None
    second_subject: str | None
    score_margin: float
    confidence: str  # HIGH | MEDIUM | LOW | UNRESOLVED
    classification_status: str  # RESOLVED | AMBIGUOUS | UNRESOLVED
    evidence: list = field(default_factory=list)

    @property
    def predicted_subject(self):
        return self.top_subject if self.classification_status == "RESOLVED" else None


def _ngrams(words: list, n: int):
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def _exact_phrase_hits(stem_norm: str, options_norm: str, phase2_idx: Phase2Index) -> dict:
    """subject -> evidence dict if a stem/option n-gram is found verbatim in
    one of that subject's chapters."""
    hits = {}
    for source_text in (stem_norm, options_norm):
        tokens = [t for t in source_text.split() if len(t) >= 3]
        if len(tokens) < PHRASE_NGRAM_SIZE:
            continue
        for ngram in _ngrams(tokens, PHRASE_NGRAM_SIZE):
            if len(ngram) < 20:  # avoid trivially short/common n-grams
                continue
            for chapter in phase2_idx.chapters.values():
                if chapter.subject in hits:
                    continue
                if ngram in chapter.normalized_text:
                    hits[chapter.subject] = {
                        "match_type": "EXACT_NCERT_PHRASE",
                        "ncert_book": chapter.book,
                        "ncert_chapter": chapter.chapter_id,
                        "ncert_page": None,
                        "matched_text": ngram,
                    }
    return hits


def _best_chapter_match(words: set, subject: str, exclusive_words: set, phase2_idx: Phase2Index):
    best_chapter, best_count = None, 0
    for chapter in phase2_idx.chapters_for_subject(subject):
        count = len((words & exclusive_words) & chapter.words)
        if count > best_count:
            best_chapter, best_count = chapter, count
    return best_chapter, best_count


def classify_phase2(stem: str, options: dict, term_idx: SubjectTermIndex, phase2_idx: Phase2Index) -> Phase2Result:
    stem_norm = normalize_text(stem)
    options_norm = normalize_text(" ".join(str(v) for v in (options or {}).values() if isinstance(v, str)))

    stem_words = _significant_words(stem_norm) - GENERIC_STOPWORDS
    option_words = _significant_words(options_norm) - GENERIC_STOPWORDS

    phrase_hits = _exact_phrase_hits(stem_norm, options_norm, phase2_idx)

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

    # Relative margin requirement scales with score size (STEP 9: 18 vs 17 ->
    # AMBIGUOUS even though top>0; 27 vs 8 -> HIGH).
    required_margin = max(6.0, 0.35 * top_score)
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

    status = "RESOLVED" if confidence in ("HIGH", "MEDIUM") else "AMBIGUOUS"
    return Phase2Result(scores, top, second, margin, confidence, status, evidence_by_subject[top])
