"""Fail-closed, read-only loader for reviewed deterministic NCERT fact packs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.modules.cms.schemas.deterministic_fact_pack import (
    DeterministicFact,
    DeterministicFactPack,
    compute_stable_fact_id,
)
from app.modules.cms.syllabus import assert_blueprint_neet_syllabus_scope
from app.modules.ingestion.services.ncert_canonical_source import (
    NcertSourceError,
    validate_ncert_generation_source,
)

_WS = re.compile(r"\s+")
_REVIEW_RANK = {
    "EXTRACTED": 0,
    "REVIEW_REQUIRED": 0,
    "REVIEWED": 1,
    "VERIFIED": 2,
    "REJECTED": -1,
}


class FactPackLoadError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class LoadedFactPack:
    schema_version: str
    pack_id: str
    facts: tuple[DeterministicFact, ...]
    input_path: Path
    input_sha256: str
    read_only: bool = True
    provider_api_calls: int = 0
    production_db_mutations: int = 0


def _normalise(value: str) -> str:
    return _WS.sub(" ", value or "").strip().casefold()


def _contains_text(haystack: str, needle: str) -> bool:
    return bool(_normalise(needle)) and _normalise(needle) in _normalise(haystack)


def extract_ncert_source_text(pdf_path: Path, page_number: int | None) -> str:
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        if page_number is not None:
            index = page_number - 1
            if index < 0 or index >= doc.page_count:
                raise FactPackLoadError(
                    "NCERT_PAGE_OUT_OF_RANGE",
                    f"page {page_number} outside PDF page count {doc.page_count}",
                )
            return doc.load_page(index).get_text("text") or ""
        return "\n".join(doc.load_page(index).get_text("text") or "" for index in range(doc.page_count))
    finally:
        doc.close()


def _syllabus_constraints(fact: DeterministicFact) -> dict[str, Any]:
    return {"neet_ug_2026": fact.syllabus_binding.model_dump(exclude_none=True)}


def load_deterministic_fact_pack(
    path: str | Path,
    *,
    source_root: Path | None = None,
    minimum_review_status: str = "REVIEWED",
) -> LoadedFactPack:
    """Load and verify an entire pack without DB, network, provider, or file writes."""
    if minimum_review_status not in _REVIEW_RANK:
        raise FactPackLoadError(
            "INVALID_MINIMUM_REVIEW_STATUS",
            f"unsupported minimum review status: {minimum_review_status}",
        )

    input_path = Path(path)
    if input_path.suffix.lower() != ".json":
        raise FactPackLoadError("MALFORMED_FACT_PACK", "fact pack must be a JSON file")
    try:
        raw_bytes = input_path.read_bytes()
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FactPackLoadError("MALFORMED_FACT_PACK", type(exc).__name__) from exc
    try:
        pack = DeterministicFactPack.model_validate(payload)
    except ValidationError as exc:
        raise FactPackLoadError("FACT_PACK_SCHEMA_INVALID", str(exc)) from exc

    seen_ids: set[str] = set()
    seen_facts: set[tuple[str, str, str, str]] = set()
    checked: list[DeterministicFact] = []
    source_text_cache: dict[tuple[Path, int | None], str] = {}
    for fact in pack.facts:
        if fact.fact_id in seen_ids:
            raise FactPackLoadError("DUPLICATE_FACT", f"duplicate fact_id: {fact.fact_id}")
        seen_ids.add(fact.fact_id)

        canonical_key = (
            fact.subject,
            fact.source_relative_path.replace("\\", "/").casefold(),
            fact.fact_type,
            _normalise(fact.canonical_fact),
        )
        if canonical_key in seen_facts:
            raise FactPackLoadError(
                "DUPLICATE_FACT",
                f"duplicate canonical fact: {fact.fact_id}",
            )
        seen_facts.add(canonical_key)

        expected_id = compute_stable_fact_id(fact)
        if fact.fact_id != expected_id:
            raise FactPackLoadError(
                "UNSTABLE_FACT_ID",
                f"{fact.fact_id} does not match computed {expected_id}",
            )
        if _REVIEW_RANK[fact.review_status] < _REVIEW_RANK[minimum_review_status]:
            raise FactPackLoadError(
                "FACT_NOT_REVIEWED",
                f"{fact.fact_id} status {fact.review_status} below {minimum_review_status}",
            )

        try:
            source = validate_ncert_generation_source(fact.source_pdf, root=source_root)
        except (NcertSourceError, OSError, RuntimeError) as exc:
            raise FactPackLoadError(
                "NCERT_SOURCE_INVALID",
                f"{fact.fact_id}: {getattr(exc, 'code', type(exc).__name__)}",
            ) from exc
        if source.relative_posix != fact.source_relative_path.replace("\\", "/"):
            raise FactPackLoadError(
                "NCERT_SOURCE_IDENTITY_MISMATCH",
                f"{fact.fact_id}: declared relative path does not match canonical source",
            )

        syllabus = assert_blueprint_neet_syllabus_scope(
            _syllabus_constraints(fact),
            academic_subject_code=fact.subject,
        )
        if not syllabus.is_in_scope:
            raise FactPackLoadError(
                syllabus.status,
                f"{fact.fact_id}: {syllabus.detail or ','.join(syllabus.reasons)}",
            )

        page_number = fact.ncert_reference.page_number
        cache_key = (source.resolved_path, page_number)
        if cache_key not in source_text_cache:
            try:
                source_text_cache[cache_key] = extract_ncert_source_text(
                    source.resolved_path,
                    page_number,
                )
            except FactPackLoadError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise FactPackLoadError(
                    "NCERT_SOURCE_UNREADABLE",
                    f"{fact.fact_id}: {type(exc).__name__}",
                ) from exc
        source_text = source_text_cache[cache_key]
        if not _contains_text(source_text, fact.evidence_text):
            raise FactPackLoadError(
                "EVIDENCE_NOT_IN_NCERT_SOURCE",
                f"{fact.fact_id}: evidence_text not found in cited source scope",
            )
        if not _contains_text(fact.evidence_text, fact.canonical_fact):
            raise FactPackLoadError(
                "CANONICAL_FACT_NOT_IN_EVIDENCE",
                f"{fact.fact_id}: canonical_fact must be explicit in evidence_text",
            )
        for distractor in fact.allowed_distractors:
            if distractor.source == "SAME_EVIDENCE" and not _contains_text(
                source_text,
                distractor.evidence_text or "",
            ):
                raise FactPackLoadError(
                    "DISTRACTOR_EVIDENCE_NOT_IN_NCERT_SOURCE",
                    f"{fact.fact_id}: distractor evidence not found",
                )
        checked.append(fact)

    checked.sort(key=lambda fact: fact.fact_id)
    return LoadedFactPack(
        schema_version=pack.schema_version,
        pack_id=pack.pack_id,
        facts=tuple(checked),
        input_path=input_path.resolve(),
        input_sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )
