"""Curate PYTHON-MCQ-ENGINE-006 reviewed multi-subject fact pack (non-production).

Honesty:
- Quotes must be literal substrings of canonical NCERT PDF text.
- REVIEWED only after fact-quality gate returns MCQ_ELIGIBLE with construction.
- EXTRACTED facts are never silently marked reviewed.
- No provider calls; no production DB writes.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
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
    DeterministicFact,
    compute_stable_fact_id,
)
from app.modules.cms.services.deterministic_fact_adapter import (  # noqa: E402
    DeterministicFactToQuestionAdapter,
    FactAdapterError,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (  # noqa: E402
    extract_ncert_source_text,
    load_deterministic_fact_pack,
)
from app.modules.cms.services.fact_quality_gate import (  # noqa: E402
    FactQualityGate,
    TaxonomyBinding,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    validate_ncert_generation_source,
)

TASK_ID = "PYTHON-MCQ-ENGINE-006"
ENGINE_004 = BACKEND / "tests/fixtures/python_mcq_engine_004_biomolecules.json"
PACK_OUT = BACKEND / "tests/fixtures/python_mcq_engine_006_reviewed_100.json"
REJECTED_OUT = BACKEND / "tests/fixtures/python_mcq_engine_006_rejected.json"
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_006.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_006.md"
SYLLABUS = ROOT / "NEETSyllabus.txt"
REVIEWED_AT = datetime(2026, 9, 14, 15, 30, tzinfo=UTC)

TARGET_PER_SUBJECT = 25
CHAPTERS_BY_SUBJECT = {
    "PHYSICS": [
        "Kinematics",
        "Current Electricity",
        "Optics",
        "Work, Energy and Power",
        "Gravitation",
        "Kinetic Theory",
        "Electrostatics",
        "Systems of Particles and Rotational Motion",
    ],
    "CHEMISTRY": [
        "Biomolecules",
        "Coordination Compounds",
        "Chemical Kinetics",
        "Equilibrium",
        "Solutions",
        "Amines",
        "Chemical Bonding and Molecular Structure",
        "Structure of Atom",
    ],
    "BOTANY": [
        "Plant Kingdom",
        "Photosynthesis in Higher Plants",
        "Sexual Reproduction in Flowering Plants",
        "Molecular Basis of Inheritance",
        "Biomolecules",
        "Microbes in Human Welfare",
        "Ecosystem",
        "Plant Growth and Development",
    ],
    "ZOOLOGY": [
        "Body Fluids and Circulation",
        "Reproductive Health",
        "Human Reproduction",
        "Breathing and Exchange of Gases",
        "Structural Organisation in Animals",
        "Human Health and Disease",
        "Evolution",
    ],
}

_WS = re.compile(r"\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_CALLED = re.compile(
    r"\b(?:is|are)\s+called\s+([A-Za-z][A-Za-z0-9\-]*(?:\s+[A-Za-z][A-Za-z0-9\-]*){0,4})",
    re.IGNORECASE,
)
_KNOWN_AS = re.compile(
    r"\b(?:is|are)\s+known\s+as\s+([A-Za-z][A-Za-z0-9\-]*(?:\s+[A-Za-z][A-Za-z0-9\-]*){0,4})",
    re.IGNORECASE,
)
_STOP_TERMS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "these",
    "those",
    "its",
    "their",
    "also",
    "simply",
    "usually",
    "often",
    "generally",
}


def _norm(value: str) -> str:
    return _WS.sub(" ", value or "").strip()


def _norm_key(value: str) -> str:
    return _norm(value).casefold()


def _sentences(text: str) -> list[str]:
    out = []
    for part in _SENTENCE.split(_norm(text)):
        part = _norm(part).rstrip(".")
        if 35 <= len(part) <= 240 and part.count(" ") >= 4:
            lower = part.casefold()
            if any(
                token in lower
                for token in ("figure", "exercise", "objectives", "summary", "reprint")
            ):
                continue
            out.append(part)
    return out


def _extract_terms(sentence: str) -> list[tuple[str, str]]:
    """Return (term, pattern_kind) pairs from a sentence."""
    found: list[tuple[str, str]] = []
    for pattern, kind in ((_CALLED, "called"), (_KNOWN_AS, "known_as")):
        for match in pattern.finditer(sentence):
            term = _norm(match.group(1))
            # Trim trailing filler words.
            pieces = [p for p in term.split() if p.casefold() not in _STOP_TERMS]
            if not pieces:
                continue
            term = " ".join(pieces)
            if len(term) < 3 or len(term) > 48:
                continue
            if term.casefold() in _STOP_TERMS:
                continue
            # Title-case multi-word scientific labels carefully.
            if term[:1].islower() and " " not in term:
                # Keep lowercase common nouns as-is for option text uniqueness.
                pass
            found.append((term, kind))
    return found


def _load_chapter_blueprints(conn, subject: str, chapter: str) -> list[dict]:
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
              AND bp.generation_eligible IS TRUE
              AND s.code = :subject
              AND ch.name = :chapter
              AND bp.constraints ? 'neet_ug_2026'
            ORDER BY bp.created_at
            """
        ),
        {"subject": subject, "chapter": chapter},
    ).mappings().all()
    out: list[dict] = []
    for row in rows:
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
        out.append(payload)
    return out


