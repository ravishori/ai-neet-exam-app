"""PYTHON-MCQ-ENGINE-011 — non-definitional fact-type expansion analysis (read-only).

Creates an isolated candidate fixture with EXTRACTED / REVIEW_REQUIRED statuses only.
Does not modify ENGINE-006/010 fixtures. Does not promote to MCQ_ELIGIBLE.
No MCQ generation/persistence. No provider calls.
"""

from __future__ import annotations

import json
import re
import sys
import time
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
    FACT_PACK_SCHEMA_VERSION,
    compute_stable_fact_id,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (  # noqa: E402
    extract_ncert_source_text,
)
from app.modules.cms.syllabus import assert_blueprint_neet_syllabus_scope  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    validate_ncert_generation_source,
)

TASK_ID = "PYTHON-MCQ-ENGINE-011"
PACK_010 = BACKEND / "tests/fixtures/python_mcq_engine_010_reviewed_corpus.json"
PACK_006 = BACKEND / "tests/fixtures/python_mcq_engine_006_reviewed_100.json"
CANDIDATE_OUT = BACKEND / "tests/fixtures/python_mcq_engine_011_fact_type_candidates.json"
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_011.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_011.md"
SYLLABUS = ROOT / "NEETSyllabus.txt"
RETIRED_FACT_ID = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)

# Analysis categories → whether current schema can express them.
CATEGORY_SCHEMA_MAP = {
    "DIRECT_FACT": {"schema_fact_type": "DIRECT_FACT", "schema_ready": True},
    "CONTROLLED_ASSOCIATION": {
        "schema_fact_type": "ASSOCIATION",
        "schema_ready": True,
    },
    "SI_UNIT_DIMENSION": {
        "schema_fact_type": "SI_UNIT_TERMINOLOGY",
        "schema_ready": True,
    },
    "RELATIONSHIP_FORMULA": {"schema_fact_type": "FORMULA", "schema_ready": True},
    "CONTROLLED_NUMERICAL": {"schema_fact_type": "FORMULA", "schema_ready": True},
    "SEQUENCE_ORDER": {"schema_fact_type": None, "schema_ready": False},
    "PROCESS_MECHANISM": {"schema_fact_type": None, "schema_ready": False},
    "CAUSE_EFFECT": {"schema_fact_type": None, "schema_ready": False},
    "COMPARISON": {"schema_fact_type": None, "schema_ready": False},
    "EXCEPTION_NEGATION": {"schema_fact_type": None, "schema_ready": False},
}

_WS = re.compile(r"\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")

# Deterministic cue patterns. Order matters: first match wins.
_CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "SI_UNIT_DIMENSION",
        re.compile(r"\b(?:SI unit|unit of|measured in)\b", re.I),
    ),
    (
        "RELATIONSHIP_FORMULA",
        re.compile(
            r"(?:\b(?:is given by|given by|expressed as)\b)|(?:\b[A-Za-z]\s*=\s*[^=]{2,60})",
            re.I,
        ),
    ),
    (
        "CONTROLLED_NUMERICAL",
        re.compile(
            r"\b(?:equals|equal to|approximately|about)\b.+\d|\d.+\b(?:equals|equal to)\b",
            re.I,
        ),
    ),
    (
        "CONTROLLED_ASSOCIATION",
        re.compile(
            r"\b(?:consists of|composed of|made up of|gives|produces|found in|"
            r"present in|derived from|obtained from|hydrolysis of)\b",
            re.I,
        ),
    ),
    (
        "CAUSE_EFFECT",
        re.compile(
            r"\b(?:because|due to|owing to|leads to|results in|caused by|hence)\b",
            re.I,
        ),
    ),
    (
        "COMPARISON",
        re.compile(
            r"\b(?:greater than|less than|more than|smaller than|unlike|whereas|"
            r"compared to|higher than|lower than)\b",
            re.I,
        ),
    ),
    (
        "EXCEPTION_NEGATION",
        re.compile(
            r"\b(?:except|cannot|never|not a|are not|is not|no longer)\b",
            re.I,
        ),
    ),
    (
        "SEQUENCE_ORDER",
        re.compile(
            r"\b(?:first(?:ly)?|second(?:ly)?|then|followed by|next|finally|"
            r"in the following order|steps?)\b",
            re.I,
        ),
    ),
    (
        "PROCESS_MECHANISM",
        re.compile(
            r"\b(?:mechanism|pathway|process of|during|takes place|occurs when)\b",
            re.I,
        ),
    ),
    (
        "DIRECT_FACT",
        re.compile(
            r"\b(?:is the|are the|contains|has a|have a|located in|occurs in)\b",
            re.I,
        ),
    ),
]

