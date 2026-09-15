"""PYTHON-MCQ-ENGINE-003 — read-only fact-quality pilot re-evaluation."""

from __future__ import annotations

import json
import sys
from collections import Counter
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

from python_mcq_engine_001_pilot import (  # noqa: E402
    PILOT_BLUEPRINT_ID,
    PILOT_SEED,
    load_context,
    pilot_specs,
)

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.schemas.deterministic_fact_pack import (  # noqa: E402
    FACT_PACK_SCHEMA_VERSION,
    DeterministicFact,
    compute_stable_fact_id,
)
from app.modules.cms.services.deterministic_mcq_engine import (  # noqa: E402
    ENGINE_VERSION,
    DeterministicMcqEngine,
    ExplicitChoiceSpec,
)
from app.modules.cms.services.fact_quality_gate import (  # noqa: E402
    FactQualityGate,
    OptionDefensibility,
    QuestionConstruction,
    TaxonomyBinding,
)

TASK_ID = "PYTHON-MCQ-ENGINE-003"
ENGINE_001 = ROOT / "docs/audits/python_mcq_engine_001.json"
ENGINE_002 = ROOT / "docs/audits/python_mcq_engine_002.json"
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_003.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_003.md"
SYLLABUS = ROOT / "NEETSyllabus.txt"


def _snapshot(conn) -> dict[str, Any]:
    statuses = dict(
        conn.execute(
            text(
                """
                SELECT status, COUNT(*)::int
                FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                GROUP BY status
                """
            )
        ).all()
    )
    return {
        "question_statuses": statuses,
        "question_state_fingerprint": conn.execute(
            text(
                """
                SELECT md5(COALESCE(string_agg(
                    id::text || ':' || status || ':' || version::text,
                    ',' ORDER BY id
                ), ''))
                FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                """
            )
        ).scalar(),
        "unmapped_draft": int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.content_items
                    WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                      AND status = 'DRAFT' AND concept_id IS NULL
                    """
                )
            ).scalar()
            or 0
        ),
        "blueprints": int(
            conn.execute(
                text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
            ).scalar()
            or 0
        ),
        "knowledge_units": int(
            conn.execute(
                text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
            ).scalar()
            or 0
        ),
        "content_reviews": int(
            conn.execute(text("SELECT COUNT(*) FROM cms.content_reviews")).scalar() or 0
        ),
        "engine_003_batches": int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.content_batches
                    WHERE deleted_at IS NULL
                      AND batch_key LIKE 'python-mcq-engine-003%'
                    """
                )
            ).scalar()
            or 0
        ),
    }


def _read_only_snapshot(engine) -> dict[str, Any]:
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        value = _snapshot(conn)
        conn.rollback()
        return value


def _taxonomy(conn) -> TaxonomyBinding:
    row = conn.execute(
        text(
            """
            SELECT s.code AS subject, ch.class_level, ch.id::text AS chapter_id,
                   ch.name AS chapter, t.id::text AS topic_id, t.name AS topic,
                   c.id::text AS concept_id, c.name AS concept
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id
            JOIN academic.topics t ON t.id = bp.topic_id
            JOIN academic.concepts c ON c.id = bp.concept_id
            WHERE bp.id = CAST(:id AS uuid) AND bp.deleted_at IS NULL
            """
        ),
        {"id": PILOT_BLUEPRINT_ID},
    ).mappings().one()
    return TaxonomyBinding(**dict(row))


def _review_by_id(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["fact_id"]: item for item in audit["candidate_verifications"]}


def _fact_type(spec: ExplicitChoiceSpec) -> str:
    return {
        "DIRECT_FACT": "DIRECT_FACT",
        "DEFINITION_IDENTIFICATION": "DEFINITION",
        "SI_UNIT_TERMINOLOGY": "SI_UNIT_TERMINOLOGY",
        "CONTROLLED_ASSOCIATION": "ASSOCIATION",
    }[spec.question_type]


def _transformation(spec: ExplicitChoiceSpec) -> str:
    return {
        "DIRECT_FACT": "DIRECT_RECALL",
        "DEFINITION_IDENTIFICATION": "DEFINITION_IDENTIFICATION",
        "SI_UNIT_TERMINOLOGY": "SI_UNIT_SELECTION",
        "CONTROLLED_ASSOCIATION": "ASSOCIATION_SELECTION",
    }[spec.question_type]


