"""NEET-SYLLABUS-DRIVEN-GENERATION-20261014 — build an on-the-fly
``orchestrator.FactSpec`` per syllabus sub-topic, WITHOUT requiring a
pre-existing hand-curated fact record, and feed it through the EXISTING,
UNMODIFIED ``GroqFactoryOrchestrator.process_fact`` pipeline.

Design summary
---------------
This module is a FactSpec *builder*, not an orchestrator rewrite. For one
``NeetSyllabusSubtopic`` (see ``app.modules.cms.syllabus.neet_2026_subtopics``)
it runs three cheap, deterministic, zero-AI/zero-network checks in
cheapest-first order and either returns a ready-to-dispatch
``(FactSpec, IndexedDocument)`` pair or a reportable skip reason:

    1. ``check_subtopic_duplicate_risk`` — pure text, no I/O. Flags a
       sub-topic as a likely duplicate of ALREADY-COVERED ground from the
       204 hand-curated facts this session already produced, BEFORE any
       PDF is ever read or any generation call is ever considered. This
       is the fix for the exact risk named in this task: re-spending real
       money regenerating a topic-block that already has a hand-curated
       fact covering the same sub-concept.
    2. Real-taxonomy lookup (``build_topic_id_taxonomy_index``) — reuses
       the REAL academic-DB-resolved ``TaxonomyIds`` already attached to
       the 204 hand-curated facts (via their reviewed
       ``syllabus_topic_mapping.resolve_syllabus_topic_id`` mapping),
       keyed by the shared parent topic-BLOCK id. No new DB connection is
       opened here — this is a derived, in-memory index built once from
       the already-committed-to-disk fact-pack JSON files, exactly the
       same "reviewed, deterministic, never-fuzzy" posture
       ``syllabus_topic_mapping.py`` already established. A topic-block
       with zero hand-curated facts has no entry — a legitimate,
       reportable gap, never guessed.
    3. ``ncert_corpus_lookup.find_ncert_passage`` — the real, deterministic,
       on-demand NCERT passage search (see that module). No match is
       also a legitimate, reportable gap.

Why this needs NO change to ``orchestrator.py``
-------------------------------------------------
``GroqFactoryOrchestrator.process_fact(spec, document, ...)`` already
takes its ``IndexedDocument`` as a PER-CALL argument, not something fixed
once per orchestrator instance or per batch. The only thing that assumes
"one shared document for the whole batch" is the separate convenience
method ``run_batch`` (and the real CLI, ``scripts/mcq_factory_groq_bulk_run.py``,
which indexes exactly one ``--evidence-pdf`` for an entire ``--fact-pack``
run) — because every hand-curated fact-pack batch so far was deliberately
grouped so all its facts share one source PDF. Syllabus-driven generation
breaks that assumption (different sub-topics legitimately need different
NCERT chapters), so this module provides ``run_syllabus_driven_batch``
below: a thin loop, living entirely in NEW code, that calls
``process_fact`` once per ``(FactSpec, its own matched IndexedDocument)``
pair — mirroring ``run_batch``'s existing resumability/budget-early-stop
sequencing policy exactly, without touching a single line of
``orchestrator.py``. ``process_fact`` itself, and every safeguard it
calls (syllabus_gate, validators, checkpoint, staging writer, budget
tracker), is reused 100% unmodified.

No AI/LLM call, no network call, no database write anywhere in this
module. ``build_topic_id_taxonomy_index`` reads local JSON files only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.modules.cms.mcq_factory_groq.ncert_corpus_lookup import NcertLookupResult, find_ncert_passage
from app.modules.cms.mcq_factory_groq.orchestrator import FactSpec, GroqFactoryOrchestrator
from app.modules.cms.mcq_factory_groq.pdf_text_index import IndexedDocument
from app.modules.cms.mcq_factory_groq.schemas import TaxonomyIds
from app.modules.cms.mcq_factory_groq.syllabus_topic_mapping import resolve_syllabus_topic_id
from app.modules.cms.syllabus.neet_2026_parser import NeetSyllabusRegistry
from app.modules.cms.syllabus.neet_2026_subtopics import NeetSyllabusSubtopic
from app.modules.knowledge.services.grounding_check import _significant_words

# ---------------------------------------------------------------------------
# Load the real, already-produced hand-curated fact pool (204 resolved
# facts across these 7 batch files; fact_pack_10q_batch1.json is
# deliberately excluded — it is a 10-fact SUBSET sample of fact_pack.json
# used for an earlier live-run rehearsal, not additional distinct ground,
# and including it would double-count facts already in fact_pack.json).
# ---------------------------------------------------------------------------

_FACT_PACK_FILENAMES: tuple[str, ...] = (
    "fact_pack.json",
    "fact_pack_batch2.json",
    "fact_pack_batch3.json",
    "fact_pack_batch4.json",
    "fact_pack_batch5.json",
    "fact_pack_batch6.json",
    "fact_pack_batch7.json",
)


def default_fact_pack_dir() -> Path:
    # .../app/modules/cms/mcq_factory_groq/syllabus_driven_fact_builder.py -> backend root
    return Path(__file__).resolve().parents[4] / "data" / "generated_mcqs" / "mcq_factory_pilot"


def load_all_hand_curated_facts(fact_pack_dir: Path | None = None) -> list[dict[str, Any]]:
    """Real, on-disk, already-committed fact records from every resolved
    batch. Never fabricated, never re-derived — a plain JSON read."""
    base = fact_pack_dir or default_fact_pack_dir()
    facts: list[dict[str, Any]] = []
    for name in _FACT_PACK_FILENAMES:
        path = base / name
        if not path.exists():
            continue
        facts.extend(json.loads(path.read_text(encoding="utf-8")))
    return facts


# ---------------------------------------------------------------------------
# 1. Pre-generation duplicate-topic check (zero I/O, zero cost)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DuplicateTopicCheckResult:
    is_likely_duplicate: bool
    matched_fact_id: str | None
    similarity_score: float
    reason: str


DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD = 0.6


def check_subtopic_duplicate_risk(
    subtopic: NeetSyllabusSubtopic,
    *,
    existing_facts: list[dict[str, Any]],
    similarity_threshold: float = DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD,
) -> DuplicateTopicCheckResult:
    """Compare ``subtopic`` only against existing facts whose REVIEWED
    ``syllabus_topic_id`` mapping (``syllabus_topic_mapping.resolve_syllabus_topic_id``
    — the same reviewed, never-fuzzy table the syllabus gate itself uses)
    equals this sub-topic's own parent topic-block id. Restricting the
    comparison set this way means a false match against an unrelated
    topic-block that merely shares a few common English words is
    impossible by construction — this is deterministic word-overlap
    (the same ``_significant_words`` primitive ``evidence_selector``
    already uses) ONLY within an already-exact-matched topic-block.

    Returns the single best (highest-similarity) existing fact match, if
    any — ``is_likely_duplicate`` is True only once that best similarity
    clears ``similarity_threshold``. A topic-block with existing facts
    whose text is genuinely distinct from this sub-topic (the common case
    when deepening a block that already has >=1 fact elsewhere — exactly
    what batches 4-6 did by hand) correctly returns
    ``is_likely_duplicate=False`` with a non-None ``matched_fact_id``
    (the closest, still-insufficiently-similar existing fact, for audit).
    """
    subtopic_words = _significant_words(subtopic.text.lower())

    best_fact_id: str | None = None
    best_score = 0.0
    for fact in existing_facts:
        fact_id = fact.get("fact_id")
        if not fact_id:
            continue
        resolved_topic_id = resolve_syllabus_topic_id(fact_id)
        if resolved_topic_id != subtopic.topic_id:
            continue
        fact_words = _significant_words(f"{fact.get('topic', '')} {fact.get('concept', '')}".lower())
        if not fact_words or not subtopic_words:
            continue
        overlap = len(subtopic_words & fact_words) / max(1, min(len(subtopic_words), len(fact_words)))
        if overlap > best_score:
            best_score = overlap
            best_fact_id = fact_id

    is_duplicate = best_fact_id is not None and best_score >= similarity_threshold
    if is_duplicate:
        reason = f"SAME_TOPIC_BLOCK_HIGH_TEXT_OVERLAP:{best_fact_id}:score={best_score:.2f}"
    elif best_fact_id is not None:
        reason = f"SAME_TOPIC_BLOCK_BUT_DISTINCT_SUBTOPIC:{best_fact_id}:score={best_score:.2f}"
    else:
        reason = "NO_EXISTING_FACT_IN_THIS_TOPIC_BLOCK"

    return DuplicateTopicCheckResult(
        is_likely_duplicate=is_duplicate,
        matched_fact_id=best_fact_id,
        similarity_score=best_score,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# 2. Real-taxonomy index, derived from the 204 already-DB-resolved facts
# ---------------------------------------------------------------------------


def build_topic_id_taxonomy_index(
    facts: list[dict[str, Any]] | None = None,
) -> dict[str, TaxonomyIds]:
    """Map parent topic-BLOCK id -> real academic-DB ``TaxonomyIds``,
    derived from whichever already-resolved hand-curated fact(s) share
    that topic_id. First occurrence wins (every fact mapped to the same
    topic_id is, by construction, the same syllabus block, so they share
    the same real subject/chapter/topic row ids).

    ``concept_id`` is deliberately dropped (set to ``None``) even when an
    existing fact at this topic_id has one: a hand-curated fact's
    concept_id was reviewed for ITS specific fine-grained concept, not for
    every other sub-topic sentence inside the same block — carrying it
    forward into an unrelated on-the-fly sub-topic would be an
    unreviewed, unverified claim. This matches the project's own
    documented convention (``schemas.TaxonomyIds`` docstring /
    ``docs/PRODUCTION_READINESS.md``: "concept_id NULL must not block
    publication") that a missing concept_id is metadata-incomplete, never
    a fabrication or a publication blocker.
    """
    all_facts = facts if facts is not None else load_all_hand_curated_facts()
    index: dict[str, TaxonomyIds] = {}
    for fact in all_facts:
        fact_id = fact.get("fact_id")
        if not fact_id:
            continue
        topic_id = resolve_syllabus_topic_id(fact_id)
        if topic_id is None or topic_id in index:
            continue
        raw = fact.get("taxonomy") or {}
        subject_id = raw.get("subject_id")
        chapter_id = raw.get("chapter_id")
        topic_db_id = raw.get("topic_id")
        if not subject_id or not chapter_id or not topic_db_id:
            continue
        index[topic_id] = TaxonomyIds(
            subject_id=subject_id,
            chapter_id=chapter_id,
            topic_id=topic_db_id,
            concept_id=None,
        )
    return index


# ---------------------------------------------------------------------------
# 3. On-the-fly FactSpec construction
# ---------------------------------------------------------------------------

STATUS_READY = "READY"
STATUS_SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"
STATUS_SKIPPED_NO_TAXONOMY = "SKIPPED_NO_TAXONOMY"
STATUS_SKIPPED_NO_EVIDENCE = "SKIPPED_NO_EVIDENCE"


@dataclass(frozen=True)
class SyllabusFactBuildOutcome:
    subtopic_id: str
    status: str
    fact_spec: FactSpec | None = None
    document: IndexedDocument | None = None
    detail: str = ""


def build_syllabus_driven_fact(
    subtopic: NeetSyllabusSubtopic,
    *,
    registry: NeetSyllabusRegistry,
    existing_facts: list[dict[str, Any]] | None = None,
    taxonomy_index: dict[str, TaxonomyIds] | None = None,
    corpus_root: Path | None = None,
    class_level: str | None = None,
    duplicate_similarity_threshold: float = DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD,
) -> SyllabusFactBuildOutcome:
    """Run the full cheapest-first gate sequence for one sub-topic and
    return either a ready ``(FactSpec, IndexedDocument)`` pair or a
    reportable skip outcome. Never fabricates a FactSpec when any gate is
    inconclusive."""
    facts = existing_facts if existing_facts is not None else load_all_hand_curated_facts()
    tax_index = taxonomy_index if taxonomy_index is not None else build_topic_id_taxonomy_index(facts)

    dup = check_subtopic_duplicate_risk(
        subtopic, existing_facts=facts, similarity_threshold=duplicate_similarity_threshold
    )
    if dup.is_likely_duplicate:
        return SyllabusFactBuildOutcome(
            subtopic_id=subtopic.subtopic_id, status=STATUS_SKIPPED_DUPLICATE, detail=dup.reason
        )

    taxonomy = tax_index.get(subtopic.topic_id)
    if taxonomy is None:
        return SyllabusFactBuildOutcome(
            subtopic_id=subtopic.subtopic_id,
            status=STATUS_SKIPPED_NO_TAXONOMY,
            detail=f"no resolved real-taxonomy mapping for topic_id={subtopic.topic_id}",
        )

    lookup: NcertLookupResult | None = find_ncert_passage(
        subject=subtopic.subject,
        unit_name=subtopic.unit_name,
        subtopic_text=subtopic.text,
        class_level=class_level,
        corpus_root=corpus_root,
    )
    if lookup is None:
        return SyllabusFactBuildOutcome(
            subtopic_id=subtopic.subtopic_id,
            status=STATUS_SKIPPED_NO_EVIDENCE,
            detail="no NCERT passage cleared the minimal-overlap bar in any scanned PDF",
        )

    fact_spec = FactSpec(
        fact_id=f"syllabus:{subtopic.subtopic_id}",
        subject=subtopic.subject,
        unit_number=subtopic.unit_number,
        chapter=f"UNIT {subtopic.unit_number:02d}: {subtopic.unit_name}",
        topic=subtopic.text,
        class_level=class_level or "11/12",
        taxonomy=taxonomy,
        concept=None,
        unit_name=subtopic.unit_name,
        academic_subject_code=subtopic.subject,
        syllabus_registry=registry,
        # Same exact-match authorization path the hand-curated facts use
        # (see syllabus_topic_mapping.py's own module docstring) — the
        # parent BLOCK id, not a new finer registry id (none exists).
        syllabus_topic_id=subtopic.topic_id,
    )
    return SyllabusFactBuildOutcome(
        subtopic_id=subtopic.subtopic_id,
        status=STATUS_READY,
        fact_spec=fact_spec,
        document=lookup.document,
        detail=f"matched {lookup.chunk.source_pdf} p.{lookup.chunk.page_number} score={lookup.score:.2f}",
    )


# ---------------------------------------------------------------------------
# Thin per-fact-document batch loop (NEW code; orchestrator.py untouched)
# ---------------------------------------------------------------------------


async def run_syllabus_driven_batch(
    orchestrator: GroqFactoryOrchestrator,
    outcomes: list[SyllabusFactBuildOutcome],
    *,
    max_attempts_per_fact: int = 1,
):
    """Mirror of ``GroqFactoryOrchestrator.run_batch``'s sequencing policy
    (prior-attempt-REJECTED skip, early stop on budget exhaustion), except
    each ready outcome carries its OWN matched ``IndexedDocument`` instead
    of one document shared by the whole list — see this module's
    docstring for why ``run_batch`` itself cannot be reused as-is for
    syllabus-driven facts. Every non-READY outcome is recorded as a
    ``STATUS_REJECTED`` audit record with its skip reason, exactly like a
    pipeline-level rejection inside ``process_fact`` itself, so nothing is
    ever silently dropped from the returned list."""
    from app.modules.cms.mcq_factory_groq.orchestrator import (
        STATUS_REJECTED,
        CandidateAuditRecord,
    )

    results: list[CandidateAuditRecord] = []
    for i, outcome in enumerate(outcomes, start=1):
        if outcome.status != STATUS_READY or outcome.fact_spec is None or outcome.document is None:
            results.append(
                CandidateAuditRecord(
                    fact_id=f"syllabus:{outcome.subtopic_id}",
                    batch_id=orchestrator.batch_id,
                    attempt_number=0,
                    status=STATUS_REJECTED,
                    reason=f"{outcome.status}:{outcome.detail}",
                )
            )
            continue

        prior_status: str | None = None
        budget_exceeded = False
        for attempt_number in range(1, max_attempts_per_fact + 1):
            if prior_status == STATUS_REJECTED:
                results.append(
                    CandidateAuditRecord(
                        fact_id=outcome.fact_spec.fact_id,
                        batch_id=orchestrator.batch_id,
                        attempt_number=attempt_number,
                        status=STATUS_REJECTED,
                        reason="SKIPPED_PRIOR_ATTEMPT_REJECTED",
                    )
                )
                continue
            record = await orchestrator.process_fact(
                outcome.fact_spec,
                outcome.document,
                sequence_in_batch=i,
                attempt_number=attempt_number,
            )
            results.append(record)
            prior_status = record.status
            if getattr(record, "budget_exceeded", False):
                budget_exceeded = True
                break
        if budget_exceeded:
            break
    return results


__all__ = [
    "default_fact_pack_dir",
    "load_all_hand_curated_facts",
    "DuplicateTopicCheckResult",
    "DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD",
    "check_subtopic_duplicate_risk",
    "build_topic_id_taxonomy_index",
    "STATUS_READY",
    "STATUS_SKIPPED_DUPLICATE",
    "STATUS_SKIPPED_NO_TAXONOMY",
    "STATUS_SKIPPED_NO_EVIDENCE",
    "SyllabusFactBuildOutcome",
    "build_syllabus_driven_fact",
    "run_syllabus_driven_batch",
]
