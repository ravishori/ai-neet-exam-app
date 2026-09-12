"""Deterministic normalization + exact fingerprinting for MMF candidates."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from app.modules.cms.acquisition.mmf.schemas import CandidateRecord, CandidateStatus

_WS = re.compile(r"\s+", re.UNICODE)
_PUNCT_SAFE = re.compile(r"[\"'`]+")


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.strip()
    text = _PUNCT_SAFE.sub("", text)
    text = _WS.sub(" ", text)
    return text.casefold()


def normalize_options(options: dict[str, str]) -> dict[str, str]:
    return {lab: normalize_text(options[lab]) for lab in ("A", "B", "C", "D")}


def candidate_fingerprint(
    *,
    stem: str,
    options: dict[str, str],
    correct_answer: str,
) -> str:
    payload = {
        "stem": normalize_text(stem),
        "options": normalize_options(options),
        "correct_answer": str(correct_answer).strip().upper(),
    }
    blob = (
        payload["stem"]
        + "|"
        + "|".join(f"{k}:{payload['options'][k]}" for k in ("A", "B", "C", "D"))
        + "|"
        + payload["correct_answer"]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def normalize_candidate(record: CandidateRecord) -> CandidateRecord:
    data = record.model_dump(by_alias=True)
    data["stem"] = _WS.sub(" ", unicodedata.normalize("NFKC", record.stem).strip())
    opts = record.options.model_dump()
    data["options"] = {
        k: _WS.sub(" ", unicodedata.normalize("NFKC", opts[k]).strip()) for k in ("A", "B", "C", "D")
    }
    data["correct_answer"] = record.correct_answer.upper()
    data["explanation"] = _WS.sub(" ", unicodedata.normalize("NFKC", record.explanation).strip())
    data["source_evidence"] = _WS.sub(
        " ", unicodedata.normalize("NFKC", record.source_evidence).strip()
    )
    fp = candidate_fingerprint(
        stem=data["stem"],
        options=data["options"],
        correct_answer=data["correct_answer"],
    )
    data["fingerprint"] = fp
    if data.get("status") == CandidateStatus.GENERATED:
        data["status"] = CandidateStatus.NORMALIZED
    return CandidateRecord.model_validate(data)


def apply_exact_deduplication(candidates: list[CandidateRecord]) -> list[CandidateRecord]:
    """Mark exact duplicates; keep first as representative. Never delete."""
    seen: dict[str, str] = {}
    out: list[CandidateRecord] = []
    for cand in candidates:
        normalized = normalize_candidate(cand)
        fp = normalized.fingerprint or ""
        data = normalized.model_dump(by_alias=True)
        if fp in seen:
            data["status"] = CandidateStatus.EXACT_DUPLICATE
            data["duplicate_of"] = seen[fp]
            data["duplicate_reason"] = "exact_fingerprint_match"
        else:
            seen[fp] = normalized.candidate_id
            if data["status"] in (
                CandidateStatus.GENERATED,
                CandidateStatus.NORMALIZED,
            ):
                data["status"] = CandidateStatus.VALID
        out.append(CandidateRecord.model_validate(data))
    return out


def fingerprints_report(candidates: list[CandidateRecord]) -> dict[str, Any]:
    fps = [c.fingerprint for c in candidates if c.fingerprint]
    return {
        "count": len(candidates),
        "with_fingerprint": len(fps),
        "unique_fingerprints": len(set(fps)),
        "exact_duplicates": sum(1 for c in candidates if c.status == CandidateStatus.EXACT_DUPLICATE),
    }
