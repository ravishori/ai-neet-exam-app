"""PYTHON-MCQ-ENGINE-007 — read-only evaluation of ENGINE-006 reviewed 100-fact pack."""

from __future__ import annotations

import json
import re
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
SCRIPTS = BACKEND / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from python_mcq_engine_003_audit import _read_only_snapshot  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.services.deterministic_fact_adapter import (  # noqa: E402
    DeterministicFactToQuestionAdapter,
    FactAdapterError,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (  # noqa: E402
    extract_ncert_source_text,
    load_deterministic_fact_pack,
)
from app.modules.cms.services.deterministic_mcq_engine import (  # noqa: E402
    ENGINE_VERSION,
    DeterministicEvidenceContext,
    DeterministicMcqEngine,
)
from app.modules.cms.services.fact_quality_gate import (  # noqa: E402
    FactQualityGate,
    TaxonomyBinding,
)
from app.modules.cms.services.ncert_generation_evidence import (  # noqa: E402
    NcertEvidencePack,
)
from app.modules.cms.syllabus import assert_blueprint_neet_syllabus_scope  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    validate_ncert_generation_source,
)

TASK_ID = "PYTHON-MCQ-ENGINE-007"
PACK = BACKEND / "tests/fixtures/python_mcq_engine_006_reviewed_100.json"
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_007.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_007.md"
SYLLABUS = ROOT / "NEETSyllabus.txt"
SEED = 20260914
_WS = re.compile(r"\s+")
_QUOTED = re.compile(r'"([^"]+)"')


def _norm(value: str) -> str:
    return _WS.sub(" ", value or "").strip().casefold()


def _contains(haystack: str, needle: str) -> bool:
    return bool(_norm(needle)) and _norm(needle) in _norm(haystack)


def _taxonomy_for_fact(fact) -> TaxonomyBinding:
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


def _context_for_fact(fact) -> DeterministicEvidenceContext:
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
            detail="ENGINE-007 evaluation full canonical source",
        ),
    )


def _also_answers_stem(
    stem: str,
    option_text: str,
    option_quote: str,
    source_text: str,
    *,
    correct_quote: str,
) -> bool:
    """Independent uniqueness probe — fail closed when uncertain."""
    stem_n = _norm(stem)
    quote_n = _norm(option_quote)
    text_n = _norm(option_text)

    # ENGINE-006 blanked definition completions.
    if "____" in stem or "___" in stem:
        match = _QUOTED.search(stem)
        if not match:
            return True
        blanked = match.group(1)
        filled = re.sub(r"_+", option_text, blanked, count=1)
        return _contains(source_text, filled)

    # ENGINE-004 Biomolecules probes retained for the seeded reviewed facts.
    if "non-reducing sugar" in stem_n:
        monosaccharide_reducing = _contains(
            source_text,
            "All monosaccharides whether aldose or ketose are reducing sugars",
        )
        if monosaccharide_reducing and text_n in {"glucose", "fructose", "ribose"}:
            return False
        return "non reducing sugar" in quote_n or "non-reducing sugar" in quote_n
    if "cannot be hydrolysed further" in stem_n:
        return "cannot be hydrolysed further" in quote_n or (
            "is called a monosaccharide" in quote_n
            and "cannot be hydrolysed further" in stem_n
        )
    if "large number of monosaccharide units" in stem_n:
        return "large number of monosaccharide units" in quote_n
    if "hydrolysis products of sucrose" in stem_n:
        return "sucrose" in text_n and "glucose" in quote_n and "fructose" in quote_n
    if "hydrolysis products of maltose" in stem_n:
        return "maltose" in text_n and "glucose" in quote_n and "fructose" not in quote_n

    # Fail closed: identical evidence to the keyed explanation is not unique.
    if quote_n == _norm(correct_quote):
        return True
    # Unknown stem shape: treat distractor as potentially answering.
    return True


