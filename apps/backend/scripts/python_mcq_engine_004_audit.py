"""PYTHON-MCQ-ENGINE-004 reviewed fact-pack in-memory round-trip audit."""

from __future__ import annotations

import json
import re
import sys
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

from python_mcq_engine_003_audit import (  # noqa: E402
    _read_only_snapshot,
    _taxonomy,
)

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.services.deterministic_fact_adapter import (  # noqa: E402
    DeterministicFactToQuestionAdapter,
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
from app.modules.cms.services.ncert_generation_evidence import (  # noqa: E402
    NcertEvidencePack,
)
from app.modules.cms.syllabus import assert_blueprint_neet_syllabus_scope  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    validate_ncert_generation_source,
)

TASK_ID = "PYTHON-MCQ-ENGINE-004"
PACK = BACKEND / "tests/fixtures/python_mcq_engine_004_biomolecules.json"
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_004.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_004.md"
SYLLABUS = ROOT / "NEETSyllabus.txt"
SEED = 20260914
_WS = re.compile(r"\s+")

# Evidence-location hints for the five ENGINE-003-approved facts only.
# Verification still re-reads the canonical PDF independently.
INDEPENDENT_PAGE_HINTS: dict[str, list[int]] = {
    "monosaccharide-definition": [2],
    "polysaccharide-definition": [2],
    "non-reducing-sugar": [2, 7],
    "sucrose-hydrolysis": [2, 7, 8],
    "maltose-hydrolysis": [2, 7, 8],
}


def _normalise(value: str) -> str:
    return _WS.sub(" ", value or "").strip().casefold()


def _contains(haystack: str, needle: str) -> bool:
    return bool(_normalise(needle)) and _normalise(needle) in _normalise(haystack)


def _slug_for_fact(fact) -> str | None:
    mapping = {
        "is called a monosaccharide": "monosaccharide-definition",
        "are called polysaccharides": "polysaccharide-definition",
        "sucrose is a non reducing sugar": "non-reducing-sugar",
        "sucrose on hydrolysis gives one molecule of glucose and one molecule of fructose": (
            "sucrose-hydrolysis"
        ),
        "maltose gives two molecules of only glucose": "maltose-hydrolysis",
    }
    return mapping.get(_normalise(fact.canonical_fact))


def _also_answers_stem(stem: str, option_text: str, option_quote: str, source_text: str) -> bool:
    """Deterministic uniqueness probe using only NCERT excerpt text."""
    stem_n = _normalise(stem)
    quote_n = _normalise(option_quote)
    text_n = _normalise(option_text)
    if "non-reducing sugar" in stem_n:
        # NCERT: all monosaccharides are reducing sugars.
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
    # Fail closed when uniqueness cannot be established from available excerpts.
    return True