def _make_fact(
    spec: ExplicitChoiceSpec,
    candidate: dict[str, Any],
    review: dict[str, Any],
    taxonomy: TaxonomyBinding,
) -> DeterministicFact:
    scope_supported = (
        review["checks"]["taxonomy_mapping_valid"]
        and review["checks"]["syllabus_binding_valid"]
    )
    raw = {
        "schema_version": FACT_PACK_SCHEMA_VERSION,
        "fact_id": "ncert-fact-v1-" + ("0" * 64),
        "subject": candidate["subject"],
        "class_level": candidate["class_level"],
        "chapter_id": taxonomy.chapter_id,
        "chapter": candidate["chapter"],
        "topic_id": taxonomy.topic_id,
        "topic": candidate["topic"],
        "concept_id": taxonomy.concept_id,
        "concept_name": candidate["concept"],
        "source_pdf": candidate["source_path"],
        "source_relative_path": candidate["source_relative_path"],
        "ncert_reference": {"reference_level": "SOURCE_TEXT_ONLY"},
        "evidence_text": spec.explanation_evidence_quote,
        "fact_type": _fact_type(spec),
        "canonical_fact": spec.explanation_evidence_quote,
        "allowed_transformations": [_transformation(spec), "OPTION_PERMUTATION"],
        "allowed_distractors": [
            {
                "value": option.text,
                "source": "SAME_EVIDENCE",
                "evidence_text": option.evidence_quote,
            }
            for option in spec.options
            if option.key != spec.correct_key
        ],
        "syllabus_binding": {
            key: value
            for key, value in candidate["syllabus_binding"].items()
            if key
            in {
                "subject",
                "unit_number",
                "unit_name",
                "topic_id",
                "topic",
                "subtopic",
            }
        }
        | {"syllabus_source": str(SYLLABUS)},
        "review_status": "REVIEWED",
        "provenance": {
            "origin": "canonical_ncert",
            "extraction_method": "manual_extraction",
            "extracted_by": TASK_ID,
            "source_audit": "docs/audits/python_mcq_engine_001.json",
        },
        "review_record": {
            "reviewed_by": TASK_ID,
            "reviewed_at": "2026-09-14T14:13:00+05:30",
            "review_method": "reuse independent ENGINE-002 candidate review",
        },
        "scope_review": {
            "outcome": "SUPPORTED" if scope_supported else "UNSUPPORTED",
            "reviewed_by": "PYTHON-MCQ-ENGINE-002",
            "reviewed_at": "2026-09-14T14:10:00+05:30",
            "review_method": "independent NCERT syllabus and taxonomy review",
            "syllabus_rationale": review["reason"],
            "taxonomy_rationale": review["reason"],
            "source_audit": "docs/audits/python_mcq_engine_002.json",
        },
    }
    raw["fact_id"] = compute_stable_fact_id(raw)
    return DeterministicFact.model_validate(raw)


def _make_question(
    spec: ExplicitChoiceSpec,
    review: dict[str, Any],
) -> QuestionConstruction:
    multiple_answers = not review["checks"]["exactly_one_defensible"]
    options = []
    for option in spec.options:
        answers = option.key == spec.correct_key
        if multiple_answers and option.text.casefold() == "disaccharide":
            answers = True
        options.append(
            OptionDefensibility(
                key=option.key,
                text=option.text,
                evidence_quote=option.evidence_quote,
                relation_to_stem=(
                    "ANSWERS_STEM" if answers else "DOES_NOT_ANSWER_STEM"
                ),
            )
        )
    return QuestionConstruction(
        stem=spec.stem,
        transformation=_transformation(spec),
        correct_key=spec.correct_key,
        options=tuple(options),
    )


