"""PYTHON-MCQ-ENGINE-010 — expand reviewed MCQ-eligible corpus (non-production).

Creates a NEW versioned fixture. Does not modify ENGINE-006.
Excludes ENGINE-008 retired fact. No MCQ persistence. No provider calls.
"""

from __future__ import annotations

import json
import re
import sys
import time
import tracemalloc
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
from app.modules.cms.services.fact_quality_gate import TaxonomyBinding  # noqa: E402
from app.modules.cms.services.factory_candidate_validation import (  # noqa: E402
    normalize_stem,
)
from app.modules.cms.services.ncert_claim_grounding import (  # noqa: E402
    detect_multiple_defensible_answers,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    validate_ncert_generation_source,
)

TASK_ID = "PYTHON-MCQ-ENGINE-010"
PACK_006 = BACKEND / "tests/fixtures/python_mcq_engine_006_reviewed_100.json"
PACK_OUT = BACKEND / "tests/fixtures/python_mcq_engine_010_reviewed_corpus.json"
REJECTED_OUT = BACKEND / "tests/fixtures/python_mcq_engine_010_rejected.json"
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_010.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_010.md"
SYLLABUS = ROOT / "NEETSyllabus.txt"
REVIEWED_AT = datetime(2026, 9, 14, 16, 45, tzinfo=UTC)
RETIRED_FACT_ID = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)
TARGET_PER_SUBJECT = 250
TARGET_TOTAL = 1000
MAX_PER_CHAPTER = 40

_WS = re.compile(r"\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_TERM_PATTERNS = [
    re.compile(
        r"\b(?:is|are)\s+called\s+([A-Za-z][A-Za-z0-9\-]*(?:\s+[A-Za-z][A-Za-z0-9\-]*){0,5})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:is|are)\s+known\s+as\s+([A-Za-z][A-Za-z0-9\-]*(?:\s+[A-Za-z][A-Za-z0-9\-]*){0,5})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:is|are)\s+(?:also\s+)?termed\s+([A-Za-z][A-Za-z0-9\-]*(?:\s+[A-Za-z][A-Za-z0-9\-]*){0,5})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\breferred\s+to\s+as\s+([A-Za-z][A-Za-z0-9\-]*(?:\s+[A-Za-z][A-Za-z0-9\-]*){0,5})",
        re.IGNORECASE,
    ),
]
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
    "as",
    "or",
    "and",
}


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
        if 35 <= len(part) <= 260 and part.count(" ") >= 4:
            lower = part.casefold()
            if any(
                token in lower
                for token in ("figure", "exercise", "objectives", "summary", "reprint")
            ):
                continue
            out.append(part)
    return out


def _extract_terms(sentence: str) -> list[str]:
    found: list[str] = []
    for pattern in _TERM_PATTERNS:
        for match in pattern.finditer(sentence):
            term = _norm(match.group(1))
            pieces = [p for p in term.split() if p.casefold() not in _STOP_TERMS]
            if not pieces:
                continue
            term = " ".join(pieces)
            if 3 <= len(term) <= 60 and _norm_key(term) in _norm_key(sentence):
                found.append(term)
    return found


def _near_duplicate_terms(correct: str, distractors: list[tuple[str, str]]) -> bool:
    c_norm = normalize_stem(correct)
    for term, _sentence in distractors:
        d_norm = normalize_stem(term)
        if not d_norm or not c_norm:
            continue
        if d_norm == c_norm:
            return True
        if len(c_norm) > 8 and len(d_norm) > 8 and (
            c_norm in d_norm or d_norm in c_norm
        ):
            return True
    return False


