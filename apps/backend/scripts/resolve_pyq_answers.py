#!/usr/bin/env python3
"""FACTORY-PYQ-P4 — deterministic PYQ answer resolution.

Resolves pyq.questions(state='ANSWER_PENDING') against the project's
existing authorized study-material corpus: knowledge.knowledge_units
(structured_facts extracted from NCERT source PDFs during Content Factory
generation — see ADR-0024/ADR-0025). No LLM. No web/general-knowledge
fallback. Reuses the existing mechanical source-overlap check
(app.modules.knowledge.services.grounding_check.is_fact_grounded) rather
than inventing a new matching heuristic.

Algorithm (per pending question):
  1. Find knowledge_units whose combined text (summary + structured_facts)
     is source-overlap-grounded against the question stem. Zero matches ->
     SOURCE_MATCH_FAILURE, left ANSWER_PENDING.
  2. Among matched units' combined evidence text, check each non-empty
     option (A-D) for the same grounding check.
     - Exactly one option grounded -> state=ANSWER_VERIFIED, one
       answer_assertions row (verification_status=VERIFIED).
     - Zero options grounded -> left ANSWER_PENDING (source found, but no
       option is unambiguously supported by it — never guessed).
     - >1 options grounded -> state=ANSWER_CONFLICT, one answer_assertions
       row per conflicting option (verification_status=DISPUTED), each
       evidence preserved.

Never touches cms.content_items, pyq.qa_reviews, pyq.promotion_log, or raw
question/source fields. Idempotent: only ever selects state='ANSWER_PENDING'
rows, and inserts are additionally guarded by
ON CONFLICT (question_id, assertion_source) DO NOTHING.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.knowledge.services.grounding_check import _significant_words, is_fact_grounded

logger = get_logger("pyq.resolver")

BATCH_SIZE = 500
OPTION_LABELS = ("A", "B", "C", "D")
# Bumped whenever the grounding algorithm itself changes (not on every code
# tweak) — recorded on every answer_assertions row so a later re-resolution
# pass can tell which build produced a given VERIFIED/DISPUTED assertion.
RESOLVER_VERSION = "pyq-resolver-v1"
# Stage 2 is a second pass over Stage 1's own leftovers, tagged separately
# in evidence provenance so a later audit can tell which pass produced a
# given assertion — the algorithm itself is documented on
# resolve_stage2_batch().
RESOLVER_VERSION_STAGE2 = "pyq-resolver-v1-stage2"


@dataclass
class KnowledgeUnitIndex:
    unit_ids: list[str] = field(default_factory=list)
    unit_text: dict[str, str] = field(default_factory=dict)
    unit_summary: dict[str, str] = field(default_factory=dict)
    unit_subject: dict[str, str | None] = field(default_factory=dict)
    word_to_units: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def candidates_for(self, words: set[str]) -> set[str]:
        out: set[str] = set()
        for w in words:
            out |= self.word_to_units.get(w, set())
        return out


async def _load_ku_index(session: AsyncSession) -> KnowledgeUnitIndex:
    # validation_status = 'PASSED' only: a FAILED unit (in this corpus,
    # always a flagged duplicate of a PASSED unit — see
    # docs/quality/ncert-retrieval-coverage-forensic-audit-2026-10-01.md
    # Section 9) must never be treated as authoritative source evidence.
    # Directly measured across the whole pending corpus before this fix:
    # including FAILED units changed zero Stage-1 Strict-threshold
    # coverage outcomes (delta=0), so this is a no-regression correctness
    # fix, not a behavior change for any currently-answered question.
    rows = (
        await session.execute(
            text(
                """
                SELECT ku.id, ku.summary, ku.structured_facts, s.code AS subject_code
                FROM knowledge.knowledge_units ku
                LEFT JOIN academic.concepts co ON co.id = ku.concept_id
                LEFT JOIN academic.topics t ON t.id = co.topic_id
                LEFT JOIN academic.chapters c ON c.id = t.chapter_id
                LEFT JOIN academic.subjects s ON s.id = c.subject_id
                WHERE ku.deleted_at IS NULL AND ku.validation_status = 'PASSED'
                """
            )
        )
    ).all()
    idx = KnowledgeUnitIndex()
    for ku_id, summary, facts, subject_code in rows:
        ku_id_s = str(ku_id)
        facts_list = facts if isinstance(facts, list) else (json.loads(facts) if facts else [])
        combined = " ".join([summary or "", *[str(f) for f in facts_list]])
        idx.unit_ids.append(ku_id_s)
        idx.unit_text[ku_id_s] = combined
        idx.unit_summary[ku_id_s] = summary or ""
        idx.unit_subject[ku_id_s] = subject_code
        for w in _significant_words(combined):
            idx.word_to_units[w].add(ku_id_s)
    return idx


@dataclass
class ResolveReport:
    total_scanned: int = 0
    answered: int = 0
    unresolved_no_source_match: int = 0
    unresolved_no_option_grounded: int = 0
    conflicts: int = 0
    assertions_inserted: int = 0
    # Stage 2 — second pass over this same batch's Stage-1 leftovers only
    # (never a separate/larger scan); see resolve_stage2_batch().
    stage2_answered: int = 0
    stage2_conflicts: int = 0
    stage2_unresolved: int = 0


def _match_units(idx: KnowledgeUnitIndex, stem: str) -> list[str]:
    """Stage-1 STRICT matching (OVERLAP_THRESHOLD, currently 0.5) — the only
    matching function ever used to decide ANSWER_VERIFIED/ANSWER_CONFLICT.
    Unchanged by the relaxed-retrieval-context feature below."""
    stem_words = _significant_words(stem)
    if not stem_words:
        return []
    candidates = idx.candidates_for(stem_words)
    matched = [uid for uid in candidates if is_fact_grounded(stem, idx.unit_text[uid])]
    return matched


def _coarse_subject(code: str | None) -> str:
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


def compute_retrieval_tier(
    idx: KnowledgeUnitIndex,
    stem: str,
    question_subject: str | None,
    *,
    relaxed_enabled: bool,
    relaxed_threshold: float,
    subject_constrained: bool,
) -> tuple[str, list[str]]:
    """Retrieval-CONTEXT tier only — never used to auto-verify an answer or
    fed into resolve_batch()'s strict Stage-1 grounding decision, which is
    unchanged (see _match_units above). Returns (tier, matched_unit_ids)
    where tier is one of 'STRICT_MATCH', 'RELAXED_MATCH', 'NONE'.

    'STRICT_MATCH' reuses _match_units unmodified -- if a question already
    clears the existing 0.5 threshold, the relaxed path is never needed and
    is not consulted (preserves the original threshold as the primary,
    unconditional result; relaxed is strictly additive).

    'RELAXED_MATCH' is only ever returned when relaxed_enabled is True
    (feature-flagged, see app.core.config.Settings.pyq_relaxed_retrieval_enabled)
    and a match clears relaxed_threshold against the SAME validated
    (PASSED-only) knowledge-unit index. When subject_constrained is True and
    the question carries a reliable subject label, candidate units are
    filtered to units whose chapter-derived subject matches the question's
    own subject (coarse-normalized) BEFORE scoring -- this is the
    cross-subject-match safeguard, not a post-hoc filter on scores alone.
    This NEVER establishes semantic relevance or answer correctness by
    itself (see docs/quality/ncert-retrieval-relevance-validation-2026-10-01.md);
    it only marks that a candidate NCERT passage is available as retrieval
    context for this question.
    """
    strict_matches = _match_units(idx, stem)
    if strict_matches:
        return "STRICT_MATCH", strict_matches

    if not relaxed_enabled:
        return "NONE", []

    stem_words = _significant_words(stem)
    if not stem_words:
        return "NONE", []

    candidates = idx.candidates_for(stem_words)
    q_subject = _coarse_subject(question_subject)
    if subject_constrained and q_subject:
        candidates = {uid for uid in candidates if _coarse_subject(idx.unit_subject.get(uid)) == q_subject}

    relaxed_matches = [
        uid for uid in candidates if is_fact_grounded(stem, idx.unit_text[uid], threshold=relaxed_threshold)
    ]
    if relaxed_matches:
        return "RELAXED_MATCH", relaxed_matches
    return "NONE", []


def _option_text(rec_options: dict[str, Any], label: str) -> str:
    val = rec_options.get(label)
    return val if isinstance(val, str) else ""


def _build_explanation(*, option_label: str, option_text: str, best_summary: str) -> str:
    """Concise, deterministic explanation built only from the same grounding
    evidence already used to select this option — never phrased by an LLM."""
    summary = (best_summary or "").strip()
    if len(summary) > 220:
        summary = summary[:217].rstrip() + "..."
    return f"Option {option_label} ({option_text.strip()}) is supported by NCERT source material: {summary}"


async def resolve_batch(
    session: AsyncSession,
    idx: KnowledgeUnitIndex,
    rows: list[tuple],
    report: ResolveReport,
    *,
    apply: bool,
) -> None:
    for question_id, raw_stem, raw_options in rows:
        report.total_scanned += 1
        options = raw_options if isinstance(raw_options, dict) else (json.loads(raw_options) if raw_options else {})

        matched_units = _match_units(idx, raw_stem or "")
        if not matched_units:
            report.unresolved_no_source_match += 1
            continue

        evidence_text = " ".join(idx.unit_text[u] for u in matched_units)
        grounded_options = [
            label for label in OPTION_LABELS
            if _option_text(options, label).strip() and is_fact_grounded(_option_text(options, label), evidence_text)
        ]

        if not grounded_options:
            report.unresolved_no_option_grounded += 1
            continue

        # assertion_source is VARCHAR(80) — use a short deterministic digest
        # of the matched knowledge_unit set (stable across reruns, so
        # (question_id, assertion_source) stays a valid idempotency key);
        # the full unit id list is preserved in evidence_note for provenance.
        sorted_units = sorted(matched_units)
        digest = hashlib.sha256(",".join(sorted_units).encode()).hexdigest()[:16]
        source_id_str = digest
        evidence_note = (
            f"knowledge_units={','.join(sorted_units)}; "
            + "; ".join(idx.unit_summary[u][:150] for u in matched_units[:3])
        )

        best_summary = idx.unit_summary[matched_units[0]] if matched_units else ""

        if len(grounded_options) == 1:
            report.answered += 1
            if apply:
                label = grounded_options[0]
                await session.execute(
                    text(
                        "INSERT INTO pyq.answer_assertions "
                        "(id, question_id, asserted_option, assertion_source, verification_status, "
                        "evidence_note, resolver_version, explanation) "
                        "VALUES (:id, :qid, :opt, :src, 'VERIFIED', :note, :rver, :expl) "
                        "ON CONFLICT (question_id, assertion_source) DO NOTHING"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "qid": question_id,
                        "opt": label,
                        "src": f"knowledge_units:{source_id_str}",
                        "note": evidence_note,
                        "rver": RESOLVER_VERSION,
                        "expl": _build_explanation(
                            option_label=label, option_text=_option_text(options, label), best_summary=best_summary
                        ),
                    },
                )
                await session.execute(
                    text("UPDATE pyq.questions SET state = 'ANSWER_VERIFIED', updated_at = now() WHERE id = :id"),
                    {"id": question_id},
                )
        else:
            report.conflicts += 1
            if apply:
                for label in grounded_options:
                    await session.execute(
                        text(
                            "INSERT INTO pyq.answer_assertions "
                            "(id, question_id, asserted_option, assertion_source, verification_status, "
                            "evidence_note, resolver_version, explanation) "
                            "VALUES (:id, :qid, :opt, :src, 'DISPUTED', :note, :rver, :expl) "
                            "ON CONFLICT (question_id, assertion_source) DO NOTHING"
                        ),
                        {
                            "id": uuid.uuid4(),
                            "qid": question_id,
                            "opt": label,
                            "src": f"knowledge_units:{source_id_str}:option_{label}",
                            "note": evidence_note,
                            "rver": RESOLVER_VERSION,
                            "expl": _build_explanation(
                                option_label=label, option_text=_option_text(options, label), best_summary=best_summary
                            ),
                        },
                    )
                await session.execute(
                    text("UPDATE pyq.questions SET state = 'ANSWER_CONFLICT', updated_at = now() WHERE id = :id"),
                    {"id": question_id},
                )

        if apply:
            report.assertions_inserted += 1 if len(grounded_options) == 1 else len(grounded_options)


EVIDENCE_UNIT_CAP = 8  # keeps the Stage 2 prompt bounded regardless of corpus size


def _stage2_default_gateway(session: AsyncSession) -> Any:
    """Stage 2 must use Gemini explicitly, never the global AIGateway
    router — FACTORY_PROVIDER governs unrelated Content Factory features
    and must not be touched or relied on here. Injecting a provider
    instance directly makes AIGateway.generate() bypass the router
    entirely (see ai_gateway.py: `if self._injected is not None`)."""
    from app.core.config import get_settings
    from app.modules.ai.gateway.ai_gateway import AIGateway
    from app.modules.ai.gateway.gemini_provider import GeminiProvider

    settings = get_settings()
    provider = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    return AIGateway(session, provider=provider)


async def resolve_stage2_batch(
    session: AsyncSession,
    idx: KnowledgeUnitIndex,
    rows: list[tuple],
    report: ResolveReport,
    *,
    apply: bool,
    ai_gateway: Any | None = None,
    run_id: str | None = None,
) -> None:
    """Second pass over questions Stage 1 left ANSWER_PENDING within this
    same batch (never a separate/larger scan, and never touches a question
    Stage 1 already resolved).

    The PYQ corpus is treated as trusted, source-derived content (approved
    NEET syllabus papers), not arbitrary/unknown-provenance MCQs — so
    Stage 2's job is never "is this question legitimate," only "which
    option, if any, does the indexed NCERT corpus actually support,"
    judged semantically rather than by literal wording match (unlike
    Stage 1's mechanical word-overlap check, which is unchanged and still
    runs first).

    Retrieval is still restricted to the SAME indexed knowledge.
    knowledge_units corpus Stage 1 uses (candidate units are found by
    shared vocabulary with the stem+options, then capped and passed to the
    model as the ONLY material it may reason over) — no web search, no
    general knowledge, and a question with literally zero shared
    vocabulary with the corpus never reaches the model at all (there is
    nothing to synthesize from, so it's left ANSWER_PENDING without
    spending a call). The model is instructed to answer only from the
    given excerpts and to return an explicit empty list when the excerpts
    are insufficient — it is never asked to guess, and a provider error,
    fallback response, or unparseable/invalid response is always treated
    as unresolved, never as an answer.

    Same safety semantics as Stage 1: no options supported by the
    evidence -> stays ANSWER_PENDING; exactly one supported ->
    ANSWER_VERIFIED; more than one (or contradictory evidence) ->
    ANSWER_CONFLICT.
    """
    from app.modules.ai.gateway.base import ProviderError
    from app.modules.ai.prompts import pyq_resolver as prompts
    from app.modules.ai.services.json_utils import parse_json_response

    gateway = ai_gateway if ai_gateway is not None else _stage2_default_gateway(session)

    for question_id, raw_stem, raw_options in rows:
        options = raw_options if isinstance(raw_options, dict) else (json.loads(raw_options) if raw_options else {})
        stem = raw_stem or ""
        option_texts = {label: _option_text(options, label) for label in OPTION_LABELS if _option_text(options, label).strip()}

        option_words: set[str] = set()
        for opt_text in option_texts.values():
            option_words |= _significant_words(opt_text)
        candidate_units = sorted(idx.candidates_for(_significant_words(stem) | option_words))

        if not candidate_units or not option_texts:
            # Genuinely no retrieved evidence at all — never invoke the
            # model with nothing to synthesize from.
            report.stage2_unresolved += 1
            continue

        evidence_units = candidate_units[:EVIDENCE_UNIT_CAP]
        evidence = "\n---\n".join(idx.unit_text[u] for u in evidence_units)
        user_prompt = prompts.build_user_prompt(stem=stem, options=option_texts, evidence=evidence)

        try:
            response = await gateway.generate(
                agent_type="PYQ_ANSWER_RESOLVER",
                system_prompt=prompts.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=400,
                require_json=True,
            )
        except ProviderError:
            logger.warning("pyq_stage2_provider_error", question_id=str(question_id))
            report.stage2_unresolved += 1
            continue

        if response.is_fallback:
            # A fallback stub response is never real evidence-derived
            # synthesis — treat exactly like a provider failure.
            report.stage2_unresolved += 1
            continue

        try:
            parsed = parse_json_response(response.text)
            raw_supported = parsed.get("supported_options", [])
            if not isinstance(raw_supported, list):
                raise ValueError("supported_options must be a list")
            supported_options = sorted({label for label in raw_supported if label in option_texts})
            reasoning = str(parsed.get("reasoning") or "").strip()
        except (ValueError, AttributeError, TypeError, KeyError):
            logger.warning("pyq_stage2_bad_response", question_id=str(question_id), raw=response.text[:200])
            report.stage2_unresolved += 1
            continue

        if not supported_options:
            report.stage2_unresolved += 1
            continue

        run_tag = f"run={run_id}; " if run_id else ""
        evidence_note = (
            f"{run_tag}stage2_ai_knowledge_units={','.join(evidence_units)}; "
            f"model={response.model}; reasoning={reasoning[:300]}"
        )
        explanation = reasoning or "Supported by the indexed NCERT source excerpts (no further detail returned)."

        if len(supported_options) == 1:
            label = supported_options[0]
            report.stage2_answered += 1
            if apply:
                # AI_RESOLVED (not VERIFIED): this is a one-pass Gemini
                # answer with no second AI verification pass and no routine
                # manual QC — it must never be represented as equivalent to
                # Stage 1's independent, deterministic NCERT-grounding
                # verification. See docs/quality/pyq-gemini-one-pass-resolution-*.md.
                await session.execute(
                    text(
                        "INSERT INTO pyq.answer_assertions "
                        "(id, question_id, asserted_option, assertion_source, verification_status, "
                        "evidence_note, resolver_version, explanation) "
                        "VALUES (:id, :qid, :opt, :src, 'AI_RESOLVED', :note, :rver, :expl) "
                        "ON CONFLICT (question_id, assertion_source) DO NOTHING"
                    ),
                    {
                        "id": uuid.uuid4(), "qid": question_id, "opt": label,
                        "src": f"knowledge_units_stage2_ai:{hashlib.sha256(','.join(evidence_units).encode()).hexdigest()[:16]}",
                        "note": evidence_note, "rver": RESOLVER_VERSION_STAGE2, "expl": explanation,
                    },
                )
                await session.execute(
                    text("UPDATE pyq.questions SET state = 'ANSWER_VERIFIED', updated_at = now() WHERE id = :id"),
                    {"id": question_id},
                )
        else:
            report.stage2_conflicts += 1
            if apply:
                for label in supported_options:
                    await session.execute(
                        text(
                            "INSERT INTO pyq.answer_assertions "
                            "(id, question_id, asserted_option, assertion_source, verification_status, "
                            "evidence_note, resolver_version, explanation) "
                            "VALUES (:id, :qid, :opt, :src, 'DISPUTED', :note, :rver, :expl) "
                            "ON CONFLICT (question_id, assertion_source) DO NOTHING"
                        ),
                        {
                            "id": uuid.uuid4(), "qid": question_id, "opt": label,
                            "src": (
                                f"knowledge_units_stage2_ai:"
                                f"{hashlib.sha256(','.join(evidence_units).encode()).hexdigest()[:16]}:option_{label}"
                            ),
                            "note": evidence_note, "rver": RESOLVER_VERSION_STAGE2, "expl": explanation,
                        },
                    )
                await session.execute(
                    text("UPDATE pyq.questions SET state = 'ANSWER_CONFLICT', updated_at = now() WHERE id = :id"),
                    {"id": question_id},
                )

        if apply:
            report.assertions_inserted += 1 if len(supported_options) == 1 else len(supported_options)


async def resolve_up_to(
    session: AsyncSession,
    idx: KnowledgeUnitIndex,
    *,
    max_total: int,
    apply: bool,
    ai_gateway: Any | None = None,
    run_id: str | None = None,
) -> ResolveReport:
    """Bounded variant of run()'s loop, for the scheduled background worker:
    processes at most `max_total` oldest ANSWER_PENDING rows (created_at ASC,
    id ASC as tiebreak), using the same idempotent resolve_batch() as the
    manual CLI (Stage 1, unchanged). Whatever Stage 1 leaves ANSWER_PENDING
    within that SAME page — never a separate/additional scan beyond
    max_total — is then retried once by resolve_stage2_batch() (Stage 2).
    Caller owns the session/commit — see pyq_resolver_worker.py.

    Stage 2 only runs when apply=True: it decides what Stage 1 actually
    left pending by re-reading real committed state, which a dry-run
    (apply=False, rolled back) cannot produce — dry-run reporting therefore
    reflects Stage 1 only.
    """
    report = ResolveReport()
    cursor: tuple[Any, uuid.UUID] | None = None
    remaining = max_total
    while remaining > 0:
        lim = min(BATCH_SIZE, remaining)
        if cursor is None:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, raw_stem, raw_options, created_at FROM pyq.questions "
                        "WHERE state = 'ANSWER_PENDING' ORDER BY created_at ASC, id ASC LIMIT :lim"
                    ),
                    {"lim": lim},
                )
            ).all()
        else:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, raw_stem, raw_options, created_at FROM pyq.questions "
                        "WHERE state = 'ANSWER_PENDING' AND (created_at, id) > (:c_at, :c_id) "
                        "ORDER BY created_at ASC, id ASC LIMIT :lim"
                    ),
                    {"c_at": cursor[0], "c_id": cursor[1], "lim": lim},
                )
            ).all()
        if not rows:
            break
        cursor = (rows[-1][3], rows[-1][0])
        remaining -= len(rows)
        page_rows = [(r[0], r[1], r[2]) for r in rows]
        await resolve_batch(session, idx, page_rows, report, apply=apply)
        if apply:
            await session.commit()
            page_ids = [r[0] for r in rows]
            still_pending_stmt = text(
                "SELECT id FROM pyq.questions WHERE id IN :ids AND state = 'ANSWER_PENDING'"
            ).bindparams(bindparam("ids", expanding=True))
            still_pending = {
                row[0] for row in (await session.execute(still_pending_stmt, {"ids": page_ids})).all()
            }
            if still_pending:
                stage2_rows = [r for r in page_rows if r[0] in still_pending]
                await resolve_stage2_batch(
                    session, idx, stage2_rows, report, apply=True, ai_gateway=ai_gateway, run_id=run_id
                )
                await session.commit()
        else:
            await session.rollback()
    return report


async def run(apply: bool) -> ResolveReport:
    from app.core.database import AsyncSessionLocal

    report = ResolveReport()
    async with AsyncSessionLocal() as session:
        idx = await _load_ku_index(session)
        logger.info("pyq_resolver_index_loaded", knowledge_units=len(idx.unit_ids))

        last_id: uuid.UUID | None = None
        while True:
            if last_id is None:
                rows = (
                    await session.execute(
                        text(
                            "SELECT id, raw_stem, raw_options FROM pyq.questions "
                            "WHERE state = 'ANSWER_PENDING' ORDER BY id LIMIT :lim"
                        ),
                        {"lim": BATCH_SIZE},
                    )
                ).all()
            else:
                rows = (
                    await session.execute(
                        text(
                            "SELECT id, raw_stem, raw_options FROM pyq.questions "
                            "WHERE state = 'ANSWER_PENDING' AND id > :last_id ORDER BY id LIMIT :lim"
                        ),
                        {"last_id": last_id, "lim": BATCH_SIZE},
                    )
                ).all()
            if not rows:
                break
            last_id = rows[-1][0]
            await resolve_batch(session, idx, rows, report, apply=apply)
            if apply:
                await session.commit()
            else:
                await session.rollback()

    return report


async def main() -> int:
    parser = argparse.ArgumentParser(description="PYQ answer resolver (deterministic Stage 1, optional one-pass Gemini Stage 2)")
    parser.add_argument("--apply", action="store_true", help="Persist writes (default: dry-run)")
    parser.add_argument(
        "--max-total",
        type=int,
        default=None,
        help="Bound the run to at most this many oldest ANSWER_PENDING rows and enable Stage 2 "
        "(one-pass Gemini) for whatever Stage 1 leaves pending within that same bound. "
        "Omit to run the unbounded, Stage-1-only (no LLM, no cost) sweep via run().",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Tag embedded in Stage 2 evidence_note for this run (default: UTC timestamp).",
    )
    args = parser.parse_args()

    if args.max_total is not None:
        import datetime

        from app.core.database import AsyncSessionLocal

        run_id = args.run_id or datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        async with AsyncSessionLocal() as session:
            idx = await _load_ku_index(session)
            logger.info("pyq_resolver_index_loaded", knowledge_units=len(idx.unit_ids))
            report = await resolve_up_to(session, idx, max_total=args.max_total, apply=args.apply, run_id=run_id)
        print("APPLY" if args.apply else "DRY RUN (no writes persisted)", f"run_id={run_id}")
        print(json.dumps(report.__dict__, indent=2))
        return 0

    report = await run(apply=args.apply)
    print("APPLY" if args.apply else "DRY RUN (no writes persisted)")
    print(json.dumps(report.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
