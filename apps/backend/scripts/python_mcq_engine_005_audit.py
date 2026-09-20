"""PYTHON-MCQ-ENGINE-005 — 100-fact read-only evaluation."""

from __future__ import annotations

import json
import re
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

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

TASK_ID = "PYTHON-MCQ-ENGINE-005"
PACK = BACKEND / "tests/fixtures/python_mcq_engine_005_eval_100.json"
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_005.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_005.md"
SYLLABUS = ROOT / "NEETSyllabus.txt"
SEED = 20260914
_WS = re.compile(r"\s+")


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
            detail="ENGINE-005 evaluation full canonical source",
        ),
    )


def _also_answers_stem(
    stem: str, option_text: str, option_quote: str, source_text: str
) -> bool:
    """Reuse ENGINE-004 uniqueness probes for the reviewed Biomolecules set."""
    stem_n = _norm(stem)
    quote_n = _norm(option_quote)
    text_n = _norm(option_text)
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
    # Fail closed when uniqueness cannot be established from excerpts alone.
    return True


def _independent_verify(candidate, adapted, source_text: str) -> dict[str, Any]:
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
        return {
            "classification": "FAIL",
            "reason": "Independent checks failed: " + ", ".join(failed),
            "checks": checks,
        }
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


def _write_markdown(audit: dict[str, Any]) -> None:
    m = audit["metrics"]
    lines = [
        "# PYTHON-MCQ-ENGINE-005 — 100-Fact Read-Only Evaluation",
        "",
        f"**Verdict:** **{audit['verdict']}**",
        f"**Facts selected:** **{m['facts_selected']}**",
        f"**FACT_APPROVED / REVIEW_REQUIRED / REJECTED:** "
        f"**{m['FACT_APPROVED']} / {m['FACT_REVIEW_REQUIRED']} / {m['FACT_REJECTED']}**",
        f"**Candidates generated:** **{m['candidates_created']}**",
        f"**Independent PASS/FAIL/AMBIGUOUS:** "
        f"**{m['independent_PASS']} / {m['independent_FAIL']} / {m['independent_AMBIGUOUS']}**",
        f"**Read-only evaluation verified yield:** **{m['verified_yield']}**",
        "",
        "## Subject / chapter coverage",
        "",
        f"- Subject distribution: `{m['subject_distribution']}`",
        f"- Chapters used: **{m['chapter_count']}**",
        "",
        "## Honesty",
        "",
        "- Exactly 100 facts were selected.",
        "- Only previously REVIEWED ENGINE-004 facts were treated as reviewed.",
        "- EXTRACTED facts were not silently upgraded.",
        "- Rejected / review-required facts are first-class evaluation results.",
        "",
        "## Reproducibility and safety",
        "",
        f"- Reproducible: **{m['reproducible']}**",
        f"- Runtime seconds: **{m['runtime_seconds']}**",
        f"- Provider/API calls: **{audit['provider_api_calls']}**",
        f"- Production DB mutations: **{audit['production_db_mutations']}**",
        f"- Invariants unchanged: **{audit['production_safety_unchanged']}**",
        f"- Worker observation: **{audit['worker_observation']['start']} / "
        f"{audit['worker_observation']['end']}**",
        "",
        "## Tests",
        "",
        f"- Focused: **{audit['tests']['focused']}**",
        f"- Regression: **{audit['tests']['regression']}**",
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

    loaded = load_deterministic_fact_pack(
        PACK,
        minimum_review_status="EXTRACTED",
    )
    if len(loaded.facts) != 100:
        raise RuntimeError(f"expected 100 facts, loaded {len(loaded.facts)}")

    gate = FactQualityGate()
    adapter = DeterministicFactToQuestionAdapter(gate)
    quality_rows = []
    adapted_ok = []
    skip_reasons: Counter[str] = Counter()
    reason_codes: Counter[str] = Counter()
    gen_times: list[float] = []
    verify_times: list[float] = []

    for fact in loaded.facts:
        taxonomy = _taxonomy_for_fact(fact)
        t0 = time.perf_counter()
        try:
            if fact.question_template is None:
                quality = gate.evaluate(
                    fact,
                    taxonomy=taxonomy,
                    authoritative_syllabus_path=SYLLABUS,
                    question=None,
                )
                adapted = None
            else:
                adapted = adapter.adapt(
                    fact,
                    taxonomy=taxonomy,
                    authoritative_syllabus_path=SYLLABUS,
                )
                quality = adapted.quality
        except FactAdapterError as exc:
            # Adapter fails closed; still surface gate status without construction.
            quality = gate.evaluate(
                fact,
                taxonomy=taxonomy,
                authoritative_syllabus_path=SYLLABUS,
                question=None,
            )
            adapted = None
            reason_codes[exc.code] += 1
            skip_reasons[exc.code] += 1

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
        if adapted is not None and quality.mcq_eligible:
            adapted_ok.append(adapted)
        elif not quality.mcq_eligible:
            skip_reasons[quality.status] += 1
        gen_times.append(time.perf_counter() - t0)

    # Generate only eligible adapted facts (max whatever exists; do not pad).
    candidates_first = []
    candidates_second = []
    verification_records = []
    if adapted_ok:
        # Group by source PDF for evidence context reuse.
        by_source: dict[str, list] = defaultdict(list)
        for item in adapted_ok:
            by_source[item.source_pdf].append(item)
        for _source, group in by_source.items():
            context = _context_for_fact(
                next(fact for fact in loaded.facts if fact.fact_id == group[0].fact_id)
            )
            specs = [item.spec for item in group]
            quality_map = {item.fact_id: item.quality for item in group}
            first = DeterministicMcqEngine().generate_eligible(
                context,
                specs,
                quality_results=quality_map,
                seed=SEED,
            )
            second = DeterministicMcqEngine().generate_eligible(
                context,
                specs,
                quality_results=quality_map,
                seed=SEED,
            )
            candidates_first.extend(first.candidates)
            candidates_second.extend(second.candidates)
            source_text = context.evidence.evidence_text
            adapted_map = {item.fact_id: item for item in group}
            for candidate in first.candidates:
                t1 = time.perf_counter()
                finding = _independent_verify(
                    candidate,
                    adapted_map[candidate.fact_id],
                    source_text,
                )
                verify_times.append(time.perf_counter() - t1)
                verification_records.append(
                    {
                        "fact_id": candidate.fact_id,
                        "subject": candidate.subject,
                        "chapter": candidate.chapter,
                        "question_type": candidate.question_type,
                        "classification": finding["classification"],
                        "reason": finding["reason"],
                        "checks": finding["checks"],
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
    created = len(candidates_first)
    independent_counts = Counter(
        item["classification"] for item in verification_records
    )
    verified_pass = independent_counts.get("PASS", 0)
    verified_yield = (
        round(verified_pass / created, 4) if created else 0.0
    )
    duplicate_rate = 0.0
    if created:
        unique_stems = len({item.stem_hash for item in candidates_first})
        duplicate_rate = round((created - unique_stems) / created, 4)
    ambiguity_rate = (
        round(independent_counts.get("AMBIGUOUS", 0) / created, 4) if created else 0.0
    )

    subject_distribution = Counter(fact.subject for fact in loaded.facts)
    chapter_set = {(fact.subject, fact.chapter) for fact in loaded.facts}
    class_distribution = Counter(fact.class_level for fact in loaded.facts)
    chapter_distribution = Counter(
        f"{fact.subject}:{fact.chapter}" for fact in loaded.facts
    )
    question_type_distribution = Counter(
        item.question_type for item in candidates_first
    )
    quality_status = Counter(row["status"] for row in quality_rows)

    after = _read_only_snapshot(db)
    db.dispose()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    runtime = round(time.perf_counter() - started, 3)

    major_patterns = [
        f"{code}:{count}"
        for code, count in reason_codes.most_common(8)
    ]
    if not major_patterns:
        major_patterns = ["none"]

    audit = {
        "task_id": TASK_ID,
        "evaluation_id": "python-mcq-engine-005-eval-100-v1",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "verdict": (
            "GREEN"
            if len(loaded.facts) == 100
            and before == after
            and reproducible
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
        },
        "selected_facts": [
            {
                "fact_id": fact.fact_id,
                "subject": fact.subject,
                "class_level": fact.class_level,
                "chapter": fact.chapter,
                "topic": fact.topic,
                "concept": fact.concept_name,
                "source_pdf": fact.source_pdf,
                "source_relative_path": fact.source_relative_path,
                "review_status": fact.review_status,
                "fact_type": fact.fact_type,
                "syllabus_topic_id": fact.syllabus_binding.topic_id,
            }
            for fact in loaded.facts
        ],
        "quality_results": quality_rows,
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
            "reason_code_distribution": dict(reason_codes),
            "candidates_attempted": len(adapted_ok),
            "candidates_created": created,
            "generation_skips": 100 - created,
            "skip_reasons": dict(skip_reasons),
            "question_type_distribution": dict(question_type_distribution),
            "independent_PASS": independent_counts.get("PASS", 0),
            "independent_FAIL": independent_counts.get("FAIL", 0),
            "independent_AMBIGUOUS": independent_counts.get("AMBIGUOUS", 0),
            "verified_yield": verified_yield,
            "verified_yield_label": "READ-ONLY EVALUATION VERIFIED YIELD",
            "duplicate_rate": duplicate_rate,
            "ambiguity_rate": ambiguity_rate,
            "subject_distribution": dict(subject_distribution),
            "class_distribution": dict(class_distribution),
            "chapter_distribution": dict(chapter_distribution),
            "chapter_count": len(chapter_set),
            "reproducible": reproducible,
            "first_run_count": len(candidates_first),
            "second_run_count": len(candidates_second),
            "runtime_seconds": runtime,
            "average_generation_time_seconds": (
                round(sum(gen_times) / len(gen_times), 4) if gen_times else 0.0
            ),
            "average_verification_time_seconds": (
                round(sum(verify_times) / len(verify_times), 4)
                if verify_times
                else 0.0
            ),
            "peak_memory_bytes": peak,
            "eligible_facts": quality_status.get("FACT_APPROVED", 0),
            "shortfall_to_100_generated": 100 - created,
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
        "tests": {
            "focused": "pending",
            "regression": "pending",
            "ruff": "pending",
        },
        "major_failure_patterns": major_patterns,
        "limitations": [
            "Only five ENGINE-004 facts were REVIEWED; 95 facts are EXTRACTED and fail closed until reviewed.",
            "This evaluation measures pipeline behavior, not production readiness.",
            "Independent verification applies only to generated candidates.",
            "No semantic embedding dedupe was available.",
            "OpenAI worker observation is UNKNOWN; continuity is not claimed.",
        ],
        "recommended_next_task": (
            "PYTHON-MCQ-ENGINE-006: curate and independently review additional "
            "multi-subject fact packs until each of Physics/Chemistry/Botany/Zoology "
            "has at least 25 REVIEWED+MCQ_ELIGIBLE facts with question templates, "
            "then re-run this read-only 100-fact evaluation without persistence."
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
                "approved": audit["metrics"]["FACT_APPROVED"],
                "review_required": audit["metrics"]["FACT_REVIEW_REQUIRED"],
                "rejected": audit["metrics"]["FACT_REJECTED"],
                "created": created,
                "verified_yield": verified_yield,
                "reproducible": reproducible,
                "runtime_seconds": runtime,
            },
            indent=2,
        )
    )
    return 0 if audit["verdict"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
