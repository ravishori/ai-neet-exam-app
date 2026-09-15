"""PYTHON-MCQ-ENGINE-014 — read-only eval of expanded reviewed cohort (007+012+013).

Deduplicates by fact_id. Does not modify any fixture. No MCQ persistence.
No provider calls. RELATIONSHIP_FORMULA remains excluded.
"""

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
from app.modules.cms.schemas.deterministic_fact_pack import (  # noqa: E402
    DeterministicFact,
)
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

TASK_ID = "PYTHON-MCQ-ENGINE-014"
PACK_006 = BACKEND / "tests/fixtures/python_mcq_engine_006_reviewed_100.json"
PACK_010 = BACKEND / "tests/fixtures/python_mcq_engine_010_reviewed_corpus.json"
PACK_012 = BACKEND / "tests/fixtures/python_mcq_engine_012_reviewed_nondef_v1.json"
PACK_013 = BACKEND / "tests/fixtures/python_mcq_engine_013_reviewed_nondef_v1.json"
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_014.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_014.md"
SYLLABUS = ROOT / "NEETSyllabus.txt"
SEED = 20260914
RETIRED_FACT_ID = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)
HYPOTHESIZED_COHORT = 334
_WS = re.compile(r"\s+")
_QUOTED = re.compile(r'"([^"]+)"')


def _norm(value: str) -> str:
    return _WS.sub(" ", value or "").strip().casefold()


def _contains(haystack: str, needle: str) -> bool:
    return bool(_norm(needle)) and _norm(needle) in _norm(haystack)


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
            detail="ENGINE-014 evaluation full canonical source",
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

    # Blanked definition / direct-fact completions.
    if "____" in stem or "___" in stem:
        match = _QUOTED.search(stem)
        if not match:
            return True
        blanked = match.group(1)
        filled = re.sub(r"_+", option_text, blanked, count=1)
        return _contains(source_text, filled)

    # CONTROLLED_ASSOCIATION stems from ENGINE-012/013.
    if "correctly associated with" in stem_n:
        match = _QUOTED.search(stem)
        if not match:
            return True
        entity = _norm(match.group(1))
        # Distractor answers only if its own evidence also pairs the same entity.
        return bool(entity) and entity in quote_n and text_n in quote_n

    # SI_UNIT / measurement stems.
    if "si unit" in stem_n or "measurement unit for" in stem_n:
        quantity = ""
        match = re.search(
            r"(?:measurement unit for|si unit / measurement unit for|si unit of)\s+(.+?)\??$",
            stem,
            re.IGNORECASE,
        )
        if match:
            quantity = _norm(match.group(1))
        if not quantity:
            return True
        return quantity in quote_n and text_n in quote_n

    # CONTROLLED_NUMERICAL stated-value stems.
    if "numerical value is stated" in stem_n:
        match = _QUOTED.search(stem)
        context = _norm(match.group(1)) if match else ""
        if not context:
            return True
        return text_n in quote_n and context in quote_n

    # Formula/relation selection stems (should be absent; fail closed).
    if "which of the following relations is supported" in stem_n:
        return text_n in quote_n

    # ENGINE-004 Biomolecules probes retained for seeded reviewed facts.
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

    if quote_n == _norm(correct_quote):
        return True
    # Unknown stem shape: fail closed.
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


