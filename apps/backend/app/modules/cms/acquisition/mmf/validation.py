"""Structural validation for MMF candidates (fail closed)."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.modules.cms.acquisition.mmf.schemas import CandidateRecord, CandidateStatus


def validate_candidate_dict(raw: dict[str, Any], *, expected_source_sha: str | None = None) -> tuple[CandidateRecord | None, list[str]]:
    errors: list[str] = []
    try:
        cand = CandidateRecord.model_validate(raw)
    except ValidationError as exc:
        return None, [e.get("msg", str(e)) for e in exc.errors()]

    opts = cand.options.model_dump()
    if set(opts.keys()) != {"A", "B", "C", "D"}:
        errors.append("options_must_be_exactly_A_B_C_D")
    if any(not str(opts[k]).strip() for k in ("A", "B", "C", "D")):
        errors.append("empty_option")
    if cand.correct_answer not in ("A", "B", "C", "D"):
        errors.append("invalid_correct_answer")
    # Exactly one correct answer is enforced by Literal single field — reject multi-key answers if present in raw
    if "correct_answers" in raw or "answers" in raw:
        errors.append("multiple_correct_answers_not_allowed")
    if expected_source_sha and cand.source_sha256 != expected_source_sha.lower():
        errors.append("source_sha_mismatch")
    if not cand.provider or not cand.model or not cand.prompt_version:
        errors.append("missing_provider_metadata")
    if not cand.provenance or cand.provenance.batch_id != cand.generation_batch_id:
        errors.append("fabricated_or_mismatched_provenance")
    if "page_number" in raw and raw["page_number"] is not None:
        # Contract: do not fabricate page numbers; reject claimed pages in this POC schema path
        errors.append("page_number_not_allowed_without_verification")

    if errors:
        return cand, errors
    return cand, []


def validate_candidate_list(
    rows: list[dict[str, Any]],
    *,
    expected_source_sha: str | None = None,
) -> dict[str, Any]:
    valid: list[CandidateRecord] = []
    invalid: list[dict[str, Any]] = []
    ids: set[str] = set()
    dup_ids: list[str] = []
    for i, raw in enumerate(rows):
        cand, errs = validate_candidate_dict(raw, expected_source_sha=expected_source_sha)
        cid = str((raw or {}).get("candidate_id") or f"row-{i}")
        if cid in ids:
            dup_ids.append(cid)
            errs = list(errs) + ["duplicate_candidate_id"]
        else:
            ids.add(cid)
        if errs or cand is None:
            invalid.append({"candidate_id": cid, "errors": errs or ["invalid"]})
            continue
        data = cand.model_dump(by_alias=True)
        data["status"] = CandidateStatus.VALID
        valid.append(CandidateRecord.model_validate(data))
    return {
        "valid": valid,
        "invalid": invalid,
        "duplicate_candidate_ids": dup_ids,
        "ok": len(invalid) == 0 and len(dup_ids) == 0,
    }
