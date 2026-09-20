"""P2.2 source evidence package builder."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.modules.cms.pyq.p2_2.triage import question_id


def canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def load_ocr_words_for_record(
    words_path: Path,
    *,
    sha256: str,
    page: int,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    if not words_path.exists():
        return words
    with words_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            w = json.loads(line)
            if w.get("source_sha256") == sha256 and int(w.get("page") or 0) == page:
                words.append(
                    {
                        "text": w.get("text"),
                        "x": w.get("left"),
                        "y": w.get("top"),
                        "width": w.get("width"),
                        "height": w.get("height"),
                        "confidence": w.get("confidence"),
                        "line_num": w.get("line_num"),
                    }
                )
                if len(words) >= limit:
                    break
    return words


def neighbor_summaries(
    records_by_page: dict[int, list[dict[str, Any]]],
    *,
    page: int,
    qnum: int,
) -> list[dict[str, Any]]:
    neighbors: list[dict[str, Any]] = []
    for rec in records_by_page.get(page, []):
        n = rec.get("question_number")
        if n is None or abs(int(n) - qnum) > 2:
            continue
        if int(n) == qnum:
            continue
        neighbors.append(
            {
                "question_number": n,
                "stem_preview": (rec.get("stem") or "")[:120],
                "quality": rec.get("p2_1e_quality_status"),
            }
        )
    return sorted(neighbors, key=lambda x: x.get("question_number") or 0)


def build_evidence_package(
    record: dict[str, Any],
    *,
    words_path: Path,
    neighbors: list[dict[str, Any]],
    source_image_available: bool = False,
) -> dict[str, Any]:
    sha = record.get("source_sha256") or ""
    page = int(record.get("source_page") or 0)
    ocr_words = load_ocr_words_for_record(words_path, sha256=sha, page=page)
    ocr_text = record.get("raw_extracted_text") or ""
    if not ocr_text and ocr_words:
        ocr_text = " ".join(w["text"] for w in ocr_words if w.get("text"))

    pkg = {
        "question_id": question_id(record),
        "year": record.get("exam_year"),
        "paper_set": record.get("paper_code"),
        "page": page,
        "column": record.get("geometry_column"),
        "r3_extraction": {
            "stem": record.get("stem") or "",
            "option_1": record.get("option_a") or "",
            "option_2": record.get("option_b") or "",
            "option_3": record.get("option_c") or "",
            "option_4": record.get("option_d") or "",
            "quality": record.get("p2_1e_quality_status"),
        },
        "ocr_text": ocr_text[:4000],
        "ocr_words": ocr_words[:500],
        "neighboring_questions": neighbors[:4],
        "source_image": f"pdf:{sha}:page:{page}" if source_image_available else None,
        "known_defects": record.get("anomalies") or [],
    }
    pkg["source_evidence_hash"] = canonical_hash(
        {
            "question_id": pkg["question_id"],
            "ocr_text": pkg["ocr_text"],
            "ocr_words_count": len(ocr_words),
            "r3_extraction": pkg["r3_extraction"],
        }
    )
    return pkg


def check_source_availability(
    record: dict[str, Any],
    *,
    zip_path: Path | None,
    words_path: Path,
    paper_meta_path: Path | None = None,
) -> dict[str, bool]:
    sha = record.get("source_sha256") or ""
    page = int(record.get("source_page") or 0)
    has_pdf = False
    if zip_path and zip_path.exists() and record.get("source_file"):
        import zipfile

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                has_pdf = record["source_file"] in zf.namelist()
        except Exception:
            has_pdf = False
    has_words = False
    if words_path.exists():
        with words_path.open(encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i > 5000:
                    break
                if not line.strip():
                    continue
                w = json.loads(line)
                if w.get("source_sha256") == sha and int(w.get("page") or 0) == page:
                    has_words = True
                    break
    has_raw = bool((record.get("raw_extracted_text") or "").strip())
    return {"has_pdf": has_pdf, "has_ocr_words": has_words or has_raw, "has_paper_meta": paper_meta_path.exists() if paper_meta_path else False}