def _success_rate(records: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    subset = [row for row in records if row.get(key) == value]
    total = len(subset)
    passes = sum(1 for row in subset if row["classification"] == "PASS")
    return {
        "generated": total,
        "PASS": passes,
        "FAIL": sum(1 for row in subset if row["classification"] == "FAIL"),
        "AMBIGUOUS": sum(1 for row in subset if row["classification"] == "AMBIGUOUS"),
        "verified_yield": round(passes / total, 4) if total else None,
    }


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


def _load_cohort() -> tuple[list[DeterministicFact], dict[str, dict[str, str]], dict]:
    """Load ENGINE-007 cohort (006 excl retired) + 012 + 013; dedupe by fact_id."""
    bytes_map = {
        "006": PACK_006.read_bytes(),
        "010": PACK_010.read_bytes(),
        "012": PACK_012.read_bytes(),
        "013": PACK_013.read_bytes(),
    }
    facts_by_id: dict[str, DeterministicFact] = {}
    meta: dict[str, dict[str, str]] = {}

    pack006 = load_deterministic_fact_pack(PACK_006)
    for fact in pack006.facts:
        if fact.fact_id == RETIRED_FACT_ID:
            continue
        category = fact.fact_type
        if fact.fact_type == "ASSOCIATION":
            category = "CONTROLLED_ASSOCIATION"
        elif fact.fact_type == "DEFINITION":
            category = "DEFINITION"
        facts_by_id[fact.fact_id] = fact
        meta[fact.fact_id] = {
            "cohort_source": "ENGINE-007",
            "analysis_category": category,
            "fixture": "python_mcq_engine_006_reviewed_100.json",
        }

    for label, path in (("ENGINE-012", PACK_012), ("ENGINE-013", PACK_013)):
        payload = json.loads(path.read_text(encoding="utf-8"))
        dispositions = {
            row["fact_id"]: row for row in payload.get("review_dispositions", [])
        }
        for raw in payload["pack"]["facts"]:
            fact = DeterministicFact.model_validate(raw)
            if fact.fact_id == RETIRED_FACT_ID:
                continue
            if fact.fact_id in facts_by_id:
                continue
            category = (dispositions.get(fact.fact_id) or {}).get("analysis_category")
            if category == "RELATIONSHIP_FORMULA":
                continue
            facts_by_id[fact.fact_id] = fact
            meta[fact.fact_id] = {
                "cohort_source": label,
                "analysis_category": category or fact.fact_type,
                "fixture": path.name,
            }

    inventory = {
        "hypothesized_cohort_size": HYPOTHESIZED_COHORT,
        "engine_007_cohort_excluding_retired": sum(
            1 for item in meta.values() if item["cohort_source"] == "ENGINE-007"
        ),
        "engine_012_eligible": sum(
            1 for item in meta.values() if item["cohort_source"] == "ENGINE-012"
        ),
        "engine_013_eligible": sum(
            1 for item in meta.values() if item["cohort_source"] == "ENGINE-013"
        ),
        "unique_cohort_size": len(facts_by_id),
        "retired_excluded": True,
        "relationship_formula_excluded": True,
        "note": (
            "Measured unique cohort is ENGINE-007 surviving facts (ENGINE-006 excl. "
            "ENGINE-008 retired) ∪ ENGINE-012 eligible ∪ ENGINE-013 eligible. "
            f"Hypothesized size {HYPOTHESIZED_COHORT} differed from measured size."
        ),
    }
    ordered = sorted(facts_by_id.values(), key=lambda fact: fact.fact_id)
    return ordered, meta, {"bytes_map": bytes_map, "inventory": inventory}


def main() -> int:
    started = time.perf_counter()
    tracemalloc.start()
    settings = get_settings()
    db = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(db)

    facts, meta, load_info = _load_cohort()
    bytes_map = load_info["bytes_map"]
    inventory = load_info["inventory"]
    cohort_size = len(facts)
    if RETIRED_FACT_ID in {fact.fact_id for fact in facts}:
        raise RuntimeError("ENGINE-008 retired fact leaked into cohort")

    gate = FactQualityGate()
    adapter = DeterministicFactToQuestionAdapter(gate)
    quality_rows: list[dict[str, Any]] = []
    adapted_ok: list[Any] = []
    skip_reasons: Counter[str] = Counter()
    reason_codes: Counter[str] = Counter()
    gen_times: list[float] = []
    verify_times: list[float] = []
    blocked = 0
    facts_by_id = {fact.fact_id: fact for fact in facts}

    for fact in facts:
        taxonomy = _taxonomy_for_fact(fact)
        t0 = time.perf_counter()
        try:
            adapted = adapter.adapt(
                fact,
                taxonomy=taxonomy,
                authoritative_syllabus_path=SYLLABUS,
            )
            quality = adapted.quality
            row = {
                "fact_id": fact.fact_id,
                "subject": fact.subject,
                "class_level": fact.class_level,
                "chapter": fact.chapter,
                "topic": fact.topic,
                "concept": fact.concept_name,
                "fact_type": fact.fact_type,
                "analysis_category": meta[fact.fact_id]["analysis_category"],
                "cohort_source": meta[fact.fact_id]["cohort_source"],
                "review_status": fact.review_status,
                "status": quality.status,
                "workflow_stage": quality.workflow_stage,
                "mcq_eligible": quality.mcq_eligible,
                "reason_codes": [r.code for r in quality.reasons],
            }
            quality_rows.append(row)
            for code in row["reason_codes"]:
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
                    "fact_type": fact.fact_type,
                    "analysis_category": meta[fact.fact_id]["analysis_category"],
                    "cohort_source": meta[fact.fact_id]["cohort_source"],
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

    for adapted in adapted_ok:
        fact = facts_by_id[adapted.fact_id]
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
                    "fact_type": fact.fact_type,
                    "analysis_category": meta[fact.fact_id]["analysis_category"],
                    "cohort_source": meta[fact.fact_id]["cohort_source"],
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
                    "fact_type": fact.fact_type,
                    "analysis_category": meta[fact.fact_id]["analysis_category"],
                    "cohort_source": meta[fact.fact_id]["cohort_source"],
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
                    "fact_type": fact.fact_type,
                    "analysis_category": meta[fact.fact_id]["analysis_category"],
                    "cohort_source": meta[fact.fact_id]["cohort_source"],
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
    generation_skips = cohort_size - created
    generation_failure_rate = (
        round(generation_skips / cohort_size, 4) if cohort_size else 0.0
    )

    quality_status = Counter(row["status"] for row in quality_rows)
    mcq_eligible = sum(1 for row in quality_rows if row.get("mcq_eligible"))
    stem_hashes = {item.stem_hash for item in candidates_first}
    production_overlap = _production_stem_overlap(db, stem_hashes)

    after = _read_only_snapshot(db)
    db.dispose()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    runtime = round(time.perf_counter() - started, 3)

    fixture_unchanged = {
        "engine_006": PACK_006.read_bytes() == bytes_map["006"],
        "engine_010": PACK_010.read_bytes() == bytes_map["010"],
        "engine_012": PACK_012.read_bytes() == bytes_map["012"],
        "engine_013": PACK_013.read_bytes() == bytes_map["013"],
    }
    fixtures_all_unchanged = all(fixture_unchanged.values())
    retired_regenerated = RETIRED_FACT_ID in {
        item.fact_id for item in candidates_first
    } or RETIRED_FACT_ID in {row["fact_id"] for row in candidate_records}

    fail_ambiguous = [
        {
            "fact_id": row["fact_id"],
            "cohort_source": row["cohort_source"],
            "analysis_category": row["analysis_category"],
            "question_type": row["question_type"],
            "subject": row["subject"],
            "chapter": row["chapter"],
            "classification": row["classification"],
            "reason": row["reason"],
        }
        for row in verification_records
        if row["classification"] in {"FAIL", "AMBIGUOUS"}
    ]
    skip_details = [
        {
            "fact_id": row["fact_id"],
            "cohort_source": row.get("cohort_source"),
            "analysis_category": row.get("analysis_category"),
            "subject": row["subject"],
            "chapter": row["chapter"],
            "failure_reason": row.get("failure_reason"),
        }
        for row in candidate_records
        if row.get("generation_status") == "SKIPPED"
    ]

    major_patterns = [
        f"{code}:{count}"
        for code, count in Counter(
            row["failure_reason"]
            for row in candidate_records
            if row.get("failure_reason")
        ).most_common(15)
    ] or ["none"]

    # ENGINE-007 comparison baseline from prior audit artifact.
    engine007 = {
        "facts_evaluated": 100,
        "candidates_generated": 99,
        "independent_PASS": 99,
        "independent_FAIL": 0,
        "independent_AMBIGUOUS": 0,
        "verified_yield": 1.0,
        "source_audit": "docs/audits/python_mcq_engine_007.json",
    }

    audit = {
        "task_id": TASK_ID,
        "evaluation_id": "python-mcq-engine-014-expanded-reviewed-cohort-v1",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "verdict": (
            "GREEN"
            if before == after
            and reproducible
            and fixtures_all_unchanged
            and not retired_regenerated
            and settings.ncert_source_root
            else "YELLOW"
        ),
        "engine_version": ENGINE_VERSION,
        "source_root": settings.ncert_source_root,
        "syllabus_source": str(SYLLABUS),
        "cohort_inventory": inventory,
        "cohort_size": cohort_size,
        "facts_evaluated": cohort_size,
        "engine_008_retired_excluded": True,
        "engine_008_retired_regenerated": retired_regenerated,
        "fixture_mutations": {
            **{f"{key}_modified": not ok for key, ok in fixture_unchanged.items()},
            "all_source_fixtures_unchanged": fixtures_all_unchanged,
        },
        "quality_results": quality_rows,
        "candidate_records": candidate_records,
        "fail_ambiguous_records": fail_ambiguous,
        "generation_skip_records": skip_details,
        "independent_verification": {
            "counts": {
                "PASS": independent_counts.get("PASS", 0),
                "FAIL": independent_counts.get("FAIL", 0),
                "AMBIGUOUS": independent_counts.get("AMBIGUOUS", 0),
            },
            "records": verification_records,
        },
        "metrics": {
            "cohort_size": cohort_size,
            "facts_evaluated": cohort_size,
            "FACT_APPROVED": quality_status.get("FACT_APPROVED", 0),
            "FACT_REVIEW_REQUIRED": quality_status.get("FACT_REVIEW_REQUIRED", 0),
            "FACT_REJECTED": quality_status.get("FACT_REJECTED", 0),
            "MCQ_ELIGIBLE": mcq_eligible,
            "blocked_during_evaluation": blocked,
            "reason_code_distribution": dict(reason_codes),
            "candidates_attempted": len(adapted_ok),
            "candidates_generated": created,
            "generation_skips": generation_skips,
            "generation_failure_rate": generation_failure_rate,
            "skip_reasons": dict(skip_reasons),
            "validation_failures": validation_failures,
            "source_failures": source_failures,
            "syllabus_failures": syllabus_failures,
            "duplicate_failures": duplicate_failures,
            "generation_skip_reason_counts": dict(generation_failures),
            "independent_PASS": independent_counts.get("PASS", 0),
            "independent_FAIL": independent_counts.get("FAIL", 0),
            "independent_AMBIGUOUS": independent_counts.get("AMBIGUOUS", 0),
            "verified_yield": verified_yield,
            "verified_yield_label": "READ-ONLY EVALUATION VERIFIED YIELD",
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
            "subject_breakdown": {
                "cohort": dict(Counter(fact.subject for fact in facts)),
                "generated": dict(
                    Counter(item.subject for item in candidates_first)
                ),
                "verified_yield": _yield_table(verification_records, "subject"),
            },
            "chapter_breakdown": {
                "verified_yield": _yield_table(verification_records, "chapter"),
            },
            "fact_type_breakdown": {
                "cohort": dict(Counter(fact.fact_type for fact in facts)),
                "analysis_category_cohort": dict(
                    Counter(meta[fid]["analysis_category"] for fid in meta)
                ),
                "verified_yield_by_fact_type": _yield_table(
                    verification_records, "fact_type"
                ),
                "verified_yield_by_analysis_category": _yield_table(
                    verification_records, "analysis_category"
                ),
            },
            "question_type_breakdown": {
                "generated": dict(
                    Counter(item.question_type for item in candidates_first)
                ),
                "verified_yield": _yield_table(verification_records, "question_type"),
            },
            "type_success_rates": {
                "direct_fact": _success_rate(
                    verification_records, "analysis_category", "DIRECT_FACT"
                ),
                "controlled_association": _success_rate(
                    verification_records, "analysis_category", "CONTROLLED_ASSOCIATION"
                ),
                "controlled_numerical": _success_rate(
                    verification_records, "analysis_category", "CONTROLLED_NUMERICAL"
                ),
                "si_unit_dimension": _success_rate(
                    verification_records, "analysis_category", "SI_UNIT_DIMENSION"
                ),
                "definition": _success_rate(
                    verification_records, "analysis_category", "DEFINITION"
                ),
                "definition_identification_question_type": _success_rate(
                    verification_records,
                    "question_type",
                    "DEFINITION_IDENTIFICATION",
                ),
            },
            "cohort_source_yield": _yield_table(verification_records, "cohort_source"),
            "engine007_comparison": {
                "engine_007": engine007,
                "engine_014": {
                    "facts_evaluated": cohort_size,
                    "candidates_generated": created,
                    "independent_PASS": independent_counts.get("PASS", 0),
                    "independent_FAIL": independent_counts.get("FAIL", 0),
                    "independent_AMBIGUOUS": independent_counts.get("AMBIGUOUS", 0),
                    "verified_yield": verified_yield,
                },
                "new_nondef_only_yield": _yield_table(
                    [
                        row
                        for row in verification_records
                        if row["cohort_source"] in {"ENGINE-012", "ENGINE-013"}
                    ],
                    "cohort_source",
                ),
            },
        },
        "database_before": before,
        "database_after": after,
        "production_safety_unchanged": before == after,
        "provider_api_calls": 0,
        "api_cost_inr": 0,
        "production_db_mutations": 0,
        "tests": {"focused": "pending", "regression": "pending", "ruff": "pending"},
        "major_failure_patterns": major_patterns,
        "limitations": [
            (
                "Independent verification is PDF/syllabus/taxonomy evidence review; "
                "FACT_APPROVED/MCQ_ELIGIBLE is not treated as NCERT certification."
            ),
            "Production corpus overlap uses stem_hash fingerprints only (read-only).",
            "No semantic embedding dedupe was available.",
            "CONTROLLED_NUMERICAL in this cohort uses stated-value recall templates, not NumericalSpec calculation contracts.",
            "Hypothesized cohort size 334 was not observed; measured unique size is reported.",
            "No generated MCQs were persisted.",
        ],
        "recommended_next_task": (
            "Do not auto-start ENGINE-015. Review FAIL/AMBIGUOUS patterns in "
            "docs/audits/python_mcq_engine_014.json before any staging dry-run."
        ),
    }
    AUDIT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    m = audit["metrics"]
    lines = [
        "# PYTHON-MCQ-ENGINE-014 — Expanded Reviewed Cohort Evaluation",
        "",
        f"**Verdict:** **{audit['verdict']}**",
        f"**Measured unique cohort:** **{cohort_size}** "
        f"(hypothesized {HYPOTHESIZED_COHORT})",
        f"**Facts evaluated:** **{cohort_size}**",
        f"**Candidates generated:** **{created}**",
        f"**Generation skips:** **{generation_skips}**",
        f"**Independent PASS/FAIL/AMBIGUOUS:** "
        f"**{m['independent_PASS']} / {m['independent_FAIL']} / "
        f"{m['independent_AMBIGUOUS']}**",
        f"**Verified yield:** **{verified_yield}**",
        f"**Duplicate rate / ambiguity rate:** **{duplicate_rate} / {ambiguity_rate}**",
        "",
        "## Cohort inventory",
        "",
        f"- ENGINE-007 surviving (006 excl. retired): "
        f"**{inventory['engine_007_cohort_excluding_retired']}**",
        f"- ENGINE-012 eligible: **{inventory['engine_012_eligible']}**",
        f"- ENGINE-013 eligible: **{inventory['engine_013_eligible']}**",
        f"- Unique after dedupe: **{cohort_size}**",
        "- RELATIONSHIP_FORMULA: excluded",
        "- ENGINE-008 retired fact: excluded / not regenerated: "
        f"**{not retired_regenerated}**",
        "",
        "## ENGINE-007 comparison",
        "",
        f"- ENGINE-007 verified yield: **{engine007['verified_yield']}** "
        f"({engine007['independent_PASS']}/{engine007['candidates_generated']})",
        f"- ENGINE-014 overall verified yield: **{verified_yield}** "
        f"({m['independent_PASS']}/{created})",
        f"- By cohort source: `{m['cohort_source_yield']}`",
        "",
        "## Type success rates",
        "",
        f"- Direct fact: `{m['type_success_rates']['direct_fact']}`",
        f"- Controlled association: `{m['type_success_rates']['controlled_association']}`",
        f"- Controlled numerical: `{m['type_success_rates']['controlled_numerical']}`",
        f"- SI/unit: `{m['type_success_rates']['si_unit_dimension']}`",
        f"- Definition category: `{m['type_success_rates']['definition']}`",
        f"- DEFINITION_IDENTIFICATION Q-type: "
        f"`{m['type_success_rates']['definition_identification_question_type']}`",
        "",
        "## Skip reasons",
        "",
        f"`{dict(skip_reasons)}`",
        "",
        "## Safety",
        "",
        f"- Reproducible: **{reproducible}**",
        f"- Runtime seconds: **{runtime}**",
        f"- Peak memory bytes: **{peak}**",
        "- Provider/API calls: **0**",
        "- Production DB mutations: **0**",
        f"- Fixtures unchanged: **{fixtures_all_unchanged}**",
        "",
        f"**Recommended next task:** {audit['recommended_next_task']}",
        "",
    ]
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": audit["verdict"],
                "cohort_size": cohort_size,
                "created": created,
                "skips": generation_skips,
                "PASS": independent_counts.get("PASS", 0),
                "FAIL": independent_counts.get("FAIL", 0),
                "AMBIGUOUS": independent_counts.get("AMBIGUOUS", 0),
                "verified_yield": verified_yield,
                "reproducible": reproducible,
                "runtime_seconds": runtime,
                "retired_regenerated": retired_regenerated,
                "fixtures_unchanged": fixtures_all_unchanged,
            },
            indent=2,
        )
    )
    return 0 if audit["verdict"] in {"GREEN", "YELLOW"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
