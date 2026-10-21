"""Deterministic validators for Groq-generated practice-MCQ candidates.

THIS IS THE CORE DELIVERABLE of the MCQ-FACTORY-GROQ-001 pipeline. Every
check here is deterministic Python — no AI judge call, no network, no
database write. Where an equivalent check already exists elsewhere in the
Content Factory, this module calls it instead of re-implementing it:

- 4-option structure / single-answer / placeholder-option detection →
  ``app.modules.cms.services.factory_qa_gates.gate_a_structure`` +
  ``factory_candidate_validation.validate_candidate_body_detailed`` (this
  module adds placeholder-text detection on top, see
  ``detect_placeholder_options``).
- Ambiguity heuristics → ``factory_v2_answer_ambiguity.
  assess_semantic_answer_uniqueness`` (reused unmodified).
- Safety / impersonation / prompt-injection scanning →
  ``factory_qa_gates.gate_g_safety`` (reused unmodified).
- Numerical recomputation → ``numerical_validation.classify_and_verify``
  (reused unmodified — this module only maps a candidate's optional
  ``calculation_check`` payload into that function's input shape).
- Final publication readiness → the REAL
  ``publication_gates.evaluate_question_publication_gates`` (reused
  unmodified, called with ``status="DRAFT"`` the same way
  ``trusted_factory_submission.py`` does, reading only its
  ``content_ready`` property — the real ``review_state_ok`` gate is left
  for the actual human-review workflow, never bypassed here).

What is NEW in this module (no existing equivalent found):
- Taxonomy-id existence/consistency validation against real academic rows
  (``TaxonomyResolver`` / ``InMemoryTaxonomyResolver`` /
  ``build_taxonomy_resolver_from_session``).
- Source-evidence provenance re-location
  (``verify_source_evidence_relocatable``) — independently re-finds the
  candidate's quoted snippet inside the actually-extracted PDF text; NEVER
  accepts a citation on the model's self-reported confidence.
- Cross-corpus answer-conflict detection
  (``find_cross_corpus_conflicts``) — flags a candidate whose normalized
  stem matches an existing corpus/staging row with a *different* keyed
  answer.
- The orchestration (`run_deterministic_validation_pipeline`) that
  combines all of the above into one GREEN/YELLOW/RED classification using
  the existing ``factory_qa_gates.classify_from_gates`` policy, plus a
  reviewer gate so that a GPT-OSS-120B verification disagreement is never
  silently overridden.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.modules.cms.mcq_factory_groq.pdf_text_index import IndexedDocument
from app.modules.cms.mcq_factory_groq.schemas import GeneratedMcqCandidate, TaxonomyIds
from app.modules.cms.services.factory_candidate_validation import normalize_stem, stem_hash
from app.modules.cms.services.factory_qa_gates import (
    GateOutcome,
    classify_from_gates,
    gate_a_structure,
    gate_e_answer_explanation,
    gate_g_safety,
    option_stem_hash,
)
from app.modules.cms.services.factory_v2_answer_ambiguity import assess_semantic_answer_uniqueness
from app.modules.cms.services.numerical_validation import classify_and_verify

# ---------------------------------------------------------------------------
# Placeholder-option detection
# ---------------------------------------------------------------------------

_PLACEHOLDER_PATTERNS = (
    "todo",
    "tbd",
    "n/a",
    "na",
    "placeholder",
    "option a",
    "option b",
    "option c",
    "option d",
    "lorem ipsum",
    "xxx",
    "...",
    "fill in",
    "fillme",
)


def detect_placeholder_options(options: list[dict[str, Any]]) -> list[str]:
    """Return option labels whose text looks like a model placeholder
    rather than real content (e.g. literally 'Option A', 'TBD', 'N/A').
    Does not flag short-but-real answers (e.g. 'Mitochondria')."""
    flagged: list[str] = []
    for opt in options:
        label = str(opt.get("label") or "").strip().upper()
        text = str(opt.get("text") or "").strip().lower()
        if not text:
            flagged.append(label)
            continue
        collapsed = " ".join(text.split())
        if collapsed in _PLACEHOLDER_PATTERNS or any(
            collapsed == p or collapsed.startswith(p + " ") for p in _PLACEHOLDER_PATTERNS
        ):
            flagged.append(label)
    return flagged


def detect_duplicate_options(options: list[dict[str, Any]]) -> list[str]:
    """Return labels of options whose normalized text duplicates another
    option's normalized text."""
    seen: dict[str, str] = {}
    dups: list[str] = []
    for opt in options:
        label = str(opt.get("label") or "").strip().upper()
        norm = normalize_stem(str(opt.get("text") or ""))
        if norm in seen:
            dups.append(label)
            dups.append(seen[norm])
        else:
            seen[norm] = label
    return sorted(set(dups))