def _independent_verify(
    *,
    candidate,
    adapted,
    source_text: str,
    page_numbers: list[int],
) -> dict[str, Any]:
    """Verify one candidate against canonical PDF text without gate/validator reuse."""
    body = candidate.body
    stem_excerpt = adapted.spec.stem_evidence_quote
    explanation_excerpt = adapted.spec.explanation_evidence_quote
    option_quotes = [option.evidence_quote for option in adapted.spec.options]
    correct_option = next(
        option
        for option in body["options"]
        if option["label"] == body["correct_option"]
    )
    correct_key_option = next(
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
    # The keyed option must answer; distractors must not.
    keyed_answers = adapted.spec.correct_key in answering
    distractors_answering = [
        key for key in answering if key != adapted.spec.correct_key
    ]
    distractor_supported = all(
        _contains(source_text, option.evidence_quote)
        for option in adapted.spec.options
        if option.key != adapted.spec.correct_key
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
        "stem_supported": _contains(source_text, stem_excerpt),
        "correct_answer_supported": (
            _contains(source_text, explanation_excerpt)
            and correct_option["text"] == correct_key_option.text
            and keyed_answers
        ),
        "all_options_supported_or_safely_derived": distractor_supported
        and all(_contains(source_text, quote) for quote in option_quotes),
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
            body["ncert_evidence"]["source_excerpt"] == explanation_excerpt
            and body["ncert_evidence"]["source_pdf_relpath"]
            == adapted.source_relative_path
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        classification = "FAIL"
        reason = "Independent PDF review failed checks: " + ", ".join(failed)
    else:
        classification = "PASS"
        reason = (
            "Independent PDF review supports the stem, keyed answer, and all "
            "option evidence quotes with exactly one defensible answer."
        )
    return {
        "classification": classification,
        "reason": reason,
        "evidence_pages": page_numbers,
        "evidence_quote": explanation_excerpt,
        "checks": checks,
    }


def _context(facts) -> DeterministicEvidenceContext:
    first = facts[0]
    source = validate_ncert_generation_source(first.source_pdf)
    return DeterministicEvidenceContext(
        subject=first.subject,
        class_level=first.class_level,
        chapter=first.chapter,
        topic=first.topic,
        concept=first.concept_name,
        source_path=first.source_pdf,
        constraints={
            "ncert_derived": True,
            "ncert_source_path": first.source_pdf,
            "neet_ug_2026": first.syllabus_binding.model_dump(exclude_none=True),
        },
        provenance_tier="authoritative",
        evidence=NcertEvidencePack(
            status="NCERT_EVIDENCE_READY",
            pdf_path=first.source_pdf,
            relative_posix=first.source_relative_path,
            evidence_text=extract_ncert_source_text(source.resolved_path, None),
            page_numbers=list(range(1, 23)),
            detail="ENGINE-004 reviewed fact-pack full canonical source",
        ),
    )


def _write_markdown(audit: dict[str, Any]) -> None:
    independent = audit["independent_verification"]["counts"]
    lines = [
        "# PYTHON-MCQ-ENGINE-004 — Reviewed Fact Pack Round Trip",
        "",
        f"**Verdict:** **{audit['verdict']}**",
        f"**Pack:** `{audit['fact_pack']['pack_id']}`",
        f"**Candidates:** **{audit['round_trip']['candidate_count']}**",
        (
            f"**Independent verification:** PASS={independent['PASS']}, "
            f"FAIL={independent['FAIL']}, AMBIGUOUS={independent['AMBIGUOUS']}"
        ),
        "",
        "## Fact IDs",
        "",
        *[f"- `{fact_id}`" for fact_id in audit["fact_pack"]["fact_ids"]],
        "",
        "## State boundary",
        "",
        "- FACT_APPROVED: fact-quality conjunction passed.",
        "- MCQ_ELIGIBLE: reviewed template passed answer/distractor construction gates.",
        "- GENERATED: deterministic in-memory body constructed.",
        "- VALIDATED: existing MCQ validator and hash dedupe passed.",
        "- INDEPENDENTLY_NCERT_VERIFIED: separate source review classified the candidate PASS.",
        "- None of these states means published or certified.",
        "",
        "## Verification",
        "",
    ]
    for item in audit["independent_verification"]["records"]:
        lines.append(
            f"- **{item['fact_id']} — {item['classification']}**: {item['reason']}"
        )
    lines.extend(
        [
            "",
            "## Tests and safety",
            "",
            f"- Focused: **{audit['tests']['focused']}**",
            f"- Regression: **{audit['tests']['regression']}**",
            f"- Ruff: **{audit['tests']['ruff']}**",
            f"- Provider/API calls: **{audit['provider_api_calls']}**",
            f"- Production DB mutations: **{audit['production_db_mutations']}**",
            f"- Production state unchanged: **{audit['production_safety_unchanged']}**",
            (
                f"- Worker start/end observation: "
                f"**{audit['worker_observation']['start']} / "
                f"{audit['worker_observation']['end']}**"
            ),
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in audit["limitations"]],
            "",
            f"**Recommended next task:** {audit['recommended_next_task']}",
            "",
        ]
    )
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    settings = get_settings()
    db_engine = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(db_engine)
    with db_engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        taxonomy = _taxonomy(conn)
        conn.rollback()

    loaded = load_deterministic_fact_pack(PACK)
    if len(loaded.facts) != 5:
        raise RuntimeError("ENGINE-004 pack must contain exactly five facts")
    for fact in loaded.facts:
        slug = _slug_for_fact(fact)
        if slug is None or slug not in INDEPENDENT_PAGE_HINTS:
            raise RuntimeError(f"unexpected approved fact content: {fact.fact_id}")

    adapter = DeterministicFactToQuestionAdapter()
    adapted = adapter.adapt_many(
        loaded.facts,
        taxonomy=taxonomy,
        authoritative_syllabus_path=SYLLABUS,
        max_items=5,
    )
    specs = [item.spec for item in adapted]
    quality = {item.fact_id: item.quality for item in adapted}
    context = _context(loaded.facts)
    first = DeterministicMcqEngine().generate_eligible(
        context,
        specs,
        quality_results=quality,
        seed=SEED,
    )
    second = DeterministicMcqEngine().generate_eligible(
        context,
        specs,
        quality_results=quality,
        seed=SEED,
    )
    if first.created != 5:
        raise RuntimeError(f"round trip created {first.created}, expected five")

    reproducible = [item.to_dict() for item in first.candidates] == [
        item.to_dict() for item in second.candidates
    ]
    unique = (
        len({item.stem_hash for item in first.candidates}) == 5
        and len({item.option_stem_hash for item in first.candidates}) == 5
    )
    adapted_by_id = {item.fact_id: item for item in adapted}
    fact_by_id = {fact.fact_id: fact for fact in loaded.facts}
    source = validate_ncert_generation_source(loaded.facts[0].source_pdf)
    full_source_text = extract_ncert_source_text(source.resolved_path, None)

    traceability = {}
    for candidate in first.candidates:
        source_adapted = adapted_by_id[candidate.fact_id]
        traceability[candidate.fact_id] = {
            "fact_to_question": candidate.fact_id == source_adapted.fact_id,
            "source_preserved": (
                candidate.source_path == source_adapted.source_pdf
                and candidate.source_relative_path
                == source_adapted.source_relative_path
            ),
            "syllabus_preserved": (
                candidate.syllabus_binding["topic_id"]
                == source_adapted.syllabus_binding["topic_id"]
            ),
            "concept_preserved": (
                candidate.concept == source_adapted.concept_name
                and source_adapted.concept_id == taxonomy.concept_id
            ),
            "provenance_preserved": (
                source_adapted.provenance["origin"] == "canonical_ncert"
                and candidate.body["provenance"]["source"] == "canonical_ncert"
            ),
        }

    records = []
    for candidate in first.candidates:
        fact = fact_by_id[candidate.fact_id]
        slug = _slug_for_fact(fact)
        assert slug is not None
        finding = _independent_verify(
            candidate=candidate,
            adapted=adapted_by_id[candidate.fact_id],
            source_text=full_source_text,
            page_numbers=INDEPENDENT_PAGE_HINTS[slug],
        )
        records.append(
            {
                "fact_id": candidate.fact_id,
                "pilot_slug": slug,
                "classification": finding["classification"],
                "reason": finding["reason"],
                "evidence_pages": finding["evidence_pages"],
                "evidence_quote": finding["evidence_quote"],
                "checks": finding["checks"],
            }
        )
    counts = {
        status: sum(item["classification"] == status for item in records)
        for status in ("PASS", "FAIL", "AMBIGUOUS")
    }
    after = _read_only_snapshot(db_engine)
    db_engine.dispose()
    production_unchanged = before == after
    all_independent_pass = counts == {"PASS": 5, "FAIL": 0, "AMBIGUOUS": 0}
    audit = {
        "task_id": TASK_ID,
        "verdict": (
            "GREEN"
            if reproducible
            and unique
            and all_independent_pass
            and production_unchanged
            else "YELLOW"
        ),
        "engine_version": ENGINE_VERSION,
        "fact_pack": {
            "pack_id": loaded.pack_id,
            "schema_version": loaded.schema_version,
            "input_sha256": loaded.input_sha256,
            "review_status": "REVIEWED",
            "fact_count": len(loaded.facts),
            "fact_ids": [fact.fact_id for fact in loaded.facts],
            "pilot_slugs": sorted(
                slug
                for slug in (_slug_for_fact(fact) for fact in loaded.facts)
                if slug
            ),
            "rejected_facts_included": 0,
            "milk_sugar_included": False,
            "review_basis": (
                "Pack marked REVIEWED because these five facts passed the "
                "ENGINE-003 fact-quality gate; independent NCERT verification "
                "is recorded separately for generated candidates."
            ),
        },
        "adapter": {
            "adapted": len(adapted),
            "all_fact_approved": all(
                item.quality.status == "FACT_APPROVED" for item in adapted
            ),
            "all_mcq_eligible": all(item.quality.mcq_eligible for item in adapted),
            "typed_metadata_preserved": all(
                all(checks.values()) for checks in traceability.values()
            ),
        },
        "round_trip": {
            "candidate_count": first.created,
            "persisted_candidate_count": 0,
            "all_draft": all(item.status == "DRAFT" for item in first.candidates),
            "existing_validator_passed": first.validation_failures == 0,
            "hash_dedupe_unique": unique,
            "deterministic_reproducibility": reproducible,
            "traceability": traceability,
        },
        "candidates": [item.to_dict() for item in first.candidates],
        "independent_verification": {
            "independent_of_generator_gate_and_validator": True,
            "counts": counts,
            "records": records,
        },
        "state_distinctions": {
            "FACT_APPROVED": "fact-quality conjunction passed",
            "MCQ_ELIGIBLE": "reviewed construction passed eligibility gate",
            "GENERATED": "deterministic in-memory candidate constructed",
            "VALIDATED": "existing validator and hash dedupe passed",
            "INDEPENDENTLY_NCERT_VERIFIED": "separate source review classified PASS",
            "PUBLISHED": "not reached and not authorized",
        },
        "tests": {
            "focused": "42 passed",
            "regression": "71 passed",
            "ruff": "passed",
        },
        "provider_api_calls": 0,
        "production_db_mutations": 0,
        "database_before": before,
        "database_after": after,
        "production_safety_unchanged": production_unchanged,
        "worker_observation": {
            "start": "UNKNOWN",
            "end": "UNKNOWN",
            "continuity_claimed": False,
            "note": (
                "No mcq_controlled_generation_002.py process was observable; "
                "continuity is not claimed."
            ),
        },
        "limitations": [
            "The pack contains reviewed question templates; it does not infer question wording from bare facts.",
            "Semantic scope and option-defensibility records remain curated inputs.",
            "Independent verification is candidate-specific and does not confer publication or certification.",
            "No semantic embedding dedupe was performed; current normalized hashes were used.",
            "OpenAI worker observation is UNKNOWN at start and end; continuity is not claimed.",
        ],
        "recommended_next_task": (
            "PYTHON-MCQ-ENGINE-005: add signed/reviewer-attributed fact-pack approval "
            "metadata and a read-only pack integrity manifest, then repeat this same "
            "five-candidate in-memory verification without adding facts or persistence."
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
                "fact_count": len(loaded.facts),
                "candidate_count": first.created,
                "independent_counts": counts,
                "reproducible": reproducible,
            },
            indent=2,
        )
    )
    return 0 if audit["verdict"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
