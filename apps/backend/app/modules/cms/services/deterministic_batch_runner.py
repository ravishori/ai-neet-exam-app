"""Staged batch driver for the provider-free deterministic MCQ engine.

Thin orchestration layer on top of ``deterministic_mcq_engine`` — it does not
change engine validation logic. It adds the pieces needed to run safe,
resumable, deduplicated batches of up to 100 new staged MCQs:

- Durable JSON staging output under ``data/generated_mcqs/`` distinct from
  both the hand-authored ``neet_mcq_batch_NNN.json`` corpus and from other
  deterministic batches.
- Deduplication against the full hand-authored corpus and all previously
  written deterministic batches, using the project's existing
  significant-word Jaccard similarity method (``_significant_words`` from
  ``app.modules.knowledge.services.grounding_check``), at the same ~0.5
  overlap threshold already documented in
  ``docs/quality/neet_10000_mcq_generation_audit.md``.
- A resumable checkpoint sidecar keyed by fact_id so an interrupted run does
  not reprocess or duplicate already-accepted facts.
- A rejection log recording every rejected/skipped candidate with a reason.

No provider/AI calls, no database access, no file deletion, no publishing.
``concept``/``concept_id`` are optional everywhere here, matching the base
engine and fact schema.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.modules.cms.schemas.deterministic_fact_pack import DeterministicFact
from app.modules.cms.services.deterministic_fact_adapter import (
    DeterministicFactToQuestionAdapter,
    FactAdapterError,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (
    extract_ncert_source_text,
)
from app.modules.cms.services.deterministic_mcq_engine import (
    ENGINE_VERSION,
    DeterministicEvidenceContext,
    DeterministicMcqEngine,
    DraftMcqCandidate,
)
from app.modules.cms.services.fact_quality_gate import FactQualityGate, TaxonomyBinding
from app.modules.cms.services.ncert_generation_evidence import NcertEvidencePack
from app.modules.ingestion.services.ncert_canonical_source import (
    validate_ncert_generation_source,
)
from app.modules.knowledge.services.grounding_check import _significant_words

GENERATION_METHOD = "deterministic_fact_engine"
BATCH_SIZE_CAP = 100
JACCARD_DUPLICATE_THRESHOLD = 0.5
_WS_RE = re.compile(r"\s+")


def _normalize_stem(text: str | None) -> str:
    return _WS_RE.sub(" ", (text or "")).strip().lower()


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


@dataclass
class CorpusRow:
    """Minimal normalized view of an existing MCQ used only for dedup."""

    source_file: str
    row_id: str
    stem: str
    words: set[str]


@dataclass
class RejectionRecord:
    fact_id: str
    question_type: str
    reason: str
    details: list[str] = field(default_factory=list)
    matched_source_file: str | None = None
    matched_row_id: str | None = None
    similarity: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "question_type": self.question_type,
            "reason": self.reason,
            "details": self.details,
            "matched_source_file": self.matched_source_file,
            "matched_row_id": self.matched_row_id,
            "similarity": self.similarity,
        }


def load_corpus_rows(generated_mcqs_dir: Path) -> list[CorpusRow]:
    """Load hand-authored neet_mcq_batch_*.json rows plus any previously
    written deterministic_batch_*.json rows, for dedup comparison only."""
    rows: list[CorpusRow] = []
    patterns = ("neet_mcq_batch_*.json", "deterministic_batch_*.json")
    for pattern in patterns:
        for path in sorted(generated_mcqs_dir.glob(pattern)):
            if path.name.endswith(".rejections.json") or path.name.endswith(
                ".checkpoint.json"
            ):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            items: Iterable[dict] = (
                payload
                if isinstance(payload, list)
                else payload.get("questions", payload.get("items", []))
            )
            for item in items:
                if not isinstance(item, dict):
                    continue
                stem = item.get("question") or item.get("stem") or ""
                row_id = str(item.get("id") or item.get("fact_id") or "")
                norm = _normalize_stem(stem)
                if not norm:
                    continue
                rows.append(
                    CorpusRow(
                        source_file=path.name,
                        row_id=row_id,
                        stem=norm,
                        words=_significant_words(norm),
                    )
                )
    return rows


def find_duplicate(
    stem: str, corpus_rows: list[CorpusRow], *, threshold: float = JACCARD_DUPLICATE_THRESHOLD
) -> CorpusRow | None:
    words = _significant_words(_normalize_stem(stem))
    if not words:
        return None
    for row in corpus_rows:
        if not row.words:
            continue
        if _jaccard_similarity(words, row.words) >= threshold:
            return row
    return None


def _taxonomy_for_fact(fact: DeterministicFact) -> TaxonomyBinding:
    return TaxonomyBinding(
        subject=fact.subject,
        class_level=fact.class_level,
        chapter_id=fact.chapter_id,
        chapter=fact.chapter,
        topic_id=fact.topic_id,
        topic=fact.topic,
        concept_id=fact.concept_id or "",
        concept=fact.concept_name or "",
    )


def _context_for_fact(fact: DeterministicFact) -> DeterministicEvidenceContext:
    source = validate_ncert_generation_source(fact.source_pdf)
    return DeterministicEvidenceContext(
        subject=fact.subject,
        class_level=fact.class_level,
        chapter=fact.chapter,
        topic=fact.topic,
        concept=fact.concept_name,
        source_path=fact.source_pdf,
        constraints={
            "ncert_derived": True,
            "ncert_source_path": fact.source_pdf,
            "neet_ug_2026": fact.syllabus_binding.model_dump(exclude_none=True),
        },
        provenance_tier="authoritative",
        evidence=NcertEvidencePack(
            status="NCERT_EVIDENCE_READY",
            pdf_path=fact.source_pdf,
            relative_posix=fact.source_relative_path,
            evidence_text=extract_ncert_source_text(source.resolved_path, None),
            page_numbers=[],
            detail="deterministic_batch_runner staged generation",
        ),
    )


def make_batch_id(seed: int) -> str:
    ts = time.strftime("%Y%m%dT%H%M%S")
    short_hash = hashlib.sha256(f"{ts}:{seed}".encode()).hexdigest()[:8]
    return f"{ts}-{short_hash}"


def candidate_to_staged_record(
    candidate: DraftMcqCandidate, fact: DeterministicFact
) -> dict[str, Any]:
    body = candidate.body
    return {
        "id": f"DET-NEET-{candidate.stem_hash[:12]}",
        "subject": candidate.subject,
        "class": candidate.class_level,
        "chapter": candidate.chapter,
        "topic": candidate.topic,
        "concept": candidate.concept,  # may be None — never required
        "concept_id": fact.concept_id,  # may be None — never required
        "difficulty": body.get("difficulty"),
        "question_type": candidate.question_type,
        "question": body["stem"],
        "options": {opt["label"]: opt["text"] for opt in body["options"]},
        "correct_answer": body["correct_option"],
        "explanation": body["explanation"],
        "generation_method": GENERATION_METHOD,
        "engine_version": candidate.engine_version,
        "seed": candidate.seed,
        "fact_id": candidate.fact_id,
        "source": {
            "source_pdf": candidate.source_path,
            "source_relative_path": candidate.source_relative_path,
            "evidence_pages": candidate.evidence_pages,
            "ncert_evidence": body.get("ncert_evidence"),
        },
        "provenance": body.get("provenance"),
        "syllabus_binding": candidate.syllabus_binding,
        "stem_hash": candidate.stem_hash,
        "option_stem_hash": candidate.option_stem_hash,
        "validation_status": "DRAFT_VALIDATED",
    }


@dataclass
class BatchRunResult:
    batch_id: str
    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejections: list[RejectionRecord] = field(default_factory=list)
    attempted_fact_ids: list[str] = field(default_factory=list)


def run_batch(
    facts: list[DeterministicFact],
    *,
    seed: int,
    generated_mcqs_dir: Path,
    syllabus_path: str | Path,
    batch_size_cap: int = BATCH_SIZE_CAP,
    checkpoint_fact_ids: set[str] | None = None,
    extra_corpus_rows: list[CorpusRow] | None = None,
) -> BatchRunResult:
    """Run one staged generation pass over ``facts``.

    Facts whose fact_id is in ``checkpoint_fact_ids`` are skipped entirely
    (already attempted in a prior run of this batch — resume support).
    Returns at most ``batch_size_cap`` accepted questions; never pads.
    """
    checkpoint_fact_ids = checkpoint_fact_ids or set()
    corpus_rows = load_corpus_rows(generated_mcqs_dir)
    if extra_corpus_rows:
        corpus_rows = corpus_rows + extra_corpus_rows

    gate = FactQualityGate()
    adapter = DeterministicFactToQuestionAdapter(gate)
    engine = DeterministicMcqEngine()

    result = BatchRunResult(batch_id=make_batch_id(seed))
    accepted_stem_hashes: set[str] = set()
    accepted_option_hashes: set[str] = set()

    for fact in facts:
        if len(result.accepted) >= batch_size_cap:
            break
        if fact.fact_id in checkpoint_fact_ids:
            continue
        result.attempted_fact_ids.append(fact.fact_id)

        taxonomy = _taxonomy_for_fact(fact)
        try:
            adapted = adapter.adapt(
                fact,
                taxonomy=taxonomy,
                authoritative_syllabus_path=syllabus_path,
            )
        except FactAdapterError as exc:
            result.rejections.append(
                RejectionRecord(
                    fact_id=fact.fact_id,
                    question_type="UNKNOWN",
                    reason=exc.code,
                    details=[str(exc.detail)] if getattr(exc, "detail", None) else [],
                )
            )
            continue

        if not adapted.quality.mcq_eligible:
            result.rejections.append(
                RejectionRecord(
                    fact_id=fact.fact_id,
                    question_type=adapted.spec.question_type,
                    reason="FACT_QUALITY_NOT_ELIGIBLE",
                    details=[r.code for r in adapted.quality.reasons],
                )
            )
            continue

        context = _context_for_fact(fact)
        generation = engine.generate_eligible(
            context,
            [adapted.spec],
            quality_results={adapted.fact_id: adapted.quality},
            seed=seed,
            existing_stem_hashes=accepted_stem_hashes,
            existing_option_stem_hashes=accepted_option_hashes,
        )

        if not generation.candidates:
            for skipped in generation.skipped:
                result.rejections.append(
                    RejectionRecord(
                        fact_id=skipped.fact_id,
                        question_type=skipped.question_type,
                        reason=skipped.reason,
                        details=skipped.details,
                    )
                )
            if not generation.skipped:
                result.rejections.append(
                    RejectionRecord(
                        fact_id=fact.fact_id,
                        question_type=adapted.spec.question_type,
                        reason="NO_CANDIDATE_GENERATED",
                    )
                )
            continue

        candidate = generation.candidates[0]
        duplicate = find_duplicate(candidate.body["stem"], corpus_rows)
        if duplicate is not None:
            similarity = _jaccard_similarity(
                _significant_words(_normalize_stem(candidate.body["stem"])),
                duplicate.words,
            )
            result.rejections.append(
                RejectionRecord(
                    fact_id=fact.fact_id,
                    question_type=candidate.question_type,
                    reason="DUPLICATE_OF_EXISTING_CORPUS_ROW",
                    matched_source_file=duplicate.source_file,
                    matched_row_id=duplicate.row_id,
                    similarity=round(similarity, 4),
                )
            )
            continue

        accepted_stem_hashes.add(candidate.stem_hash)
        accepted_option_hashes.add(candidate.option_stem_hash)
        staged = candidate_to_staged_record(candidate, fact)
        result.accepted.append(staged)
        corpus_rows.append(
            CorpusRow(
                source_file=f"deterministic_batch_{result.batch_id}.json",
                row_id=staged["id"],
                stem=_normalize_stem(staged["question"]),
                words=_significant_words(_normalize_stem(staged["question"])),
            )
        )

    return result


def write_batch_outputs(
    result: BatchRunResult, generated_mcqs_dir: Path
) -> tuple[Path, Path]:
    """Write the staging output and the rejection log. Never overwrites an
    existing batch file for a different batch_id, and never deletes."""
    generated_mcqs_dir.mkdir(parents=True, exist_ok=True)
    out_path = generated_mcqs_dir / f"deterministic_batch_{result.batch_id}.json"
    rej_path = generated_mcqs_dir / f"deterministic_batch_{result.batch_id}.rejections.json"
    out_path.write_text(
        json.dumps(
            {
                "batch_id": result.batch_id,
                "generation_method": GENERATION_METHOD,
                "engine_version": ENGINE_VERSION,
                "count": len(result.accepted),
                "batch_size_cap": BATCH_SIZE_CAP,
                "questions": result.accepted,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rej_path.write_text(
        json.dumps(
            {
                "batch_id": result.batch_id,
                "rejection_count": len(result.rejections),
                "rejections": [r.to_dict() for r in result.rejections],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return out_path, rej_path


def write_checkpoint(
    checkpoint_path: Path, batch_id: str, attempted_fact_ids: Iterable[str]
) -> None:
    existing: set[str] = set()
    if checkpoint_path.exists():
        try:
            existing = set(json.loads(checkpoint_path.read_text(encoding="utf-8")).get(
                "attempted_fact_ids", []
            ))
        except (OSError, json.JSONDecodeError):
            existing = set()
    merged = sorted(existing | set(attempted_fact_ids))
    checkpoint_path.write_text(
        json.dumps({"batch_id": batch_id, "attempted_fact_ids": merged}, indent=2),
        encoding="utf-8",
    )


def load_checkpoint(checkpoint_path: Path) -> set[str]:
    if not checkpoint_path.exists():
        return set()
    try:
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return set(payload.get("attempted_fact_ids", []))


# ---------------------------------------------------------------------------
# Optional local-database staging (additive — never replaces the JSON output
# above). Every candidate, accepted or rejected/duplicate, can also be
# persisted to generation_staging.candidates via
# ``app.modules.cms.services.generation_staging_store``. This is opt-in:
# callers that don't pass a DB session keep the exact pre-existing
# file-only behaviour.
# ---------------------------------------------------------------------------


async def persist_batch_to_staging(
    result: BatchRunResult,
    session: Any,
    *,
    attempt_number: int = 1,
) -> dict[str, int]:
    """Write every accepted and rejected candidate in ``result`` to the
    local ``generation_staging.candidates`` table (additive to the JSON
    files written by ``write_batch_outputs``).

    Idempotent: re-calling this for a batch_id/fact_id/attempt_number
    already staged is a no-op for that row (see
    ``generation_staging_store.insert_staging_candidate``). Never raises on
    a content duplicate — duplicates are stored and flagged, not rejected.
    Raises ``NotLocalDatabaseError`` immediately if ``session`` is not bound
    to a localhost database.
    """
    from app.modules.cms.services.generation_staging_store import (
        StagingCandidateRecord,
        _session_bind_url,
        assert_local_database_target,
        insert_staging_candidate,
    )

    assert_local_database_target(_session_bind_url(session))

    inserted = 0
    skipped_existing = 0
    sequence = 0

    for staged in result.accepted:
        sequence += 1
        record = StagingCandidateRecord(
            batch_id=result.batch_id,
            sequence_in_batch=sequence,
            attempt_number=attempt_number,
            fact_id=staged.get("fact_id", ""),
            outcome="ACCEPTED",
            generation_method=staged.get("generation_method"),
            engine_version=staged.get("engine_version"),
            seed=staged.get("seed"),
            source_pdf=(staged.get("source") or {}).get("source_pdf"),
            source_relative_path=(staged.get("source") or {}).get("source_relative_path"),
            evidence_pages=(staged.get("source") or {}).get("evidence_pages"),
            provenance=staged.get("provenance"),
            subject=staged.get("subject"),
            class_level=staged.get("class"),
            chapter=staged.get("chapter"),
            topic=staged.get("topic"),
            concept=staged.get("concept"),
            concept_id=staged.get("concept_id"),
            syllabus_binding=staged.get("syllabus_binding"),
            question_type=staged.get("question_type"),
            difficulty=staged.get("difficulty"),
            question_text=staged.get("question"),
            options=staged.get("options"),
            correct_answer=staged.get("correct_answer"),
            explanation=staged.get("explanation"),
            stem_hash=staged.get("stem_hash"),
            option_stem_hash=staged.get("option_stem_hash"),
            validation_status=staged.get("validation_status"),
            is_duplicate=False,
            raw_candidate=staged,
        )
        if await insert_staging_candidate(session, record):
            inserted += 1
        else:
            skipped_existing += 1

    for rejection in result.rejections:
        sequence += 1
        is_dup = rejection.reason == "DUPLICATE_OF_EXISTING_CORPUS_ROW"
        record = StagingCandidateRecord(
            batch_id=result.batch_id,
            sequence_in_batch=sequence,
            attempt_number=attempt_number,
            fact_id=rejection.fact_id,
            outcome="REJECTED",
            generation_method=GENERATION_METHOD,
            question_type=rejection.question_type,
            rejection_reason=rejection.reason,
            rejection_details=rejection.details,
            is_duplicate=is_dup,
            duplicate_of_question_id=rejection.matched_row_id if is_dup else None,
            duplicate_matched_source_file=rejection.matched_source_file if is_dup else None,
            duplicate_similarity=rejection.similarity if is_dup else None,
            raw_candidate=rejection.to_dict(),
        )
        if await insert_staging_candidate(session, record):
            inserted += 1
        else:
            skipped_existing += 1

    await session.commit()
    return {"inserted": inserted, "skipped_existing": skipped_existing}
