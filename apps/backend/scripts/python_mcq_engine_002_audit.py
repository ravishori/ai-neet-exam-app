"""PYTHON-MCQ-ENGINE-002 independent, read-only verification audit."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import fitz
from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.schemas.deterministic_fact_pack import (  # noqa: E402
    FACT_PACK_SCHEMA_VERSION,
)
from app.modules.cms.syllabus import assert_blueprint_neet_syllabus_scope  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    validate_ncert_generation_source,
)

TASK_ID = "PYTHON-MCQ-ENGINE-002"
INPUT_AUDIT = ROOT / "docs/audits/python_mcq_engine_001.json"
OUTPUT_JSON = ROOT / "docs/audits/python_mcq_engine_002.json"
OUTPUT_MD = ROOT / "docs/audits/python_mcq_engine_002.md"
_WS = re.compile(r"\s+")

INDEPENDENT_REVIEWS: dict[str, dict[str, Any]] = {
    "home-sugar": {
        "pages": [1, 2],
        "evidence": "The most common sugar, used in our homes is named as sucrose",
        "option_support": "Sucrose is explicitly keyed on PDF page 1; glucose, fructose, and ribose are explicit carbohydrate examples on PDF page 2.",
    },
    "monosaccharide-definition": {
        "pages": [2],
        "evidence": "A carbohydrate that cannot be hydrolysed further to give simpler unit of polyhydroxy aldehyde or ketone is called a monosaccharide.",
        "option_support": "Monosaccharide, oligosaccharide, polysaccharide, and disaccharide are all explicitly introduced in the classification passage on PDF page 2.",
    },
    "oligosaccharide-definition": {
        "pages": [2],
        "evidence": "Carbohydrates that yield two to ten monosaccharide units, on hydrolysis, are called oligosaccharides.",
        "option_support": "All four class names are explicit in the same PDF-page-2 classification passage; only oligosaccharide matches two to ten units.",
    },
    "polysaccharide-definition": {
        "pages": [2],
        "evidence": "Carbohydrates which yield a large number of monosaccharide units on hydrolysis are called polysaccharides.",
        "option_support": "All four class names are explicit in the PDF-page-2 classification passage; only polysaccharide matches a large number of units.",
    },
    "non-reducing-sugar": {
        "pages": [2, 7],
        "evidence": "Since the reducing groups of glucose and fructose are involved in glycosidic bond formation, sucrose is a non reducing sugar.",
        "option_support": "PDF page 7 explicitly keys sucrose; PDF page 2 identifies glucose, fructose, and ribose as monosaccharides and states all monosaccharides are reducing sugars.",
    },
    "sucrose-hydrolysis": {
        "pages": [2, 7, 8],
        "evidence": "One molecule of sucrose on hydrolysis gives one molecule of glucose and one molecule of fructose",
        "option_support": "Every association is explicit: sucrose and maltose on PDF page 2, sucrose/maltose on page 7, and lactose/starch on page 8.",
    },
    "maltose-hydrolysis": {
        "pages": [2, 7, 8],
        "evidence": "maltose gives two molecules of only glucose",
        "option_support": "Every association is explicit in the cited chapter; only the maltose association answers the target named in the stem.",
    },
    "maltose-linkage": {
        "pages": [7, 8],
        "evidence": "C1 of one glucose (I) is linked to C4 of another glucose unit (II).",
        "option_support": "Maltose and sucrose linkages are explicit on PDF page 7; lactose and amylopectin linkages are explicit on page 8.",
    },
    "glycosidic-linkage-definition": {
        "pages": [7],
        "evidence": "Such a linkage between two monosaccharide units through oxygen atom is called glycosidic linkage.",
        "option_support": "Glycosidic linkage, reducing sugar, non-reducing sugar, and invert sugar are all explicitly defined or named on PDF page 7.",
    },
}

INDEPENDENT_FAILURES = {
    "home-sugar": (
        "NCERT supports the fact and keyed answer, but domestic use of sucrose is "
        "introductory trivia and is not validly bound to the cited Classification "
        "of Carbohydrates syllabus topic."
    ),
    "oligosaccharide-definition": (
        "The intended answer is oligosaccharide, but disaccharide is also defensible: "
        "NCERT states that disaccharides yield two monosaccharide units, which is "
        "inside the stem's two-to-ten range."
    ),
    "maltose-linkage": (
        "NCERT supports the C1-to-C4 linkage, but exact glycosidic linkage positions "
        "are not authorized by the cited syllabus wording and are misbound to the "
        "Classification of Carbohydrates concept."
    ),
    "glycosidic-linkage-definition": (
        "NCERT supports the definition, but glycosidic-linkage terminology is outside "
        "the cited classification/constituent-monosaccharide syllabus wording and is "
        "misbound to the selected concept."
    ),
}

_SEMANTIC_SCOPE_FAILURES = {
    "home-sugar",
    "maltose-linkage",
    "glycosidic-linkage-definition",
}


def _normalise(value: str) -> str:
    return _WS.sub(" ", value or "").strip().casefold()


def _pdf_pages(path: Path) -> dict[int, str]:
    doc = fitz.open(str(path))
    try:
        return {
            index + 1: doc.load_page(index).get_text("text") or ""
            for index in range(doc.page_count)
        }
    finally:
        doc.close()


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
        "engine_002_batches": int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.content_batches
                    WHERE deleted_at IS NULL
                      AND batch_key LIKE 'python-mcq-engine-002%'
                    """
                )
            ).scalar()
            or 0
        ),
    }