# ---------------------------------------------------------------------------
# Taxonomy-id validation (real academic rows — never invented ids)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaxonomyResolution:
    subject_ok: bool
    chapter_ok: bool
    topic_ok: bool
    concept_ok: bool
    chapter_under_subject: bool
    topic_under_chapter: bool
    concept_under_topic: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def consistent(self) -> bool:
        return (
            self.subject_ok
            and self.chapter_ok
            and self.topic_ok
            and self.concept_ok
            and self.chapter_under_subject
            and self.topic_under_chapter
            and self.concept_under_topic
        )


class TaxonomyResolver(Protocol):
    def resolve(self, ids: TaxonomyIds) -> TaxonomyResolution: ...


@dataclass(frozen=True)
class _Row:
    id: str
    parent_id: str | None


class InMemoryTaxonomyResolver:
    """Taxonomy resolver backed by plain id→parent-id maps.

    Production code builds this once per request from the real
    ``app.modules.academic.models`` tables (see
    ``build_taxonomy_resolver_from_rows``); tests build it directly from
    fixture dicts, with no database involved.
    """

    def __init__(
        self,
        *,
        subjects: dict[str, None],
        chapters: dict[str, str],  # chapter_id -> subject_id
        topics: dict[str, str],  # topic_id -> chapter_id
        concepts: dict[str, str],  # concept_id -> topic_id
    ) -> None:
        self._subjects = set(subjects)
        self._chapters = dict(chapters)
        self._topics = dict(topics)
        self._concepts = dict(concepts)

    def resolve(self, ids: TaxonomyIds) -> TaxonomyResolution:
        reasons: list[str] = []
        subject_ok = ids.subject_id in self._subjects
        if not subject_ok:
            reasons.append(f"TAXONOMY_SUBJECT_NOT_FOUND:{ids.subject_id}")

        chapter_ok = ids.chapter_id in self._chapters
        if not chapter_ok:
            reasons.append(f"TAXONOMY_CHAPTER_NOT_FOUND:{ids.chapter_id}")

        topic_ok = ids.topic_id in self._topics
        if not topic_ok:
            reasons.append(f"TAXONOMY_TOPIC_NOT_FOUND:{ids.topic_id}")

        concept_ok = True
        if ids.concept_id is not None:
            concept_ok = ids.concept_id in self._concepts
            if not concept_ok:
                reasons.append(f"TAXONOMY_CONCEPT_NOT_FOUND:{ids.concept_id}")

        chapter_under_subject = (
            chapter_ok and subject_ok and self._chapters[ids.chapter_id] == ids.subject_id
        )
        if chapter_ok and subject_ok and not chapter_under_subject:
            reasons.append("TAXONOMY_CHAPTER_NOT_UNDER_SUBJECT")

        topic_under_chapter = topic_ok and chapter_ok and self._topics[ids.topic_id] == ids.chapter_id
        if topic_ok and chapter_ok and not topic_under_chapter:
            reasons.append("TAXONOMY_TOPIC_NOT_UNDER_CHAPTER")

        concept_under_topic = True
        if ids.concept_id is not None and concept_ok and topic_ok:
            concept_under_topic = self._concepts[ids.concept_id] == ids.topic_id
            if not concept_under_topic:
                reasons.append("TAXONOMY_CONCEPT_NOT_UNDER_TOPIC")

        return TaxonomyResolution(
            subject_ok=subject_ok,
            chapter_ok=chapter_ok,
            topic_ok=topic_ok,
            concept_ok=concept_ok,
            chapter_under_subject=chapter_under_subject,
            topic_under_chapter=topic_under_chapter,
            concept_under_topic=concept_under_topic,
            reasons=reasons,
        )


