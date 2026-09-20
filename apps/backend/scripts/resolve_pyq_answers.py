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

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.knowledge.services.grounding_check import _significant_words, is_fact_grounded

logger = get_logger("pyq.resolver")

BATCH_SIZE = 500
OPTION_LABELS = ("A", "B", "C", "D")


@dataclass
class KnowledgeUnitIndex:
    unit_ids: list[str] = field(default_factory=list)
    unit_text: dict[str, str] = field(default_factory=dict)
    unit_summary: dict[str, str] = field(default_factory=dict)
    word_to_units: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def candidates_for(self, words: set[str]) -> set[str]:
        out: set[str] = set()
        for w in words:
            out |= self.word_to_units.get(w, set())
        return out


async def _load_ku_index(session: AsyncSession) -> KnowledgeUnitIndex:
    rows = (
        await session.execute(
            text("SELECT id, summary, structured_facts FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        )
    ).all()
    idx = KnowledgeUnitIndex()
    for ku_id, summary, facts in rows:
        ku_id_s = str(ku_id)
        facts_list = facts if isinstance(facts, list) else (json.loads(facts) if facts else [])
        combined = " ".join([summary or "", *[str(f) for f in facts_list]])
        idx.unit_ids.append(ku_id_s)
        idx.unit_text[ku_id_s] = combined
        idx.unit_summary[ku_id_s] = summary or ""
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


def _match_units(idx: KnowledgeUnitIndex, stem: str) -> list[str]:
    stem_words = _significant_words(stem)
    if not stem_words:
        return []
    candidates = idx.candidates_for(stem_words)
    matched = [uid for uid in candidates if is_fact_grounded(stem, idx.unit_text[uid])]
    return matched


def _option_text(rec_options: dict[str, Any], label: str) -> str:
    val = rec_options.get(label)
    return val if isinstance(val, str) else ""


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

        if len(grounded_options) == 1:
            report.answered += 1
            if apply:
                await session.execute(
                    text(
                        "INSERT INTO pyq.answer_assertions "
                        "(id, question_id, asserted_option, assertion_source, verification_status, evidence_note) "
                        "VALUES (:id, :qid, :opt, :src, 'VERIFIED', :note) "
                        "ON CONFLICT (question_id, assertion_source) DO NOTHING"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "qid": question_id,
                        "opt": grounded_options[0],
                        "src": f"knowledge_units:{source_id_str}",
                        "note": evidence_note,
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
                            "(id, question_id, asserted_option, assertion_source, verification_status, evidence_note) "
                            "VALUES (:id, :qid, :opt, :src, 'DISPUTED', :note) "
                            "ON CONFLICT (question_id, assertion_source) DO NOTHING"
                        ),
                        {
                            "id": uuid.uuid4(),
                            "qid": question_id,
                            "opt": label,
                            "src": f"knowledge_units:{source_id_str}:option_{label}",
                            "note": evidence_note,
                        },
                    )
                await session.execute(
                    text("UPDATE pyq.questions SET state = 'ANSWER_CONFLICT', updated_at = now() WHERE id = :id"),
                    {"id": question_id},
                )

        if apply:
            report.assertions_inserted += 1 if len(grounded_options) == 1 else len(grounded_options)


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
    parser = argparse.ArgumentParser(description="Deterministic PYQ answer resolver (no LLM)")
    parser.add_argument("--apply", action="store_true", help="Persist writes (default: dry-run)")
    args = parser.parse_args()

    report = await run(apply=args.apply)
    print("APPLY" if args.apply else "DRY RUN (no writes persisted)")
    print(json.dumps(report.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
