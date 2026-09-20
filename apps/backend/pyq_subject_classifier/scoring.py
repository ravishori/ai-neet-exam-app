"""STEP 5/6 — deterministic scoring + confidence banding.

Score per subject = count of the question's significant words that fall in
that subject's NCERT-exclusive vocabulary (see ncert_index.py). Interpretable
integer scores only — never fabricated percentages.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.knowledge.services.grounding_check import _significant_words

from .ncert_index import SubjectTermIndex

SUBJECTS = ("Physics", "Chemistry", "Biology")


@dataclass
class ClassificationResult:
    scores: dict[str, int]
    matched_words: dict[str, list[str]]
    predicted_subject: str | None
    confidence: str  # HIGH | MEDIUM | LOW | UNRESOLVED
    status: str  # RESOLVED | AMBIGUOUS | UNRESOLVED
    evidence: list[dict] = field(default_factory=list)


def classify_text(question_text: str, idx: SubjectTermIndex) -> ClassificationResult:
    words = _significant_words(question_text)

    scores = {s: 0 for s in SUBJECTS}
    matched_words: dict[str, list[str]] = {s: [] for s in SUBJECTS}
    for w in words:
        for s in SUBJECTS:
            if w in idx.exclusive_words.get(s, ()):
                scores[s] += 1
                matched_words[s].append(w)

    ranked = sorted(SUBJECTS, key=lambda s: -scores[s])
    top_subj, second_subj = ranked[0], ranked[1]
    top_score, second_score = scores[top_subj], scores[second_subj]

    if top_score == 0:
        return ClassificationResult(scores, matched_words, None, "UNRESOLVED", "UNRESOLVED", [])

    if top_score == second_score:
        # Tied best evidence across two+ subjects — never force a pick.
        return ClassificationResult(scores, matched_words, None, "UNRESOLVED", "AMBIGUOUS", _evidence(matched_words[top_subj], idx) + _evidence(matched_words[second_subj], idx))

    margin = top_score - second_score
    if top_score >= 5 and margin >= 3:
        confidence = "HIGH"
    elif top_score >= 2 and margin >= 1:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Close-call guard: even with a nominal leader, a thin margin on small
    # scores is treated as AMBIGUOUS rather than a forced LOW-confidence pick.
    if top_score <= 2 and margin == 1:
        return ClassificationResult(
            scores, matched_words, None, "UNRESOLVED", "AMBIGUOUS",
            _evidence(matched_words[top_subj], idx) + _evidence(matched_words[second_subj], idx),
        )

    return ClassificationResult(
        scores, matched_words, top_subj, confidence, "RESOLVED", _evidence(matched_words[top_subj], idx)
    )


def _evidence(words: list[str], idx: SubjectTermIndex) -> list[dict]:
    out = []
    for w in words[:5]:
        ev = idx.word_evidence.get(w)
        if ev:
            out.append({"term": w, **ev})
    return out