async def build_taxonomy_resolver_from_session(session: Any) -> InMemoryTaxonomyResolver:
    """Build a resolver from the real academic tables via an AsyncSession.

    Mirrors the query style already used in
    ``publication_gates.evaluate_question_publication_gates`` (joining
    Concept → Topic → Chapter → Subject). Excludes soft-deleted rows
    (``deleted_at IS NOT NULL``), matching that same existing gate's
    convention. Not exercised by unit tests (which use
    ``InMemoryTaxonomyResolver`` directly) — covered by any integration
    test that already stands up the real academic schema.
    """
    from sqlalchemy import select

    from app.modules.academic.models import Chapter, Concept, Subject, Topic

    subjects = {
        str(row.id): None
        for row in (await session.execute(select(Subject.id).where(Subject.deleted_at.is_(None)))).all()
    }
    chapters = {
        str(row.id): str(row.subject_id)
        for row in (
            await session.execute(select(Chapter.id, Chapter.subject_id).where(Chapter.deleted_at.is_(None)))
        ).all()
    }
    topics = {
        str(row.id): str(row.chapter_id)
        for row in (
            await session.execute(select(Topic.id, Topic.chapter_id).where(Topic.deleted_at.is_(None)))
        ).all()
    }
    concepts = {
        str(row.id): str(row.topic_id)
        for row in (
            await session.execute(select(Concept.id, Concept.topic_id).where(Concept.deleted_at.is_(None)))
        ).all()
    }
    return InMemoryTaxonomyResolver(subjects=subjects, chapters=chapters, topics=topics, concepts=concepts)


# ---------------------------------------------------------------------------
# Source-evidence provenance re-location (anti-fabrication)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvenanceCheckResult:
    ok: bool
    relocated_page: int | None = None
    relocated_offset: int | None = None
    reasons: list[str] = field(default_factory=list)


def verify_source_evidence_relocatable(
    candidate: GeneratedMcqCandidate, document: IndexedDocument
) -> ProvenanceCheckResult:
    """Independently re-locate ``candidate.source_evidence.quoted_snippet``
    inside ``document`` — the actually-extracted PDF text — at the cited
    ``(doc_id, page)``.

    NEVER accepts the citation because the model "sounded confident"; the
    only signal this function uses is whether the normalized snippet text
    is actually findable in the extracted document. A candidate whose
    ``doc_id`` doesn't even match the supplied document, or whose snippet
    cannot be found on the cited page (or anywhere in the document), is
    rejected as a fabricated/mismatched citation.
    """
    ev = candidate.source_evidence
    reasons: list[str] = []

    if ev.doc_id != document.doc_id:
        return ProvenanceCheckResult(
            ok=False,
            reasons=[f"PROVENANCE_DOC_ID_MISMATCH:claimed={ev.doc_id}:actual={document.doc_id}"],
        )

    found_on_cited_page = document.find_snippet(ev.quoted_snippet, page_number=ev.page)
    if found_on_cited_page is not None:
        page_no, offset = found_on_cited_page
        return ProvenanceCheckResult(ok=True, relocated_page=page_no, relocated_offset=offset)

    found_anywhere = document.find_snippet(ev.quoted_snippet)
    if found_anywhere is not None:
        page_no, offset = found_anywhere
        reasons.append(f"PROVENANCE_PAGE_MISMATCH:claimed_page={ev.page}:actual_page={page_no}")
        return ProvenanceCheckResult(ok=False, relocated_page=page_no, relocated_offset=offset, reasons=reasons)

    reasons.append("PROVENANCE_SNIPPET_NOT_FOUND_FABRICATED_CITATION")
    return ProvenanceCheckResult(ok=False, reasons=reasons)


# ---------------------------------------------------------------------------
# Cross-corpus answer-conflict detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusAnswerRecord:
    """Minimal normalized view of an existing staged/published question,
    used only for the conflict check below. Callers build this list from
    ``generation_staging.candidates`` rows and/or published QUESTION
    bodies — this module does not read any database itself."""

    source: str  # e.g. "staging:<batch_id>" or "published:<item_id>"
    stem: str
    correct_option_text_norm: str


def find_cross_corpus_conflicts(
    candidate: GeneratedMcqCandidate, existing_corpus: list[CorpusAnswerRecord]
) -> list[str]:
    """Return human-readable conflict descriptions when an existing corpus
    row has the SAME normalized stem as ``candidate`` but a DIFFERENT
    normalized correct-answer text — i.e. two sources disagree on the
    answer to what looks like the same question. An empty return means no
    conflict was found (not that the question was scientifically
    verified)."""
    cand_stem_norm = normalize_stem(candidate.stem)
    cand_correct_text = normalize_stem(candidate.option_text(candidate.correct_option) or "")
    conflicts: list[str] = []
    for row in existing_corpus:
        if normalize_stem(row.stem) != cand_stem_norm:
            continue
        if row.correct_option_text_norm and row.correct_option_text_norm != cand_correct_text:
            conflicts.append(
                f"ANSWER_CONFLICT_WITH:{row.source}:existing_answer={row.correct_option_text_norm!r}"
            )
    return conflicts