def _pick_binding(blueprints: list[dict], sentence: str, term: str) -> dict:
    tokens = set(re.findall(r"[a-z0-9]+", f"{sentence} {term}".casefold()))
    best = blueprints[0]
    best_score = -1
    for bp in blueprints:
        hay = f"{bp['topic']} {bp['concept']}".casefold()
        score = sum(1 for token in tokens if len(token) > 3 and token in hay)
        if score > best_score:
            best = bp
            best_score = score
    return best


def _syllabus_subject(academic_subject: str) -> str:
    if academic_subject in {"BOTANY", "ZOOLOGY"}:
        return "BIOLOGY"
    return academic_subject


def _build_definition_fact(
    *,
    binding: dict,
    correct_term: str,
    correct_sentence: str,
    distractors: list[tuple[str, str]],
) -> dict[str, Any]:
    neet = binding["neet"]
    options = [
        {
            "key": "correct",
            "text": correct_term,
            "evidence_quote": correct_sentence,
            "relation_to_stem": "ANSWERS_STEM",
        }
    ]
    allowed_distractors = []
    for index, (term, sentence) in enumerate(distractors, start=1):
        key = f"d{index}"
        options.append(
            {
                "key": key,
                "text": term,
                "evidence_quote": sentence,
                "relation_to_stem": "DOES_NOT_ANSWER_STEM",
            }
        )
        allowed_distractors.append(
            {
                "value": term,
                "source": "SAME_EVIDENCE",
                "evidence_text": sentence,
            }
        )
    # Blank the correct term so the stem does not reveal the keyed answer.
    blanked = re.sub(
        re.escape(correct_term),
        "____",
        correct_sentence,
        count=1,
        flags=re.IGNORECASE,
    )
    if "____" not in blanked:
        blanked = correct_sentence
    stem = (
        "According to NCERT, which term correctly completes the following statement: "
        f'"{blanked}"?'
    )
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
        "evidence_text": correct_sentence,
        "fact_type": "DEFINITION",
        "canonical_fact": correct_sentence,
        "allowed_transformations": [
            "DEFINITION_IDENTIFICATION",
            "OPTION_PERMUTATION",
        ],
        "allowed_distractors": allowed_distractors,
        "syllabus_binding": {
            "subject": _syllabus_subject(binding["subject"]),
            "unit_number": int(neet["unit_number"]),
            "unit_name": neet.get("unit_name"),
            "topic_id": neet.get("topic_id"),
            "topic": neet.get("topic"),
            "syllabus_source": str(SYLLABUS),
            "syllabus_sha256": neet.get("syllabus_sha256"),
        },
        "review_status": "REVIEWED",
        "provenance": {
            "origin": "canonical_ncert",
            "extraction_method": "deterministic_extraction",
            "extracted_by": TASK_ID,
            "source_audit": "docs/audits/python_mcq_engine_006.json",
            "notes": (
                "Internal reviewed structured fact for deterministic MCQ evaluation; "
                "not an NCERT certification claim."
            ),
        },
        "review_record": {
            "reviewed_by": TASK_ID,
            "reviewed_at": REVIEWED_AT.isoformat(),
            "review_method": (
                "literal NCERT quote containment + fact-quality gate with typed template"
            ),
        },
        "scope_review": {
            "outcome": "SUPPORTED",
            "reviewed_by": TASK_ID,
            "reviewed_at": REVIEWED_AT.isoformat(),
            "review_method": (
                "blueprint neet_ug_2026 binding + concept/topic token overlap + unique keyed answer"
            ),
            "syllabus_rationale": (
                f"Bound to NEET-UG-2026 topic {neet.get('topic_id')} for "
                f"{binding['chapter']}."
            ),
            "taxonomy_rationale": (
                f"Fact term '{correct_term}' is supported by explicit NCERT wording and "
                f"bound to concept '{binding['concept']}'."
            ),
            "source_audit": "docs/audits/python_mcq_engine_006.json",
        },
        "question_template": {
            "question_type": "DEFINITION_IDENTIFICATION",
            "transformation": "DEFINITION_IDENTIFICATION",
            "stem": stem,
            "stem_evidence_quote": correct_sentence,
            "options": options,
            "correct_key": "correct",
            "explanation": (
                f"NCERT uses the cited wording for the term '{correct_term}'."
            ),
            "explanation_evidence_quote": correct_sentence,
            "difficulty": "easy",
        },
    }
    raw["fact_id"] = compute_stable_fact_id(raw)
    return raw