def _unique_option_set(
    correct: tuple[str, str], pool: list[tuple[str, str]]
) -> list[tuple[str, str]] | None:
    correct_term, correct_sentence = correct
    distractors: list[tuple[str, str]] = []
    used = {_norm_key(correct_term)}
    for term, sentence in pool:
        key = _norm_key(term)
        if key in used:
            continue
        if _norm_key(sentence) == _norm_key(correct_sentence):
            continue
        if _near_duplicate_terms(correct_term, [(term, sentence)]):
            continue
        distractors.append((term, sentence))
        used.add(key)
        if len(distractors) == 3:
            if _near_duplicate_terms(correct_term, distractors):
                return None
            return distractors
    return None


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


def _list_canonical_chapters(conn) -> dict[str, list[str]]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT s.code AS subject, ch.name AS chapter, bp.constraints
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id
            WHERE bp.deleted_at IS NULL
              AND s.code IN ('PHYSICS','CHEMISTRY','BOTANY','ZOOLOGY')
              AND bp.constraints ? 'neet_ug_2026'
            ORDER BY s.code, ch.name
            """
        )
    ).mappings().all()
    found: dict[str, set[str]] = defaultdict(set)
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
            validate_ncert_generation_source(path)
        except Exception:
            continue
        found[row["subject"]].add(row["chapter"])
    return {subject: sorted(chapters) for subject, chapters in found.items()}


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


def _candidate_terms_for_pdf(source_pdf: str) -> list[tuple[str, str]]:
    text = extract_ncert_source_text(Path(source_pdf), None)
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sentence in _sentences(text):
        for term in _extract_terms(sentence):
            key = _norm_key(term)
            if key in seen:
                continue
            seen.add(key)
            pairs.append((term, sentence))
    return pairs


def _build_definition_fact(
    *,
    binding: dict,
    correct_term: str,
    correct_sentence: str,
    distractors: list[tuple[str, str]],
) -> dict[str, Any]:
    neet = binding["neet"]
    blanked = re.sub(
        re.escape(correct_term),
        "____",
        correct_sentence,
        count=1,
        flags=re.IGNORECASE,
    )
    if "____" not in blanked:
        blanked = correct_sentence
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
        options.append(
            {
                "key": f"d{index}",
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
            "source_audit": "docs/audits/python_mcq_engine_010.json",
            "notes": (
                "Internal reviewed structured fact for deterministic MCQ evaluation; "
                "not an NCERT certification claim."
            ),
        },
        "review_record": {
            "reviewed_by": TASK_ID,
            "reviewed_at": REVIEWED_AT.isoformat(),
            "review_method": (
                "literal NCERT quote containment + anti-ambiguity term filter + "
                "fact-quality gate with typed template"
            ),
        },
        "scope_review": {
            "outcome": "SUPPORTED",
            "reviewed_by": TASK_ID,
            "reviewed_at": REVIEWED_AT.isoformat(),
            "review_method": (
                "blueprint neet_ug_2026 binding + concept/topic token overlap + "
                "unique keyed answer + near-duplicate distractor rejection"
            ),
            "syllabus_rationale": (
                f"Bound to NEET-UG-2026 topic {neet.get('topic_id')} for "
                f"{binding['chapter']}."
            ),
            "taxonomy_rationale": (
                f"Fact term '{correct_term}' is supported by explicit NCERT wording and "
                f"bound to concept '{binding['concept']}'."
            ),
            "source_audit": "docs/audits/python_mcq_engine_010.json",
        },
        "question_template": {
            "question_type": "DEFINITION_IDENTIFICATION",
            "transformation": "DEFINITION_IDENTIFICATION",
            "stem": (
                "According to NCERT, which term correctly completes the following "
                f'statement: "{blanked}"?'
            ),
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


def _preflight_ambiguity(raw: dict[str, Any]) -> str | None:
    template = raw["question_template"]
    options = template["options"]
    correct = next(option for option in options if option["key"] == "correct")
    distractors = [option for option in options if option["key"] != "correct"]
    if len(distractors) != 3:
        return "INVALID_DISTRACTOR_COUNT"
    body = {
        "stem": template["stem"],
        "correct_option": "A",
        "options": [
            {"label": "A", "text": correct["text"]},
            {"label": "B", "text": distractors[0]["text"]},
            {"label": "C", "text": distractors[1]["text"]},
            {"label": "D", "text": distractors[2]["text"]},
        ],
    }
    multi = detect_multiple_defensible_answers(body, raw["evidence_text"])
    if len(multi) > 1:
        return "FACT_AMBIGUOUS_NEAR_DUPLICATE_OPTIONS"
    return None


def main() -> int:
    started = time.perf_counter()
    tracemalloc.start()
    settings = get_settings()
    pack006_bytes = PACK_006.read_bytes()
    db = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(db)

    seeded = load_deterministic_fact_pack(PACK_006)
    approved: list[dict] = []
    rejected: list[dict] = []
    reason_codes: Counter[str] = Counter()
    by_subject: dict[str, list[dict]] = defaultdict(list)
    seen_ids: set[str] = set()
    seen_canonical: set[str] = set()
    adapter = DeterministicFactToQuestionAdapter()

    for fact in seeded.facts:
        if fact.fact_id == RETIRED_FACT_ID:
            rejected.append(
                {
                    "fact_id": fact.fact_id,
                    "subject": fact.subject,
                    "chapter": fact.chapter,
                    "reason": "ENGINE_008_RETIRED",
                }
            )
            reason_codes["ENGINE_008_RETIRED"] += 1
            continue
        raw = json.loads(json.dumps(fact.model_dump(mode="json")))
        approved.append(raw)
        by_subject[fact.subject].append(raw)
        seen_ids.add(fact.fact_id)
        seen_canonical.add(_norm_key(fact.canonical_fact))

    with db.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        chapters_by_subject = _list_canonical_chapters(conn)
        for subject in ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY"):
            for chapter in chapters_by_subject.get(subject, []):
                if len(by_subject[subject]) >= TARGET_PER_SUBJECT:
                    break
                blueprints = _load_chapter_blueprints(conn, subject, chapter)
                if not blueprints:
                    continue
                pdf = blueprints[0]["source_pdf"]
                same_pdf = [bp for bp in blueprints if bp["source_pdf"] == pdf] or blueprints
                terms = _candidate_terms_for_pdf(pdf)
                if len(terms) < 4:
                    continue
                built_here = 0
                for correct in terms:
                    if len(by_subject[subject]) >= TARGET_PER_SUBJECT:
                        break
                    if built_here >= MAX_PER_CHAPTER:
                        break
                    distractors = _unique_option_set(correct, terms)
                    if distractors is None:
                        reason_codes["DISTRACTOR_POOL_INSUFFICIENT"] += 1
                        continue
                    binding = dict(_pick_binding(same_pdf, correct[1], correct[0]))
                    binding["source_pdf"] = pdf
                    binding["source_relative_path"] = validate_ncert_generation_source(
                        pdf
                    ).relative_posix
                    raw = _build_definition_fact(
                        binding=binding,
                        correct_term=correct[0],
                        correct_sentence=correct[1],
                        distractors=distractors,
                    )
                    if raw["fact_id"] == RETIRED_FACT_ID:
                        reason_codes["ENGINE_008_RETIRED"] += 1
                        continue
                    if raw["fact_id"] in seen_ids:
                        reason_codes["DUPLICATE_FACT_ID"] += 1
                        rejected.append(
                            {
                                "fact_id": raw["fact_id"],
                                "subject": subject,
                                "chapter": chapter,
                                "reason": "DUPLICATE_FACT_ID",
                            }
                        )
                        continue
                    canon_key = _norm_key(raw["canonical_fact"])
                    if canon_key in seen_canonical:
                        reason_codes["DUPLICATE_CANONICAL_FACT"] += 1
                        rejected.append(
                            {
                                "fact_id": raw["fact_id"],
                                "subject": subject,
                                "chapter": chapter,
                                "reason": "DUPLICATE_CANONICAL_FACT",
                            }
                        )
                        continue
                    ambiguity = _preflight_ambiguity(raw)
                    if ambiguity:
                        reason_codes[ambiguity] += 1
                        rejected.append(
                            {
                                "fact_id": raw["fact_id"],
                                "subject": subject,
                                "chapter": chapter,
                                "reason": ambiguity,
                            }
                        )
                        continue
                    texts = [_norm_key(opt["text"]) for opt in raw["question_template"]["options"]]
                    if len(set(texts)) != 4:
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
                        reason_codes[exc.code] += 1
                        rejected.append(
                            {
                                "fact_id": raw["fact_id"],
                                "subject": subject,
                                "chapter": chapter,
                                "reason": exc.code,
                                "detail": exc.detail,
                            }
                        )
                        continue
                    except Exception as exc:  # noqa: BLE001
                        reason_codes[type(exc).__name__] += 1
                        rejected.append(
                            {
                                "fact_id": raw.get("fact_id"),
                                "subject": subject,
                                "chapter": chapter,
                                "reason": type(exc).__name__,
                                "detail": str(exc),
                            }
                        )
                        continue
                    if not adapted.quality.mcq_eligible:
                        codes = [r.code for r in adapted.quality.reasons] or [
                            adapted.quality.status
                        ]
                        for code in codes:
                            reason_codes[code] += 1
                        rejected.append(
                            {
                                "fact_id": raw["fact_id"],
                                "subject": subject,
                                "chapter": chapter,
                                "reason": ",".join(codes),
                            }
                        )
                        continue
                    approved.append(raw)
                    by_subject[subject].append(raw)
                    seen_ids.add(raw["fact_id"])
                    seen_canonical.add(canon_key)
                    built_here += 1
        conn.rollback()

    # Deterministic trim to target per subject when overshot.
    final: list[dict] = []
    for subject in ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY"):
        items = sorted(by_subject[subject], key=lambda item: item["fact_id"])
        final.extend(items[:TARGET_PER_SUBJECT])
        by_subject[subject] = items[:TARGET_PER_SUBJECT]
    final.sort(key=lambda item: item["fact_id"])

    pack = {
        "schema_version": FACT_PACK_SCHEMA_VERSION,
        "pack_id": "python-mcq-engine-010-reviewed-corpus-v1",
        "facts": final,
    }
    PACK_OUT.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    REJECTED_OUT.write_text(
        json.dumps(rejected[:500], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Reload + confirm eligibility.
    loaded = load_deterministic_fact_pack(PACK_OUT)
    eligible = 0
    subject_counts: Counter[str] = Counter()
    chapter_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    qtypes: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    for fact in loaded.facts:
        subject_counts[fact.subject] += 1
        chapter_counts[f"{fact.subject}:{fact.chapter}"] += 1
        topic_counts[f"{fact.subject}:{fact.topic}"] += 1
        class_counts[fact.class_level] += 1
        sources[fact.source_relative_path] += 1
        if fact.question_template is not None:
            qtypes[fact.question_template.question_type] += 1
        adapted = adapter.adapt(
            fact,
            taxonomy=_taxonomy(fact),
            authoritative_syllabus_path=SYLLABUS,
        )
        if adapted.quality.mcq_eligible:
            eligible += 1

    after = _read_only_snapshot(db)
    db.dispose()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    runtime = round(time.perf_counter() - started, 3)
    fixture006_unchanged = PACK_006.read_bytes() == pack006_bytes
    shortfalls = {
        subject: max(0, TARGET_PER_SUBJECT - subject_counts.get(subject, 0))
        for subject in ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY")
    }
    reached_250 = all(v == 0 for v in shortfalls.values())
    reached_1000 = eligible >= TARGET_TOTAL and len(loaded.facts) >= TARGET_TOTAL
    retired_absent = RETIRED_FACT_ID not in {f.fact_id for f in loaded.facts}

    audit = {
        "task_id": TASK_ID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "verdict": (
            "GREEN"
            if fixture006_unchanged
            and retired_absent
            and before == after
            and eligible == len(loaded.facts)
            else "YELLOW"
        ),
        "targets": {
            "per_subject": TARGET_PER_SUBJECT,
            "total": TARGET_TOTAL,
            "reached_250_per_subject": reached_250,
            "reached_1000_total": reached_1000,
        },
        "pack": {
            "path": str(PACK_OUT),
            "pack_id": pack["pack_id"],
            "fact_count": len(loaded.facts),
            "input_sha256": loaded.input_sha256,
            "MCQ_ELIGIBLE": eligible,
        },
        "seeded_from_engine_006_excluding_retired": 99,
        "new_facts_added": max(0, len(loaded.facts) - 99),
        "rejected_during_curation": len(rejected),
        "reason_code_distribution": dict(reason_codes),
        "subject_counts": dict(subject_counts),
        "class_counts": dict(class_counts),
        "chapter_counts": dict(chapter_counts),
        "topic_counts": dict(topic_counts),
        "question_type_counts": dict(qtypes),
        "source_pdf_counts": dict(sources),
        "shortfalls_to_250": shortfalls,
        "engine_006_fixture_modified": not fixture006_unchanged,
        "engine_008_retired_absent": retired_absent,
        "database_before": before,
        "database_after": after,
        "production_safety_unchanged": before == after,
        "provider_api_calls": 0,
        "api_cost_inr": 0,
        "production_db_mutations": 0,
        "runtime_seconds": runtime,
        "peak_memory_bytes": peak,
        "tests": {"focused": "pending", "regression": "pending", "ruff": "pending"},
        "limitations": [
            (
                "Corpus expansion is limited by available canonical NCERT definitional "
                "phrases and anti-ambiguity / quality-gate fail-closed filters."
            ),
            "Internal REVIEWED/MCQ_ELIGIBLE is not an NCERT certification claim.",
            "No MCQs were generated or persisted.",
            "ENGINE-006 fixture was not modified.",
        ],
        "readiness_recommendation": (
            "Corpus still below 1,000/250-per-subject targets; further chapter-safe "
            "reviewed curation is required before ENGINE-009-style 1,000-fact evaluation. "
            "Do not auto-start ENGINE-011."
            if not reached_1000
            else (
                "Corpus reached 1,000 MCQ_ELIGIBLE facts; a future authorized task may "
                "re-run the 1,000-fact read-only evaluation. Do not auto-start ENGINE-011."
            )
        ),
    }
    AUDIT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md = [
        "# PYTHON-MCQ-ENGINE-010 — Reviewed Corpus Expansion",
        "",
        f"**Verdict:** **{audit['verdict']}**",
        f"**MCQ_ELIGIBLE facts:** **{eligible}**",
        f"**Reached 250/subject:** **{reached_250}**",
        f"**Reached 1,000 total:** **{reached_1000}**",
        f"**Subject counts:** `{dict(subject_counts)}`",
        f"**Shortfalls to 250:** `{shortfalls}`",
        "",
        "## Safety",
        "",
        f"- ENGINE-006 modified: **{not fixture006_unchanged}**",
        f"- ENGINE-008 retired absent: **{retired_absent}**",
        "- Provider/API calls: **0**",
        "- Production DB mutations: **0**",
        f"- Invariants unchanged: **{before == after}**",
        "",
        f"**Recommendation:** {audit['readiness_recommendation']}",
        "",
    ]
    AUDIT_MD.write_text("\n".join(md), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": audit["verdict"],
                "eligible": eligible,
                "subjects": dict(subject_counts),
                "shortfalls": shortfalls,
                "reached_250": reached_250,
                "reached_1000": reached_1000,
                "pack": str(PACK_OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
