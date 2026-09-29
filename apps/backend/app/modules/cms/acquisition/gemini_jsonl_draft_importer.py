"""Gemini JSONL → TALOS CMS DRAFT importer (acquisition only).

Uses ContentWorkflowService.create_item — never submits, approves, or publishes.
Defaults to dry-run. Idempotent by slug = gemini-{external_question_id}.
Does not auto-create taxonomy; concept_id stays NULL unless exact concept match.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.modules.cms.models import ContentItem
from app.modules.cms.schemas.content_bodies import QuestionBody, assert_body_publishable
from app.modules.cms.schemas.question_evidence import NcertEvidence, ProvenanceBlock
from app.modules.cms.services.content_workflow_service import ContentWorkflowService

logger = get_logger("cms.acquisition.gemini_jsonl")

PROMPT_VERSION = "gemini-jsonl-acq-v1"  # content_versions.prompt_version VARCHAR(20)
IMPORT_TAG = "gemini-jsonl-import"
CONCEPT_UNRESOLVED_TAG = "concept:unresolved"
ECAEP_INTAKE_TAG = "ecaep:intake-draft-only"
NCERT_NOT_VERIFIED_TAG = "ncert:NOT_VERIFIED"
NUMERICAL_UNSTRUCTURED_TAG = "numerical:unstructured"

_DIFFICULTIES = frozenset({"easy", "medium", "hard"})

# ---------------------------------------------------------------------------
# Canonical question_type representation (CMS)
# ---------------------------------------------------------------------------
# QuestionBody has NO question_type field; the student CMS API hardcodes
# ``"question_type": "MCQ"`` (format), not cognitive type.
#
# Cognitive / acquisition type is stored on ContentItem.tags as:
#   ``question_type:<canonical>``
# matching T6D/physics acquisition banks and aligned with P2.3 vocabulary
# (``app.modules.cms.mcq.p2_3.schemas.QuestionType``) plus Mode-B extension
# ``comparison`` (preserved as its own tag value — NOT collapsed to conceptual).
#
# Acquisition → canonical map is identity for all supported labels below.
# Unsupported labels are rejected (never silently remapped to conceptual).
# ---------------------------------------------------------------------------
ACQUISITION_TO_CANONICAL_QUESTION_TYPE: dict[str, str] = {
    "conceptual": "conceptual",
    "numerical": "numerical",
    "factual": "factual",  # P2.3 QuestionType
    "application": "application",  # P2.3 QuestionType
    "statement_based": "statement_based",  # P2.3 QuestionType
    "assertion_reasoning": "assertion_reasoning",  # P2.3 QuestionType
    "match_relationship": "match_relationship",  # P2.3 QuestionType
    # Mode-B Biology acquisition extension — stored as tag value "comparison".
    # Not in P2.3 Literal; ContentItem.tags (string array) is the canonical store.
    "comparison": "comparison",
}
_QUESTION_TYPES = frozenset(ACQUISITION_TO_CANONICAL_QUESTION_TYPE.keys())


def map_acquisition_question_type(acquisition_type: str) -> str:
    """Map acquisition question_type → canonical CMS tag value.

    Raises ValueError for unsupported types (callers must reject, not remap).
    """
    key = str(acquisition_type or "").strip().lower()
    if key not in ACQUISITION_TO_CANONICAL_QUESTION_TYPE:
        raise ValueError(f"unsupported_acquisition_question_type:{key or '<empty>'}")
    return ACQUISITION_TO_CANONICAL_QUESTION_TYPE[key]


@dataclass
class TaxonomyResolution:
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    chapter_id: uuid.UUID | None = None
    chapter_name: str | None = None
    chapter_code: str | None = None
    topic_id: uuid.UUID | None = None
    topic_name: str | None = None
    topic_code: str | None = None
    concept_id: uuid.UUID | None = None
    concept_name: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class RecordOutcome:
    external_question_id: str
    status: str  # created | already_exists | rejected | would_create | failed
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    slug: str | None = None
    item_id: str | None = None
    concept_id: str | None = None


@dataclass
class ImportReport:
    batch_id: str | None
    input_path: str
    dry_run: bool
    input_count: int = 0
    would_create: int = 0
    created: int = 0
    already_exists: int = 0
    rejected: int = 0
    failed: int = 0
    warning_count: int = 0
    outcomes: list[RecordOutcome] = field(default_factory=list)
    taxonomy_summary: dict[str, Any] = field(default_factory=dict)
    db_writes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "input_path": self.input_path,
            "dry_run": self.dry_run,
            "input_count": self.input_count,
            "would_create": self.would_create,
            "created": self.created,
            "already_exists": self.already_exists,
            "rejected": self.rejected,
            "failed": self.failed,
            "warning_count": self.warning_count,
            "db_writes": self.db_writes,
            "taxonomy_summary": self.taxonomy_summary,
            "rejected_ids": [o.external_question_id for o in self.outcomes if o.status == "rejected"],
            "warning_ids": [o.external_question_id for o in self.outcomes if o.warnings],
            "outcomes": [
                {
                    "external_question_id": o.external_question_id,
                    "status": o.status,
                    "reasons": o.reasons,
                    "warnings": o.warnings,
                    "slug": o.slug,
                    "item_id": o.item_id,
                    "concept_id": o.concept_id,
                }
                for o in self.outcomes
            ],
        }


def import_slug(external_question_id: str) -> str:
    eid = (external_question_id or "").strip()
    return f"gemini-{eid}"[:320]


def options_dict_to_list(options: Any) -> list[dict[str, str]]:
    if not isinstance(options, dict):
        raise ValueError("options must be an object with keys A–D")
    if set(options.keys()) != {"A", "B", "C", "D"}:
        raise ValueError("options must have exactly keys A, B, C, D")
    return [{"label": lab, "text": str(options[lab]).strip()} for lab in ("A", "B", "C", "D")]


def detect_answer_explanation_contradiction(
    *,
    correct_option: str,
    options: dict[str, str],
    explanation: str,
) -> str | None:
    """Return a reason if explanation clearly identifies a different option."""
    expl = explanation or ""
    expl_l = expl.lower()
    correct = correct_option.strip().upper()

    for lab in ("A", "B", "C", "D"):
        if lab == correct:
            continue
        patterns = [
            rf"\bcorrect(?:\s+option)?\s+is\s+{lab}\b",
            rf"\banswer\s+is\s+(?:option\s+)?{lab}\b",
            rf"\boption\s+{lab}\s+is\s+correct\b",
            rf"\btherefore\s+option\s+{lab}\b",
            rf"\bthus[,.]?\s+option\s+{lab}\b",
        ]
        for pat in patterns:
            if re.search(pat, expl_l, flags=re.I):
                return f"answer_explanation_contradiction: explanation identifies {lab}, correct_option={correct}"

    # Ratio conclusion: "... ratio ... is N : M" must agree with correct option text
    m = re.search(r"\bratio\b[\s\S]{0,160}?\bis\s+\$?(\d+)\s*:\s*(\d+)\$?", expl_l)
    if not m:
        m = re.search(r"\bratio\s+is\s+\$?(\d+)\s*:\s*(\d+)\$?", expl_l)
    if m:
        concluded = f"{m.group(1)}:{m.group(2)}"
        concluded_spaced = f"{m.group(1)} : {m.group(2)}"
        matching_labs = []
        for lab, text in options.items():
            compact = re.sub(r"[\s$]+", "", text)
            target = re.sub(r"[\s$]+", "", concluded_spaced)
            if target in compact or concluded in compact:
                matching_labs.append(lab)
        if matching_labs and correct not in matching_labs:
            return (
                f"answer_explanation_contradiction: explanation concludes {concluded_spaced} "
                f"(options {matching_labs}), correct_option={correct}"
            )

    return None


def validate_gemini_record(raw: Any) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Validate one Gemini JSONL object. Returns (normalized, errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(raw, dict):
        return None, ["record_not_object"], warnings

    eid = str(raw.get("external_question_id") or "").strip()
    if not eid:
        errors.append("missing_external_question_id")

    stem = str(raw.get("stem") or "").strip()
    if not stem:
        errors.append("missing_stem")

    explanation = str(raw.get("explanation") or "").strip()
    if not explanation:
        errors.append("missing_explanation")

    difficulty = str(raw.get("difficulty") or "").strip().lower()
    if difficulty not in _DIFFICULTIES:
        errors.append("invalid_difficulty")

    qtype_raw = str(raw.get("question_type") or "").strip().lower()
    acquisition_qtype: str | None = None
    canonical_qtype: str | None = None
    if qtype_raw:
        if qtype_raw not in _QUESTION_TYPES:
            errors.append("invalid_question_type")
        else:
            acquisition_qtype = qtype_raw
            canonical_qtype = map_acquisition_question_type(qtype_raw)

    try:
        opt_list = options_dict_to_list(raw.get("options"))
    except ValueError as exc:
        errors.append(str(exc))
        opt_list = []

    if opt_list:
        texts = [o["text"] for o in opt_list]
        if any(not t for t in texts):
            errors.append("empty_option_text")
        if len({t.lower() for t in texts}) != 4:
            errors.append("duplicate_option_text")

    correct = str(raw.get("correct_option") or "").strip().upper()
    if correct not in {"A", "B", "C", "D"}:
        errors.append("invalid_correct_option")
    elif opt_list and correct not in {o["label"] for o in opt_list}:
        errors.append("correct_option_not_in_options")

    source = raw.get("source")
    if not isinstance(source, dict):
        errors.append("missing_source")
        source = {}
    else:
        if not str(source.get("source_file") or "").strip():
            errors.append("missing_source_file")
        if not str(source.get("source_evidence") or "").strip():
            errors.append("missing_source_evidence")
        page = source.get("page_number")
        if page is not None and not isinstance(page, int):
            errors.append("invalid_page_number_type")

    provenance = raw.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("missing_provenance")
        provenance = {}
    else:
        if not str(provenance.get("provider") or "").strip():
            errors.append("missing_provenance_provider")
        if not str(provenance.get("generation_source") or "").strip():
            errors.append("missing_provenance_generation_source")
        if not str(provenance.get("generation_batch_id") or "").strip():
            errors.append("missing_provenance_batch_id")

    if errors:
        return None, errors, warnings

    options_map = {o["label"]: o["text"] for o in opt_list}
    contradiction = detect_answer_explanation_contradiction(
        correct_option=correct,
        options=options_map,
        explanation=explanation,
    )
    if contradiction:
        errors.append(contradiction)
        return None, errors, warnings

    numerical = raw.get("numerical") if isinstance(raw.get("numerical"), dict) else {}
    is_numerical = bool(numerical.get("is_numerical")) or acquisition_qtype == "numerical"
    if canonical_qtype is None:
        # Missing acquisition type: infer from numerical flag (Physics Mode-A default path).
        acquisition_qtype = "numerical" if is_numerical else "conceptual"
        canonical_qtype = map_acquisition_question_type(acquisition_qtype)
    calc = numerical.get("calculation_check")
    if is_numerical:
        if calc is None or (isinstance(calc, str) and not calc.strip()):
            warnings.append("numerical_missing_calculation_check")
        elif isinstance(calc, str):
            warnings.append("numerical_evidence_unstructured")
        elif not isinstance(calc, dict):
            warnings.append("numerical_evidence_unstructured")

    visual = raw.get("visual") if isinstance(raw.get("visual"), dict) else {}
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []

    normalized = {
        "external_question_id": eid,
        "subject": str(raw.get("subject") or "").strip(),
        "class_level": str(raw.get("class_level") or "").strip(),
        "chapter": str(raw.get("chapter") or "").strip(),
        "topic": str(raw.get("topic") or "").strip(),
        "concept": str(raw.get("concept") or "").strip(),
        "acquisition_question_type": acquisition_qtype,
        "question_type": canonical_qtype,
        "difficulty": difficulty,
        "stem": stem,
        "options_list": opt_list,
        "options_map": options_map,
        "correct_option": correct,
        "explanation": explanation,
        "source": source,
        "provenance": provenance,
        "visual": visual,
        "numerical": numerical,
        "is_numerical": is_numerical,
        "calculation_check": calc,
        "tags": [str(t) for t in tags if str(t).strip()],
    }
    return normalized, errors, warnings


def build_question_body(normalized: dict[str, Any]) -> dict[str, Any]:
    source = normalized["source"]
    provenance = normalized["provenance"]
    source_file = str(source.get("source_file") or "").strip()
    batch_id = str(provenance.get("generation_batch_id") or "").strip()

    body: dict[str, Any] = {
        "stem": normalized["stem"],
        "options": normalized["options_list"],
        "correct_option": normalized["correct_option"],
        "explanation": normalized["explanation"],
        "difficulty": normalized["difficulty"],
        "ncert_evidence": {
            "verification_level": "NOT_VERIFIED",
            "source_document": source_file,
            "class_level": normalized["class_level"] or "unknown",
            "chapter": str(source.get("chapter") or normalized["chapter"] or "unknown"),
            "section": (str(source.get("section")).strip() if source.get("section") else None),
            "page_number": source.get("page_number"),
            "source_excerpt": str(source.get("source_evidence") or "").strip(),
            "verification_method": "gemini_jsonl_acquisition_unverified",
            "source_pdf_relpath": f"StudyMaterial/{source_file}" if source_file else None,
        },
        "provenance": {
            "origin": "ai_generated",
            "source": str(provenance.get("generation_source") or "attached_ncert_pdf"),
            "batch_id": batch_id or None,
            "validation_process": "UNVERIFIED_ACQUISITION",
            "verification_process": None,
            "class_level": normalized["class_level"] or None,
            "chapter": normalized["chapter"] or None,
            "section": (str(source.get("section")).strip() if source.get("section") else None),
        },
    }

    # Validate evidence contracts early
    NcertEvidence.model_validate(body["ncert_evidence"])
    ProvenanceBlock.model_validate(body["provenance"])

    if normalized["is_numerical"]:
        calc = normalized.get("calculation_check")
        raw_calc: dict[str, Any]
        if isinstance(calc, dict):
            raw_calc = dict(calc)
        else:
            raw_calc = {"raw": calc, "status": "UNSTRUCTURED_ACQUISITION"}
        body["calculation_check"] = raw_calc
        body["numerical_evidence"] = {
            "status": "NUMERICAL_INCOMPLETE",
            "calculation_check": raw_calc,
        }

    visual = normalized.get("visual") or {}
    if visual.get("visual_required"):
        body["diagram_description"] = visual.get("visual_description")
        body["visual_spec"] = visual

    QuestionBody.model_validate(body)
    return assert_body_publishable("QUESTION", body)


def build_import_tags(normalized: dict[str, Any], tax: TaxonomyResolution) -> list[str]:
    provenance = normalized["provenance"]
    batch_id = str(provenance.get("generation_batch_id") or "").strip()
    tags = list(normalized.get("tags") or [])
    canonical_qtype = str(normalized.get("question_type") or "").strip()
    acquisition_qtype = str(normalized.get("acquisition_question_type") or canonical_qtype).strip()
    extras = [
        IMPORT_TAG,
        ECAEP_INTAKE_TAG,
        NCERT_NOT_VERIFIED_TAG,
        f"external_id:{normalized['external_question_id']}",
        f"provider:{str(provenance.get('provider') or 'gemini').strip()}",
    ]
    if canonical_qtype:
        # Canonical cognitive type (T6D / P2.3-aligned tag store).
        extras.append(f"question_type:{canonical_qtype}")
    if acquisition_qtype and acquisition_qtype != canonical_qtype:
        # Preserve original acquisition label when mapped (deterministic, non-silent).
        extras.append(f"acquisition_question_type:{acquisition_qtype}")
    if batch_id:
        extras.append(f"batch:{batch_id}")
        extras.append(batch_id)
    if normalized.get("class_level"):
        extras.append(f"class:{normalized['class_level']}")
    if normalized.get("subject"):
        extras.append(f"gemini_subject:{normalized['subject']}")
    if normalized.get("chapter"):
        extras.append(f"gemini_chapter:{normalized['chapter']}")
    if normalized.get("topic"):
        extras.append(f"gemini_topic:{normalized['topic']}")
    if normalized.get("concept"):
        extras.append(f"gemini_concept:{normalized['concept']}")
    if tax.chapter_code:
        extras.append(f"talos_chapter:{tax.chapter_code}")
    if tax.topic_code:
        extras.append(f"talos_topic:{tax.topic_code}")
    if tax.concept_id is None:
        extras.append(CONCEPT_UNRESOLVED_TAG)
    # Free-text / incomplete numerical payloads are DRAFT-ok but not publish-complete.
    if normalized.get("is_numerical"):
        extras.append(NUMERICAL_UNSTRUCTURED_TAG)

    seen: set[str] = set()
    out: list[str] = []
    for t in tags + extras:
        t = str(t).strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def load_jsonl(path: Path) -> tuple[list[Any], list[str]]:
    """Load JSONL; returns (records, malformed_line_errors)."""
    records: list[Any] = []
    malformed: list[str] = []
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            malformed.append(f"line_{i}: {exc}")
    return records, malformed


@dataclass
class _PreparedCreate:
    external_question_id: str
    slug: str
    title: str
    body: dict[str, Any]
    tags: list[str]
    concept_id: uuid.UUID | None
    model_used: str
    warnings: list[str]
    tax_notes: list[str]


class GeminiJsonlDraftImporter:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.workflow = ContentWorkflowService(session)

    async def resolve_taxonomy(self, normalized: dict[str, Any]) -> TaxonomyResolution:
        tax = TaxonomyResolution()
        subject_name = normalized.get("subject") or ""
        chapter_name = normalized.get("chapter") or ""
        concept_name = normalized.get("concept") or ""

        if not subject_name:
            tax.notes.append("subject_missing")
            return tax

        # Raw SQL avoids ORM attrs not yet migrated (e.g. chapters.class_level on dirty trees).
        from sqlalchemy import text

        subj = (
            await self.session.execute(
                text(
                    """
                    SELECT id, name, code FROM academic.subjects
                    WHERE deleted_at IS NULL AND name ILIKE :name
                    LIMIT 1
                    """
                ),
                {"name": subject_name},
            )
        ).mappings().first()
        if not subj:
            tax.notes.append(f"subject_unresolved:{subject_name}")
            return tax
        tax.subject_id = subj["id"]
        tax.subject_name = subj["name"]

        chapter = (
            await self.session.execute(
                text(
                    """
                    SELECT id, name, code FROM academic.chapters
                    WHERE deleted_at IS NULL AND subject_id = :sid AND name ILIKE :name
                    LIMIT 1
                    """
                ),
                {"sid": tax.subject_id, "name": chapter_name},
            )
        ).mappings().first()

        topic = None
        if chapter:
            tax.chapter_id = chapter["id"]
            tax.chapter_name = chapter["name"]
            tax.chapter_code = chapter["code"]
            topic = (
                await self.session.execute(
                    text(
                        """
                        SELECT id, name, code, chapter_id FROM academic.topics
                        WHERE deleted_at IS NULL AND chapter_id = :cid AND name ILIKE :name
                        LIMIT 1
                        """
                    ),
                    {"cid": tax.chapter_id, "name": chapter_name},
                )
            ).mappings().first()
        else:
            topic = (
                await self.session.execute(
                    text(
                        """
                        SELECT t.id, t.name, t.code, t.chapter_id,
                               ch.id AS ch_id, ch.name AS ch_name, ch.code AS ch_code
                        FROM academic.topics t
                        JOIN academic.chapters ch ON ch.id = t.chapter_id
                        WHERE t.deleted_at IS NULL AND ch.deleted_at IS NULL
                          AND ch.subject_id = :sid AND t.name ILIKE :name
                        LIMIT 1
                        """
                    ),
                    {"sid": tax.subject_id, "name": chapter_name},
                )
            ).mappings().first()
            if topic:
                tax.chapter_id = topic["ch_id"]
                tax.chapter_name = topic["ch_name"]
                tax.chapter_code = topic["ch_code"]
                tax.notes.append(f"chapter_via_topic:{topic['ch_name']}")
            else:
                tax.notes.append(f"chapter_unresolved:{chapter_name}")

        if topic:
            tax.topic_id = topic["id"]
            tax.topic_name = topic["name"]
            tax.topic_code = topic["code"]
        elif tax.chapter_id and normalized.get("topic"):
            topic = (
                await self.session.execute(
                    text(
                        """
                        SELECT id, name, code FROM academic.topics
                        WHERE deleted_at IS NULL AND chapter_id = :cid AND name ILIKE :name
                        LIMIT 1
                        """
                    ),
                    {"cid": tax.chapter_id, "name": normalized["topic"]},
                )
            ).mappings().first()
            if topic:
                tax.topic_id = topic["id"]
                tax.topic_name = topic["name"]
                tax.topic_code = topic["code"]
            else:
                tax.notes.append(f"topic_unresolved:{normalized['topic']}")
        elif tax.chapter_id:
            tax.notes.append("topic_unresolved")

        if tax.topic_id and concept_name:
            concept = (
                await self.session.execute(
                    text(
                        """
                        SELECT id, name FROM academic.concepts
                        WHERE deleted_at IS NULL AND topic_id = :tid AND name ILIKE :name
                        LIMIT 1
                        """
                    ),
                    {"tid": tax.topic_id, "name": concept_name},
                )
            ).mappings().first()
            if concept:
                tax.concept_id = concept["id"]
                tax.concept_name = concept["name"]
            else:
                tax.notes.append("concept_unresolved_exact")
        else:
            tax.notes.append("concept_unresolved_exact")

        return tax

    async def _existing_by_slug(self, slug: str) -> ContentItem | None:
        result = await self.session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.slug == slug, ContentItem.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def run(
        self,
        *,
        input_path: Path,
        author_id: uuid.UUID,
        dry_run: bool = True,
        batch_id: str | None = None,
        limit: int | None = None,
        atomic: bool = True,
        supersede_existing: bool = False,
        lineage_path: Path | None = None,
    ) -> ImportReport:
        """Import Gemini JSONL as DRAFT.

        dry_run=True: validate/transform only (default).
        dry_run=False + atomic=True (default for commit): flush all creates then
        single commit; any DB failure rolls back the whole create set.
        dry_run=False + atomic=False: legacy per-row create_item(commit=True).
        supersede_existing=True: explicit repaired-batch install mode (see
        gemini_jsonl_supersede). Ordinary --commit create-only semantics unchanged.
        """
        if supersede_existing:
            from app.modules.cms.acquisition.gemini_jsonl_supersede import run_supersede

            return await run_supersede(
                self,
                input_path=input_path,
                author_id=author_id,
                dry_run=dry_run,
                batch_id=batch_id,
                limit=limit,
                lineage_path=lineage_path,
            )

        report = ImportReport(
            batch_id=batch_id,
            input_path=str(input_path),
            dry_run=dry_run,
        )
        records, malformed = load_jsonl(input_path)
        for err in malformed:
            report.rejected += 1
            report.outcomes.append(
                RecordOutcome(
                    external_question_id=f"MALFORMED:{err}",
                    status="rejected",
                    reasons=[f"malformed_jsonl:{err}"],
                )
            )

        if limit is not None:
            records = records[: max(0, limit)]
        report.input_count = len(records)

        tax_snapshot: TaxonomyResolution | None = None
        prepared: list[_PreparedCreate] = []

        # Phase 1 — validate / transform / taxonomy / idempotency (no writes)
        for raw in records:
            normalized, errors, warnings = validate_gemini_record(raw)
            eid = str((raw or {}).get("external_question_id") or "UNKNOWN") if isinstance(raw, dict) else "UNKNOWN"
            if errors or normalized is None:
                report.rejected += 1
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=eid,
                        status="rejected",
                        reasons=errors or ["invalid_record"],
                        warnings=warnings,
                    )
                )
                continue

            if batch_id is None:
                batch_id = str(normalized["provenance"].get("generation_batch_id") or "").strip() or None
                report.batch_id = batch_id
            elif str(normalized["provenance"].get("generation_batch_id") or "").strip() not in ("", batch_id):
                warnings.append(
                    f"batch_id_mismatch_record={normalized['provenance'].get('generation_batch_id')}"
                )

            try:
                body = build_question_body(normalized)
            except Exception as exc:  # noqa: BLE001
                report.rejected += 1
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=normalized["external_question_id"],
                        status="rejected",
                        reasons=[f"body_transform:{exc}"],
                        warnings=warnings,
                    )
                )
                continue

            tax = await self.resolve_taxonomy(normalized)
            tax_snapshot = tax
            tags = build_import_tags(normalized, tax)
            if warnings and NUMERICAL_UNSTRUCTURED_TAG not in tags and any(
                w.startswith("numerical") for w in warnings
            ):
                tags.append(NUMERICAL_UNSTRUCTURED_TAG)

            slug = import_slug(normalized["external_question_id"])
            existing = await self._existing_by_slug(slug)
            if existing:
                report.already_exists += 1
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=normalized["external_question_id"],
                        status="already_exists",
                        slug=slug,
                        item_id=str(existing.id),
                        concept_id=str(existing.concept_id) if existing.concept_id else None,
                        warnings=warnings,
                        reasons=["slug_exists"],
                    )
                )
                if warnings:
                    report.warning_count += 1
                continue

            if warnings:
                report.warning_count += 1

            model_used = str(normalized["provenance"].get("model") or "gemini").strip() or "gemini"
            model_used = model_used[:20]
            title = f"{normalized['external_question_id']}: {normalized['stem'][:200]}"
            prepared.append(
                _PreparedCreate(
                    external_question_id=normalized["external_question_id"],
                    slug=slug,
                    title=title[:300],
                    body=body,
                    tags=tags,
                    concept_id=tax.concept_id,
                    model_used=model_used,
                    warnings=warnings,
                    tax_notes=list(tax.notes),
                )
            )

        if dry_run:
            report.would_create = len(prepared)
            for p in prepared:
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=p.external_question_id,
                        status="would_create",
                        slug=p.slug,
                        concept_id=str(p.concept_id) if p.concept_id else None,
                        warnings=p.warnings,
                        reasons=p.tax_notes,
                    )
                )
            report.taxonomy_summary = _tax_summary(tax_snapshot)
            return report

        if not prepared:
            report.taxonomy_summary = _tax_summary(tax_snapshot)
            return report

        # Phase 2 — write DRAFT rows
        if atomic:
            await self._commit_atomic(prepared, author_id=author_id, report=report)
        else:
            await self._commit_per_row(prepared, author_id=author_id, report=report)

        report.taxonomy_summary = _tax_summary(tax_snapshot)
        return report

    async def _commit_atomic(
        self,
        prepared: list[_PreparedCreate],
        *,
        author_id: uuid.UUID,
        report: ImportReport,
    ) -> None:
        """Flush all creates inside one SAVEPOINT; release then commit parent once.

        On any failure the SAVEPOINT is rolled back so earlier flushes do not remain.
        Still uses ContentWorkflowService.create_item(..., commit=False) for validation.
        """
        nested = await self.session.begin_nested()
        try:
            for p in prepared:
                item = await self.workflow.create_item(
                    content_type="QUESTION",
                    concept_id=p.concept_id,
                    title=p.title,
                    slug=p.slug,
                    tags=p.tags,
                    language="en",
                    body=p.body,
                    author_id=author_id,
                    model_used=p.model_used,
                    prompt_version=PROMPT_VERSION,
                    commit=False,
                )
                if item.status != "DRAFT":
                    raise RuntimeError(f"unexpected_status:{item.status}")
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=p.external_question_id,
                        status="created",
                        slug=p.slug,
                        item_id=str(item.id),
                        concept_id=str(item.concept_id) if item.concept_id else None,
                        warnings=p.warnings,
                        reasons=p.tax_notes,
                    )
                )
            await nested.commit()
            await self.session.commit()
            report.created = len(prepared)
            report.db_writes = len(prepared)
        except Exception as exc:  # noqa: BLE001
            if nested.is_active:
                await nested.rollback()
            report.created = 0
            report.db_writes = 0
            report.failed = len(prepared)
            report.outcomes = [o for o in report.outcomes if o.status != "created"]
            for p in prepared:
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=p.external_question_id,
                        status="failed",
                        slug=p.slug,
                        reasons=[f"atomic_batch_failed:{exc}"],
                        warnings=p.warnings,
                    )
                )
            logger.error("gemini_jsonl_atomic_batch_failed", error=str(exc), count=len(prepared))
            raise

    async def _commit_per_row(
        self,
        prepared: list[_PreparedCreate],
        *,
        author_id: uuid.UUID,
        report: ImportReport,
    ) -> None:
        """Legacy escape hatch — each create_item commits independently."""
        for p in prepared:
            try:
                item = await self.workflow.create_item(
                    content_type="QUESTION",
                    concept_id=p.concept_id,
                    title=p.title,
                    slug=p.slug,
                    tags=p.tags,
                    language="en",
                    body=p.body,
                    author_id=author_id,
                    model_used=p.model_used,
                    prompt_version=PROMPT_VERSION,
                    commit=True,
                )
                if item.status != "DRAFT":
                    raise RuntimeError(f"unexpected_status:{item.status}")
                report.created += 1
                report.db_writes += 1
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=p.external_question_id,
                        status="created",
                        slug=p.slug,
                        item_id=str(item.id),
                        concept_id=str(item.concept_id) if item.concept_id else None,
                        warnings=p.warnings,
                        reasons=p.tax_notes,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                report.failed += 1
                report.outcomes.append(
                    RecordOutcome(
                        external_question_id=p.external_question_id,
                        status="failed",
                        slug=p.slug,
                        reasons=[f"create_failed:{exc}"],
                        warnings=p.warnings,
                    )
                )
                logger.error("gemini_jsonl_create_failed", error=str(exc), slug=p.slug)
                raise


def _tax_summary(tax: TaxonomyResolution | None) -> dict[str, Any]:
    if not tax:
        return {"subject": "unresolved", "chapter": "unresolved", "topic": "unresolved", "concept_id": None}
    return {
        "subject": tax.subject_name or "unresolved",
        "chapter": tax.chapter_name or "unresolved",
        "chapter_code": tax.chapter_code,
        "topic": tax.topic_name or "unresolved",
        "topic_code": tax.topic_code,
        "concept_id": str(tax.concept_id) if tax.concept_id else None,
        "notes": tax.notes,
    }


def format_console_report(report: ImportReport) -> str:
    rejected_ids = [o.external_question_id for o in report.outcomes if o.status == "rejected"]
    warn_notes = sorted({w for o in report.outcomes for w in o.warnings})
    tax = report.taxonomy_summary
    rejected_lines = [f"  - {rid}" for rid in rejected_ids] or ["  (none)"]
    warning_lines = [f"  - {w}" for w in warn_notes] or ["  (none)"]
    lines = [
        f"Batch: {report.batch_id or '(unknown)'}",
        f"Input: {report.input_count}",
        f"Would create: {report.would_create}",
        f"Created: {report.created}",
        f"Already exists: {report.already_exists}",
        f"Rejected: {report.rejected}",
        f"Failed: {report.failed}",
        f"Validation warnings: {report.warning_count}",
        "Rejected IDs:",
        *rejected_lines,
        "Warnings:",
        *warning_lines,
        "Taxonomy:",
        f"  - subject: {tax.get('subject')}",
        f"  - chapter: {tax.get('chapter')} ({tax.get('chapter_code')})",
        f"  - topic: {tax.get('topic')} ({tax.get('topic_code')})",
        f"  - concept_id: {tax.get('concept_id')}",
        f"Database writes: {report.db_writes}",
        f"Mode: {'DRY RUN' if report.dry_run else 'COMMIT'}",
    ]
    supersede = tax.get("supersede") if isinstance(tax, dict) else None
    if isinstance(supersede, dict):
        lines.extend(
            [
                "Supersede:",
                f"  - lineage: {supersede.get('lineage_path')}",
                f"  - would_update: {supersede.get('would_update', 0)}",
                f"  - updated: {supersede.get('updated', 0)}",
                f"  - would_create_replacement: {supersede.get('would_create_replacement', 0)}",
                f"  - created_replacement: {supersede.get('created_replacement', 0)}",
                f"  - would_supersede: {supersede.get('would_supersede', 0)}",
                f"  - superseded: {supersede.get('superseded', 0)}",
                f"  - unchanged: {supersede.get('unchanged', 0)}",
            ]
        )
    return "\n".join(lines)


async def _resolve_author_id(session: AsyncSession) -> uuid.UUID:
    from app.modules.identity.models.user import User

    result = await session.execute(select(User.id).where(User.email == "content-seed@trinetra.local").limit(1))
    author_id = result.scalar_one_or_none()
    if author_id is None:
        result = await session.execute(select(User.id).limit(1))
        author_id = result.scalar_one_or_none()
    if author_id is None:
        raise RuntimeError("No users in database — seed identity before import")
    return author_id


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Import Gemini JSONL MCQs as TALOS DRAFT (never publish)")
    p.add_argument("--input", required=True, type=Path, help="Path to questions.jsonl")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only; no DB writes (default when --commit is omitted)",
    )
    p.add_argument("--commit", action="store_true", help="Write DRAFT rows via ContentWorkflowService")
    p.add_argument(
        "--supersede-existing",
        action="store_true",
        help=(
            "Explicit repaired-batch install: update stable DRAFT IDs and supersede "
            "mapped originals with replacement DRAFTs. Requires lineage file. "
            "Does not change ordinary --commit create-only semantics."
        ),
    )
    p.add_argument(
        "--lineage",
        type=Path,
        default=None,
        help="replacement_lineage.json or repair_results.json (default: beside --input)",
    )
    p.add_argument(
        "--atomic",
        action="store_true",
        default=True,
        help="Commit all creates in one transaction (default with --commit)",
    )
    p.add_argument(
        "--no-atomic",
        action="store_true",
        help="Legacy per-row commits (not recommended)",
    )
    p.add_argument("--batch-id", default=None, help="Optional expected/override batch id for reporting")
    p.add_argument("--limit", type=int, default=None, help="Optional max records to process")
    p.add_argument("--verbose", action="store_true", help="Print JSON report")
    return p


def _resolve_input_path(raw: Path) -> Path:
    if raw.is_file():
        return raw
    here = Path(__file__).resolve()
    # acquisition → cms → modules → app → backend → apps → repo
    repo_root = here.parents[6] if len(here.parents) > 6 else here.parents[-1]
    backend_root = here.parents[4] if len(here.parents) > 4 else Path.cwd()
    candidates = [
        raw,
        Path.cwd() / raw,
        backend_root / raw,
        repo_root / raw,
        repo_root / "docs" / "acquisition" / "batches" / raw.name,
    ]
    for c in candidates:
        if c.is_file():
            return c
    return raw


async def async_main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.commit and args.dry_run:
        print("ERROR: pass only one of --dry-run or --commit", file=sys.stderr)
        return 2
    dry_run = not bool(args.commit)
    atomic = not bool(args.no_atomic)

    input_path = _resolve_input_path(args.input)
    if not input_path.is_file():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 2

    import app.modules.academic.models  # noqa: F401
    import app.modules.cms.models  # noqa: F401
    import app.modules.knowledge.models  # noqa: F401
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        author_id = await _resolve_author_id(session)
        importer = GeminiJsonlDraftImporter(session)
        report = await importer.run(
            input_path=input_path,
            author_id=author_id,
            dry_run=dry_run,
            batch_id=args.batch_id,
            limit=args.limit,
            atomic=atomic,
            supersede_existing=bool(args.supersede_existing),
            lineage_path=args.lineage,
        )

    print(format_console_report(report))
    if args.verbose:
        print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.failed == 0 else 1


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(asyncio.run(async_main(argv)))


if __name__ == "__main__":
    main()