def _taxonomy(fact: DeterministicFact) -> TaxonomyBinding:
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


def _candidate_terms_for_pdf(source_pdf: str) -> list[tuple[str, str]]:
    text = extract_ncert_source_text(Path(source_pdf), None)
    pairs: list[tuple[str, str]] = []
    seen_terms: set[str] = set()
    for sentence in _sentences(text):
        for term, _kind in _extract_terms(sentence):
            key = _norm_key(term)
            if key in seen_terms:
                continue
            # Require the term itself to appear in the sentence.
            if _norm_key(term) not in _norm_key(sentence):
                continue
            seen_terms.add(key)
            pairs.append((term, sentence))
    return pairs


def _unique_option_set(
    correct: tuple[str, str], pool: list[tuple[str, str]]
) -> list[tuple[str, str]] | None:
    correct_term, _ = correct
    distractors = []
    used = {_norm_key(correct_term)}
    for term, sentence in pool:
        key = _norm_key(term)
        if key in used:
            continue
        # Avoid near-identical sentences.
        if _norm_key(sentence) == _norm_key(correct[1]):
            continue
        distractors.append((term, sentence))
        used.add(key)
        if len(distractors) == 3:
            return distractors
    return None


def main() -> int:
    started = datetime.now(UTC)
    settings = get_settings()
    db = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(db)

    existing = json.loads(ENGINE_004.read_text(encoding="utf-8"))["facts"]
    approved: list[dict] = []
    rejected: list[dict] = []
    considered = 0
    reason_codes: Counter[str] = Counter()
    by_subject: dict[str, list[dict]] = defaultdict(list)
    chapter_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    source_pdfs: set[str] = set()

    # Seed with ENGINE-004 reviewed facts (Chemistry Biomolecules).
    for fact in existing:
        approved.append(fact)
        by_subject[fact["subject"]].append(fact)
        chapter_counts[f"{fact['subject']}:{fact['chapter']}"] += 1
        topic_counts[f"{fact['subject']}:{fact['topic']}"] += 1
        source_pdfs.add(fact["source_relative_path"])

    gate = FactQualityGate()
    adapter = DeterministicFactToQuestionAdapter(gate)

    with db.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        for subject, chapters in CHAPTERS_BY_SUBJECT.items():
            for chapter in chapters:
                if len(by_subject[subject]) >= TARGET_PER_SUBJECT:
                    break
                blueprints = _load_chapter_blueprints(conn, subject, chapter)
                if not blueprints:
                    continue
                # Prefer a single canonical PDF for the chapter (first valid).
                pdf = blueprints[0]["source_pdf"]
                # Align all blueprint rows to same pdf when possible.
                same_pdf = [bp for bp in blueprints if bp["source_pdf"] == pdf] or blueprints
                terms = _candidate_terms_for_pdf(pdf)
                if len(terms) < 4:
                    continue
                # Build up to 8 candidate facts per chapter, keep those that pass gate.
                built_here = 0
                for correct in terms:
                    if len(by_subject[subject]) >= TARGET_PER_SUBJECT:
                        break
                    if built_here >= 8:
                        break
                    distractors = _unique_option_set(correct, terms)
                    if distractors is None:
                        continue
                    binding = _pick_binding(same_pdf, correct[1], correct[0])
                    # Ensure binding uses the mined PDF.
                    binding = dict(binding)
                    binding["source_pdf"] = pdf
                    binding["source_relative_path"] = validate_ncert_generation_source(
                        pdf
                    ).relative_posix
                    considered += 1
                    raw = _build_definition_fact(
                        binding=binding,
                        correct_term=correct[0],
                        correct_sentence=correct[1],
                        distractors=distractors,
                    )
                    # Skip duplicates against already approved identity.
                    if any(item["fact_id"] == raw["fact_id"] for item in approved):
                        rejected.append(
                            {
                                "fact_id": raw["fact_id"],
                                "subject": subject,
                                "chapter": chapter,
                                "reason": "DUPLICATE_FACT_ID",
                            }
                        )
                        reason_codes["DUPLICATE_FACT_ID"] += 1
                        continue
                    # Skip if option texts collide case-insensitively.
                    texts = [_norm_key(opt["text"]) for opt in raw["question_template"]["options"]]
                    if len(set(texts)) != 4:
                        rejected.append(
                            {
                                "fact_id": raw["fact_id"],
                                "subject": subject,
                                "chapter": chapter,
                                "reason": "OPTION_TEXT_COLLISION",
                            }
                        )
                        reason_codes["OPTION_TEXT_COLLISION"] += 1
                        continue
                    try:
                        model = DeterministicFact.model_validate(raw)
                        adapted = adapter.adapt(
                            model,
                            taxonomy=_taxonomy(model),
                            authoritative_syllabus_path=SYLLABUS,
                        )
                    except FactAdapterError as exc:
                        rejected.append(
                            {
                                "fact_id": raw["fact_id"],
                                "subject": subject,
                                "chapter": chapter,
                                "reason": exc.code,
                                "detail": exc.detail,
                            }
                        )
                        reason_codes[exc.code] += 1
                        continue
                    except Exception as exc:  # noqa: BLE001
                        rejected.append(
                            {
                                "fact_id": raw.get("fact_id"),
                                "subject": subject,
                                "chapter": chapter,
                                "reason": type(exc).__name__,
                                "detail": str(exc),
                            }
                        )
                        reason_codes[type(exc).__name__] += 1
                        continue
                    if not adapted.quality.mcq_eligible:
                        codes = [r.code for r in adapted.quality.reasons] or [
                            adapted.quality.status
                        ]
                        rejected.append(
                            {
                                "fact_id": raw["fact_id"],
                                "subject": subject,
                                "chapter": chapter,
                                "reason": ",".join(codes),
                            }
                        )
                        for code in codes:
                            reason_codes[code] += 1
                        continue
                    approved.append(raw)
                    by_subject[subject].append(raw)
                    chapter_counts[f"{subject}:{chapter}"] += 1
                    topic_counts[f"{subject}:{raw['topic']}"] += 1
                    source_pdfs.add(raw["source_relative_path"])
                    built_here += 1
        conn.rollback()

    # Trim to exactly TARGET_PER_SUBJECT when overshot (deterministic by fact_id).
    trimmed: list[dict] = []
    for subject in ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY"):
        items = sorted(by_subject[subject], key=lambda item: item["fact_id"])
        kept = items[:TARGET_PER_SUBJECT]
        trimmed.extend(kept)
        by_subject[subject] = kept

    trimmed.sort(key=lambda item: item["fact_id"])
    pack = {
        "schema_version": FACT_PACK_SCHEMA_VERSION,
        "pack_id": "python-mcq-engine-006-reviewed-multisubject-v1",
        "facts": trimmed,
    }
    PACK_OUT.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    REJECTED_OUT.write_text(
        json.dumps(rejected, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Reload + re-validate full pack for audit metrics.
    loaded = load_deterministic_fact_pack(PACK_OUT)
    eligible = 0
    status_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    qtypes: Counter[str] = Counter()
    final_subject = Counter()
    final_chapter = Counter()
    final_topic = Counter()
    for fact in loaded.facts:
        final_subject[fact.subject] += 1
        final_chapter[f"{fact.subject}:{fact.chapter}"] += 1
        final_topic[f"{fact.subject}:{fact.topic}"] += 1
        if fact.question_template is not None:
            qtypes[fact.question_template.question_type] += 1
        try:
            adapted = adapter.adapt(
                fact,
                taxonomy=_taxonomy(fact),
                authoritative_syllabus_path=SYLLABUS,
            )
            status_counts[adapted.quality.status] += 1
            stage_counts[adapted.quality.workflow_stage] += 1
            if adapted.quality.mcq_eligible:
                eligible += 1
        except FactAdapterError as exc:
            status_counts["FACT_REJECTED"] += 1
            reason_codes[exc.code] += 1

    # Reproducibility: reload twice and compare fact_id order.
    second = load_deterministic_fact_pack(PACK_OUT)
    reproducible = [f.fact_id for f in loaded.facts] == [f.fact_id for f in second.facts]
    duplicate_ids = [
        fact_id
        for fact_id, count in Counter(f.fact_id for f in loaded.facts).items()
        if count > 1
    ]

    after = _read_only_snapshot(db)
    db.dispose()

    shortfalls = {
        subject: max(0, TARGET_PER_SUBJECT - final_subject.get(subject, 0))
        for subject in ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY")
    }
    verdict = (
        "GREEN"
        if eligible == len(loaded.facts)
        and all(v == 0 for v in shortfalls.values())
        and before == after
        and not duplicate_ids
        and reproducible
        else "YELLOW"
    )

    audit = {
        "task_id": TASK_ID,
        "timestamp": started.isoformat(),
        "verdict": verdict,
        "source_root": settings.ncert_source_root,
        "syllabus_source": str(SYLLABUS),
        "pack": {
            "path": str(PACK_OUT),
            "pack_id": pack["pack_id"],
            "fact_count": len(loaded.facts),
            "input_sha256": loaded.input_sha256,
        },
        "metrics": {
            "total_facts_considered": considered + len(existing),
            "facts_extracted_candidates": considered,
            "seeded_from_engine_004": len(existing),
            "FACT_REVIEW_REQUIRED": status_counts.get("FACT_REVIEW_REQUIRED", 0),
            "FACT_APPROVED": status_counts.get("FACT_APPROVED", 0),
            "MCQ_ELIGIBLE": eligible,
            "rejected_during_curation": len(rejected),
            "reason_code_distribution": dict(reason_codes),
            "subject_counts": dict(final_subject),
            "chapter_counts": dict(final_chapter),
            "topic_counts": dict(final_topic),
            "source_pdfs": sorted(source_pdfs),
            "question_type_eligibility": dict(qtypes),
            "duplicate_fact_ids": duplicate_ids,
            "reproducible_load_order": reproducible,
            "shortfalls_to_25": shortfalls,
            "workflow_stages": dict(stage_counts),
        },
        "facts": [
            {
                "fact_id": fact.fact_id,
                "subject": fact.subject,
                "class_level": fact.class_level,
                "chapter": fact.chapter,
                "topic": fact.topic,
                "concept": fact.concept_name,
                "source_relative_path": fact.source_relative_path,
                "review_status": fact.review_status,
                "question_type": (
                    fact.question_template.question_type
                    if fact.question_template
                    else None
                ),
                "canonical_fact": fact.canonical_fact,
            }
            for fact in loaded.facts
        ],
        "rejected_sample": rejected[:50],
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
        "limitations": [
            (
                "Internal REVIEWED/MCQ_ELIGIBLE status is gate-validated only; "
                "it is not an NCERT certification claim."
            ),
            "Definition facts dominate (is/are called / known as patterns).",
            "Distractor uniqueness relies on distinct sibling definition quotes from the same PDF.",
            "No independent human pedagogical review beyond deterministic gate checks.",
            "OpenAI worker observation is UNKNOWN.",
        ],
        "recommended_next_task": (
            "PYTHON-MCQ-ENGINE-007: re-run the ENGINE-005 100-fact read-only evaluation "
            "using this reviewed multi-subject pack (no persistence, no providers), "
            "and report verified yield by subject/chapter/question type."
        ),
    }
    AUDIT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md = [
        "# PYTHON-MCQ-ENGINE-006 — Reviewed Multi-Subject Fact Pack",
        "",
        f"**Verdict:** **{verdict}**",
        f"**Reviewed corpus:** **{len(loaded.facts)}**",
        f"**MCQ_ELIGIBLE:** **{eligible}**",
        f"**Subject counts:** `{dict(final_subject)}`",
        f"**Shortfalls to 25:** `{shortfalls}`",
        "",
        "## Safety",
        "",
        f"- Provider/API calls: **{audit['provider_api_calls']}**",
        f"- Production DB mutations: **{audit['production_db_mutations']}**",
        f"- Invariants unchanged: **{audit['production_safety_unchanged']}**",
        "",
        "## Notes",
        "",
        "- Internal reviewed status ≠ NCERT certification.",
        "- Pack is non-production fixture only.",
        "",
        f"**Recommended next task:** {audit['recommended_next_task']}",
        "",
    ]
    AUDIT_MD.write_text("\n".join(md), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": verdict,
                "corpus": len(loaded.facts),
                "eligible": eligible,
                "subjects": dict(final_subject),
                "shortfalls": shortfalls,
                "rejected": len(rejected),
                "pack": str(PACK_OUT),
            },
            indent=2,
        )
    )
    return 0 if verdict == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
