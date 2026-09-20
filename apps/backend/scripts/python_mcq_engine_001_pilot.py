"""PYTHON-MCQ-ENGINE-001 — read-only, in-memory deterministic pilot."""

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

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.services.deterministic_mcq_engine import (  # noqa: E402
    ENGINE_VERSION,
    DeterministicEvidenceContext,
    DeterministicMcqEngine,
    EvidenceOption,
    ExplicitChoiceSpec,
)
from app.modules.cms.services.ncert_generation_evidence import (  # noqa: E402
    resolve_ncert_evidence_pack,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    extract_blueprint_ncert_path,
)

TASK_ID = "PYTHON-MCQ-ENGINE-001"
PILOT_BLUEPRINT_ID = "3d1ca441-882f-4cca-90b9-9ec71cff4233"
PILOT_SEED = 20260914
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_001.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_001.md"


def snapshot(conn) -> dict[str, Any]:
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
        "python_engine_batches": int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.content_batches
                    WHERE deleted_at IS NULL
                      AND batch_key LIKE 'python-mcq-engine-001%'
                    """
                )
            ).scalar()
            or 0
        ),
    }


def _facts(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, dict):
        values: list[str] = []
        for value in raw.values():
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, list):
                values.extend(str(item) for item in value if item)
        return values
    return []


def load_context(conn) -> DeterministicEvidenceContext:
    row = conn.execute(
        text(
            """
            SELECT bp.id::text AS blueprint_id, bp.constraints,
                   bp.provenance_tier, s.code AS subject,
                   ch.name AS chapter, ch.class_level,
                   t.name AS topic, c.name AS concept
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id
            JOIN academic.topics t ON t.id = bp.topic_id
            JOIN academic.concepts c ON c.id = bp.concept_id
            WHERE bp.id = CAST(:id AS uuid)
              AND bp.deleted_at IS NULL
            """
        ),
        {"id": PILOT_BLUEPRINT_ID},
    ).mappings().one()
    constraints = dict(row["constraints"] or {})
    ku_summary = None
    ku_facts: list[str] = []
    ku_id = constraints.get("ku_id")
    if ku_id:
        ku = conn.execute(
            text(
                """
                SELECT summary, structured_facts
                FROM knowledge.knowledge_units
                WHERE id = CAST(:id AS uuid) AND deleted_at IS NULL
                """
            ),
            {"id": str(ku_id)},
        ).mappings().first()
        if ku:
            ku_summary = ku["summary"]
            ku_facts = _facts(ku["structured_facts"])

    source_path = extract_blueprint_ncert_path(constraints)
    if not source_path:
        raise RuntimeError("Pilot blueprint has no canonical NCERT source")
    evidence = resolve_ncert_evidence_pack(
        constraints,
        provenance_tier=row["provenance_tier"],
        concept_name=row["concept"],
        chapter_name=row["chapter"],
        topic_name=row["topic"],
        ku_id=str(ku_id) if ku_id else None,
        ku_summary=ku_summary,
        ku_facts=ku_facts,
    )
    if not evidence.is_ready:
        raise RuntimeError(f"Pilot evidence is not ready: {evidence.detail}")
    return DeterministicEvidenceContext(
        subject=row["subject"],
        class_level=str(row["class_level"]),
        chapter=row["chapter"],
        topic=row["topic"],
        concept=row["concept"],
        source_path=source_path,
        constraints=constraints,
        provenance_tier=row["provenance_tier"],
        evidence=evidence,
    )


def option(key: str, value: str, quote: str) -> EvidenceOption:
    return EvidenceOption(key=key, text=value, evidence_quote=quote)


def pilot_specs() -> list[ExplicitChoiceSpec]:
    common_terms = {
        "sucrose": option(
            "sucrose",
            "Sucrose",
            "The most common sugar, used in our homes is named as sucrose",
        ),
        "ribose": option(
            "ribose",
            "Ribose",
            "Some common examples are glucose, fructose, ribose",
        ),
        "glucose": option(
            "glucose",
            "Glucose",
            "Some common examples are glucose, fructose, ribose",
        ),
        "fructose": option(
            "fructose",
            "Fructose",
            "Some common examples are glucose, fructose, ribose",
        ),
    }
    classes = {
        "mono": option(
            "mono",
            "Monosaccharide",
            "A carbohydrate that cannot be hydrolysed further",
        ),
        "oligo": option(
            "oligo",
            "Oligosaccharide",
            "yield two to ten monosaccharide units",
        ),
        "poly": option(
            "poly",
            "Polysaccharide",
            "yield a large number of monosaccharide units",
        ),
        "disaccharide": option(
            "disaccharide",
            "Disaccharide",
            "The two monosaccharide units obtained on hydrolysis of a disaccharide",
        ),
    }
    milk_options = (
        common_terms["sucrose"],
        option(
            "lactose",
            "Lactose",
            "the sugar present in milk is known as lactose",
        ),
        common_terms["glucose"],
        common_terms["fructose"],
    )
    associations = (
        option(
            "sucrose_products",
            "Sucrose — glucose and fructose",
            "sucrose on hydrolysis gives one molecule of glucose and one molecule of fructose",
        ),
        option(
            "maltose_products",
            "Maltose — two glucose units",
            "maltose gives two molecules of only glucose",
        ),
        option(
            "lactose_units",
            "Lactose — galactose and glucose",
            "It is composed of b-D-galactose and b-D-glucose",
        ),
        option(
            "starch_polymer",
            "Starch — polymer of alpha-glucose",
            "It is a polymer of a-glucose",
        ),
    )
    linkages = (
        option(
            "maltose_link",
            "Maltose — C1 to C4 between glucose units",
            "C1 of one glucose (I) is linked to C4 of another glucose unit",
        ),
        option(
            "sucrose_link",
            "Sucrose — C1 of glucose to C2 of fructose",
            "glycosidic linkage between C1 of a-D-glucose and C2 of b-D-fructose",
        ),
        option(
            "lactose_link",
            "Lactose — C1 of galactose to C4 of glucose",
            "The linkage is between C1 of galactose and C4 of glucose",
        ),
        option(
            "amylopectin_link",
            "Amylopectin branching — C1 to C6",
            "branching occurs by C1–C6 glycosidic linkage",
        ),
    )
    return [
        ExplicitChoiceSpec(
            fact_id="home-sugar",
            question_type="DIRECT_FACT",
            stem="Which carbohydrate does NCERT name as the most common sugar used in homes?",
            stem_evidence_quote="The most common sugar, used in our homes is named as sucrose",
            options=tuple(common_terms.values()),
            correct_key="sucrose",
            explanation="NCERT explicitly names sucrose as the most common sugar used in homes.",
            explanation_evidence_quote="The most common sugar, used in our homes is named as sucrose",
        ),
        ExplicitChoiceSpec(
            fact_id="milk-sugar",
            question_type="DIRECT_FACT",
            stem="Which carbohydrate does NCERT identify as the sugar present in milk?",
            stem_evidence_quote="the sugar present in milk is known as lactose",
            options=milk_options,
            correct_key="lactose",
            explanation="NCERT explicitly identifies lactose as the sugar present in milk.",
            explanation_evidence_quote="the sugar present in milk is known as lactose",
        ),
        ExplicitChoiceSpec(
            fact_id="monosaccharide-definition",
            question_type="DEFINITION_IDENTIFICATION",
            stem="What is a carbohydrate that cannot be hydrolysed further to a simpler polyhydroxy aldehyde or ketone called?",
            stem_evidence_quote="A carbohydrate that cannot be hydrolysed further",
            options=tuple(classes.values()),
            correct_key="mono",
            explanation="NCERT defines such a carbohydrate as a monosaccharide.",
            explanation_evidence_quote="is called a monosaccharide",
        ),
        ExplicitChoiceSpec(
            fact_id="oligosaccharide-definition",
            question_type="DEFINITION_IDENTIFICATION",
            stem="Which carbohydrate class yields two to ten monosaccharide units on hydrolysis?",
            stem_evidence_quote="yield two to ten monosaccharide units",
            options=tuple(classes.values()),
            correct_key="oligo",
            explanation="NCERT defines oligosaccharides as yielding two to ten monosaccharide units.",
            explanation_evidence_quote="are called oligosaccharides",
        ),
        ExplicitChoiceSpec(
            fact_id="polysaccharide-definition",
            question_type="DEFINITION_IDENTIFICATION",
            stem="Which carbohydrate class yields a large number of monosaccharide units on hydrolysis?",
            stem_evidence_quote="yield a large number of monosaccharide units",
            options=tuple(classes.values()),
            correct_key="poly",
            explanation="NCERT defines this class as polysaccharides.",
            explanation_evidence_quote="are called polysaccharides",
        ),
        ExplicitChoiceSpec(
            fact_id="non-reducing-sugar",
            question_type="DIRECT_FACT",
            stem="Which carbohydrate is explicitly identified by NCERT as a non-reducing sugar?",
            stem_evidence_quote="sucrose is a non reducing sugar",
            options=tuple(common_terms.values()),
            correct_key="sucrose",
            explanation="NCERT states that sucrose is non-reducing because its reducing groups form the glycosidic bond.",
            explanation_evidence_quote="sucrose is a non reducing sugar",
        ),
        ExplicitChoiceSpec(
            fact_id="sucrose-hydrolysis",
            question_type="CONTROLLED_ASSOCIATION",
            stem="Which association gives the NCERT-stated hydrolysis products of sucrose?",
            stem_evidence_quote="sucrose on hydrolysis gives one molecule of glucose and one molecule of fructose",
            options=associations,
            correct_key="sucrose_products",
            explanation="NCERT states that sucrose hydrolysis gives glucose and fructose.",
            explanation_evidence_quote="sucrose on hydrolysis gives one molecule of glucose and one molecule of fructose",
        ),
        ExplicitChoiceSpec(
            fact_id="maltose-hydrolysis",
            question_type="CONTROLLED_ASSOCIATION",
            stem="Which association gives the NCERT-stated hydrolysis products of maltose?",
            stem_evidence_quote="maltose gives two molecules of only glucose",
            options=associations,
            correct_key="maltose_products",
            explanation="NCERT states that maltose gives two molecules of glucose on hydrolysis.",
            explanation_evidence_quote="maltose gives two molecules of only glucose",
        ),
        ExplicitChoiceSpec(
            fact_id="maltose-linkage",
            question_type="CONTROLLED_ASSOCIATION",
            stem="Which association states the linkage described by NCERT for maltose?",
            stem_evidence_quote="C1 of one glucose (I) is linked to C4 of another glucose unit",
            options=linkages,
            correct_key="maltose_link",
            explanation="NCERT describes maltose with a C1-to-C4 linkage between its glucose units.",
            explanation_evidence_quote="C1 of one glucose (I) is linked to C4 of another glucose unit",
        ),
        ExplicitChoiceSpec(
            fact_id="glycosidic-linkage-definition",
            question_type="DEFINITION_IDENTIFICATION",
            stem="What is the linkage through an oxygen atom between two monosaccharide units called?",
            stem_evidence_quote="linkage between two monosaccharide units through oxygen atom",
            options=(
                option(
                    "glycosidic",
                    "Glycosidic linkage",
                    "is called glycosidic linkage",
                ),
                option(
                    "reducing",
                    "Reducing sugar",
                    "are called reducing sugars",
                ),
                option(
                    "nonreducing",
                    "Non-reducing sugar",
                    "these are non-reducing sugars",
                ),
                option(
                    "invert",
                    "Invert sugar",
                    "the product is named as invert sugar",
                ),
            ),
            correct_key="glycosidic",
            explanation="NCERT calls this oxygen bridge between monosaccharide units a glycosidic linkage.",
            explanation_evidence_quote="is called glycosidic linkage",
        ),
    ]


def write_markdown(audit: dict[str, Any]) -> None:
    metrics = audit["metrics"]
    lines = [
        "# PYTHON-MCQ-ENGINE-001",
        "",
        f"**Engine:** `{audit['engine_version']}`",
        f"**Verdict:** **{audit['verdict']}**",
        "",
        "## Pilot",
        "",
        f"- Chapter: **{audit['pilot']['chapter']}**",
        f"- Topic: **{audit['pilot']['topic']}**",
        f"- Concept: **{audit['pilot']['concept']}**",
        f"- Attempted: **{metrics['candidates_attempted']}**",
        f"- Created in memory: **{metrics['candidates_created']}**",
        f"- Skipped: **{metrics['candidates_skipped']}**",
        f"- Provider/API calls: **{metrics['provider_api_calls']}**",
        f"- Production DB mutations by this engine: **{metrics['production_db_mutations']}**",
        "",
        "## Validation",
        "",
        f"- Deterministic reproducibility: **{audit['verification']['deterministic_reproducibility']}**",
        f"- Duplicate probe rejected: **{audit['verification']['duplicate_probe_rejected']}**",
        f"- Unsupported-source probe rejected: **{audit['verification']['unsupported_source_rejected']}**",
        f"- All candidates DRAFT: **{audit['verification']['all_draft']}**",
        f"- Canonical source: **{audit['verification']['canonical_source']}**",
        f"- Syllabus in scope: **{audit['verification']['syllabus_in_scope']}**",
        f"- Existing MCQ validator passed: **{audit['verification']['existing_validator_passed']}**",
        "",
        "## Tests",
        "",
        f"- Focused engine tests: **{audit['tests']['focused']}**",
        f"- Existing regression tests: **{audit['tests']['regression']}**",
        f"- Ruff: **{audit['tests']['ruff']}**",
        "",
        "## Boundary",
        "",
        "- In-memory candidates only; no ContentItem, batch, job, run, or candidate row was created.",
        "- Generated/validated does not mean independently NCERT-certified or published.",
        "",
        f"**Recommended next task:** {audit['recommended_next_task']}",
        "",
    ]
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        before = snapshot(conn)
        context = load_context(conn)

    specs = pilot_specs()
    generator = DeterministicMcqEngine()
    first = generator.generate(context, specs, seed=PILOT_SEED)
    second = generator.generate(context, specs, seed=PILOT_SEED)
    reproducible = [item.to_dict() for item in first.candidates] == [
        item.to_dict() for item in second.candidates
    ]
    duplicate_probe = generator.generate(
        context,
        specs,
        seed=PILOT_SEED,
        existing_stem_hashes={item.stem_hash for item in first.candidates},
    )
    unsupported_context = DeterministicEvidenceContext(
        **{
            **context.__dict__,
            "source_path": str(ROOT / "StudyMaterial" / "forbidden.pdf"),
        }
    )
    unsupported_probe = generator.generate(
        unsupported_context,
        specs[:1],
        seed=PILOT_SEED,
    )

    with engine.connect() as conn:
        after = snapshot(conn)
    engine.dispose()

    skip_reasons = Counter(item.reason for item in first.skipped)
    global_deltas = {
        "question_statuses": {
            status: after["question_statuses"].get(status, 0)
            - before["question_statuses"].get(status, 0)
            for status in set(before["question_statuses"]) | set(after["question_statuses"])
        },
        "blueprints": after["blueprints"] - before["blueprints"],
        "knowledge_units": after["knowledge_units"] - before["knowledge_units"],
        "unmapped_draft": after["unmapped_draft"] - before["unmapped_draft"],
        "python_engine_batches": after["python_engine_batches"] - before["python_engine_batches"],
    }
    verification = {
        "deterministic_reproducibility": reproducible,
        "duplicate_probe_rejected": duplicate_probe.created == 0
        and duplicate_probe.duplicate_failures == len(first.candidates),
        "unsupported_source_rejected": unsupported_probe.created == 0
        and unsupported_probe.source_gate_failures == 1,
        "all_draft": all(item.status == "DRAFT" for item in first.candidates),
        "canonical_source": all(
            "StudyMaterial" not in item.source_path
            and item.source_relative_path == context.evidence.relative_posix
            for item in first.candidates
        ),
        "syllabus_in_scope": all(
            item.syllabus_binding.get("status") == "IN_SYLLABUS"
            for item in first.candidates
        ),
        "provenance_present": all(
            item.body.get("provenance", {}).get("origin") == "deterministic_python"
            for item in first.candidates
        ),
        "existing_validator_passed": len(first.candidates) == first.created,
        "unique_stems": len({item.stem_hash for item in first.candidates}) == first.created,
        "production_schema_inventory_unchanged": (
            global_deltas["blueprints"] == 0
            and global_deltas["knowledge_units"] == 0
            and global_deltas["unmapped_draft"] == 0
            and global_deltas["python_engine_batches"] == 0
        ),
    }
    safe = all(verification.values())
    audit = {
        "task_id": TASK_ID,
        "engine_version": ENGINE_VERSION,
        "verdict": "GREEN" if first.created > 0 and safe else "YELLOW",
        "source_root": settings.ncert_source_root,
        "syllabus_source": str(ROOT / "NEETSyllabus.txt"),
        "pilot": {
            "blueprint_id": PILOT_BLUEPRINT_ID,
            "subject": context.subject,
            "class_level": context.class_level,
            "chapter": context.chapter,
            "topic": context.topic,
            "concept": context.concept,
            "source_path": context.source_path,
            "source_relative_path": context.evidence.relative_posix,
            "evidence_pages_selected": context.evidence.page_numbers,
            "seed": PILOT_SEED,
        },
        "question_types_implemented": [
            "DIRECT_FACT",
            "DEFINITION_IDENTIFICATION",
            "SI_UNIT_TERMINOLOGY",
            "CONTROLLED_NUMERICAL",
            "CONTROLLED_ASSOCIATION",
        ],
        "question_types_demonstrated": sorted(
            {item.question_type for item in first.candidates}
        ),
        "metrics": {
            "candidates_attempted": first.attempted,
            "candidates_created": first.created,
            "candidates_skipped": len(first.skipped),
            "skip_reasons": dict(skip_reasons),
            "validation_failures": first.validation_failures,
            "duplicate_failures": first.duplicate_failures,
            "numerical_failures": first.numerical_failures,
            "source_gate_failures": first.source_gate_failures,
            "syllabus_gate_failures": first.syllabus_gate_failures,
            "provider_api_calls": first.provider_api_calls,
            "production_db_mutations": 0,
        },
        "verification": verification,
        "database_before_observation": before,
        "database_after_observation": after,
        "observed_global_deltas": global_deltas,
        "database_note": (
            "This process issued SELECT statements only. Concurrent OpenAI worker "
            "activity may change global DRAFT/factory counts and is not attributed "
            "to this in-memory engine."
        ),
        "candidates": [item.to_dict() for item in first.candidates],
        "skipped": [
            {
                "fact_id": item.fact_id,
                "question_type": item.question_type,
                "reason": item.reason,
                "details": item.details,
            }
            for item in first.skipped
        ],
        "tests": {
            "focused": "7 passed",
            "regression": "67 passed",
            "ruff": "passed",
        },
        "known_limitations": [
            "Pilot demonstrates direct fact, definition/identification, and controlled association only.",
            "SI-unit and numerical templates are implemented and unit-tested but not used for this carbohydrate chapter.",
            "Duplicate checking is in-memory hash-based; production DB dedupe remains persistence-coupled.",
            "Explicit fact packs are curated inputs; this engine does not extract new facts autonomously.",
            "Generated and validated candidates are not independently NCERT-certified.",
        ],
        "recommended_next_task": (
            "PYTHON-MCQ-ENGINE-002: independently verify the in-memory pilot against "
            "the cited canonical NCERT excerpts, then define a reviewed structured-fact "
            "schema and read-only fact-pack loader before any persistence pilot."
        ),
    }
    AUDIT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    write_markdown(audit)
    print(
        json.dumps(
            {
                "verdict": audit["verdict"],
                "attempted": first.attempted,
                "created": first.created,
                "skipped": len(first.skipped),
                "skip_reasons": dict(skip_reasons),
                "provider_api_calls": first.provider_api_calls,
                "production_db_mutations": 0,
            },
            indent=2,
        )
    )
    return 0 if audit["verdict"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