# ---------------------------------------------------------------------------
# Cross-attempt / cross-batch TRUE DUPLICATE detection
# (NEET-MCQ-FACTORY-MULTI-ATTEMPT-001)
#
# Distinct from ``find_cross_corpus_conflicts`` above: that function only
# ever flags an ANSWER conflict (same stem, DIFFERENT answer) — a true
# duplicate with the SAME answer was never flagged by anything in this
# module before this addition. This is "priority #1" per the task that
# added it: the real gap is that nothing checked whether a NEW candidate
# (a later attempt on the same fact, or a candidate in a brand-new batch)
# is simply the SAME question as one already accepted/staged earlier.
#
# ``prior_candidates`` is a pre-fetched, plain-data snapshot list — this
# function performs NO I/O and NO async work itself, exactly like
# ``find_cross_corpus_conflicts``'s ``existing_corpus`` parameter. Two
# distinct call sites build this list and concatenate it before calling
# ``run_deterministic_validation_pipeline``:
#   (a) cross-attempt: the orchestrator's own in-memory
#       ``self._accepted_candidates_by_fact[fact_id]``, populated only
#       after an EARLIER ATTEMPT on the SAME fact was decided ACCEPTED,
#       within the current run.
#   (b) cross-batch: a real, fresh read of
#       ``generation_staging.candidates`` (ALL prior batches) via the
#       orchestrator's injected ``cross_batch_duplicate_lookup`` callable
#       (see ``orchestrator.py``) — never a stale in-memory snapshot taken
#       once at construction time (that mistake is exactly what made
#       ``find_cross_corpus_conflicts``'s ``existing_corpus`` a structural
#       no-op in every real CLI run to date).
#
# Discipline (matches the project's established "exact-match trusted,
# fuzzy = review-signal-only, never auto-accept via fuzzy" convention):
#   - EXACT normalized-stem match (``factory_candidate_validation.stem_hash``
#     equality) -> trusted, auto-actionable: forces REVIEW_REQUIRED via the
#     gate below (never silently dropped, never silently accepted as a
#     second copy).
#   - Partial option-text overlap (>= 50% of the 4 options identical after
#     normalization) -> WARNING ONLY, recorded in the gate's ``detail``
#     dict for the audit trail. Never changes the accept/reject/review
#     outcome by itself.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DuplicateCandidateSnapshot:
    """Minimal snapshot of ONE prior candidate, used only for the
    cross-attempt/cross-batch duplicate check below. ``source`` is a
    human-readable provenance string (e.g.
    ``"staging:<batch_id>:<fact_id>:attempt<n>"`` or
    ``"staging:<batch_id>:<fact_id>:attempt<n>:id=<staging_row_id>"``) —
    the SAME composite-identity convention ``CorpusAnswerRecord.source``
    already uses elsewhere in this module, carrying batch_id/fact_id/
    attempt_number provenance without needing a separate lookup.

    ``stem_hash_value`` is compared by exact equality only (it already IS
    ``sha256(normalize_stem(stem))`` — recomputing/re-normalizing here
    would be redundant). ``option_texts_norm`` is optional: when empty
    (e.g. a cross-batch DB match where fetching full option text was
    skipped to keep the query cheap), only the exact-match signal is
    evaluated for that entry — the near-duplicate warning signal is
    simply not computed for it, never defaulted to firing.
    """

    source: str
    stem_hash_value: str
    option_texts_norm: tuple[str, ...] = ()