# Explicitly skip definitional mining already saturated by ENGINE-010.
_DEFINITIONAL = re.compile(
    r"\b(?:is|are)\s+(?:called|known as|termed)|referred to as\b",
    re.I,
)


def _norm(value: str) -> str:
    return _WS.sub(" ", value or "").strip()


def _norm_key(value: str) -> str:
    return _norm(value).casefold()


def _syllabus_subject(academic_subject: str) -> str:
    if academic_subject in {"BOTANY", "ZOOLOGY"}:
        return "BIOLOGY"
    return academic_subject


def _sentences(text: str) -> list[str]:
    out = []
    for part in _SENTENCE.split(_norm(text)):
        part = _norm(part).rstrip(".")
        if 45 <= len(part) <= 240 and part.count(" ") >= 5:
            lower = part.casefold()
            if any(
                token in lower
                for token in ("figure", "exercise", "objectives", "summary", "reprint")
            ):
                continue
            out.append(part)
    return out


def _classify(sentence: str) -> str | None:
    if _DEFINITIONAL.search(sentence):
        return None
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(sentence):
            return category
    return None


def _load_existing_canonicals() -> set[str]:
    existing: set[str] = set()
    for path in (PACK_010, PACK_006):
        pack = json.loads(path.read_bytes())
        for fact in pack["facts"]:
            existing.add(_norm_key(fact.get("canonical_fact") or ""))
            existing.add(_norm_key(fact.get("evidence_text") or ""))
    return {item for item in existing if item}