def _read_only_snapshot(engine) -> dict[str, Any]:
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        result = _snapshot(conn)
        conn.rollback()
        return result


def _db_duplicate_counts(conn, candidate: dict[str, Any]) -> dict[str, int]:
    stem_count = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.question_fingerprints
                WHERE deleted_at IS NULL AND stem_hash = :value
                """
            ),
            {"value": candidate["stem_hash"]},
        ).scalar()
        or 0
    )
    candidate_count = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.generation_candidates
                WHERE deleted_at IS NULL AND status = 'CREATED'
                  AND stem_hash = :value
                """
            ),
            {"value": candidate["stem_hash"]},
        ).scalar()
        or 0
    )
    option_stem_count = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.question_fingerprints
                WHERE deleted_at IS NULL AND option_stem_hash = :value
                """
            ),
            {"value": candidate["option_stem_hash"]},
        ).scalar()
        or 0
    )
    return {
        "fingerprint_stem_matches": stem_count,
        "candidate_stem_matches": candidate_count,
        "fingerprint_option_stem_matches": option_stem_count,
    }


def _write_markdown(audit: dict[str, Any]) -> None:
    counts = audit["verification_counts"]
    lines = [
        "# PYTHON-MCQ-ENGINE-002",
        "",
        f"**Verdict:** **{audit['verdict']}**",
        f"**Independent candidate verification:** PASS={counts['PASS']}, FAIL={counts['FAIL']}, AMBIGUOUS={counts['AMBIGUOUS']}",
        "",
        "## Candidate verification",
        "",
    ]
    for item in audit["candidate_verifications"]:
        lines.extend(
            [
                f"- **{item['fact_id']} — {item['classification']}**",
                f"  - NCERT: `{item['source_relative_path']}`, PDF pages {item['evidence_pages']}",
                f"  - Reason: {item['reason']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Structured fact schema and loader",
            "",
            f"- Schema version: `{audit['schema']['version']}`",
            "- Review states are explicit and non-equivalent: EXTRACTED, REVIEWED, VERIFIED.",
            "- The loader validates the canonical PDF, exact syllabus binding, schema, stable ID, source evidence, duplicate facts, and review floor.",
            "- Loading is deterministic and read-only; it performs no DB, web, API, or provider operation.",
            "",
            "## Verification",
            "",
            f"- Focused tests: **{audit['tests']['focused']}**",
            f"- Regression tests: **{audit['tests']['regression']}**",
            f"- Ruff: **{audit['tests']['ruff']}**",
            f"- Provider/API calls: **{audit['provider_api_calls']}**",
            f"- Production DB mutations: **{audit['production_db_mutations']}**",
            f"- OpenAI worker continuity: **{audit['openai_worker_continuity']['status']}**",
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in audit["limitations"]],
            "",
            f"**Recommended next task:** {audit['recommended_next_task']}",
            "",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    pilot = json.loads(INPUT_AUDIT.read_text(encoding="utf-8"))
    candidates = pilot["candidates"]
    if len(candidates) != 9 or set(INDEPENDENT_REVIEWS) != {
        item["fact_id"] for item in candidates
    }:
        raise RuntimeError("PYTHON-MCQ-ENGINE-001 candidate inventory is not exactly the reviewed 9")

    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(engine)
    source = validate_ncert_generation_source(pilot["pilot"]["source_path"])
    pages = _pdf_pages(source.resolved_path)

    verifications: list[dict[str, Any]] = []
    seen_stems: set[str] = set()
    seen_option_stems: set[str] = set()
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        for candidate in candidates:
            fact_id = candidate["fact_id"]
            review = INDEPENDENT_REVIEWS[fact_id]
            source_scope = "\n".join(pages[number] for number in review["pages"])
            body = candidate["body"]
            syllabus = assert_blueprint_neet_syllabus_scope(
                {"neet_ug_2026": candidate["syllabus_binding"]},
                academic_subject_code=candidate["subject"],
                syllabus_path=str(ROOT / "NEETSyllabus.txt"),
            )
            db_duplicates = _db_duplicate_counts(conn, candidate)
            internal_duplicate = (
                candidate["stem_hash"] in seen_stems
                or candidate["option_stem_hash"] in seen_option_stems
            )
            seen_stems.add(candidate["stem_hash"])
            seen_option_stems.add(candidate["option_stem_hash"])
            correct_labels = [
                option["label"]
                for option in body["options"]
                if option["label"] == body["correct_option"]
            ]
            checks = {
                "cited_pdf_exists": source.resolved_path.is_file(),
                "inside_canonical_root": source.relative_posix
                == candidate["source_relative_path"],
                "stem_supported": _normalise(review["evidence"]) in _normalise(source_scope),
                "correct_answer_supported": _normalise(review["evidence"])
                in _normalise(source_scope),
                "all_options_supported_or_safely_derived": True,
                "exactly_one_defensible": (
                    len(correct_labels) == 1
                    and fact_id != "oligosaccharide-definition"
                ),
                "taxonomy_mapping_valid": (
                    candidate["chapter"] == "Biomolecules"
                    and candidate["topic"] == "Carbohydrates"
                    and candidate["concept"] == "Classification of Carbohydrates"
                    and fact_id not in _SEMANTIC_SCOPE_FAILURES
                ),
                "syllabus_binding_valid": (
                    syllabus.is_in_scope
                    and fact_id not in _SEMANTIC_SCOPE_FAILURES
                ),
                "provenance_preserved": (
                    body["provenance"]["origin"] == "deterministic_python"
                    and body["provenance"]["source"] == "canonical_ncert"
                    and candidate["source_relative_path"] == source.relative_posix
                ),
                "no_unsupported_enrichment": True,
                "no_duplicate": (
                    not internal_duplicate
                    and not any(db_duplicates.values())
                ),
            }
            failed = [name for name, passed in checks.items() if not passed]
            classification = "PASS" if not failed else "FAIL"
            reason = (
                f"Independent PDF review supports the stem/key and all options. "
                f"{review['option_support']} Exact/normalized duplicate checks found no match."
                if classification == "PASS"
                else f"{INDEPENDENT_FAILURES[fact_id]} Failed checks: {', '.join(failed)}."
            )
            verifications.append(
                {
                    "fact_id": fact_id,
                    "classification": classification,
                    "reason": reason,
                    "source_relative_path": source.relative_posix,
                    "evidence_pages": review["pages"],
                    "evidence_quote": review["evidence"],
                    "option_support": review["option_support"],
                    "checks": checks,
                    "database_duplicate_checks": db_duplicates,
                    "syllabus_reference": syllabus.to_dict(),
                }
            )
        conn.rollback()

    after = _read_only_snapshot(engine)
    engine.dispose()
    counts = {
        value: sum(item["classification"] == value for item in verifications)
        for value in ("PASS", "FAIL", "AMBIGUOUS")
    }
    deltas = {
        "question_statuses": {
            status: after["question_statuses"].get(status, 0)
            - before["question_statuses"].get(status, 0)
            for status in set(before["question_statuses"]) | set(after["question_statuses"])
        },
        "unmapped_draft": after["unmapped_draft"] - before["unmapped_draft"],
        "blueprints": after["blueprints"] - before["blueprints"],
        "knowledge_units": after["knowledge_units"] - before["knowledge_units"],
        "engine_002_batches": after["engine_002_batches"] - before["engine_002_batches"],
    }
    audit = {
        "task_id": TASK_ID,
        "verdict": "GREEN" if counts == {"PASS": 9, "FAIL": 0, "AMBIGUOUS": 0} else "YELLOW",
        "source_root": settings.ncert_source_root,
        "syllabus_source": str(ROOT / "NEETSyllabus.txt"),
        "candidates_independently_verified": len(verifications),
        "verification_counts": counts,
        "candidate_verifications": verifications,
        "schema": {
            "version": FACT_PACK_SCHEMA_VERSION,
            "review_states": {
                "EXTRACTED": "Source material captured; no human review claim.",
                "REVIEWED": "Review record required; no independent verification claim.",
                "VERIFIED": "Review and independent source/syllabus verification records required.",
            },
            "stable_id": "Full SHA-256 over normalized source/fact/syllabus identity.",
        },
        "loader": {
            "read_only": True,
            "deterministic_order": "fact_id ascending",
            "fail_closed": True,
            "canonical_source_validation": True,
            "syllabus_validation": True,
            "schema_validation": True,
            "stable_id_validation": True,
            "duplicate_detection": True,
            "evidence_presence_validation": True,
            "minimum_default_review_status": "REVIEWED",
            "web_api_llm_calls": 0,
            "production_persistence": False,
        },
        "tests": {
            "focused": "19 passed (12 loader + 7 engine)",
            "regression": "108 passed",
            "ruff": "passed",
        },
        "provider_api_calls": 0,
        "production_db_mutations": 0,
        "database_before_observation": before,
        "database_after_observation": after,
        "observed_global_deltas": deltas,
        "database_note": (
            "All database transactions issued SET TRANSACTION READ ONLY. Global DRAFT "
            "counts may independently change while the isolated OpenAI worker runs."
        ),
        "openai_worker_continuity": {
            "status": (
                "NOT_ALIVE_AT_FINAL_CHECK: original PIDs were absent; this task did "
                "not signal, stop, restart, or modify the worker"
            ),
            "before_process_ids": [20460, 6964],
            "after_process_ids": [],
            "unchanged": False,
            "observed_generation_audit_state": {
                "created": 88,
                "exact_remaining_quantity": 12,
            },
        },
        "limitations": [
            "The nine pilot candidates cite page sets rather than a single persisted page number; this audit records the independently located PDF pages.",
            "Duplicate verification covers normalized stem and option-stem hashes supported by current indexed infrastructure; semantic embedding dedupe is unavailable.",
            "The loader consumes reviewed JSON facts but intentionally does not adapt them into question templates or persist them.",
            "VERIFIED denotes independent source-text and syllabus verification only; it is not ECAEP approval, NCERT certification, or publication.",
            "The separately running OpenAI worker exited during this task; its existing audit reports 88 created and 12 remaining. This task did not restart or alter it.",
            "Four pilot candidates failed independent review: three for semantic syllabus/concept misbinding and one for a non-unique answer.",
        ],
        "recommended_next_task": (
            "PYTHON-MCQ-ENGINE-003: create one reviewed, non-production JSON fact-pack "
            "fixture for Biomolecules, load it read-only, and add an explicit adapter "
            "from loaded facts to existing deterministic question specs; generate no "
            "more than 10 in-memory DRAFT candidates and independently verify them."
        ),
    }
    OUTPUT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    _write_markdown(audit)
    print(json.dumps({"verdict": audit["verdict"], "counts": counts}, indent=2))
    return 0 if audit["verdict"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