def find_cross_attempt_duplicates(
    candidate: GeneratedMcqCandidate, prior_candidates: list[DuplicateCandidateSnapshot]
) -> tuple[list[str], list[str]]:
    """Return ``(exact_match_descriptions, near_duplicate_warnings)``.

    ``exact_match_descriptions`` is non-empty iff at least one prior
    candidate's normalized stem is IDENTICAL to ``candidate``'s — this is
    the trusted, auto-actionable signal (see module-section docstring
    above). ``near_duplicate_warnings`` is a SEPARATE, non-gating list:
    informational only, never causes a status change by itself.
    """
    cand_hash = stem_hash(candidate.stem)
    cand_options_norm = {normalize_stem(o.text) for o in candidate.options}
    exact: list[str] = []
    near_duplicate_warnings: list[str] = []
    for prior in prior_candidates:
        if prior.stem_hash_value == cand_hash:
            exact.append(f"CROSS_ATTEMPT_DUPLICATE_WITH:{prior.source}")
            continue
        if prior.option_texts_norm:
            overlap = len(cand_options_norm & set(prior.option_texts_norm))
            ratio = overlap / max(len(candidate.options), 1)
            if ratio >= 0.5:
                near_duplicate_warnings.append(
                    f"CROSS_ATTEMPT_SIMILARITY_WARNING:{prior.source}:option_overlap_ratio={ratio:.2f}"
                )
    return exact, near_duplicate_warnings


def gate_cross_attempt_duplicate(
    candidate: GeneratedMcqCandidate, prior_candidates: list[DuplicateCandidateSnapshot]
) -> GateOutcome:
    """``C_CROSS_ATTEMPT_DUPLICATE`` gate. Severity mirrors
    ``C_CROSS_CORPUS_CONFLICT`` above (YELLOW, not RED) so an exact
    duplicate is forced into human review (``REVIEW_REQUIRED`` via
    ``classify_from_gates``'s ``yellow_signals`` check) rather than
    quarantined (RED) or silently dropped — a genuine duplicate is not a
    content-quality defect in the SAME sense a fabricated citation is, it
    is a review-worthy "this may already exist" signal. The near-duplicate
    (option-overlap) warnings are carried in ``detail`` only — they are
    NEVER consulted by ``classify_from_gates`` (which only reads
    ``severity``/``passed``/specific soft-yellow warning strings), so they
    can never, by themselves, flip the outcome."""
    exact, near_duplicate_warnings = find_cross_attempt_duplicates(candidate, prior_candidates)
    return GateOutcome(
        "C_CROSS_ATTEMPT_DUPLICATE",
        not exact,
        "YELLOW" if exact else "INFO",
        warnings=list(exact),
        detail={"near_duplicate_warnings": near_duplicate_warnings} if near_duplicate_warnings else {},
    )


# ---------------------------------------------------------------------------
# Numerical recomputation (best-effort — reuses numerical_validation.py)
# ---------------------------------------------------------------------------


def recompute_numerical(calculation_check: dict[str, Any] | None) -> tuple[str, str]:
    """Best-effort independent recomputation for quantitative questions.

    Delegates entirely to ``numerical_validation.classify_and_verify``,
    which only recognizes a fixed, explicit set of physics formulas (see
    ``REQUIRED_KEYS`` in that module — e.g. ``v=u+at``, ``F=ma``,
    ``projectile_R``). LIMITATIONS (documented, not hidden): a question
    with no ``calculation_check`` payload at all is classified
    ``NOT_NUMERICAL`` even if its stem contains numbers — this function
    does not itself parse arithmetic out of free-text stems; a generation
    call site that wants numerical verification must populate
    ``calculation_check`` with one of the supported formula keys. Chemistry
    numericals (molarity, stoichiometry, etc.) are NOT covered by the
    current formula set and will always classify as NOT_NUMERICAL/
    NUMERICAL_INCOMPLETE — this is a known gap, not a false pass.
    """
    return classify_and_verify(calculation_check)


# ---------------------------------------------------------------------------
# Reviewer (GPT-OSS-120B verification) gate — never silently overridden
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationVerdict:
    """Parsed output of the GPT-OSS-120B verification call (see
    ``prompt_templates.VERIFICATION_*``). This dataclass is populated by a
    live-call site, not constructed here from any network response —
    ``validators.py`` never calls a provider."""

    answer_supported: bool
    ambiguous: bool
    unsupported_claims: list[str] = field(default_factory=list)
    notes: str = ""