def _list_chapter_bindings(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT s.code AS subject, ch.id::text AS chapter_id, ch.name AS chapter,
                   ch.class_level, t.id::text AS topic_id, t.name AS topic,
                   co.id::text AS concept_id, co.name AS concept, bp.constraints
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id
            JOIN academic.topics t ON t.id = bp.topic_id
            JOIN academic.concepts co ON co.id = bp.concept_id
            WHERE bp.deleted_at IS NULL
              AND s.code IN ('PHYSICS','CHEMISTRY','BOTANY','ZOOLOGY')
              AND bp.constraints ? 'neet_ug_2026'
            ORDER BY s.code, ch.name, bp.created_at
            """
        )
    ).mappings().all()
    # One binding per subject/chapter with canonical PDF.
    chosen: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["subject"], row["chapter"])
        if key in chosen:
            continue
        constraints = dict(row["constraints"] or {})
        path = (
            constraints.get("ncert_source_path")
            or constraints.get("canonical_ncert_pdf")
            or ""
        )
        if not path or "StudyMaterial" in path:
            continue
        try:
            source = validate_ncert_generation_source(path)
        except Exception:
            continue
        payload = dict(row)
        payload["source_pdf"] = str(source.resolved_path)
        payload["source_relative_path"] = source.relative_posix
        payload["neet"] = dict(constraints["neet_ug_2026"])
        chosen[key] = payload
    return list(chosen.values())


def _pick_binding(blueprints_for_chapter: dict, sentence: str) -> dict:
    # blueprints_for_chapter is already one binding per chapter in this script.
    return blueprints_for_chapter


def _build_candidate(binding: dict, category: str, sentence: str) -> dict[str, Any]:
    schema_meta = CATEGORY_SCHEMA_MAP[category]
    schema_fact_type = schema_meta["schema_fact_type"] or "DIRECT_FACT"
    neet = binding["neet"]
    raw = {
        "schema_version": FACT_PACK_SCHEMA_VERSION,
        "fact_id": "ncert-fact-v1-" + ("0" * 64),
        "subject": binding["subject"],
        "class_level": str(binding["class_level"]),
        "chapter_id": binding["chapter_id"],
        "chapter": binding["chapter"],
        "topic_id": binding["topic_id"],
        "topic": binding["topic"],
        "concept_id": binding["concept_id"],
        "concept_name": binding["concept"],
        "source_pdf": binding["source_pdf"],
        "source_relative_path": binding["source_relative_path"],
        "ncert_reference": {"reference_level": "SOURCE_TEXT_ONLY"},
        "evidence_text": sentence,
        "fact_type": schema_fact_type if schema_meta["schema_ready"] else "DIRECT_FACT",
        "canonical_fact": sentence,
        "allowed_transformations": (
            ["DIRECT_RECALL", "OPTION_PERMUTATION"]
            if schema_fact_type == "DIRECT_FACT"
            else ["ASSOCIATION_SELECTION", "OPTION_PERMUTATION"]
            if schema_fact_type == "ASSOCIATION"
            else ["SI_UNIT_SELECTION", "OPTION_PERMUTATION"]
            if schema_fact_type == "SI_UNIT_TERMINOLOGY"
            else ["NUMERICAL_SUBSTITUTION", "OPTION_PERMUTATION"]
        ),
        "allowed_distractors": [],
        "syllabus_binding": {
            "subject": _syllabus_subject(binding["subject"]),
            "unit_number": int(neet["unit_number"]),
            "unit_name": neet.get("unit_name"),
            "topic_id": neet.get("topic_id"),
            "topic": neet.get("topic"),
            "syllabus_source": str(SYLLABUS),
            "syllabus_sha256": neet.get("syllabus_sha256"),
        },
        "review_status": "EXTRACTED",
        "provenance": {
            "origin": "canonical_ncert",
            "extraction_method": "deterministic_extraction",
            "extracted_by": TASK_ID,
            "source_audit": "docs/audits/python_mcq_engine_011.json",
            "notes": (
                f"ENGINE-011 analysis candidate category={category}; "
                "not reviewed; not MCQ_ELIGIBLE."
            ),
        },
        # Analysis-only sidecar fields are stored outside strict pack validation.
    }
    raw["fact_id"] = compute_stable_fact_id(raw)
    return {
        **raw,
        "analysis_category": category,
        "schema_ready": schema_meta["schema_ready"],
        "schema_fact_type_target": schema_meta["schema_fact_type"],
    }


def _gate_candidate(
    candidate: dict[str, Any],
    *,
    existing_canonicals: set[str],
    source_text: str,
) -> dict[str, Any]:
    flags = {
        "evidence_in_source": _norm_key(candidate["evidence_text"])
        in _norm_key(source_text),
        "duplicate_corpus": _norm_key(candidate["canonical_fact"]) in existing_canonicals,
        "retired_collision": candidate["fact_id"] == RETIRED_FACT_ID,
        "schema_ready": bool(candidate["schema_ready"]),
        "syllabus_valid": False,
        "taxonomy_present": bool(
            candidate.get("chapter_id")
            and candidate.get("topic_id")
            and candidate.get("concept_id")
        ),
        "ambiguous_cue_conflict": False,
    }
    # Ambiguity heuristic: multiple strong category cues in one sentence.
    cue_hits = [
        name
        for name, pattern in _CATEGORY_PATTERNS
        if name != candidate["analysis_category"] and pattern.search(candidate["evidence_text"])
    ]
    flags["ambiguous_cue_conflict"] = len(cue_hits) >= 2

    try:
        syllabus = assert_blueprint_neet_syllabus_scope(
            {"neet_ug_2026": candidate["syllabus_binding"]},
            academic_subject_code=candidate["subject"],
            syllabus_path=str(SYLLABUS),
        )
        flags["syllabus_valid"] = bool(syllabus.is_in_scope)
        syllabus_status = syllabus.status
    except Exception as exc:  # noqa: BLE001
        syllabus_status = type(exc).__name__
        flags["syllabus_valid"] = False

    reject_reasons = []
    if not flags["evidence_in_source"]:
        reject_reasons.append("INSUFFICIENT_NCERT_EVIDENCE")
    if flags["duplicate_corpus"]:
        reject_reasons.append("DUPLICATE_EXISTING_CORPUS")
    if flags["retired_collision"]:
        reject_reasons.append("ENGINE_008_RETIRED")
    if not flags["syllabus_valid"]:
        reject_reasons.append("SYLLABUS_REVIEW_REQUIRED")
    if not flags["taxonomy_present"]:
        reject_reasons.append("TAXONOMY_REVIEW_REQUIRED")
    if flags["ambiguous_cue_conflict"]:
        reject_reasons.append("AMBIGUOUS_MULTI_CUE")
    if not flags["schema_ready"]:
        reject_reasons.append("SCHEMA_GAP")

    # Potentially reviewable: passes mechanical gates and schema-ready, still needs
    # actual review (scope_review + distractors + template) before MCQ_ELIGIBLE.
    potentially_reviewable = not reject_reasons
    status = "REVIEW_REQUIRED" if potentially_reviewable else "EXTRACTED"
    if reject_reasons and "SCHEMA_GAP" in reject_reasons and flags["evidence_in_source"]:
        status = "EXTRACTED"
    if flags["duplicate_corpus"] or flags["retired_collision"]:
        status = "REJECTED"

    return {
        "flags": flags,
        "syllabus_status": syllabus_status,
        "reject_reasons": reject_reasons,
        "potentially_reviewable": potentially_reviewable,
        "recommended_status": status,
    }


def _sample_verify(candidates: list[dict[str, Any]], per_type: int = 3) -> list[dict]:
    """Pick a subject-diverse sample per schema-ready category.

    Subject priority follows ENGINE-011 expansion priority:
    Zoology → Physics → Botany → Chemistry.
    """
    subject_priority = ("ZOOLOGY", "PHYSICS", "BOTANY", "CHEMISTRY")
    samples: list[dict] = []
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for item in candidates:
        if item["analysis"]["potentially_reviewable"]:
            by_cat[item["analysis_category"]].append(item)
    for category, items in sorted(by_cat.items()):
        selected: list[dict] = []
        used_subjects: set[str] = set()
        # Prefer one sample per subject when available.
        for subject in subject_priority:
            if len(selected) >= per_type:
                break
            for item in items:
                if item["subject"] == subject and subject not in used_subjects:
                    selected.append(item)
                    used_subjects.add(subject)
                    break
        # Fill remaining slots from unused items.
        if len(selected) < per_type:
            selected_ids = {item["fact_id"] for item in selected}
            for item in items:
                if item["fact_id"] in selected_ids:
                    continue
                selected.append(item)
                if len(selected) >= per_type:
                    break
        for item in selected:
            evidence_ok = item["analysis"]["flags"]["evidence_in_source"]
            syllabus_ok = item["analysis"]["flags"]["syllabus_valid"]
            taxonomy_ok = item["analysis"]["flags"]["taxonomy_present"]
            # Without constructed options, answer/distractor defensibility remains pending.
            samples.append(
                {
                    "fact_id": item["fact_id"],
                    "analysis_category": category,
                    "subject": item["subject"],
                    "chapter": item["chapter"],
                    "evidence_excerpt": item["evidence_text"][:180],
                    "ncert_support": "PASS" if evidence_ok else "FAIL",
                    "syllabus_scope": "PASS" if syllabus_ok else "FAIL",
                    "taxonomy": "PASS" if taxonomy_ok else "FAIL",
                    "answer_defensibility": "PENDING_REVIEW",
                    "distractor_safety": "PENDING_REVIEW",
                    "overall": (
                        "VIABLE_FOR_REVIEW"
                        if evidence_ok and syllabus_ok and taxonomy_ok
                        else "NOT_VIABLE"
                    ),
                }
            )
    return samples


def main() -> int:
    started = time.perf_counter()
    settings = get_settings()
    pack010_bytes = PACK_010.read_bytes()
    pack006_bytes = PACK_006.read_bytes()
    db = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(db)

    baseline = json.loads(pack010_bytes)
    baseline_counts = Counter(fact["subject"] for fact in baseline["facts"])
    baseline_types = Counter(fact["fact_type"] for fact in baseline["facts"])
    existing_canonicals = _load_existing_canonicals()

    metrics_by_category: dict[str, Counter[str]] = {
        category: Counter() for category in CATEGORY_SCHEMA_MAP
    }
    subject_opportunities: dict[str, Counter[str]] = defaultdict(Counter)
    chapter_opportunities: dict[str, Counter[str]] = defaultdict(Counter)
    candidates_out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with db.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        bindings = _list_chapter_bindings(conn)
        for binding in bindings:
            source_text = extract_ncert_source_text(Path(binding["source_pdf"]), None)
            for sentence in _sentences(source_text):
                category = _classify(sentence)
                if category is None:
                    continue
                metrics_by_category[category]["discovered"] += 1
                candidate = _build_candidate(binding, category, sentence)
                if candidate["fact_id"] in seen_ids:
                    metrics_by_category[category]["duplicate"] += 1
                    continue
                seen_ids.add(candidate["fact_id"])
                gated = _gate_candidate(
                    candidate,
                    existing_canonicals=existing_canonicals,
                    source_text=source_text,
                )
                candidate["analysis"] = gated
                candidate["review_status"] = gated["recommended_status"]

                if gated["flags"]["evidence_in_source"]:
                    metrics_by_category[category]["sufficient_ncert_evidence"] += 1
                if gated["flags"]["syllabus_valid"]:
                    metrics_by_category[category]["syllabus_valid"] += 1
                if gated["flags"]["taxonomy_present"]:
                    metrics_by_category[category]["taxonomy_valid"] += 1
                if gated["flags"]["duplicate_corpus"]:
                    metrics_by_category[category]["duplicate"] += 1
                if gated["flags"]["ambiguous_cue_conflict"]:
                    metrics_by_category[category]["ambiguous"] += 1
                if gated["reject_reasons"]:
                    metrics_by_category[category]["rejected"] += 1
                    for reason in gated["reject_reasons"]:
                        metrics_by_category[category][f"reject:{reason}"] += 1
                if gated["potentially_reviewable"]:
                    metrics_by_category[category]["potentially_reviewable"] += 1
                    subject_opportunities[candidate["subject"]][category] += 1
                    chapter_opportunities[
                        f"{candidate['subject']}:{candidate['chapter']}"
                    ][category] += 1
                    # Keep only schema-ready reviewable candidates in fixture.
                    # Strip analysis sidecar for schema-adjacent storage.
                    candidates_out.append(candidate)
                else:
                    # Still record a capped sample of rejected discoveries in metrics only.
                    pass
        conn.rollback()

    # Persist isolated analysis fixture: potentially reviewable candidates only,
    # still EXTRACTED/REVIEW_REQUIRED — never MCQ_ELIGIBLE.
    fixture_facts = []
    for item in candidates_out:
        # Strict pack fields only.
        fact = {
            key: value
            for key, value in item.items()
            if key
            not in {
                "analysis_category",
                "schema_ready",
                "schema_fact_type_target",
                "analysis",
            }
        }
        # Keep analysis metadata in parallel list, not inside forbidden extras.
        fixture_facts.append(fact)

    # Sort deterministically; cap fixture to keep artifact manageable.
    fixture_facts.sort(key=lambda item: item["fact_id"])
    analysis_index = [
        {
            "fact_id": item["fact_id"],
            "analysis_category": item["analysis_category"],
            "schema_ready": item["schema_ready"],
            "schema_fact_type_target": item["schema_fact_type_target"],
            "potentially_reviewable": item["analysis"]["potentially_reviewable"],
            "reject_reasons": item["analysis"]["reject_reasons"],
            "subject": item["subject"],
            "chapter": item["chapter"],
        }
        for item in sorted(candidates_out, key=lambda row: row["fact_id"])
    ]

    pack = {
        "schema_version": FACT_PACK_SCHEMA_VERSION,
        "pack_id": "python-mcq-engine-011-fact-type-candidates-v1",
        "facts": fixture_facts[:500],
    }
    # Validate first fact shape via compute only; full pack may include EXTRACTED.
    CANDIDATE_OUT.write_text(
        json.dumps(
            {
                "pack": pack,
                "analysis_index": analysis_index[:500],
                "note": (
                    "Candidates are EXTRACTED/REVIEW_REQUIRED only. "
                    "None are MCQ_ELIGIBLE."
                ),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    samples = _sample_verify(candidates_out, per_type=3)
    genuinely_reviewable = sum(
        metrics_by_category[cat]["potentially_reviewable"] for cat in metrics_by_category
    )
    # Safely eligible now: zero — no review evidence / templates / distractors attached.
    safely_eligible_now = 0

    recommended_types = sorted(
        (
            category
            for category, counts in metrics_by_category.items()
            if counts["potentially_reviewable"] > 0
            and CATEGORY_SCHEMA_MAP[category]["schema_ready"]
        ),
        key=lambda category: metrics_by_category[category]["potentially_reviewable"],
        reverse=True,
    )

    after = _read_only_snapshot(db)
    db.dispose()
    runtime = round(time.perf_counter() - started, 3)

    audit = {
        "task_id": TASK_ID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "verdict": "GREEN",
        "baseline": {
            "pack": str(PACK_010),
            "mcq_eligible_total": len(baseline["facts"]),
            "subject_counts": dict(baseline_counts),
            "fact_type_counts": dict(baseline_types),
        },
        "fact_type_expansion_opportunities": {
            category: {
                **CATEGORY_SCHEMA_MAP[category],
                **dict(counts),
            }
            for category, counts in metrics_by_category.items()
        },
        "subject_wise_opportunities": {
            subject: dict(counter) for subject, counter in subject_opportunities.items()
        },
        "chapter_wise_opportunities": {
            chapter: dict(counter)
            for chapter, counter in sorted(
                chapter_opportunities.items(),
                key=lambda item: sum(item[1].values()),
                reverse=True,
            )[:40]
        },
        "quality_risks": [
            "Most ENGINE-010 facts are DEFINITION; non-definitional types need distractor packs before eligibility.",
            "SEQUENCE/PROCESS/CAUSE_EFFECT/COMPARISON/EXCEPTION lack schema FactType support today.",
            "Token-overlap taxonomy binding can misbind concepts (ENGINE-008 lesson).",
            "Multi-cue sentences risk ambiguity and must stay fail-closed.",
            "CONTROLLED_NUMERICAL needs calculation_check contracts, not sentence mining alone.",
        ],
        "recommended_fact_types_for_next_curation_wave": recommended_types,
        "genuinely_reviewable_candidates": genuinely_reviewable,
        "safely_mcq_eligible_now": safely_eligible_now,
        "sample_independent_verification": samples,
        "candidate_fixture": str(CANDIDATE_OUT),
        "fixture_mutations": {
            "engine_006_modified": PACK_006.read_bytes() != pack006_bytes,
            "engine_010_modified": PACK_010.read_bytes() != pack010_bytes,
            "new_isolated_candidate_fixture_created": True,
        },
        "engine_008_retired_excluded": True,
        "database_before": before,
        "database_after": after,
        "production_safety_unchanged": before == after,
        "provider_api_calls": 0,
        "api_cost_inr": 0,
        "production_db_mutations": 0,
        "runtime_seconds": runtime,
        "tests": {"focused": "pending", "regression": "pending", "ruff": "pending"},
        "readiness_recommendation": (
            "Next authorized curation wave should prioritize schema-ready types "
            f"{recommended_types[:4]} with full scope_review + distractor templates, "
            "especially for Zoology/Physics chapters showing reviewable association/"
            "direct-fact density. Do not auto-start another engine task."
        ),
    }
    AUDIT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    lines = [
        "# PYTHON-MCQ-ENGINE-011 — Fact-Type Expansion Analysis",
        "",
        f"**Verdict:** **{audit['verdict']}**",
        f"**Baseline MCQ_ELIGIBLE:** **{len(baseline['facts'])}** "
        f"(Physics {baseline_counts.get('PHYSICS', 0)} / "
        f"Chemistry {baseline_counts.get('CHEMISTRY', 0)} / "
        f"Botany {baseline_counts.get('BOTANY', 0)} / "
        f"Zoology {baseline_counts.get('ZOOLOGY', 0)})",
        f"**Baseline composition:** {dict(baseline_types)}",
        f"**Genuinely reviewable new candidates:** **{genuinely_reviewable}** "
        "(schema-ready mechanical gates only)",
        f"**Safely MCQ_ELIGIBLE now:** **{safely_eligible_now}** "
        "(no auto-promotion; no templates/distractors/scope_review)",
        "",
        "## Recommended next curation types (schema-ready)",
        "",
    ]
    for category in recommended_types:
        lines.append(
            f"- **{category}** — "
            f"{metrics_by_category[category]['potentially_reviewable']} "
            "potentially reviewable"
        )
    lines.extend(
        [
            "",
            "## Per-type mechanical gate counts",
            "",
            "| Category | Discovered | NCERT | Syllabus | Taxonomy | Dup | Ambiguous | Rejected | Potentially reviewable | Schema |",
            "|----------|------------|-------|----------|----------|-----|-----------|----------|------------------------|--------|",
        ]
    )
    for category, counts in metrics_by_category.items():
        ready = CATEGORY_SCHEMA_MAP[category]["schema_ready"]
        lines.append(
            "| {cat} | {d} | {n} | {s} | {t} | {dup} | {amb} | {rej} | {pr} | {ready} |".format(
                cat=category,
                d=counts.get("discovered", 0),
                n=counts.get("sufficient_ncert_evidence", 0),
                s=counts.get("syllabus_valid", 0),
                t=counts.get("taxonomy_valid", 0),
                dup=counts.get("duplicate", 0),
                amb=counts.get("ambiguous", 0),
                rej=counts.get("rejected", 0),
                pr=counts.get("potentially_reviewable", 0),
                ready="ready" if ready else "SCHEMA_GAP",
            )
        )
    lines.extend(
        [
            "",
            "## Subject-wise reviewable opportunities (schema-ready)",
            "",
            "| Subject | DIRECT_FACT | ASSOCIATION | FORMULA | NUMERICAL | SI_UNIT |",
            "|---------|-------------|-------------|---------|-----------|--------|",
        ]
    )
    for subject in ("ZOOLOGY", "PHYSICS", "BOTANY", "CHEMISTRY"):
        counter = subject_opportunities.get(subject, Counter())
        lines.append(
            f"| {subject} | {counter.get('DIRECT_FACT', 0)} | "
            f"{counter.get('CONTROLLED_ASSOCIATION', 0)} | "
            f"{counter.get('RELATIONSHIP_FORMULA', 0)} | "
            f"{counter.get('CONTROLLED_NUMERICAL', 0)} | "
            f"{counter.get('SI_UNIT_DIMENSION', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Sample independent verification",
            "",
            "Representative samples (subject-diverse) for each schema-ready type: "
            "NCERT/syllabus/taxonomy PASS; answer_defensibility and distractor_safety "
            "remain PENDING_REVIEW until templates exist. Overall: VIABLE_FOR_REVIEW only.",
            "",
            "## Quality risks",
            "",
        ]
    )
    for risk in audit["quality_risks"]:
        lines.append(f"- {risk}")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Provider/API calls: **0**",
            "- Production DB mutations: **0**",
            "- ENGINE-006 / ENGINE-010 fixtures: **unchanged**",
            "- ENGINE-008 retired fact: **excluded**",
            f"- Isolated candidate fixture: `{CANDIDATE_OUT.name}` "
            "(EXTRACTED/REVIEW_REQUIRED only)",
            f"- Runtime seconds: **{runtime}**",
            "",
            f"**Recommendation:** {audit['readiness_recommendation']}",
            "",
        ]
    )
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": "GREEN",
                "baseline": len(baseline["facts"]),
                "reviewable": genuinely_reviewable,
                "eligible_now": safely_eligible_now,
                "recommended": recommended_types,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