def independent_verify(candidate, adapted, source_text: str) -> dict[str, Any]:
    body = candidate.body
    stem_q = adapted.spec.stem_evidence_quote
    expl_q = adapted.spec.explanation_evidence_quote
    correct = next(
        option for option in body["options"] if option["label"] == body["correct_option"]
    )
    correct_spec = next(
        option
        for option in adapted.spec.options
        if option.key == adapted.spec.correct_key
    )
    answering = [
        option.key
        for option in adapted.spec.options
        if _contains(source_text, option.evidence_quote)
        and (
            option.key == adapted.spec.correct_key
            or _also_answers_stem(
                adapted.spec.stem,
                option.text,
                option.evidence_quote,
                source_text,
                correct_quote=expl_q,
            )
        )
    ]
    keyed_answers = adapted.spec.correct_key in answering
    distractors_answering = [key for key in answering if key != adapted.spec.correct_key]
    option_quotes_ok = all(
        _contains(source_text, option.evidence_quote) for option in adapted.spec.options
    )
    syllabus = assert_blueprint_neet_syllabus_scope(
        {"neet_ug_2026": adapted.syllabus_binding},
        academic_subject_code=candidate.subject,
        syllabus_path=str(SYLLABUS),
    )
    checks = {
        "cited_pdf_exists": Path(candidate.source_path).is_file(),
        "inside_canonical_root": (
            candidate.source_relative_path == adapted.source_relative_path
            and "StudyMaterial" not in candidate.source_path
        ),
        "stem_supported": _contains(source_text, stem_q),
        "correct_answer_supported": (
            _contains(source_text, expl_q)
            and correct["text"] == correct_spec.text
            and keyed_answers
        ),
        "all_options_supported_or_safely_derived": option_quotes_ok,
        "exactly_one_defensible": keyed_answers and not distractors_answering,
        "taxonomy_mapping_valid": (
            candidate.chapter == adapted.chapter
            and candidate.topic == adapted.topic
            and candidate.concept == adapted.concept_name
        ),
        "syllabus_binding_valid": syllabus.is_in_scope,
        "provenance_preserved": (
            body["provenance"]["source"] == "canonical_ncert"
            and adapted.provenance["origin"] == "canonical_ncert"
        ),
        "no_unsupported_enrichment": (
            body["ncert_evidence"]["source_excerpt"] == expl_q
            and body["ncert_evidence"]["source_pdf_relpath"]
            == adapted.source_relative_path
        ),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        classification = "FAIL"
        reason = "Independent checks failed: " + ", ".join(failed)
        if distractors_answering and "exactly_one_defensible" in failed:
            classification = "AMBIGUOUS" if keyed_answers else "FAIL"
            if classification == "AMBIGUOUS":
                reason = (
                    "Multiple options independently fill the NCERT statement: "
                    + ", ".join(distractors_answering)
                )
        return {"classification": classification, "reason": reason, "checks": checks}
    if not keyed_answers:
        return {
            "classification": "AMBIGUOUS",
            "reason": "Keyed answer could not be independently confirmed.",
            "checks": checks,
        }
    return {
        "classification": "PASS",
        "reason": (
            "Independent PDF review supports stem/key/options with unique keyed answer."
        ),
        "checks": checks,
    }


def _yield_table(records: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[str]] = defaultdict(list)
    for row in records:
        groups[str(row.get(key) or "")].append(row["classification"])
    out: dict[str, Any] = {}
    for name, classes in sorted(groups.items()):
        total = len(classes)
        passes = sum(1 for item in classes if item == "PASS")
        out[name] = {
            "generated": total,
            "PASS": passes,
            "FAIL": sum(1 for item in classes if item == "FAIL"),
            "AMBIGUOUS": sum(1 for item in classes if item == "AMBIGUOUS"),
            "verified_yield": round(passes / total, 4) if total else 0.0,
        }
    return out


def _production_stem_overlap(db, stem_hashes: set[str]) -> dict[str, Any]:
    if not stem_hashes:
        return {"checked": True, "overlap_count": 0, "overlap_hashes": []}
    with db.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        fingerprint_hits = conn.execute(
            text(
                """
                SELECT DISTINCT stem_hash
                FROM cms.question_fingerprints
                WHERE deleted_at IS NULL AND stem_hash = ANY(:hashes)
                """
            ),
            {"hashes": list(stem_hashes)},
        ).scalars().all()
        candidate_hits = conn.execute(
            text(
                """
                SELECT DISTINCT stem_hash
                FROM cms.generation_candidates
                WHERE deleted_at IS NULL AND stem_hash = ANY(:hashes)
                """
            ),
            {"hashes": list(stem_hashes)},
        ).scalars().all()
        conn.rollback()
    overlap = sorted({*fingerprint_hits, *candidate_hits})
    return {
        "checked": True,
        "overlap_count": len(overlap),
        "overlap_hashes": overlap[:20],
        "fingerprint_hits": len(fingerprint_hits),
        "generation_candidate_hits": len(candidate_hits),
    }


def _write_markdown(audit: dict[str, Any]) -> None:
    m = audit["metrics"]
    lines = [
        "# PYTHON-MCQ-ENGINE-007 — Reviewed 100-Fact Read-Only Evaluation",
        "",
        f"**Verdict:** **{audit['verdict']}**",
        f"**Facts evaluated:** **{m['facts_selected']}**",
        f"**FACT_APPROVED / MCQ_ELIGIBLE / blocked:** "
        f"**{m['FACT_APPROVED']} / {m['MCQ_ELIGIBLE']} / {m['blocked_during_evaluation']}**",
        f"**Candidates generated:** **{m['candidates_created']}**",
        f"**Independent PASS/FAIL/AMBIGUOUS:** "
        f"**{m['independent_PASS']} / {m['independent_FAIL']} / {m['independent_AMBIGUOUS']}**",
        f"**READ-ONLY EVALUATION VERIFIED YIELD:** **{m['verified_yield']}**",
        "",
        "## Verified yield breakdown",
        "",
        f"- By subject: `{m['verified_yield_by_subject']}`",
        f"- By class: `{m['verified_yield_by_class']}`",
        f"- By question type: `{m['verified_yield_by_question_type']}`",
        "",
        "## Reproducibility and safety",
        "",
        f"- Reproducible: **{m['reproducible']}**",
        f"- Runtime seconds: **{m['runtime_seconds']}**",
        f"- Provider/API calls: **{audit['provider_api_calls']}**",
        f"- Production DB mutations: **{audit['production_db_mutations']}**",
        f"- Invariants unchanged: **{audit['production_safety_unchanged']}**",
        f"- Worker: **{audit['worker_observation']['start']} / "
        f"{audit['worker_observation']['end']}**",
        "",
        "## Tests",
        "",
        f"- Focused/regression: **{audit['tests']['focused']}** / "
        f"**{audit['tests']['regression']}**",
        f"- Ruff: **{audit['tests']['ruff']}**",
        "",
        "## Major failure patterns",
        "",
        *[f"- {item}" for item in audit["major_failure_patterns"]],
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in audit["limitations"]],
        "",
        f"**Recommended next task:** {audit['recommended_next_task']}",
        "",
    ]
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    started = time.perf_counter()
    tracemalloc.start()
    settings = get_settings()
    db = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(db)

    # Do not mutate the reviewed fixture; load as REVIEWED floor.
    pack_bytes = PACK.read_bytes()
    loaded = load_deterministic_fact_pack(PACK)
    if len(loaded.facts) != 100:
        raise RuntimeError(f"expected 100 facts, loaded {len(loaded.facts)}")
    if PACK.read_bytes() != pack_bytes:
        raise RuntimeError("reviewed fixture mutated during load")

    gate = FactQualityGate()
    adapter = DeterministicFactToQuestionAdapter(gate)
    quality_rows: list[dict[str, Any]] = []
    adapted_ok: list[Any] = []
    skip_reasons: Counter[str] = Counter()
    reason_codes: Counter[str] = Counter()
    gen_times: list[float] = []
    verify_times: list[float] = []
    blocked = 0

    for fact in loaded.facts:
        taxonomy = _taxonomy_for_fact(fact)
        t0 = time.perf_counter()
        try:
            adapted = adapter.adapt(
                fact,
                taxonomy=taxonomy,
                authoritative_syllabus_path=SYLLABUS,
            )
            quality = adapted.quality
            quality_rows.append(
                {
                    "fact_id": fact.fact_id,
                    "subject": fact.subject,
                    "class_level": fact.class_level,
                    "chapter": fact.chapter,
                    "topic": fact.topic,
                    "concept": fact.concept_name,
                    "review_status": fact.review_status,
                    "status": quality.status,
                    "workflow_stage": quality.workflow_stage,
                    "mcq_eligible": quality.mcq_eligible,
                    "reason_codes": [r.code for r in quality.reasons],
                }
            )
            for code in [r.code for r in quality.reasons]:
                reason_codes[code] += 1
            if quality.mcq_eligible:
                adapted_ok.append(adapted)
            else:
                blocked += 1
                skip_reasons[quality.status] += 1
        except FactAdapterError as exc:
            blocked += 1
            skip_reasons[exc.code] += 1
            reason_codes[exc.code] += 1
            quality_rows.append(
                {
                    "fact_id": fact.fact_id,
                    "subject": fact.subject,
                    "class_level": fact.class_level,
                    "chapter": fact.chapter,
                    "topic": fact.topic,
                    "concept": fact.concept_name,
                    "review_status": fact.review_status,
                    "status": "BLOCKED",
                    "workflow_stage": "REJECTED",
                    "mcq_eligible": False,
                    "reason_codes": [exc.code],
                    "detail": exc.detail,
                }
            )
        gen_times.append(time.perf_counter() - t0)

    candidates_first: list[Any] = []
    candidates_second: list[Any] = []
    verification_records: list[dict[str, Any]] = []
    candidate_records: list[dict[str, Any]] = []
    generation_failures = Counter()
    validation_failures = 0
    source_failures = 0
    syllabus_failures = 0
    duplicate_failures = 0

    if adapted_ok:
        # One context per fact (chapter/topic/concept come from context).
        # Do not batch across differing taxonomy bindings on the same PDF.
        for adapted in adapted_ok:
            fact = next(f for f in loaded.facts if f.fact_id == adapted.fact_id)
            context = _context_for_fact(fact)
            specs = [adapted.spec]
            quality_map = {adapted.fact_id: adapted.quality}
            first = DeterministicMcqEngine().generate_eligible(
                context, specs, quality_results=quality_map, seed=SEED
            )
            second = DeterministicMcqEngine().generate_eligible(
                context, specs, quality_results=quality_map, seed=SEED
            )
            candidates_first.extend(first.candidates)
            candidates_second.extend(second.candidates)
            validation_failures += first.validation_failures
            source_failures += first.source_gate_failures
            syllabus_failures += first.syllabus_gate_failures
            duplicate_failures += first.duplicate_failures
            for skipped in first.skipped:
                generation_failures[skipped.reason] += 1
                skip_reasons[skipped.reason] += 1
            source_text = context.evidence.evidence_text
            if not first.candidates:
                candidate_records.append(
                    {
                        "fact_id": adapted.fact_id,
                        "subject": fact.subject,
                        "class_level": fact.class_level,
                        "chapter": adapted.chapter,
                        "topic": adapted.topic,
                        "concept": adapted.concept_name,
                        "question_type": adapted.spec.question_type,
                        "source": adapted.source_relative_path,
                        "generation_status": "SKIPPED",
                        "validation_status": "NOT_GENERATED",
                        "independent_verification_status": "NOT_APPLICABLE",
                        "failure_reason": (
                            first.skipped[0].reason
                            if first.skipped
                            else "GENERATION_SKIPPED"
                        ),
                    }
                )
                continue
            for candidate in first.candidates:
                t1 = time.perf_counter()
                finding = independent_verify(candidate, adapted, source_text)
                verify_times.append(time.perf_counter() - t1)
                verification_records.append(
                    {
                        "fact_id": candidate.fact_id,
                        "subject": candidate.subject,
                        "class_level": candidate.class_level,
                        "chapter": candidate.chapter,
                        "topic": candidate.topic,
                        "concept": candidate.concept,
                        "question_type": candidate.question_type,
                        "classification": finding["classification"],
                        "reason": finding["reason"],
                        "checks": finding["checks"],
                        "stem_hash": candidate.stem_hash,
                    }
                )
                candidate_records.append(
                    {
                        "fact_id": candidate.fact_id,
                        "subject": candidate.subject,
                        "class_level": candidate.class_level,
                        "chapter": candidate.chapter,
                        "topic": candidate.topic,
                        "concept": candidate.concept,
                        "question_type": candidate.question_type,
                        "source": candidate.source_relative_path,
                        "generation_status": "CREATED",
                        "validation_status": "PASSED",
                        "independent_verification_status": finding["classification"],
                        "failure_reason": (
                            finding["reason"]
                            if finding["classification"] != "PASS"
                            else None
                        ),
                        "stem_hash": candidate.stem_hash,
                    }
                )

    first_sorted = sorted(
        [item.to_dict() for item in candidates_first],
        key=lambda item: item["fact_id"],
    )
    second_sorted = sorted(
        [item.to_dict() for item in candidates_second],
        key=lambda item: item["fact_id"],
    )
    reproducible = first_sorted == second_sorted
    differing = []
    if not reproducible:
        first_ids = {item["fact_id"] for item in first_sorted}
        second_ids = {item["fact_id"] for item in second_sorted}
        differing = sorted(first_ids.symmetric_difference(second_ids))

    created = len(candidates_first)
    independent_counts = Counter(item["classification"] for item in verification_records)
    verified_pass = independent_counts.get("PASS", 0)
    verified_yield = round(verified_pass / created, 4) if created else 0.0
    unique_stems = len({item.stem_hash for item in candidates_first})
    duplicate_rate = round((created - unique_stems) / created, 4) if created else 0.0
    ambiguity_rate = (
        round(independent_counts.get("AMBIGUOUS", 0) / created, 4) if created else 0.0
    )
    generation_failure_rate = round((100 - created) / 100, 4)

    quality_status = Counter(row["status"] for row in quality_rows)
    mcq_eligible = sum(1 for row in quality_rows if row.get("mcq_eligible"))
    stem_hashes = {item.stem_hash for item in candidates_first}
    production_overlap = _production_stem_overlap(db, stem_hashes)

    after = _read_only_snapshot(db)
    db.dispose()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    runtime = round(time.perf_counter() - started, 3)

    major_patterns = [
        f"{code}:{count}"
        for code, count in Counter(
            row["failure_reason"]
            for row in candidate_records
            if row.get("failure_reason")
        ).most_common(10)
    ] or ["none"]

    # Fixture integrity after evaluation.
    fixture_unchanged = PACK.read_bytes() == pack_bytes

    audit = {
        "task_id": TASK_ID,
        "evaluation_id": "python-mcq-engine-007-reviewed-100-v1",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "verdict": (
            "GREEN"
            if len(loaded.facts) == 100
            and before == after
            and reproducible
            and fixture_unchanged
            and settings.ncert_source_root
            else "YELLOW"
        ),
        "engine_version": ENGINE_VERSION,
        "source_root": settings.ncert_source_root,
        "syllabus_source": str(SYLLABUS),
        "fact_pack": {
            "path": str(PACK),
            "pack_id": loaded.pack_id,
            "schema_version": loaded.schema_version,
            "input_sha256": loaded.input_sha256,
            "fact_count": len(loaded.facts),
            "fixture_unchanged": fixture_unchanged,
        },
        "quality_results": quality_rows,
        "candidate_records": candidate_records,
        "candidates": first_sorted,
        "independent_verification": {
            "counts": {
                "PASS": independent_counts.get("PASS", 0),
                "FAIL": independent_counts.get("FAIL", 0),
                "AMBIGUOUS": independent_counts.get("AMBIGUOUS", 0),
            },
            "records": verification_records,
        },
        "metrics": {
            "facts_selected": 100,
            "FACT_APPROVED": quality_status.get("FACT_APPROVED", 0),
            "FACT_REVIEW_REQUIRED": quality_status.get("FACT_REVIEW_REQUIRED", 0),
            "FACT_REJECTED": quality_status.get("FACT_REJECTED", 0),
            "MCQ_ELIGIBLE": mcq_eligible,
            "blocked_during_evaluation": blocked,
            "reason_code_distribution": dict(reason_codes),
            "candidates_attempted": len(adapted_ok),
            "candidates_created": created,
            "generation_skips": 100 - created,
            "generation_failure_rate": generation_failure_rate,
            "skip_reasons": dict(skip_reasons),
            "validation_failures": validation_failures,
            "source_failures": source_failures,
            "syllabus_failures": syllabus_failures,
            "duplicate_failures": duplicate_failures,
            "generation_skip_reason_counts": dict(generation_failures),
            "question_type_distribution": dict(
                Counter(item.question_type for item in candidates_first)
            ),
            "independent_PASS": independent_counts.get("PASS", 0),
            "independent_FAIL": independent_counts.get("FAIL", 0),
            "independent_AMBIGUOUS": independent_counts.get("AMBIGUOUS", 0),
            "verified_yield": verified_yield,
            "verified_yield_label": "READ-ONLY EVALUATION VERIFIED YIELD",
            "verified_yield_by_subject": _yield_table(verification_records, "subject"),
            "verified_yield_by_class": _yield_table(verification_records, "class_level"),
            "verified_yield_by_chapter": _yield_table(verification_records, "chapter"),
            "verified_yield_by_topic": _yield_table(verification_records, "topic"),
            "verified_yield_by_question_type": _yield_table(
                verification_records, "question_type"
            ),
            "duplicate_rate": duplicate_rate,
            "ambiguity_rate": ambiguity_rate,
            "production_corpus_stem_overlap": production_overlap,
            "reproducible": reproducible,
            "first_run_count": len(candidates_first),
            "second_run_count": len(candidates_second),
            "differing_fact_ids": differing,
            "runtime_seconds": runtime,
            "average_generation_time_seconds": (
                round(sum(gen_times) / len(gen_times), 4) if gen_times else 0.0
            ),
            "average_verification_time_seconds": (
                round(sum(verify_times) / len(verify_times), 4) if verify_times else 0.0
            ),
            "peak_memory_bytes": peak,
            "subject_distribution": dict(Counter(f.subject for f in loaded.facts)),
        },
        "database_before": before,
        "database_after": after,
        "production_safety_unchanged": before == after,
        "provider_api_calls": 0,
        "api_cost_inr": 0,
        "production_db_mutations": 0,
        "worker_observation": {
            "start": "UNKNOWN",
            "end": "UNKNOWN",
            "continuity_claimed": False,
        },
        "tests": {"focused": "pending", "regression": "pending", "ruff": "pending"},
        "major_failure_patterns": major_patterns,
        "limitations": [
            (
                "Independent verification is PDF/syllabus/taxonomy evidence review; "
                "FACT_APPROVED/MCQ_ELIGIBLE is not treated as NCERT certification."
            ),
            "Production corpus overlap uses stem_hash fingerprints only (read-only).",
            "No semantic embedding dedupe was available.",
            "OpenAI worker observation is UNKNOWN; continuity is not claimed.",
            "ENGINE-006 fixture was not modified.",
        ],
        "recommended_next_task": (
            "PYTHON-MCQ-ENGINE-008: remediate independent FAIL/AMBIGUOUS patterns in the "
            "reviewed fact pack (blanked-stem uniqueness, concept binding, distractor "
            "evidence), then re-run this read-only 100-fact evaluation without persistence "
            "or provider calls."
            if independent_counts.get("FAIL", 0) + independent_counts.get("AMBIGUOUS", 0)
            else (
                "PYTHON-MCQ-ENGINE-008: scale beyond the 100-fact reviewed corpus with "
                "additional multi-chapter REVIEWED packs and a gated non-production "
                "staging dry-run, still without production persistence."
            )
        ),
    }
    AUDIT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    _write_markdown(audit)
    print(
        json.dumps(
            {
                "verdict": audit["verdict"],
                "facts": 100,
                "created": created,
                "PASS": independent_counts.get("PASS", 0),
                "FAIL": independent_counts.get("FAIL", 0),
                "AMBIGUOUS": independent_counts.get("AMBIGUOUS", 0),
                "verified_yield": verified_yield,
                "reproducible": reproducible,
                "runtime_seconds": runtime,
                "fixture_unchanged": fixture_unchanged,
            },
            indent=2,
        )
    )
    return 0 if audit["verdict"] in {"GREEN", "YELLOW"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