def gate_reviewer(verification: VerificationVerdict | None) -> GateOutcome:
    """A missing verification result is YELLOW (human-review eligible,
    never GREEN-sampled) rather than a hard failure, so a transient
    verification-call failure cannot silently promote a candidate to
    GREEN by omission. A verification result that disagrees or flags
    ambiguity is RED — this is the "never silently overridden by the AI
    reviewer" requirement: the 120B model's disagreement forces
    REVIEW_REQUIRED, it can never force acceptance on its own."""
    if verification is None:
        return GateOutcome("R_REVIEWER", False, "YELLOW", warnings=["REVIEWER_PENDING"])
    if verification.ambiguous or not verification.answer_supported:
        return GateOutcome(
            "R_REVIEWER",
            False,
            "RED",
            failures=["REVIEWER_DISAGREEMENT_OR_AMBIGUITY"],
            detail={
                "unsupported_claims": verification.unsupported_claims,
                "notes": verification.notes,
            },
        )
    return GateOutcome("R_REVIEWER", True, "INFO")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class FactoryValidationReport:
    classification: str  # "GREEN" | "YELLOW" | "RED"
    sampling_eligible: bool
    quarantine: bool
    gates: list[GateOutcome] = field(default_factory=list)
    stem_hash: str = ""
    option_stem_hash: str = ""

    @property
    def failing_gate_codes(self) -> list[str]:
        return [g.code for g in self.gates if not g.passed]


def run_deterministic_validation_pipeline(
    candidate: GeneratedMcqCandidate,
    *,
    document: IndexedDocument,
    taxonomy_resolver: TaxonomyResolver,
    existing_corpus: list[CorpusAnswerRecord] | None = None,
    calculation_check: dict[str, Any] | None = None,
    verification: VerificationVerdict | None = None,
    prior_candidates_for_duplicate_check: list[DuplicateCandidateSnapshot] | None = None,
) -> FactoryValidationReport:
    """Run every deterministic gate and classify the candidate GREEN /
    YELLOW / RED via the existing ``factory_qa_gates.classify_from_gates``
    policy (reused unmodified — GREEN = GREEN-sample eligible, YELLOW =
    100% human-review eligible, RED = quarantined, never published).

    ANY RED gate — including a taxonomy id that doesn't exist, a
    fabricated/unlocatable citation, or reviewer disagreement — forces
    RED/quarantine. This function never grants GREEN on the strength of
    the generator's own claims alone.
    """
    existing_corpus = existing_corpus or []
    body = candidate.to_question_body_dict()

    structure_gate = gate_a_structure(body)
    answer_gate = gate_e_answer_explanation(body)
    safety_gate = gate_g_safety(body)

    placeholder_labels = detect_placeholder_options(body["options"])
    duplicate_labels = detect_duplicate_options(body["options"])
    placeholder_gate = GateOutcome(
        "H_PLACEHOLDER_OR_DUPLICATE_OPTIONS",
        not placeholder_labels and not duplicate_labels,
        "RED" if (placeholder_labels or duplicate_labels) else "INFO",
        failures=(
            [f"PLACEHOLDER_OPTION:{label}" for label in placeholder_labels]
            + [f"DUPLICATE_OPTION:{label}" for label in duplicate_labels]
        ),
    )

    taxonomy_resolution = taxonomy_resolver.resolve(candidate.taxonomy)
    taxonomy_gate = GateOutcome(
        "T_TAXONOMY",
        taxonomy_resolution.consistent,
        "RED" if not taxonomy_resolution.consistent else "INFO",
        failures=list(taxonomy_resolution.reasons),
    )

    provenance_result = verify_source_evidence_relocatable(candidate, document)
    provenance_gate = GateOutcome(
        "P_PROVENANCE",
        provenance_result.ok,
        "RED" if not provenance_result.ok else "INFO",
        failures=list(provenance_result.reasons),
        detail={"relocated_page": provenance_result.relocated_page},
    )

    semantic = assess_semantic_answer_uniqueness(body)
    ambiguity_gate = GateOutcome(
        "AMB_SEMANTIC_AMBIGUITY",
        not semantic.hard_fail,
        "RED" if semantic.hard_fail else ("YELLOW" if semantic.warnings else "INFO"),
        failures=["SEMANTIC_AMBIGUITY_DETECTED"] if semantic.hard_fail else [],
        warnings=list(semantic.warnings),
        detail={"signals": semantic.signals},
    )

    num_status, num_detail = recompute_numerical(calculation_check)
    if num_status == "NUMERICAL_INVALID":
        numerical_gate = GateOutcome("N_NUMERICAL", False, "RED", failures=[num_detail])
    elif num_status == "NUMERICAL_INCOMPLETE":
        numerical_gate = GateOutcome("N_NUMERICAL", False, "YELLOW", warnings=[num_detail])
    else:
        numerical_gate = GateOutcome("N_NUMERICAL", True, "INFO", detail={"status": num_status})

    conflicts = find_cross_corpus_conflicts(candidate, existing_corpus)
    conflict_gate = GateOutcome(
        "C_CROSS_CORPUS_CONFLICT",
        not conflicts,
        "YELLOW" if conflicts else "INFO",
        warnings=list(conflicts),
    )

    reviewer_gate = gate_reviewer(verification)

    cross_attempt_gate = gate_cross_attempt_duplicate(
        candidate, prior_candidates_for_duplicate_check or []
    )

    gates = [
        structure_gate,
        answer_gate,
        safety_gate,
        placeholder_gate,
        taxonomy_gate,
        provenance_gate,
        ambiguity_gate,
        numerical_gate,
        conflict_gate,
        cross_attempt_gate,
        reviewer_gate,
    ]

    duplicate_class = "NONE"
    if conflicts:
        duplicate_class = "POSSIBLE_DUPLICATE"
    classification, sampling_eligible, quarantine = classify_from_gates(
        gates, duplicate_class=duplicate_class
    )

    return FactoryValidationReport(
        classification=classification,
        sampling_eligible=sampling_eligible,
        quarantine=quarantine,
        gates=gates,
        stem_hash=stem_hash(candidate.stem),
        option_stem_hash=option_stem_hash(candidate.stem, body["options"]),
    )