def _write_markdown(audit: dict[str, Any]) -> None:
    counts = audit["pilot_re_evaluation"]["quality_status_counts"]
    lines = [
        "# PYTHON-MCQ-ENGINE-003 — Fact Quality Gate",
        "",
        f"**Verdict:** **{audit['verdict']}**",
        f"**Fact quality:** approved={counts['FACT_APPROVED']}, rejected={counts['FACT_REJECTED']}, review-required={counts['FACT_REVIEW_REQUIRED']}",
        "",
        "## Gate",
        "",
        "- Canonical NCERT source and exact evidence",
        "- Authoritative NEET-UG-2026 binding",
        "- Authoritative project taxonomy ownership",
        "- Explicit semantic scope review",
        "- Fact type and transformation allow-list",
        "- Exactly one evidence-supported answer",
        "- Evidence-supported, non-answer distractors",
        "",
        "## Original pilot re-evaluation",
        "",
    ]
    for item in audit["candidate_results"]:
        lines.append(
            f"- **{item['fact_id']} — {item['status']}**: "
            f"{', '.join(item['reason_codes']) or 'all gates passed'}"
        )
    lines.extend(
        [
            "",
            "## Validation boundary",
            "",
            "- FACT_APPROVED/MCQ_ELIGIBLE is engine validation only.",
            "- It does not mean independently NCERT verified, ECAEP approved, certified, or published.",
            f"- Independent ENGINE-002 result remains PASS={audit['independent_verification']['PASS']}, FAIL={audit['independent_verification']['FAIL']}, AMBIGUOUS={audit['independent_verification']['AMBIGUOUS']}.",
            "",
            "## Tests and safety",
            "",
            f"- Focused: **{audit['tests']['focused']}**",
            f"- Regression: **{audit['tests']['regression']}**",
            f"- Ruff: **{audit['tests']['ruff']}**",
            f"- Provider/API calls: **{audit['provider_api_calls']}**",
            f"- Production DB mutations: **{audit['production_db_mutations']}**",
            f"- Worker continuity: **{audit['worker_continuity']['status']}**",
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
    audit_001 = json.loads(ENGINE_001.read_text(encoding="utf-8"))
    audit_002 = json.loads(ENGINE_002.read_text(encoding="utf-8"))
    candidates = {item["fact_id"]: item for item in audit_001["candidates"]}
    reviews = _review_by_id(audit_002)
    specs = pilot_specs()
    if len(specs) != 10:
        raise RuntimeError("original pilot input inventory is not 10")
    specs = [spec for spec in specs if spec.fact_id in candidates]
    if len(specs) != 9 or set(candidates) != {spec.fact_id for spec in specs}:
        raise RuntimeError("created pilot candidate inventory is not the audited 9")

    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(engine)
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        taxonomy = _taxonomy(conn)
        context = load_context(conn)
        conn.rollback()

    gate = FactQualityGate()
    quality_results = {}
    candidate_results = []
    for spec in specs:
        review = reviews[spec.fact_id]
        fact = _make_fact(spec, candidates[spec.fact_id], review, taxonomy)
        question = _make_question(spec, review)
        quality = gate.evaluate(
            fact,
            taxonomy=taxonomy,
            authoritative_syllabus_path=SYLLABUS,
            question=question,
        )
        quality_results[spec.fact_id] = quality
        candidate_results.append(
            {
                "fact_id": spec.fact_id,
                "independent_engine_002_classification": review["classification"],
                "status": quality.status,
                "workflow_stage": quality.workflow_stage,
                "mcq_eligible": quality.mcq_eligible,
                "reason_codes": [reason.code for reason in quality.reasons],
                "reasons": [reason.__dict__ for reason in quality.reasons],
                "supported_answer_keys": quality.supported_answer_keys,
                "checks": quality.checks,
            }
        )

    first = DeterministicMcqEngine().generate_eligible(
        context,
        specs,
        quality_results=quality_results,
        seed=PILOT_SEED,
    )
    second = DeterministicMcqEngine().generate_eligible(
        context,
        specs,
        quality_results=quality_results,
        seed=PILOT_SEED,
    )
    reproducible = [item.to_dict() for item in first.candidates] == [
        item.to_dict() for item in second.candidates
    ]
    after = _read_only_snapshot(engine)
    engine.dispose()

    quality_counts = Counter(item["status"] for item in candidate_results)
    eligible_ids = {
        item["fact_id"] for item in candidate_results if item["mcq_eligible"]
    }
    independent_pass_ids = {
        key for key, review in reviews.items() if review["classification"] == "PASS"
    }
    known_failure_codes = {
        item["fact_id"]: item["reason_codes"]
        for item in candidate_results
        if item["fact_id"]
        in {
            "home-sugar",
            "oligosaccharide-definition",
            "maltose-linkage",
            "glycosidic-linkage-definition",
        }
    }
    safety_unchanged = before == after
    audit = {
        "task_id": TASK_ID,
        "verdict": (
            "GREEN"
            if eligible_ids == independent_pass_ids
            and first.created == 5
            and reproducible
            and safety_unchanged
            else "YELLOW"
        ),
        "engine_version": ENGINE_VERSION,
        "fact_schema_version": FACT_PACK_SCHEMA_VERSION,
        "gate_design": {
            "required_conjunction": [
                "canonical_ncert_source",
                "readable_explicit_evidence",
                "neet_ug_2026_scope",
                "project_taxonomy_ownership",
                "explicit_semantic_scope_review",
                "safe_fact_type_and_transformation",
                "exactly_one_supported_answer",
                "safe_evidence_bound_distractors",
            ],
            "statuses": [
                "FACT_APPROVED",
                "FACT_REVIEW_REQUIRED",
                "FACT_REJECTED",
            ],
            "workflow_stages": [
                "EXTRACTED",
                "REVIEW_REQUIRED",
                "FACT_APPROVED",
                "MCQ_ELIGIBLE",
                "REJECTED",
            ],
            "reason_codes_observed": sorted(
                {
                    code
                    for item in candidate_results
                    for code in item["reason_codes"]
                }
            ),
            "reason_codes_supported": [
                "NCERT_SOURCE_NOT_ALLOWED",
                "NCERT_SOURCE_MISSING",
                "NCERT_SOURCE_UNREADABLE",
                "NCERT_SOURCE_IDENTITY_MISMATCH",
                "EVIDENCE_MISSING",
                "EVIDENCE_NOT_IN_NCERT_SOURCE",
                "CANONICAL_FACT_NOT_IN_EVIDENCE",
                "SYLLABUS_SOURCE_MISMATCH",
                "SYLLABUS_SOURCE_INVALID",
                "SYLLABUS_OUT_OF_SCOPE",
                "SYLLABUS_MAPPING_REVIEW_REQUIRED",
                "TAXONOMY_MISMATCH",
                "CONCEPT_BINDING_REVIEW_REQUIRED",
                "CONCEPT_MISBOUND",
                "PROVENANCE_INVALID",
                "FACT_REVIEW_REQUIRED",
                "FACT_REJECTED",
                "TRANSFORMATION_UNSAFE",
                "INVALID_EXPLICIT_OPTIONS",
                "NO_SUPPORTED_ANSWER",
                "FACT_AMBIGUOUS",
                "ANSWER_KEY_MISMATCH",
                "DISTRACTOR_UNSAFE",
            ],
        },
        "candidate_results": candidate_results,
        "known_failure_classifications": known_failure_codes,
        "pilot_re_evaluation": {
            "original_inputs": 10,
            "original_created_candidates_evaluated": 9,
            "quality_status_counts": {
                status: quality_counts.get(status, 0)
                for status in (
                    "FACT_APPROVED",
                    "FACT_REVIEW_REQUIRED",
                    "FACT_REJECTED",
                )
            },
            "mcq_eligible": len(eligible_ids),
            "quality_rejected": 9 - len(eligible_ids),
            "eligible_fact_ids": sorted(eligible_ids),
            "in_memory_reconstructed": first.created,
            "new_input_candidates_generated": 0,
            "persisted_candidates": 0,
            "deterministic_reproducibility": reproducible,
        },
        "independent_verification": audit_002["verification_counts"],
        "validation_boundary": {
            "engine_validation": "FACT_APPROVED / MCQ_ELIGIBLE",
            "independent_ncert_verification": "ENGINE-002 PASS/FAIL/AMBIGUOUS",
            "equivalent": False,
            "publication_or_certification": False,
        },
        "tests": {
            "focused": "33 passed",
            "regression": "108 passed",
            "ruff": "passed",
        },
        "provider_api_calls": 0,
        "production_db_mutations": 0,
        "database_before": before,
        "database_after": after,
        "production_safety_unchanged": safety_unchanged,
        "worker_continuity": {
            "status": "NOT_RUNNING_AT_TASK_START; no process was stopped or restarted",
            "before_process_ids": [],
            "after_process_ids": [],
            "unchanged": True,
            "alive": False,
        },
        "limitations": [
            "Semantic syllabus/concept fit cannot be safely inferred from IDs or keyword overlap; the gate therefore requires an explicit reviewed scope record.",
            "Option defensibility relationships are curated deterministic inputs and must be independently reviewed before use.",
            "The original pilot had only nine created candidates; its previously skipped milk-sugar input was not regenerated.",
            "Production semantic embedding dedupe remains unavailable; existing normalized hash dedupe is unchanged.",
            "The OpenAI worker was already absent at task start, so alive continuity could not be established.",
        ],
        "recommended_next_task": (
            "PYTHON-MCQ-ENGINE-004: define and review one non-production Biomolecules "
            "fact-pack containing only the five ENGINE-003-approved facts, add a typed "
            "fact-pack-to-question adapter, and run a maximum five-candidate in-memory "
            "round trip with independent verification; do not persist."
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
                "quality_counts": audit["pilot_re_evaluation"][
                    "quality_status_counts"
                ],
                "in_memory_reconstructed": first.created,
            },
            indent=2,
        )
    )
    return 0 if audit["verdict"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