async def evaluate_publication_readiness(
    session: Any,
    candidate: GeneratedMcqCandidate,
    *,
    ncert_evidence: dict[str, Any],
    provenance: dict[str, Any],
    tags: list[str] | None = None,
) -> Any:
    """Call the REAL ``publication_gates.evaluate_question_publication_gates``
    against a DRAFT-shaped body built from ``candidate`` — exactly the
    pattern ``trusted_factory_submission.py`` uses to ask "would this pass
    publish() on content grounds" for an item that is not yet in review.

    ``status="DRAFT"`` means the returned report's ``review_state_ok`` is
    always False (by construction — a DRAFT has not been through human
    review) and callers MUST read ``.content_ready``, never ``.passed``,
    from the result. This function performs no writes and never flips any
    item's status; it is read-only db access via ``session``.
    """
    from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

    body = candidate.to_question_body_dict()
    body["ncert_evidence"] = ncert_evidence
    body["provenance"] = provenance

    # MCQ-FACTORY-CONCEPT-ID-PARSE-001 (2026-10-14): ``candidate.taxonomy``
    # here is round-tripped through the MODEL's own generated JSON, not
    # the original FactSpec's real taxonomy — a model can hallucinate or
    # garble this value. Proven live: a real OpenAI (gpt-5.6-luna) response
    # returned a non-UUID concept_id, and this unguarded ``uuid.UUID(...)``
    # call crashed the entire CLI process (not just this one fact),
    # silently losing every later fact in that batch invocation. A
    # malformed concept_id here is metadata-incomplete, never a reason to
    # crash — treat it exactly like a missing one (``None``), consistent
    # with this project's established "concept_id NULL must not block
    # publication" convention (see ``TaxonomyIds`` docstring /
    # ``docs/PRODUCTION_READINESS.md``).
    parsed_concept_id = None
    if candidate.taxonomy.concept_id:
        try:
            parsed_concept_id = uuid.UUID(candidate.taxonomy.concept_id)
        except (ValueError, AttributeError, TypeError):
            parsed_concept_id = None

    return await evaluate_question_publication_gates(
        session,
        item_id=None,
        status="DRAFT",
        content_type="QUESTION",
        concept_id=parsed_concept_id,
        body=body,
        tags=tags or [],
        model_used="groq/" + "openai/gpt-oss-20b",
        knowledge_unit_id=None,
    )


__all__ = [
    "detect_placeholder_options",
    "detect_duplicate_options",
    "TaxonomyResolution",
    "TaxonomyResolver",
    "InMemoryTaxonomyResolver",
    "build_taxonomy_resolver_from_session",
    "ProvenanceCheckResult",
    "verify_source_evidence_relocatable",
    "CorpusAnswerRecord",
    "find_cross_corpus_conflicts",
    "DuplicateCandidateSnapshot",
    "find_cross_attempt_duplicates",
    "gate_cross_attempt_duplicate",
    "recompute_numerical",
    "VerificationVerdict",
    "gate_reviewer",
    "FactoryValidationReport",
    "run_deterministic_validation_pipeline",
    "evaluate_publication_readiness",
]
